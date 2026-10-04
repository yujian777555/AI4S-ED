"""KnowledgeRepository port — L2 knowledge store boundary.

Do not hard-code SQLite / FAISS / HTTP here. Concrete adapters live in
knowledge_curator.adapters. Formal L2 API is not frozen (CG-004).
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.assertions import Assertion


@runtime_checkable
class KnowledgeRepository(Protocol):
    """Minimal knowledge-graph query/commit boundary for Phase 1 curation."""

    def find_assertions(
        self,
        subject: str,
        property_name: str,
        ref_id_exclude: Optional[str] = None,
    ) -> list[Assertion]:
        """Return existing assertions with the same subject+property.

        Args:
            subject: Resolved subject entity id.
            property_name: EDDO property name.
            ref_id_exclude: Optional source ref_id to exclude (self-comparison).

        Returns:
            Existing assertions stored in the knowledge repository.
        """
        ...

    def commit_assertions(self, assertions: list[Assertion]) -> str:
        """Commit accepted assertions and return a placeholder snapshot id.

        Phase 1 does not require real atomic multi-store commit. Implementations
        must not fabricate production KB versions.
        """
        ...
