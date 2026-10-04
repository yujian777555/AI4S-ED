"""Integration-only SI-2B provider fixture (Phase SI-2B).

TEST USE ONLY. Not a production recommendation.

Selected via:
    AI4S_SYSTEM_ADAPTER_FACTORY=integration.system.fixtures.si2b_provider:create_si2b_provider_bundle

Uses test-local protocol-compatible stores. Does NOT import/instantiate/
subclass/wrap/delegate to forbidden Knowledge Curator InMemory lifecycle/
revision/source adapters.
"""

from __future__ import annotations

import copy
from typing import Any, Optional

from knowledge_curator.schemas.lifecycle import (
    AssertionLifecycleRecord,
    DocumentLifecycleRecord,
    LifecycleEvent,
)
from knowledge_curator.schemas.revision_publication import RevisionPublicationRecord
from knowledge_curator.schemas.source_versions import (
    SourceVersionRecord,
    WorkRecord,
)


# ---------------------------------------------------------------------------
# Reuse SI-2A test-local commit stores (same fixture family)
# ---------------------------------------------------------------------------
from integration.system.fixtures.si2a_provider import (  # noqa: E402
    TestFailureInjection,
    _StubOntology,
    _StubRepository,
    _StubValidator,
    _TestCommitStore,
    _TestStructuralStore,
    _TestUSDOStore,
    _TestVectorIndex,
    _TestVersionStore,
)


# ---------------------------------------------------------------------------
# Test-local revision stores
# ---------------------------------------------------------------------------


class _TestSourceVersionRegistry:
    """Test-local SourceVersionRegistry."""

    def __init__(self, failures: Optional[TestFailureInjection] = None) -> None:
        self._works: dict[str, WorkRecord] = {}
        self._versions: dict[str, SourceVersionRecord] = {}
        self._failures = failures or TestFailureInjection()

    def append_work(self, record: WorkRecord) -> WorkRecord:
        self._failures.check_before("source_registry.append_work")
        self._works[record.work_id] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def get_work(self, work_id: str) -> Optional[WorkRecord]:
        self._failures.check_before("source_registry.get_work")
        rec = self._works.get(work_id)
        return copy.deepcopy(rec) if rec else None

    def append_source_version(self, record: SourceVersionRecord) -> SourceVersionRecord:
        self._failures.check_before("source_registry.append_source_version")
        existing = self._versions.get(record.source_version_id)
        if existing is not None:
            # R1-14: same-ID replay must not overwrite contradictory material
            if existing.ref_id != record.ref_id or existing.source_fingerprint != record.source_fingerprint:
                raise ValueError(f"contradictory source version replay: {record.source_version_id}")
            return copy.deepcopy(existing)
        self._versions[record.source_version_id] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def get_source_version(self, source_version_id: str) -> Optional[SourceVersionRecord]:
        self._failures.check_before("source_registry.get_source_version")
        rec = self._versions.get(source_version_id)
        return copy.deepcopy(rec) if rec else None

    def list_versions(self, work_id: str) -> list[SourceVersionRecord]:
        return [copy.deepcopy(v) for v in self._versions.values() if v.work_id == work_id]

    def lookup_by_ref_fingerprint(self, ref_id: str, source_fingerprint: str) -> Optional[SourceVersionRecord]:
        for v in self._versions.values():
            if v.ref_id == ref_id and v.source_fingerprint == source_fingerprint:
                return copy.deepcopy(v)
        return None

    def lookup_by_doi(self, normalized_doi: Optional[str]) -> list[SourceVersionRecord]:
        if not normalized_doi:
            return []
        return [copy.deepcopy(v) for v in self._versions.values() if v.normalized_doi == normalized_doi]

    def lookup_by_stable_id(self, stable_id: Optional[str]) -> list[SourceVersionRecord]:
        if not stable_id:
            return []
        return [copy.deepcopy(v) for v in self._versions.values() if v.stable_id == stable_id]

    def lookup_by_normalized_title(self, normalized_title: Optional[str]) -> list[SourceVersionRecord]:
        if not normalized_title:
            return []
        return [copy.deepcopy(v) for v in self._versions.values() if v.normalized_title == normalized_title]

    def bind_source_version(self, source_version_id: str, kb_version_id: str, snapshot_id: str) -> SourceVersionRecord:
        self._failures.check_before("source_registry.bind")
        rec = self._versions.get(source_version_id)
        if rec is None:
            raise ValueError(f"source version not found: {source_version_id}")
        if rec.kb_version_id is not None:
            raise ValueError(f"source version already bound: {source_version_id}")
        rec.kb_version_id = kb_version_id
        rec.snapshot_id = snapshot_id
        return copy.deepcopy(rec)


