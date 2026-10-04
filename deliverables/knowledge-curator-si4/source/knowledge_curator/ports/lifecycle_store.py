"""LifecycleStore / EventOutbox ports (Phase 5.0, CG-018 internal only).

Append-only lifecycle history + version-scoped visibility lookup.
No external event transport.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.lifecycle import (
    AssertionLifecycleRecord,
    DocumentLifecycleRecord,
    LifecycleEligibility,
    LifecycleEvent,
)


@runtime_checkable
class LifecycleStore(Protocol):
    """Append-only document/assertion lifecycle records."""

    def append_document_record(self, record: DocumentLifecycleRecord) -> DocumentLifecycleRecord:
        """Append one document lifecycle record. Idempotent by lifecycle_id."""
        ...

    def append_assertion_records(
        self, records: list[AssertionLifecycleRecord]
    ) -> list[AssertionLifecycleRecord]:
        """Append assertion lifecycle records. Idempotent by (lifecycle_id, assertion_id)."""
        ...

    def bind_effective_version(self, lifecycle_id: str, version_id: str) -> None:
        """Bind a staged lifecycle record to a published version id.

        Only allowed while the record has no effective_version_id (staging).
        Does not rewrite historical assertion payloads.
        """
        ...

    def get_document_record(self, lifecycle_id: str) -> Optional[DocumentLifecycleRecord]:
        ...

    def latest_document_state(
        self, ref_id: str, at_version_id: Optional[str] = None
    ) -> Optional[DocumentLifecycleRecord]:
        """Latest document lifecycle record visible at the given version (or current)."""
        ...

    def latest_assertion_state(
        self, assertion_id: str, at_version_id: Optional[str] = None
    ) -> Optional[AssertionLifecycleRecord]:
        ...

    def list_records_for_ref(self, ref_id: str) -> list[DocumentLifecycleRecord]:
        ...

    def list_assertion_records_for_ref(self, ref_id: str) -> list[AssertionLifecycleRecord]:
        ...


@runtime_checkable
class LifecycleVisibilityPort(Protocol):
    """Current / version-scoped eligibility answers."""

    def document_eligibility(
        self, ref_id: str, at_version_id: Optional[str] = None
    ) -> LifecycleEligibility:
        ...

    def assertion_eligibility(
        self, assertion_id: str, ref_id: str, at_version_id: Optional[str] = None
    ) -> LifecycleEligibility:
        ...

    def eligible_ref_ids(
        self, ref_ids: list[str], at_version_id: Optional[str] = None
    ) -> list[str]:
        """Filter ref_ids down to those currently eligible for retrieval."""
        ...


@runtime_checkable
class EventOutbox(Protocol):
    """Internal append-only lifecycle event outbox (CG-018)."""

    def append(self, event: LifecycleEvent) -> LifecycleEvent:
        """Append one event. Idempotent by event_id."""
        ...

    def list_all(self) -> list[LifecycleEvent]:
        ...

    def list_pending(self) -> list[LifecycleEvent]:
        ...

    def mark_delivered(self, event_id: str) -> None:
        ...
