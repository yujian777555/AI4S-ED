"""System-level production dependency composition (Phase SI-1).

Composes external production adapters into the existing
CuratorRuntime / EvidenceRuntime injection points.

Does NOT duplicate curation or retrieval algorithms.
Does NOT call DocumentCommitCoordinator / RevisionPublicationCoordinator /
LifecycleRevisionCoordinator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Known test/integration adapter class names and module fragments that must
# never appear as production dependencies.
_FORBIDDEN_ADAPTER_NAMES = frozenset(
    {
        "InMemoryKnowledgeRepository",
        "SimpleOntologyService",
        "FakeMechanismValidator",
        "InMemoryDocumentCommitStore",
        "InMemoryStructuralKnowledgeStore",
        "InMemoryUSDOStore",
        "InMemoryVectorIndex",
        "InMemoryVersionStore",
        "InMemoryLifecycleStore",
        "InMemoryEventOutbox",
        "InMemorySourceVersionRegistry",
        "InMemoryRevisionPublicationStore",
        "InMemoryVectorSearch",
        "InMemoryKeywordSearch",
        "FakeReranker",
        "InMemoryEvidenceStore",
    }
)

_FORBIDDEN_MODULE_FRAGMENTS = (
    "knowledge_curator.adapters.in_memory_repository",
    "knowledge_curator.adapters.in_memory_commit",
    "knowledge_curator.adapters.in_memory_lifecycle",
    "knowledge_curator.adapters.in_memory_source_versions",
    "knowledge_curator.adapters.in_memory_revision_publication",
    "knowledge_curator.adapters.in_memory_retrieval",
    "knowledge_curator.adapters.in_memory_evidence",
)


class ProductionAdapterError(ValueError):
    """Raised when a production dependency is invalid or a test adapter is used."""


def _is_forbidden_adapter(obj: Any) -> bool:
    """Return True if obj is a known test/integration adapter instance or class."""
    cls = obj if isinstance(obj, type) else type(obj)
    if cls.__name__ in _FORBIDDEN_ADAPTER_NAMES:
        return True
    module = getattr(cls, "__module__", "") or ""
    for frag in _FORBIDDEN_MODULE_FRAGMENTS:
        if frag in module:
            return True
    return False


def _validate_production_adapter(obj: Any, label: str) -> None:
    if obj is None:
        raise ProductionAdapterError(f"{label} must not be None")
    if _is_forbidden_adapter(obj):
        cls = obj if isinstance(obj, type) else type(obj)
        raise ProductionAdapterError(
            f"{label} must not use test/integration adapter: {cls.__module__}.{cls.__name__}"
        )


@dataclass
class CuratorDependencies:
    """External production dependencies for KnowledgeCurator construction."""

    repository: Any
    ontology: Any
    mechanism_validator: Any
    provider_identity: str = "external"


@dataclass
class EvidenceDependencies:
    """External production dependencies for evidence retrieval/guard."""

    retrieval: Optional[Any] = None
    mechanism_validator: Optional[Any] = None
    provider_identity: str = "external"


@dataclass
class SystemRuntime:
    """Composed system runtime yielding existing injection-point objects."""

    curator_runtime: Any  # CuratorRuntime from knowledge_curator.mcp_server.runtime
    evidence_runtime: Any  # EvidenceRuntime from knowledge_curator.mcp_server.evidence_runtime
    provider_identity: str = "external"


def _validate_curator_deps(deps: CuratorDependencies) -> None:
    _validate_production_adapter(deps.repository, "repository")
    _validate_production_adapter(deps.ontology, "ontology")
    _validate_production_adapter(deps.mechanism_validator, "mechanism_validator")


def _validate_evidence_deps(deps: EvidenceDependencies) -> None:
    if deps.retrieval is not None:
        _validate_production_adapter(deps.retrieval, "evidence retrieval")
    if deps.mechanism_validator is not None:
        _validate_production_adapter(deps.mechanism_validator, "evidence mechanism_validator")


def compose_system_runtime(
    *,
    curator_deps: CuratorDependencies,
    evidence_deps: Optional[EvidenceDependencies] = None,
) -> SystemRuntime:
    """Compose production dependencies into existing runtime injection points."""
    _validate_curator_deps(curator_deps)
    if evidence_deps is not None:
        _validate_evidence_deps(evidence_deps)

    from knowledge_curator.mcp_server.runtime import create_curator_runtime
    from knowledge_curator.mcp_server.evidence_runtime import (
        create_production_evidence_runtime,
        create_unavailable_evidence_runtime,
    )

    curator_runtime = create_curator_runtime(
        repository=curator_deps.repository,
        ontology=curator_deps.ontology,
        mechanism_validator=curator_deps.mechanism_validator,
        adapter_note=f"production:{curator_deps.provider_identity}",
    )

    if evidence_deps is not None and evidence_deps.retrieval is not None:
        evidence_runtime = create_production_evidence_runtime(
            retrieval=evidence_deps.retrieval,
            mechanism_validator=evidence_deps.mechanism_validator,
            adapter_note=f"production:{evidence_deps.provider_identity}",
        )
    else:
        # Intentional absence: fail-closed unavailable evidence is correct.
        evidence_runtime = create_unavailable_evidence_runtime(
            mechanism_validator=evidence_deps.mechanism_validator if evidence_deps else None
        )

    return SystemRuntime(
        curator_runtime=curator_runtime,
        evidence_runtime=evidence_runtime,
        provider_identity=curator_deps.provider_identity,
    )
