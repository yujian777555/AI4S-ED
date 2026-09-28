"""In-memory adapters for Phase 2.1 document commit / structural / version / vector / USDO.

Models real persistence boundaries:
  * copy-on-write lifecycle store (no aliasing mutations)
  * staged vs committed visibility for structural + USDO
  * version-safe immutable vector identities
  * idempotent version publish
  * deterministic failure injection (before/after side effect)
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Optional

from knowledge_curator.ports.document_commit_store import DocumentCommitRecord, DocumentCommitStore
from knowledge_curator.ports.structural_store import (
    StructuralDocumentRecord,
    StructuralKnowledgeStore,
)
from knowledge_curator.ports.usdo_store import USDOStore
from knowledge_curator.ports.vector_index import VectorIndex
from knowledge_curator.ports.version_store import SnapshotRecord, VersionRecord, VersionStore
from knowledge_curator.schemas.commit import SnapshotManifest, USDORecord, VectorPayload


class FailureInjection:
    """Deterministic failure injection for in-memory adapters.

    Modes:
      * fail_on(op)         — raise before the side effect
      * fail_after(op)      — perform the side effect, then raise
      * fail_after(op, also_fail=[...]) — after side effect, also arm fail_on for targets
      * fail_on_nth(op, n)  — raise on the n-th call (1-based); side effect skipped
    """

    def __init__(self) -> None:
        self._fail_before: set[str] = set()
        self._fail_after: dict[str, list[str]] = {}
        self._nth: dict[str, list[int]] = {}
        self._counts: dict[str, int] = {}

    def fail_on(self, op: str) -> None:
        self._fail_before.add(op)

    def fail_after(self, op: str, also_fail: Optional[list[str]] = None) -> None:
        self._fail_after[op] = list(also_fail or [])

    def fail_on_nth(self, op: str, n: int) -> None:
        self._nth.setdefault(op, []).append(n)

    def clear(self, op: Optional[str] = None) -> None:
        if op is None:
            self._fail_before.clear()
            self._fail_after.clear()
            self._nth.clear()
        else:
            self._fail_before.discard(op)
            self._fail_after.pop(op, None)
            self._nth.pop(op, None)

    def check_before(self, op: str) -> None:
        self._counts[op] = self._counts.get(op, 0) + 1
        if op in self._fail_before:
            self._fail_before.discard(op)
            raise RuntimeError(f"injected failure before side effect: {op}")
        for n in self._nth.get(op, []):
            if self._counts[op] == n:
                self._nth[op].remove(n)
                raise RuntimeError(f"injected failure on call {n}: {op}")

    def check_after(self, op: str) -> None:
        if op in self._fail_after:
            extras = self._fail_after.pop(op)
            for target in extras:
                self._fail_before.add(target)
            raise RuntimeError(f"injected failure after side effect: {op}")


class InMemoryDocumentCommitStore(DocumentCommitStore):
    """Copy-on-write document commit lifecycle + idempotency store."""

    def __init__(self, failures: Optional[FailureInjection] = None) -> None:
        self._records: dict[tuple[str, str], DocumentCommitRecord] = {}
        self._by_commit_id: dict[str, DocumentCommitRecord] = {}
        self._failures = failures or FailureInjection()

    def find_by_key(self, ref_id: str, source_fingerprint: str) -> Optional[DocumentCommitRecord]:
        self._failures.check_before("document_commit.find")
        record = self._records.get((ref_id, source_fingerprint))
        return copy.deepcopy(record) if record is not None else None

    def create(self, record: DocumentCommitRecord) -> DocumentCommitRecord:
        self._failures.check_before("document_commit.create")
        key = (record.ref_id, record.source_fingerprint)
        if key in self._records:
            raise ValueError(f"document commit already exists: {key}")
        stored = copy.deepcopy(record)
        self._records[key] = stored
        self._by_commit_id[stored.commit_id] = stored
        return copy.deepcopy(stored)

    def update(self, record: DocumentCommitRecord) -> DocumentCommitRecord:
        self._failures.check_before("document_commit.update")
        key = (record.ref_id, record.source_fingerprint)
        stored = copy.deepcopy(record)
        self._records[key] = stored
        self._by_commit_id[stored.commit_id] = stored
        self._failures.check_after("document_commit.update")
        return copy.deepcopy(stored)

    def count_structural_assertions(self, commit_id: str) -> int:
        record = self._by_commit_id.get(commit_id)
        return len(record.admitted) if record else 0


class InMemoryStructuralKnowledgeStore(StructuralKnowledgeStore):
    """Staged/committed structural assertion + metadata store."""

    def __init__(self, failures: Optional[FailureInjection] = None) -> None:
        self._staged: dict[str, StructuralDocumentRecord] = {}
        self._committed: dict[str, StructuralDocumentRecord] = {}
        self._failures = failures or FailureInjection()

    def stage_document(self, record: StructuralDocumentRecord) -> None:
        self._failures.check_before("structural.stage")
        self._staged[record.stage_id] = copy.deepcopy(record)

    def commit_stage(self, stage_id: str) -> None:
        self._failures.check_before("structural.commit")
        if stage_id not in self._staged:
            raise ValueError(f"no staged structural document: {stage_id}")
        self._committed[stage_id] = copy.deepcopy(self._staged[stage_id])
        self._failures.check_after("structural.commit")

    def abort_stage(self, stage_id: str) -> None:
        self._staged.pop(stage_id, None)

    def list_committed_for_ref(self, ref_id: str) -> list[StructuralDocumentRecord]:
        return [
            copy.deepcopy(r) for r in self._committed.values() if r.ref_id == ref_id
        ]

    def get_committed(self, stage_id: str) -> Optional[StructuralDocumentRecord]:
        record = self._committed.get(stage_id)
        return copy.deepcopy(record) if record else None

    def is_committed(self, stage_id: str) -> bool:
        return stage_id in self._committed


class InMemoryVectorIndex(VectorIndex):
    """Immutable version-safe vector index adapter."""

    def __init__(self, failures: Optional[FailureInjection] = None) -> None:
        self._vectors: dict[str, VectorPayload] = {}
        self._failures = failures or FailureInjection()

    def upsert(self, payloads: list[VectorPayload]) -> None:
        self._failures.check_before("vector.upsert")
        for item in payloads:
            # Immutable identity: never mutate an existing different payload in place.
            self._vectors[item.vector_id] = copy.deepcopy(item)
        self._failures.check_after("vector.upsert")

    def has_ids(self, vector_ids: list[str]) -> bool:
        return all(vid in self._vectors for vid in vector_ids)

    def get_by_id(self, vector_id: str) -> Optional[VectorPayload]:
        item = self._vectors.get(vector_id)
        return copy.deepcopy(item) if item else None

    def count_for_ref(self, ref_id: str) -> int:
        return sum(1 for v in self._vectors.values() if v.ref_id == ref_id)


class InMemoryUSDOStore(USDOStore):
    """Staged/committed USDO registration adapter."""

    def __init__(self, failures: Optional[FailureInjection] = None) -> None:
        self._staged: dict[str, dict[str, USDORecord]] = {}
        self._committed: dict[str, USDORecord] = {}
        self._failures = failures or FailureInjection()

    def stage(self, stage_id: str, records: list[USDORecord]) -> None:
        self._failures.check_before("usdo.stage")
        bucket = self._staged.setdefault(stage_id, {})
        for rec in records:
            bucket[rec.record_id] = copy.deepcopy(rec)

    def commit_stage(self, stage_id: str) -> None:
        self._failures.check_before("usdo.commit")
        bucket = self._staged.pop(stage_id, None)
        if bucket is None:
            raise ValueError(f"no staged USDO records: {stage_id}")
        for rec in bucket.values():
            self._committed[rec.record_id] = copy.deepcopy(rec)
        self._failures.check_after("usdo.commit")

    def abort_stage(self, stage_id: str) -> None:
        self._staged.pop(stage_id, None)

    def list_for_ref(self, ref_id: str) -> list[USDORecord]:
        # Downstream-visible: committed only.
        return [copy.deepcopy(r) for r in self._committed.values() if r.ref_id == ref_id]

    def has_records(self, record_ids: list[str]) -> bool:
        staged_ids = {rid for bucket in self._staged.values() for rid in bucket}
        return all(rid in self._committed or rid in staged_ids for rid in record_ids)


class InMemoryVersionStore(VersionStore):
    """Snapshot/version store with idempotent publish and visible pointer."""

    def __init__(self, failures: Optional[FailureInjection] = None) -> None:
        self._snapshots: dict[str, SnapshotRecord] = {}
        self._versions: dict[str, VersionRecord] = {}
        self._snapshot_to_version: dict[str, str] = {}
        self._published_order: list[str] = []
        self._current_version_id: Optional[str] = None
        self._counter = 0
        self._failures = failures or FailureInjection()

    def create_snapshot(self, manifest: SnapshotManifest) -> SnapshotRecord:
        self._failures.check_before("version.create_snapshot")
        self._counter += 1
        snapshot_id = f"snap-{self._counter:04d}"
        record = SnapshotRecord(snapshot_id=snapshot_id, manifest=copy.deepcopy(manifest))
        self._snapshots[snapshot_id] = record
        self._failures.check_after("version.create_snapshot")
        return copy.deepcopy(record)

    def publish_version(self, snapshot_id: str) -> VersionRecord:
        self._failures.check_before("version.publish")
        if snapshot_id not in self._snapshots:
            raise ValueError(f"unknown snapshot: {snapshot_id}")
        # Idempotent publish: one version per snapshot.
        existing_id = self._snapshot_to_version.get(snapshot_id)
        if existing_id is not None:
            return copy.deepcopy(self._versions[existing_id])

        self._counter += 1
        version_id = f"kbv-{self._counter:04d}"
        prior = self._current_version_id
        record = VersionRecord(
            version_id=version_id,
            snapshot_id=snapshot_id,
            prior_version_id=prior,
            published=True,
        )
        self._versions[version_id] = record
        self._snapshot_to_version[snapshot_id] = version_id
        self._published_order.append(version_id)
        self._current_version_id = version_id
        self._failures.check_after("version.publish")
        return copy.deepcopy(record)

    def get_version(self, version_id: str) -> Optional[VersionRecord]:
        record = self._versions.get(version_id)
        return copy.deepcopy(record) if record else None

    def get_version_by_snapshot(self, snapshot_id: str) -> Optional[VersionRecord]:
        version_id = self._snapshot_to_version.get(snapshot_id)
        if version_id is None:
            return None
        return copy.deepcopy(self._versions[version_id])

    def list_published_versions(self) -> list[VersionRecord]:
        return [
            copy.deepcopy(self._versions[vid])
            for vid in self._published_order
            if self._versions[vid].published
        ]

    def current_version(self) -> Optional[VersionRecord]:
        if self._current_version_id is None:
            return None
        return copy.deepcopy(self._versions.get(self._current_version_id))

    def rollback_to(self, version_id: str) -> VersionRecord:
        self._failures.check_before("version.rollback")
        record = self._versions.get(version_id)
        if record is None:
            raise ValueError(f"rollback target does not exist: {version_id}")
        if not record.published:
            raise ValueError(f"rollback target is not a published version: {version_id}")
        self._current_version_id = version_id
        return copy.deepcopy(record)

    def get_snapshot(self, snapshot_id: str) -> Optional[SnapshotRecord]:
        record = self._snapshots.get(snapshot_id)
        return copy.deepcopy(record) if record else None
