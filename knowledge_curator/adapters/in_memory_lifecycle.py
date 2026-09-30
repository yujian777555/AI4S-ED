"""In-memory lifecycle store + event outbox adapters (Phase 5.0)."""

from __future__ import annotations

import copy
from typing import Callable, Optional

from knowledge_curator.schemas.lifecycle import (
    AssertionLifecycleRecord,
    DocumentLifecycleRecord,
    LifecycleEligibility,
    LifecycleEvent,
    assertion_material_equal,
    document_material_equal,
    event_material_equal,
)

# Resolve whether effective_version_id is visible at query version.
# Returns True when the effective version is an ancestor-or-self of query version.
VersionVisibleFn = Callable[[str, Optional[str]], bool]


def _always_visible(effective_version_id: str, at_version_id: Optional[str]) -> bool:
    return True


class InMemoryLifecycleStore:
    """Append-only lifecycle store with idempotent event-id replay."""

    def __init__(self, version_visible: Optional[VersionVisibleFn] = None) -> None:
        self._doc_by_id: dict[str, DocumentLifecycleRecord] = {}
        self._doc_order: list[str] = []
        self._assert_by_key: dict[str, AssertionLifecycleRecord] = {}
        self._assert_order: list[str] = []
        self._seq = 0
        self._version_visible = version_visible or _always_visible

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def append_document_record(self, record: DocumentLifecycleRecord) -> DocumentLifecycleRecord:
        existing = self._doc_by_id.get(record.lifecycle_id)
        if existing is not None:
            # Idempotent replay only when ALL material fields match (R1-C).
            if document_material_equal(existing, record):
                return copy.deepcopy(existing)
            raise ValueError(
                f"conflicting document lifecycle id reuse: {record.lifecycle_id}"
            )
        stored = copy.deepcopy(record)
        if stored.created_seq <= 0:
            stored.created_seq = self._next_seq()
        self._doc_by_id[stored.lifecycle_id] = stored
        self._doc_order.append(stored.lifecycle_id)
        return copy.deepcopy(stored)

    def append_assertion_records(
        self, records: list[AssertionLifecycleRecord]
    ) -> list[AssertionLifecycleRecord]:
        out: list[AssertionLifecycleRecord] = []
        for rec in records:
            key = rec.identity_key()
            existing = self._assert_by_key.get(key)
            if existing is not None:
                if assertion_material_equal(existing, rec):
                    out.append(copy.deepcopy(existing))
                    continue
                raise ValueError(f"conflicting assertion lifecycle id reuse: {key}")
            stored = copy.deepcopy(rec)
            if stored.created_seq <= 0:
                stored.created_seq = self._next_seq()
            self._assert_by_key[key] = stored
            self._assert_order.append(key)
            out.append(copy.deepcopy(stored))
        return out

    def bind_effective_version(self, lifecycle_id: str, version_id: str) -> None:
        rec = self._doc_by_id.get(lifecycle_id)
        if rec is None:
            raise ValueError(f"unknown lifecycle_id: {lifecycle_id}")
        if rec.effective_version_id is None:
            rec.effective_version_id = version_id
        elif rec.effective_version_id != version_id:
            raise ValueError(
                f"lifecycle {lifecycle_id} already bound to {rec.effective_version_id}"
            )
        # Stamp assertion records sharing this lifecycle_id
        for key in self._assert_order:
            ar = self._assert_by_key[key]
            if ar.lifecycle_id == lifecycle_id and ar.effective_version_id is None:
                ar.effective_version_id = version_id

    def get_document_record(self, lifecycle_id: str) -> Optional[DocumentLifecycleRecord]:
        rec = self._doc_by_id.get(lifecycle_id)
        return copy.deepcopy(rec) if rec else None

    def _visible_doc_records(
        self, ref_id: str, at_version_id: Optional[str]
    ) -> list[DocumentLifecycleRecord]:
        recs = [
            self._doc_by_id[k]
            for k in self._doc_order
            if self._doc_by_id[k].ref_id == ref_id
        ]
        # Only bound (published) records participate in visibility. Staged
        # records with effective_version_id=None must not flip current state.
        visible = [
            r
            for r in recs
            if r.effective_version_id is not None
            and self._version_visible(r.effective_version_id, at_version_id)
        ]
        visible.sort(key=lambda r: (r.created_seq, r.lifecycle_id))
        return visible

    def latest_document_state(
        self, ref_id: str, at_version_id: Optional[str] = None
    ) -> Optional[DocumentLifecycleRecord]:
        visible = self._visible_doc_records(ref_id, at_version_id)
        if not visible:
            return None
        return copy.deepcopy(visible[-1])

    def latest_assertion_state(
        self, assertion_id: str, at_version_id: Optional[str] = None
    ) -> Optional[AssertionLifecycleRecord]:
        recs = [
            self._assert_by_key[k]
            for k in self._assert_order
            if self._assert_by_key[k].assertion_id == assertion_id
        ]
        visible = [
            r
            for r in recs
            if r.effective_version_id is not None
            and self._version_visible(r.effective_version_id, at_version_id)
        ]
        visible.sort(key=lambda r: (r.created_seq, r.identity_key()))
        if not visible:
            return None
        return copy.deepcopy(visible[-1])

    def list_records_for_ref(self, ref_id: str) -> list[DocumentLifecycleRecord]:
        return [
            copy.deepcopy(self._doc_by_id[k])
            for k in self._doc_order
            if self._doc_by_id[k].ref_id == ref_id
        ]

    def list_assertion_records_for_ref(self, ref_id: str) -> list[AssertionLifecycleRecord]:
        return [
            copy.deepcopy(self._assert_by_key[k])
            for k in self._assert_order
            if self._assert_by_key[k].ref_id == ref_id
        ]


