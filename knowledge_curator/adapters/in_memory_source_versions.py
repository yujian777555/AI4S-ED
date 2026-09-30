"""In-memory SourceVersionRegistry adapter (Phase 5.1)."""

from __future__ import annotations

import copy
from typing import Optional

from knowledge_curator.schemas.source_versions import (
    SourceVersionRecord,
    WorkRecord,
    source_version_material_equal,
)


class InMemorySourceVersionRegistry:
    """Append-only work/version family registry."""

    def __init__(self) -> None:
        self._works: dict[str, WorkRecord] = {}
        self._work_order: list[str] = []
        self._versions: dict[str, SourceVersionRecord] = {}
        self._version_order: list[str] = []
        self._by_ref_fp: dict[tuple[str, str], str] = {}
        self._by_doi: dict[str, list[str]] = {}
        self._by_stable: dict[str, list[str]] = {}
        self._by_title: dict[str, list[str]] = {}
        self._seq = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    # ---- lookup ----

    def lookup_by_ref_fingerprint(
        self, ref_id: str, source_fingerprint: str
    ) -> Optional[SourceVersionRecord]:
        vid = self._by_ref_fp.get((ref_id, source_fingerprint))
        if vid is None:
            return None
        return copy.deepcopy(self._versions[vid])

    def lookup_by_doi(self, normalized_doi: str) -> list[SourceVersionRecord]:
        ids = self._by_doi.get(normalized_doi, [])
        return [copy.deepcopy(self._versions[i]) for i in ids]

    def lookup_by_stable_id(self, stable_id: str) -> list[SourceVersionRecord]:
        ids = self._by_stable.get(stable_id, [])
        return [copy.deepcopy(self._versions[i]) for i in ids]

    def lookup_by_normalized_title(self, normalized_title: str) -> list[SourceVersionRecord]:
        ids = self._by_title.get(normalized_title, [])
        return [copy.deepcopy(self._versions[i]) for i in ids]

    def get_work(self, work_id: str) -> Optional[WorkRecord]:
        rec = self._works.get(work_id)
        return copy.deepcopy(rec) if rec else None

    def get_source_version(self, source_version_id: str) -> Optional[SourceVersionRecord]:
        rec = self._versions.get(source_version_id)
        return copy.deepcopy(rec) if rec else None

    def list_versions(self, work_id: str) -> list[SourceVersionRecord]:
        return [
            copy.deepcopy(self._versions[vid])
            for vid in self._version_order
            if self._versions[vid].work_id == work_id
        ]

    # ---- append ----

    def append_work(self, work: WorkRecord) -> WorkRecord:
        existing = self._works.get(work.work_id)
        if existing is not None:
            return copy.deepcopy(existing)
        stored = copy.deepcopy(work)
        if stored.created_seq <= 0:
            stored.created_seq = self._next_seq()
        self._works[stored.work_id] = stored
        self._work_order.append(stored.work_id)
        return copy.deepcopy(stored)

    def append_source_version(self, record: SourceVersionRecord) -> SourceVersionRecord:
        existing = self._versions.get(record.source_version_id)
        if existing is not None:
            if source_version_material_equal(existing, record):
                return copy.deepcopy(existing)
            raise ValueError(
                f"conflicting source_version_id material: {record.source_version_id}"
            )
        stored = copy.deepcopy(record)
        if stored.created_seq <= 0:
            stored.created_seq = self._next_seq()
        self._versions[stored.source_version_id] = stored
        self._version_order.append(stored.source_version_id)
        # Indexes
        self._by_ref_fp[(stored.ref_id, stored.source_fingerprint)] = stored.source_version_id
        if stored.normalized_doi:
            self._by_doi.setdefault(stored.normalized_doi, []).append(stored.source_version_id)
        if stored.stable_id:
            self._by_stable.setdefault(stored.stable_id, []).append(stored.source_version_id)
        if stored.normalized_title:
            self._by_title.setdefault(stored.normalized_title, []).append(stored.source_version_id)
        return copy.deepcopy(stored)

    def bind_source_version(
        self, source_version_id: str, kb_version_id: str, snapshot_id: str
    ) -> SourceVersionRecord:
        rec = self._versions.get(source_version_id)
        if rec is None:
            raise ValueError(f"unknown source_version_id: {source_version_id}")
        if rec.kb_version_id is None:
            rec.kb_version_id = kb_version_id
            rec.snapshot_id = snapshot_id
        elif rec.kb_version_id != kb_version_id:
            raise ValueError(
                f"source_version {source_version_id} already bound to "
                f"{rec.kb_version_id}; conflicting rebind to {kb_version_id}"
            )
        # snapshot_id must match on idempotent retry
        elif rec.snapshot_id is not None and rec.snapshot_id != snapshot_id:
            raise ValueError(
                f"source_version {source_version_id} snapshot mismatch on rebind"
            )
        return copy.deepcopy(rec)
