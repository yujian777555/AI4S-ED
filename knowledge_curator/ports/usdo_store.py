"""USDO store port — staged/committed payload registration boundary.

Supports compensation of committed-but-unpublished documents (P2.2-01).
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.commit import USDORecord


@runtime_checkable
class USDOStore(Protocol):
    """Registration boundary for USDO / source payload records."""

    def stage(self, stage_id: str, records: list[USDORecord]) -> None:
        """Stage USDO records for a document commit. Not downstream-visible."""
        ...

    def commit_stage(self, stage_id: str) -> None:
        """Make staged USDO records committed/visible."""
        ...

    def abort_stage(self, stage_id: str) -> None:
        """Discard staged (uncommitted) USDO records."""
        ...

    def compensate_committed(self, stage_id: str) -> None:
        """Undo committed visibility for an unpublished failed document."""
        ...

    def list_for_ref(self, ref_id: str) -> list[USDORecord]:
        """Return only committed USDO records for a source document."""
        ...

    def get_by_id(self, record_id: str) -> Optional[USDORecord]:
        """Lookup one USDO record by id (staged or committed)."""
        ...

    def has_records(self, record_ids: list[str]) -> bool:
        """True when all record ids are present (staged or committed)."""
        ...

    def count_staged(self) -> int:
        """Diagnostic: number of staged-but-uncommitted record buckets."""
        ...