class InMemoryEventOutbox:
    """Append-only lifecycle event outbox (CG-018 internal)."""

    def __init__(self) -> None:
        self._events: dict[str, LifecycleEvent] = {}
        self._order: list[str] = []
        self._seq = 0

    def append(self, event: LifecycleEvent) -> LifecycleEvent:
        existing = self._events.get(event.event_id)
        if existing is not None:
            # Idempotent only when ALL material fields match (R1-C).
            if event_material_equal(existing, event):
                return copy.deepcopy(existing)
            raise ValueError(f"conflicting event id reuse: {event.event_id}")
        stored = copy.deepcopy(event)
        if stored.created_seq <= 0:
            self._seq += 1
            stored.created_seq = self._seq
        self._events[stored.event_id] = stored
        self._order.append(stored.event_id)
        return copy.deepcopy(stored)

    def list_all(self) -> list[LifecycleEvent]:
        return [copy.deepcopy(self._events[k]) for k in self._order]

    def list_pending(self) -> list[LifecycleEvent]:
        return [copy.deepcopy(self._events[k]) for k in self._order if not self._events[k].delivered]

    def mark_delivered(self, event_id: str) -> None:
        if event_id in self._events:
            self._events[event_id].delivered = True


class InMemoryLifecycleVisibility:
    """Version-scoped eligibility based on LifecycleStore."""

    def __init__(self, store: InMemoryLifecycleStore) -> None:
        self._store = store

    def document_eligibility(
        self, ref_id: str, at_version_id: Optional[str] = None
    ) -> LifecycleEligibility:
        rec = self._store.latest_document_state(ref_id, at_version_id=at_version_id)
        if rec is None:
            return LifecycleEligibility(
                visible_for_retrieval=True,
                eligible_for_training=True,
                status="active",
                reason="no lifecycle record",
                at_version_id=at_version_id,
            )
        status = rec.status.value
        if status == "retracted":
            return LifecycleEligibility(
                visible_for_retrieval=False,
                eligible_for_training=False,
                status=status,
                reason=rec.reason.value,
                at_version_id=at_version_id,
            )
        if status == "archived":
            return LifecycleEligibility(
                visible_for_retrieval=False,
                eligible_for_training=False,
                status=status,
                reason=rec.reason.value,
                at_version_id=at_version_id,
            )
        if status == "superseded":
            return LifecycleEligibility(
                visible_for_retrieval=False,
                eligible_for_training=False,
                status=status,
                reason=rec.reason.value,
                at_version_id=at_version_id,
            )
        return LifecycleEligibility(
            visible_for_retrieval=True,
            eligible_for_training=True,
            status=status,
            reason=rec.reason.value,
            at_version_id=at_version_id,
        )

    def assertion_eligibility(
        self, assertion_id: str, ref_id: str, at_version_id: Optional[str] = None
    ) -> LifecycleEligibility:
        doc = self.document_eligibility(ref_id, at_version_id=at_version_id)
        if not doc.visible_for_retrieval:
            return LifecycleEligibility(
                visible_for_retrieval=False,
                eligible_for_training=False,
                status=doc.status,
                reason=f"document {doc.status}",
                at_version_id=at_version_id,
            )
        rec = self._store.latest_assertion_state(assertion_id, at_version_id=at_version_id)
        if rec is None:
            return LifecycleEligibility(
                visible_for_retrieval=True,
                eligible_for_training=True,
                status="active",
                reason="no assertion lifecycle record",
                at_version_id=at_version_id,
            )
        status = rec.status.value
        if status in ("archived", "superseded"):
            return LifecycleEligibility(
                visible_for_retrieval=False,
                eligible_for_training=False,
                status=status,
                reason=status,
                at_version_id=at_version_id,
            )
        return LifecycleEligibility(
            visible_for_retrieval=True,
            eligible_for_training=True,
            status=status,
            reason=status,
            at_version_id=at_version_id,
        )

    def eligible_ref_ids(
        self, ref_ids: list[str], at_version_id: Optional[str] = None
    ) -> list[str]:
        return [
            r
            for r in ref_ids
            if self.document_eligibility(r, at_version_id=at_version_id).visible_for_retrieval
        ]
