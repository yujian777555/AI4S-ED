"""In-memory RevisionPublicationStore adapter (Phase 5.3)."""

from __future__ import annotations

import copy
from typing import Optional

from knowledge_curator.schemas.revision_publication import (
    PublicationPhase,
    RevisionPublicationRecord,
)

# Monotonic phase ordering
_PHASE_ORDER = {
    PublicationPhase.PREPARED: 0,
    PublicationPhase.TARGET_PUBLISHED: 1,
    PublicationPhase.LIFECYCLE_PUBLISHED: 2,
    PublicationPhase.FINALIZED: 3,
}


class InMemoryRevisionPublicationStore:
    """Copy-on-write in-memory publication journal."""

    def __init__(self) -> None:
        self._records: dict[str, RevisionPublicationRecord] = {}

    def get(self, publication_id: str) -> Optional[RevisionPublicationRecord]:
        rec = self._records.get(publication_id)
        return copy.deepcopy(rec) if rec else None

    def create(self, record: RevisionPublicationRecord) -> RevisionPublicationRecord:
        existing = self._records.get(record.publication_id)
        if existing is not None:
            if existing.request_material_hash == record.request_material_hash:
                return copy.deepcopy(existing)
            raise ValueError(
                f"conflicting publication material for {record.publication_id}"
            )
        stored = copy.deepcopy(record)
        self._records[stored.publication_id] = stored
        return copy.deepcopy(stored)

    def update(self, record: RevisionPublicationRecord) -> RevisionPublicationRecord:
        existing = self._records.get(record.publication_id)
        if existing is None:
            raise ValueError(f"unknown publication_id: {record.publication_id}")
        if existing.request_material_hash != record.request_material_hash:
            raise ValueError(
                f"conflicting publication material for {record.publication_id}"
            )
        # Phase must be monotonic (allow same phase for idempotent update).
        if _PHASE_ORDER[record.phase] < _PHASE_ORDER[existing.phase]:
            raise ValueError(
                f"publication phase cannot regress: {existing.phase.value} -> {record.phase.value}"
            )
        stored = copy.deepcopy(record)
        self._records[stored.publication_id] = stored
        return copy.deepcopy(stored)
