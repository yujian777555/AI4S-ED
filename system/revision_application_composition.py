"""SI-2B revision publication application composition.

Composes frozen RevisionPublicationCoordinator + LifecycleRevisionCoordinator
alongside the existing SI-2A DocumentCommitCoordinator over shared stores.

Does NOT reimplement revision/lifecycle logic. Does NOT modify frozen files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from system.composition import _is_forbidden_adapter
from system.provider_loader import load_provider_bundle


class RevisionCompositionError(ValueError):
    """Raised when SI-2B revision dependencies are invalid."""


_FORBIDDEN_REVISION_ADAPTER_NAMES = frozenset(
    {
        "InMemoryLifecycleStore",
        "InMemoryEventOutbox",
        "InMemoryRevisionPublicationStore",
        "InMemorySourceVersionRegistry",
    }
)

_FORBIDDEN_REVISION_MODULE_FRAGMENTS = (
    "knowledge_curator.adapters.in_memory_lifecycle",
    "knowledge_curator.adapters.in_memory_revision_publication",
    "knowledge_curator.adapters.in_memory_source_versions",
)


def _is_forbidden_revision_adapter(obj: Any) -> bool:
    cls = obj if isinstance(obj, type) else type(obj)
    if cls.__name__ in _FORBIDDEN_REVISION_ADAPTER_NAMES:
        return True
    module = getattr(cls, "__module__", "") or ""
    for frag in _FORBIDDEN_REVISION_MODULE_FRAGMENTS:
        if frag in module:
            return True
    return _is_forbidden_adapter(obj)


def _validate_revision_port(obj: Any, port_cls: type, label: str) -> None:
    if obj is None:
        raise RevisionCompositionError(f"{label} must not be None")
    if _is_forbidden_revision_adapter(obj):
        cls = obj if isinstance(obj, type) else type(obj)
        raise RevisionCompositionError(
            f"{label} must not use test/integration adapter: {cls.__module__}.{cls.__name__}"
        )
    if not isinstance(obj, port_cls):
        raise RevisionCompositionError(
            f"{label} does not satisfy required Port: {port_cls.__name__}"
        )


@dataclass
class RevisionDependencies:
    source_registry: Any
    lifecycle_store: Any
    event_outbox: Any
    publication_store: Any
    provider_identity: str = "external"


@dataclass
class RevisionPublicationApplicationRuntime:
    document_commit_coordinator: Any
    lifecycle_coordinator: Any
    revision_publication_coordinator: Any
    source_registry: Any
    provider_identity: str = "external"


def _extract_revision_deps(bundle: Any) -> RevisionDependencies:
    if isinstance(bundle, dict):
        rev_raw = bundle.get("revision")
    else:
        rev_raw = getattr(bundle, "revision", None)

    if rev_raw is None:
        raise RevisionCompositionError(
            "provider bundle missing 'revision' group for SI-2B"
        )

    if isinstance(rev_raw, dict):
        return RevisionDependencies(
            source_registry=rev_raw.get("source_registry"),
            lifecycle_store=rev_raw.get("lifecycle_store"),
            event_outbox=rev_raw.get("event_outbox"),
            publication_store=rev_raw.get("publication_store"),
            provider_identity=str(rev_raw.get("provider_identity", "external")),
        )
    return RevisionDependencies(
        source_registry=getattr(rev_raw, "source_registry", None),
        lifecycle_store=getattr(rev_raw, "lifecycle_store", None),
        event_outbox=getattr(rev_raw, "event_outbox", None),
        publication_store=getattr(rev_raw, "publication_store", None),
        provider_identity=str(getattr(rev_raw, "provider_identity", "external")),
    )


def _validate_revision_deps(deps: RevisionDependencies) -> None:
    from knowledge_curator.ports.lifecycle_store import EventOutbox, LifecycleStore
    from knowledge_curator.ports.revision_publication_store import RevisionPublicationStore
    from knowledge_curator.ports.source_version_registry import SourceVersionRegistry

    _validate_revision_port(deps.source_registry, SourceVersionRegistry, "source_registry")
    _validate_revision_port(deps.lifecycle_store, LifecycleStore, "lifecycle_store")
    _validate_revision_port(deps.event_outbox, EventOutbox, "event_outbox")
    _validate_revision_port(deps.publication_store, RevisionPublicationStore, "publication_store")


def _reject_split_brain(bundle: Any) -> None:
    """Fail closed if revision group tries to own version_store or commit_store."""
    if isinstance(bundle, dict):
        rev_raw = bundle.get("revision") or {}
    else:
        rev_raw = getattr(bundle, "revision", None) or {}

    forbidden_keys = ("version_store", "commit_store", "document_commit_store")
    if isinstance(rev_raw, dict):
        for key in forbidden_keys:
            if key in rev_raw and rev_raw[key] is not None:
                raise RevisionCompositionError(
                    f"revision group must not provide '{key}' (split-brain risk); "
                    f"reuse the commit group's instance"
                )


def compose_revision_publication_application(
    spec: Optional[str] = None,
    *,
    environ: Optional[dict[str, str]] = None,
) -> RevisionPublicationApplicationRuntime:
    """Compose SI-2B application runtime from a single provider bundle load.

    1. Load provider bundle ONCE.
    2. Extract + validate SI-2A commit dependencies (reuse internal helpers).
    3. Construct DocumentCommitCoordinator over those exact deps.
    4. Extract + validate revision dependencies.
    5. Reject split-brain (revision group providing own version_store/commit_store).
    6. Construct LifecycleRevisionCoordinator with the EXACT commit.version_store.
    7. Construct RevisionPublicationCoordinator with EXACT shared stores.
    """
    # Single load — do not call load_provider_bundle twice.
    bundle = load_provider_bundle(spec, environ=environ)

    # --- SI-2A commit deps (reuse extraction, do not modify SI-2A files) ---
    from system.application_composition import (
        CommitDependencies,
        _extract_commit_deps,
        _validate_commit_deps,
    )

    commit_deps = _extract_commit_deps(bundle)
    _validate_commit_deps(commit_deps)

    from knowledge_curator.core.commit import DocumentCommitCoordinator

    doc_commit = DocumentCommitCoordinator(
        commit_store=commit_deps.commit_store,
        structural_store=commit_deps.structural_store,
        vector_index=commit_deps.vector_index,
        usdo_store=commit_deps.usdo_store,
        version_store=commit_deps.version_store,
    )

    # --- revision deps ---
    _reject_split_brain(bundle)
    rev_deps = _extract_revision_deps(bundle)
    _validate_revision_deps(rev_deps)

    from knowledge_curator.core.lifecycle import LifecycleRevisionCoordinator
    from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator

    lifecycle = LifecycleRevisionCoordinator(
        lifecycle_store=rev_deps.lifecycle_store,
        outbox=rev_deps.event_outbox,
        version_store=commit_deps.version_store,  # EXACT shared instance
    )

    publication = RevisionPublicationCoordinator(
        publication_store=rev_deps.publication_store,
        source_registry=rev_deps.source_registry,
        version_store=commit_deps.version_store,  # EXACT shared instance
        lifecycle_coordinator=lifecycle,
        document_commit_coordinator=doc_commit,
        document_commit_store=commit_deps.commit_store,  # EXACT shared instance
    )

    return RevisionPublicationApplicationRuntime(
        document_commit_coordinator=doc_commit,
        lifecycle_coordinator=lifecycle,
        revision_publication_coordinator=publication,
        source_registry=rev_deps.source_registry,
        provider_identity=rev_deps.provider_identity,
    )