class _TestLifecycleStore:
    """Test-local LifecycleStore (append-only, R1-13/14 hardened)."""

    def __init__(self, failures: Optional[TestFailureInjection] = None) -> None:
        self._doc_records: dict[str, DocumentLifecycleRecord] = {}
        self._assertion_keys: dict[tuple[str, str], int] = {}  # (lifecycle_id, assertion_id) -> index
        self._assertion_records: list[AssertionLifecycleRecord] = []
        self._failures = failures or TestFailureInjection()

    def append_document_record(self, record: DocumentLifecycleRecord) -> DocumentLifecycleRecord:
        self._failures.check_before("lifecycle.append_document")
        # R1-14: same lifecycle_id must not silently create contradictory duplicates
        existing = self._doc_records.get(record.lifecycle_id)
        if existing is not None:
            # Idempotent replay: same material -> return existing; different -> fail
            if existing.ref_id != record.ref_id or existing.status != record.status:
                raise ValueError(f"contradictory lifecycle document replay: {record.lifecycle_id}")
            return copy.deepcopy(existing)
        self._doc_records[record.lifecycle_id] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def get_document_record(self, lifecycle_id: str) -> Optional[DocumentLifecycleRecord]:
        rec = self._doc_records.get(lifecycle_id)
        return copy.deepcopy(rec) if rec else None

    def append_assertion_records(self, records: list[AssertionLifecycleRecord]) -> list[AssertionLifecycleRecord]:
        self._failures.check_before("lifecycle.append_assertions")
        appended = []
        for r in records:
            key = (r.lifecycle_id, r.assertion_id)
            # R1-14: replay must not duplicate same lifecycle/assertion identity
            if key in self._assertion_keys:
                appended.append(copy.deepcopy(self._assertion_records[self._assertion_keys[key]]))
                continue
            self._assertion_keys[key] = len(self._assertion_records)
            self._assertion_records.append(copy.deepcopy(r))
            appended.append(copy.deepcopy(r))
        return appended  # R1-13: Port specifies return list

    def bind_effective_version(self, lifecycle_id: str, version_id: str) -> None:
        self._failures.check_before("lifecycle.bind_version")
        rec = self._doc_records.get(lifecycle_id)
        if rec is None:
            raise ValueError(f"lifecycle record not found: {lifecycle_id}")
        rec.effective_version_id = version_id

    def list_records_for_ref(self, ref_id: str) -> list[DocumentLifecycleRecord]:
        return [copy.deepcopy(r) for r in self._doc_records.values() if r.ref_id == ref_id]

    def list_assertion_records_for_ref(self, ref_id: str) -> list[AssertionLifecycleRecord]:
        return [copy.deepcopy(r) for r in self._assertion_records if r.ref_id == ref_id]

    def latest_document_state(self, ref_id: str, at_version_id: Optional[str] = None) -> Optional[DocumentLifecycleRecord]:
        # R1-13: accept at_version_id argument per Port
        recs = self.list_records_for_ref(ref_id)
        return recs[-1] if recs else None

    def latest_assertion_state(self, assertion_id: str, at_version_id: Optional[str] = None) -> Optional[AssertionLifecycleRecord]:
        # R1-13: Port signature is (assertion_id, at_version_id) not (ref_id, assertion_id)
        recs = [r for r in self._assertion_records if r.assertion_id == assertion_id]
        return recs[-1] if recs else None


