"""Structural knowledge store port — staged/committed assertion persistence.

Internal temporary L2 boundary (not the frozen cross-team contract).
Supports compensation of committed-but-unpublished documents (P2.2-01).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.commit import AdmittedAssertion


@dataclass
class StructuralDocumentRecord:
    """Committed structural knowledge payload for one document version."""

    ref_id: str
    source_fingerprint: str
    stage_id: str
    assertions: list[AdmittedAssertion] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    metadata_hash: str = ""


@runtime_checkable
class StructuralKnowledgeStore(Protocol):
    """Stage/commit/compensate/abort boundary for structural writes."""

    def stage_document(self, record: StructuralDocumentRecord) -> None:
        """Stage one document's structural payload. Not downstream-visible."""
        ...

    def commit_stage(self, stage_id: str) -> None:
        """Make a staged document's structural payload committed/visible."""
        ...

    def abort_stage(self, stage_id: str) -> None:
        """Discard an uncommitted stage. Committed data is never removed here."""
        ...

    def compensate_committed(self, stage_id: str) -> None:
        """Undo committed visibility for an unpublished failed document.

        Only valid before any KB version publish. Used for pre-publish
        atomic-visibility compensation (not history rewrite of published data).
        """
        ...

    def list_committed_for_ref(self, ref_id: str) -> list[StructuralDocumentRecord]:
        """Downstream-visible committed structural records for a source ref."""
        ...

    def get_committed(self, stage_id: str) -> Optional[StructuralDocumentRecord]:
        """Lookup a committed structural record by stage/commit id."""
        ...

    def is_committed(self, stage_id: str) -> bool:
        """True when the stage has been finalized as committed."""
        ...

    def count_staged(self) -> int:
        """Diagnostic: number of staged-but-uncommitted documents."""
        ...
