"""Ports package: Protocol boundaries for external modules."""

from knowledge_curator.ports.document_commit_store import (
    DocumentCommitRecord,
    DocumentCommitStore,
)
from knowledge_curator.ports.knowledge_repository import KnowledgeRepository
from knowledge_curator.ports.mechanism_validator import (
    MechanismCheckResult,
    MechanismValidator,
)
from knowledge_curator.ports.ontology_service import OntologyService
from knowledge_curator.ports.structural_store import (
    StructuralDocumentRecord,
    StructuralKnowledgeStore,
)
from knowledge_curator.ports.usdo_store import USDOStore
from knowledge_curator.ports.vector_index import VectorIndex
from knowledge_curator.ports.version_store import SnapshotRecord, VersionRecord, VersionStore

__all__ = [
    "DocumentCommitRecord",
    "DocumentCommitStore",
    "KnowledgeRepository",
    "MechanismCheckResult",
    "MechanismValidator",
    "OntologyService",
    "SnapshotRecord",
    "StructuralDocumentRecord",
    "StructuralKnowledgeStore",
    "USDOStore",
    "VectorIndex",
    "VersionRecord",
    "VersionStore",
]
