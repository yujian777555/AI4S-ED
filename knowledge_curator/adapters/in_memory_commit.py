"""In-memory adapters for Phase 2 document commit / version / vector / USDO.

Deterministic failure injection is supported for tests. No SQLite/FAISS/HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from knowledge_curator.ports.document_commit_store import DocumentCommitRecord, DocumentCommitStore
from knowledge_curator.ports.usdo_store import USDOStore
from knowledge_curator.ports.vector_index import VectorIndex
from knowledge_curator.ports.version_store import SnapshotRecord, VersionRecord, VersionStore
from knowledge_curator.schemas.commit import SnapshotManifest, USDORecord, VectorPayload


class FailureInjection:
    """Deterministic failure injection for in-memory adapters."""

    def __init__(self) -> None:
        self._fail_ops: set[str] = set()

    def fail_on(self, op: str) -> None:
        """Make the next call of ``op`` raise RuntimeError."""
        self._fail_ops.add(op)

    def clear(self, op: Optional[str] = None) -> None:
        if op is None:
            self._fail_ops.clear()
        else:
            self._fail_ops.discard(op)

    def check(self, op: str) -> None:
        if op in self._fail_ops:
            self._fail_ops.discard(op)
            raise RuntimeError(f"injected failure: {op}")


class InMemoryDocumentCommitStore(DocumentCommitStore):
    """In-memory document commit lifecycle + idempotency store."""

    def __init__(self, failures: Optional[FailureInjection] = None) -> None:
        self._records: dict[tuple[str, str], DocumentCommitRecord] = {}
        self._by_commit_id: dict[str, DocumentCommitRecord] = {}
        self._failures = failures or FailureInjection()

    def find_by_key(self, ref_id: str, source_fingerprint: str) -> Optional[DocumentCommitRecord]:
        self._failures.check("document_commit.find")
        return self._records.get((ref_id, source_fingerprint))

    def create(self, record: DocumentCommitRecord) -> DocumentCommitRecord:
        self._failures.check("document_commit.create")
        key = (record.ref_id, record.source_fingerprint)
        if key in self._records:
            raise ValueError(f"document commit already exists: {key}")
        self._records[key] = record
        self._by_commit_id[record.commit_id] = record
        return record

    def update(self, record: DocumentCommitRecord) -> DocumentCommitRecord:
        self._failures.check("document_commit.update")
        key = (record.ref_id, record.source_fingerprint)
        self._records[key] = record
        self._by_commit_id[record.commit_id] = record
        return record

    def count_structural_assertions(self, commit_id: str) -> int:
        record = self._by_commit_id.get(commit_id)
        return len(record.admitted) if record else 0


class InMemoryVectorIndex(VectorIndex):
    """In-memory vector index adapter with idempotent upsert."""

    def __init__(self, failures: Optional[FailureInjection] = None) -> None:
        self._vectors: dict[str, VectorPayload] = {}
        self._failures = failures or FailureInjection()

    def upsert(self, payloads: list[VectorPayload]) -> None:
        self._failures.check("vector.upsert")
        for item in payloads:
            self._vectors[item.vector_id] = item

    def has_ids(self, vector_ids: list[str]) -> bool:
        return all(vid in self._vectors for vid in vector_ids)

    def count_for_ref(self, ref_id: str) -> int:
        return sum(1 for v in self._vectors.values() if v.ref_id == ref_id)


class InMemoryUSDOStore(USDOStore):
    """In-memory USDO registration adapter."""

    def __init__(self, failures: Optional[FailureInjection] = None) -> None:
        self._records: dict[str, USDORecord] = {}
        self._failures = failures or FailureInjection()

    def register(self, records: list[USDORecord]) -> None:
        self._failures.check("usdo.register")
        for rec in records:
            self._records[rec.record_id] = rec

    def has_records(self, record_ids: list[str]) -> bool:
        return all(rid in self._records for rid in record_ids)

    def list_for_ref(self, ref_id: str) -> list[USDORecord]:
        return [r for r in self._records.values() if r.ref_id == ref_id]


class InMemoryVersionStore(VersionStore):
    """In-memory snapshot/version store with visible pointer and rollback."""

    def __init__(self, failures: Optional[FailureInjection] = None) -> None:
        self._snapshots: dict[str, SnapshotRecord] = {}
        self._versions: dict[str, VersionRecord] = {}
        self._published_order: list[str] = []
        self._current_version_id: Optional[str] = None
        self._counter = 0
        self._failures = failures or FailureInjection()

    def create_snapshot(self, manifest: SnapshotManifest) -> SnapshotRecord:
        self._failures.check("version.create_snapshot")
        self._counter += 1
        snapshot_id = f"snap-{self._counter:04d}"
        record = SnapshotRecord(snapshot_id=snapshot_id, manifest=manifest)
        self._snapshots[snapshot_id] = record
        return record

    def publish_version(self, snapshot_id: str) -> VersionRecord:
        self._failures.check("version.publish")
        if snapshot_id not in self._snapshots:
            raise ValueError(f"unknown snapshot: {snapshot_id}")
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
        self._published_order.append(version_id)
        self._current_version_id = version_id
        return record

    def get_version(self, version_id: str) -> Optional[VersionRecord]:
        return self._versions.get(version_id)

    def list_published_versions(self) -> list[VersionRecord]:
        return [self._versions[vid] for vid in self._published_order if self._versions[vid].published]

    def current_version(self) -> Optional[VersionRecord]:
        if self._current_version_id is None:
            return None
        return self._versions.get(self._current_version_id)

    def rollback_to(self, version_id: str) -> VersionRecord:
        self._failures.check("version.rollback")
        record = self._versions.get(version_id)
        if record is None:
            raise ValueError(f"rollback target does not exist: {version_id}")
        if not record.published:
            raise ValueError(f"rollback target is not a published version: {version_id}")
        # Only switch the visible pointer; retain historical versions.
        self._current_version_id = version_id
        return record

    def get_snapshot(self, snapshot_id: str) -> Optional[SnapshotRecord]:
        return self._snapshots.get(snapshot_id)
