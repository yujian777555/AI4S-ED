"""USDO store port — content-addressed payload registration boundary.

Do not hard-code filesystem/HTTP. Formal L2 API is not frozen (CG-004).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from knowledge_curator.schemas.commit import USDORecord


@runtime_checkable
class USDOStore(Protocol):
    """Registration boundary for USDO / source payload records."""

    def register(self, records: list[USDORecord]) -> None:
        """Register USDO records. Must be idempotent on record_id."""
        ...

    def has_records(self, record_ids: list[str]) -> bool:
        """True when all record ids are registered."""
        ...

    def list_for_ref(self, ref_id: str) -> list[USDORecord]:
        """Return registered USDO records for a source document."""
        ...