class _TestEventOutbox:
    """Test-local EventOutbox."""

    def __init__(self, failures: Optional[TestFailureInjection] = None) -> None:
        self._events: list[LifecycleEvent] = []
        self._delivered: set[str] = set()
        self._failures = failures or TestFailureInjection()

    def append(self, event: LifecycleEvent) -> LifecycleEvent:
        self._failures.check_before("outbox.append")
        # R1-14: idempotent by event_id
        for existing in self._events:
            if existing.event_id == event.event_id:
                return copy.deepcopy(existing)
        self._events.append(copy.deepcopy(event))
        return copy.deepcopy(event)

    def list_all(self) -> list[LifecycleEvent]:
        return [copy.deepcopy(e) for e in self._events]

    def list_pending(self) -> list[LifecycleEvent]:
        return [copy.deepcopy(e) for e in self._events if e.event_id not in self._delivered]

    def mark_delivered(self, event_id: str) -> None:
        self._delivered.add(event_id)


class _TestRevisionPublicationStore:
    """Test-local RevisionPublicationStore (journal)."""

    def __init__(self, failures: Optional[TestFailureInjection] = None) -> None:
        self._records: dict[str, RevisionPublicationRecord] = {}
        self._failures = failures or TestFailureInjection()

    def create(self, record: RevisionPublicationRecord) -> RevisionPublicationRecord:
        self._failures.check_before("publication.create")
        existing = self._records.get(record.publication_id)
        if existing is not None:
            # R1-14: same-ID create must not overwrite contradictory material
            if existing.package_id != record.package_id:
                raise ValueError(f"contradictory publication create: {record.publication_id}")
            return copy.deepcopy(existing)
        self._records[record.publication_id] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def get(self, publication_id: str) -> Optional[RevisionPublicationRecord]:
        self._failures.check_before("publication.get")
        rec = self._records.get(publication_id)
        return copy.deepcopy(rec) if rec else None

    def update(self, record: RevisionPublicationRecord) -> RevisionPublicationRecord:
        self._failures.check_before("publication.update")
        self._records[record.publication_id] = copy.deepcopy(record)
        self._failures.check_after("publication.update")
        return copy.deepcopy(record)


# ---------------------------------------------------------------------------
# Provider bundle factory
# ---------------------------------------------------------------------------


def create_si2b_provider_bundle(
    *,
    failures: Optional[TestFailureInjection] = None,
    include_revision: bool = True,
    include_commit: bool = True,
) -> dict:
    """Return a provider bundle with curator + commit + revision groups.

    Args:
        failures: shared TestFailureInjection for all stores.
        include_revision: if False, omit revision group (for fail-closed tests).
        include_commit: if False, omit commit group.
    """
    fail = failures or TestFailureInjection()
    bundle: dict[str, Any] = {
        "curator": {
            "repository": _StubRepository(),
            "ontology": _StubOntology(),
            "mechanism_validator": _StubValidator(),
            "provider_identity": "si2b-test-provider",
        }
    }
    if include_commit:
        bundle["commit"] = {
            "commit_store": _TestCommitStore(fail),
            "structural_store": _TestStructuralStore(fail),
            "vector_index": _TestVectorIndex(fail),
            "usdo_store": _TestUSDOStore(fail),
            "version_store": _TestVersionStore(fail),
            "provider_identity": "si2b-test-provider",
        }
    if include_revision:
        bundle["revision"] = {
            "source_registry": _TestSourceVersionRegistry(fail),
            "lifecycle_store": _TestLifecycleStore(fail),
            "event_outbox": _TestEventOutbox(fail),
            "publication_store": _TestRevisionPublicationStore(fail),
            "provider_identity": "si2b-test-provider",
        }
    return bundle
