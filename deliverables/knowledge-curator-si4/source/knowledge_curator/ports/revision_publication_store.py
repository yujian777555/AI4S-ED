"""RevisionPublicationStore port (Phase 5.3, internal)."""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.revision_publication import RevisionPublicationRecord


@runtime_checkable
class RevisionPublicationStore(Protocol):
    """Append-only publication journal."""

    def get(self, publication_id: str) -> Optional[RevisionPublicationRecord]:
        ...

    def create(self, record: RevisionPublicationRecord) -> RevisionPublicationRecord:
        ...

    def update(self, record: RevisionPublicationRecord) -> RevisionPublicationRecord:
        ...
