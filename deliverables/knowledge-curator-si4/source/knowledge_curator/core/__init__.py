"""Core package: deterministic curation rules (03 §5) and document commit (§5.4)."""

from knowledge_curator.core.commit import DocumentCommitCoordinator, validate_commit_request
from knowledge_curator.core.curator import KnowledgeCurator
from knowledge_curator.core.version_view import ResolvedKnowledgeBundle, VersionedKnowledgeView

__all__ = [
    "DocumentCommitCoordinator",
    "KnowledgeCurator",
    "ResolvedKnowledgeBundle",
    "VersionedKnowledgeView",
    "validate_commit_request",
]
