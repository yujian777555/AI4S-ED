"""SI-2A application composition: commit dependency wiring.

Composes production commit dependencies into the existing frozen
DocumentCommitCoordinator alongside the existing SI-1 curator runtime.

Does NOT reimplement commit logic. Does NOT modify frozen SI-1 files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from system.composition import (
    CuratorDependencies,
    _is_forbidden_adapter,
    compose_system_runtime,
)
from system.provider_loader import load_provider_bundle


class ApplicationCompositionError(ValueError):
    """Raised when SI-2A application dependencies are invalid."""


# Known checked-in in-memory commit adapters (forbidden as production).
_FORBIDDEN_COMMIT_ADAPTER_NAMES = frozenset(
    {
        "InMemoryDocumentCommitStore",
        "InMemoryStructuralKnowledgeStore",
        "InMemoryVectorIndex",
        "InMemoryUSDOStore",
        "InMemoryVersionStore",
    }
)

_FORBIDDEN_COMMIT_MODULE_FRAGMENTS = (
    "knowledge_curator.adapters.in_memory_commit",
)


def _is_forbidden_commit_adapter(obj: Any) -> bool:
    cls = obj if isinstance(obj, type) else type(obj)
    if cls.__name__ in _FORBIDDEN_COMMIT_ADAPTER_NAMES:
        return True
    module = getattr(cls, "__module__", "") or ""
    for frag in _FORBIDDEN_COMMIT_MODULE_FRAGMENTS:
        if frag in module:
            return True
    # Also use the shared SI-1 forbidden-adapter check.
    return _is_forbidden_adapter(obj)


def _validate_commit_port(obj: Any, port_cls: type, label: str) -> None:
    if obj is None:
        raise ApplicationCompositionError(f"{label} must not be None")
    if _is_forbidden_commit_adapter(obj):
        cls = obj if isinstance(obj, type) else type(obj)
        raise ApplicationCompositionError(
            f"{label} must not use test/integration adapter: {cls.__module__}.{cls.__name__}"
        )
    if not isinstance(obj, port_cls):
        raise ApplicationCompositionError(
            f"{label} does not satisfy required Port: {port_cls.__name__}"
        )


@dataclass
class CommitDependencies:
    commit_store: Any
    structural_store: Any
    vector_index: Any
    usdo_store: Any
    version_store: Any
    provider_identity: str = "external"


@dataclass
class CurationCommitApplicationRuntime:
    curator_runtime: Any
    commit_coordinator: Any
    provider_identity: str = "external"


def _validate_commit_deps(deps: CommitDependencies) -> None:
    from knowledge_curator.ports.document_commit_store import DocumentCommitStore
    from knowledge_curator.ports.structural_store import StructuralKnowledgeStore
    from knowledge_curator.ports.usdo_store import USDOStore
    from knowledge_curator.ports.vector_index import VectorIndex
    from knowledge_curator.ports.version_store import VersionStore

    _validate_commit_port(deps.commit_store, DocumentCommitStore, "commit_store")
    _validate_commit_port(
        deps.structural_store, StructuralKnowledgeStore, "structural_store"
    )
    _validate_commit_port(deps.vector_index, VectorIndex, "vector_index")
    _validate_commit_port(deps.usdo_store, USDOStore, "usdo_store")
    _validate_commit_port(deps.version_store, VersionStore, "version_store")


def _extract_commit_deps(bundle: Any) -> CommitDependencies:
    if isinstance(bundle, dict):
        commit_raw = bundle.get("commit")
    else:
        commit_raw = getattr(bundle, "commit", None)

    if commit_raw is None:
        raise ApplicationCompositionError(
            "provider bundle missing 'commit' group for SI-2A"
        )

    if isinstance(commit_raw, dict):
        return CommitDependencies(
            commit_store=commit_raw.get("commit_store"),
            structural_store=commit_raw.get("structural_store"),
            vector_index=commit_raw.get("vector_index"),
            usdo_store=commit_raw.get("usdo_store"),
            version_store=commit_raw.get("version_store"),
            provider_identity=str(commit_raw.get("provider_identity", "external")),
        )
    return CommitDependencies(
        commit_store=getattr(commit_raw, "commit_store", None),
        structural_store=getattr(commit_raw, "structural_store", None),
        vector_index=getattr(commit_raw, "vector_index", None),
        usdo_store=getattr(commit_raw, "usdo_store", None),
        version_store=getattr(commit_raw, "version_store", None),
        provider_identity=str(getattr(commit_raw, "provider_identity", "external")),
    )


def compose_curation_commit_application(
    spec: Optional[str] = None,
    *,
    environ: Optional[dict[str, str]] = None,
) -> CurationCommitApplicationRuntime:
    """Compose SI-2A application runtime from the provider bundle.

    1. Load the same provider bundle via load_provider_bundle().
    2. Compose curator through existing compose_system_runtime().
    3. Extract and validate the commit dependency group.
    4. Construct DocumentCommitCoordinator.
    """
    bundle = load_provider_bundle(spec, environ=environ)

    # Curator dependencies (existing SI-1 shape).
    if isinstance(bundle, dict):
        curator_raw = bundle.get("curator")
    else:
        curator_raw = getattr(bundle, "curator", None)
    if curator_raw is None:
        raise ApplicationCompositionError("bundle.curator is required")

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

    commit_deps = _extract_commit_deps(bundle)
    _validate_commit_deps(commit_deps)

    from knowledge_curator.core.commit import DocumentCommitCoordinator

    coordinator = DocumentCommitCoordinator(
        commit_store=commit_deps.commit_store,
        structural_store=commit_deps.structural_store,
        vector_index=commit_deps.vector_index,
        usdo_store=commit_deps.usdo_store,
        version_store=commit_deps.version_store,
    )

    return CurationCommitApplicationRuntime(
        curator_runtime=system_rt.curator_runtime,
        commit_coordinator=coordinator,
        provider_identity=commit_deps.provider_identity,
    )
