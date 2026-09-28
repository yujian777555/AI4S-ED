"""VectorIndex port — staged vector write boundary.

Vector identities must be version-safe/immutable so older snapshots
remain reproducible after newer document versions publish.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.commit import VectorPayload


@runtime_checkable
class VectorIndex(Protocol):
    """Upsert/query boundary for evidence/chunk vectors."""

    def upsert(self, payloads: list[VectorPayload]) -> None:
        """Upsert vector payloads. Must be idempotent and never mutate other ids."""
        ...

    def has_ids(self, vector_ids: list[str]) -> bool:
        """True when all vector ids are present."""
        ...

    def get_by_id(self, vector_id: str) -> Optional[VectorPayload]:
        """Return the stored payload for a vector id (for audit/rollback tests)."""
        ...

    def count_for_ref(self, ref_id: str) -> int:
        """Number of vector payloads stored for a source document."""
        ...
