"""Ports package: Protocol boundaries for external modules."""

from knowledge_curator.ports.knowledge_repository import KnowledgeRepository
from knowledge_curator.ports.mechanism_validator import (
    MechanismCheckResult,
    MechanismValidator,
)
from knowledge_curator.ports.ontology_service import OntologyService

__all__ = [
    "KnowledgeRepository",
    "MechanismCheckResult",
    "MechanismValidator",
    "OntologyService",
]
