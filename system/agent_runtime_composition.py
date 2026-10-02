"""SI-3A Agent Runtime composition.

Composes AI4SAgent from the existing provider bundle via
AI4S_SYSTEM_ADAPTER_FACTORY. Reuses existing composition boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from system.agent_runtime.agent import AI4SAgent
from system.agent_runtime.errors import ProviderNotConfiguredError
from system.agent_runtime.task_router import TaskRouter
from system.agent_runtime.workflow_registry import WorkflowRegistry


@dataclass
class AgentRuntimeConfig:
    """Configuration for agent runtime composition."""

    provider_identity: str = "external"


def compose_agent_runtime(
    spec: Optional[str] = None,
    *,
    environ: Optional[dict[str, str]] = None,
) -> AI4SAgent:
    """Compose AI4SAgent from the provider bundle.

    1. Load provider bundle via the existing loader.
    2. Compose curation commit workflow (SI-2A).
    3. Compose revision publication workflow (SI-2B).
    4. Register both in the WorkflowRegistry.
    5. Return AI4SAgent with TaskRouter + WorkflowRegistry.

    Missing provider => ProviderNotConfiguredError (fail closed).
    """
    from system.provider_loader import ProviderLoadError, load_provider_bundle

    try:
        bundle = load_provider_bundle(spec, environ=environ)
    except ProviderLoadError as exc:
        raise ProviderNotConfiguredError(str(exc)) from exc

    # --- Compose curation commit workflow (reuse SI-2A composition) ---
    from system.application_composition import (
        _extract_commit_deps,
        _validate_commit_deps,
    )
    from system.composition import CuratorDependencies, compose_system_runtime
    from system.workflows.curation_commit import CurationCommitWorkflow
    from knowledge_curator.core.commit import DocumentCommitCoordinator

    if isinstance(bundle, dict):
        curator_raw = bundle.get("curator")
        commit_raw = bundle.get("commit")
    else:
        curator_raw = getattr(bundle, "curator", None)
        commit_raw = getattr(bundle, "commit", None)

    if curator_raw is None:
        raise ProviderNotConfiguredError("bundle.curator is required")

    # Curator
    if isinstance(curator_raw, dict):
        curator_deps = CuratorDependencies(
            repository=curator_raw.get("repository"),
            ontology=curator_raw.get("ontology"),
            mechanism_validator=curator_raw.get("mechanism_validator"),
            provider_identity=str(curator_raw.get("provider_identity", "external")),
        )
    else:
        curator_deps = CuratorDependencies(
            repository=getattr(curator_raw, "repository", None),
            ontology=getattr(curator_raw, "ontology", None),
            mechanism_validator=getattr(curator_raw, "mechanism_validator", None),
            provider_identity=str(getattr(curator_raw, "provider_identity", "external")),
        )
    system_rt = compose_system_runtime(curator_deps=curator_deps, evidence_deps=None)

    # Commit workflow
    curation_workflow = None
    if commit_raw is not None:
        commit_deps = _extract_commit_deps(bundle)
        _validate_commit_deps(commit_deps)
        doc_commit = DocumentCommitCoordinator(
            commit_store=commit_deps.commit_store,
            structural_store=commit_deps.structural_store,
            vector_index=commit_deps.vector_index,
            usdo_store=commit_deps.usdo_store,
            version_store=commit_deps.version_store,
        )
        curation_workflow = CurationCommitWorkflow(
            curator_runtime=system_rt.curator_runtime,
            commit_coordinator=doc_commit,
            provider_identity=commit_deps.provider_identity,
        )

    # --- Compose revision publication workflow (reuse SI-2B composition) ---
    revision_workflow = None
    revision_raw = bundle.get("revision") if isinstance(bundle, dict) else getattr(bundle, "revision", None)
    if revision_raw is not None and curation_workflow is not None:
        from system.revision_application_composition import (
            _extract_revision_deps,
            _reject_split_brain,
            _validate_revision_deps,
        )
        from system.workflows.revision_publication import RevisionPublicationWorkflow
        from knowledge_curator.core.lifecycle import LifecycleRevisionCoordinator
        from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator

        _reject_split_brain(bundle)
        rev_deps = _extract_revision_deps(bundle)
        _validate_revision_deps(rev_deps)

        # Reuse the same commit deps stores
        lifecycle = LifecycleRevisionCoordinator(
            lifecycle_store=rev_deps.lifecycle_store,
            outbox=rev_deps.event_outbox,
            version_store=commit_deps.version_store,
        )
        publication = RevisionPublicationCoordinator(
            publication_store=rev_deps.publication_store,
            source_registry=rev_deps.source_registry,
            version_store=commit_deps.version_store,
            lifecycle_coordinator=lifecycle,
            document_commit_coordinator=doc_commit,
            document_commit_store=commit_deps.commit_store,
        )
        revision_workflow = RevisionPublicationWorkflow(
            revision_publication_coordinator=publication,
            provider_identity=rev_deps.provider_identity,
        )

    # --- Build registry ---
    registry = WorkflowRegistry()
    if curation_workflow is not None:
        registry.register("curation_commit", curation_workflow)
    if revision_workflow is not None:
        registry.register("revision_publication", revision_workflow)

    router = TaskRouter()

    provider_identity = (
        (commit_raw or {}).get("provider_identity", "external")
        if isinstance(commit_raw, dict)
        else getattr(commit_raw, "provider_identity", "external")
        if commit_raw
        else "external"
    )

    return AI4SAgent(
        router=router,
        registry=registry,
        provider_identity=str(provider_identity),
    )
