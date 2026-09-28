"""VectorIndex port — staged vector write boundary.

Do not hard-code FAISS/Qdrant/HTTP. Formal L2 API is not frozen (CG-004).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from knowledge_curator.schemas.commit import VectorPayload


@runtime_checkable
class VectorIndex(Protocol):
    """Upsert/query boundary for evidence/chunk vectors."""

    def upsert(self, payloads: list[VectorPayload]) -> None:
        """Upsert vector payloads for one document commit.

        Must be idempotent for the same vector_id.
        """
        ...

    def has_ids(self, vector_ids: list[str]) -> bool:
        """True when all vector ids are present."""
        ...

    def count_for_ref(self, ref_id: str) -> int:
        """Number of vector payloads stored for a source document."""
        ...
