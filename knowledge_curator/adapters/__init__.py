"""Adapters package: in-memory / fake implementations for tests and Phase 1–2."""

from knowledge_curator.adapters.in_memory_commit import (
    FailureInjection,
    InMemoryDocumentCommitStore,
    InMemoryUSDOStore,
    InMemoryVectorIndex,
    InMemoryVersionStore,
)
from knowledge_curator.adapters.in_memory_repository import (
    FakeMechanismValidator,
    InMemoryKnowledgeRepository,
    SimpleOntologyService,
)

__all__ = [
    "FailureInjection",
    "FakeMechanismValidator",
    "InMemoryDocumentCommitStore",
    "InMemoryKnowledgeRepository",
    "InMemoryUSDOStore",
    "InMemoryVectorIndex",
    "InMemoryVersionStore",
    "SimpleOntologyService",
]
