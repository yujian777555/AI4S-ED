"""System-level production dependency composition (Phase SI-1 / R1).

Composes external production adapters into the existing
CuratorRuntime / EvidenceRuntime injection points.

Does NOT duplicate curation or retrieval algorithms.
Does NOT call DocumentCommitCoordinator / RevisionPublicationCoordinator /
LifecycleRevisionCoordinator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Known test/integration adapter class names that must never appear as production.
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


def _validate_port(obj: Any, port_cls: type, label: str) -> None:
    """Validate obj satisfies a frozen runtime-checkable Port."""
    _validate_production_adapter(obj, label)
    if not isinstance(obj, port_cls):
        raise ProductionAdapterError(
            f"{label} does not satisfy required Port: {port_cls.__name__}"
        )


def _validate_evidence_service(service: Any, label: str) -> None:
    """Validate EvidenceRetrievalService and inspect nested backends (R1-01)."""
    _validate_production_adapter(service, label)
    from knowledge_curator.retrieval.evidence_service import EvidenceRetrievalService

    if not isinstance(service, EvidenceRetrievalService):
        raise ProductionAdapterError(
            f"{label} must be EvidenceRetrievalService, got {type(service).__name__}"
        )
    # Inspect nested backends for known test adapters
    for attr, backend_label in (
        ("_vector_port", "evidence vector backend"),
        ("_keyword_port", "evidence keyword backend"),
        ("_reranker", "evidence reranker"),
    ):
        backend = getattr(service, attr, None)
        if backend is not None:
            _validate_production_adapter(backend, backend_label)


@dataclass
class CuratorDependencies:
    repository: Any
    ontology: Any
    mechanism_validator: Any
    provider_identity: str = "external"


@dataclass
class EvidenceDependencies:
    retrieval: Optional[Any] = None
    mechanism_validator: Optional[Any] = None
    provider_identity: str = "external"


@dataclass
class SystemRuntime:
    curator_runtime: Any
    evidence_runtime: Any
    provider_identity: str = "external"


def _validate_curator_deps(deps: CuratorDependencies) -> None:
    from knowledge_curator.ports.knowledge_repository import KnowledgeRepository
    from knowledge_curator.ports.ontology_service import OntologyService
    from knowledge_curator.ports.mechanism_validator import MechanismValidator

    _validate_port(deps.repository, KnowledgeRepository, "repository")
    _validate_port(deps.ontology, OntologyService, "ontology")
    _validate_port(deps.mechanism_validator, MechanismValidator, "mechanism_validator")


def _validate_evidence_deps(deps: EvidenceDependencies) -> None:
    if deps.retrieval is not None:
        _validate_evidence_service(deps.retrieval, "evidence retrieval")
    if deps.mechanism_validator is not None:
        from knowledge_curator.ports.mechanism_validator import MechanismValidator

        _validate_port(deps.mechanism_validator, MechanismValidator, "evidence mechanism_validator")


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
        evidence_runtime = create_unavailable_evidence_runtime(
            mechanism_validator=evidence_deps.mechanism_validator if evidence_deps else None
        )

    return SystemRuntime(
        curator_runtime=curator_runtime,
        evidence_runtime=evidence_runtime,
        provider_identity=curator_deps.provider_identity,
    )
