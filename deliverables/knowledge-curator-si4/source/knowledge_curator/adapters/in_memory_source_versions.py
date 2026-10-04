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

    def append_source_version(self, record: SourceVersionRecord) -> SourceVersionRecord:
        # Idempotent same source_version_id + identical material.
        existing = self._versions.get(record.source_version_id)
        if existing is not None:
            if source_version_material_equal(existing, record):
                return copy.deepcopy(existing)
            raise ValueError(
                f"conflicting source_version_id material: {record.source_version_id}"
            )

        # --- Conflict checks BEFORE any mutation (R1/R2 atomicity) ---

        # R2-C: work must already exist (no auto-create in adapter).
        if record.work_id not in self._works:
            raise ValueError(f"unknown work_id: {record.work_id}")

        # R2-C: prior referential integrity.
        if record.prior_source_version_id is not None:
            prior = self._versions.get(record.prior_source_version_id)
            if prior is None:
                raise ValueError(
                    f"missing prior_source_version_id: {record.prior_source_version_id}"
                )
            if prior.work_id != record.work_id:
                raise ValueError(
                    f"cross-work prior: prior work {prior.work_id} != "
                    f"record work {record.work_id}"
                )

        # (ref_id, fingerprint) uniqueness: same key must not map to a different version.
        ref_fp_key = (record.ref_id, record.source_fingerprint)
        existing_vid = self._by_ref_fp.get(ref_fp_key)
        if existing_vid is not None and existing_vid != record.source_version_id:
            existing_rec = self._versions[existing_vid]
            if not source_version_material_equal(existing_rec, record):
                raise ValueError(
                    f"duplicate (ref_id, fingerprint) maps to different source version: "
                    f"{ref_fp_key} -> {existing_vid} vs {record.source_version_id}"
                )

        # DOI across works: same normalized DOI may appear in one work only.
        if record.normalized_doi:
            for vid in self._by_doi.get(record.normalized_doi, []):
                if self._versions[vid].work_id != record.work_id:
                    raise ValueError(
                        f"normalized DOI {record.normalized_doi!r} already mapped to work "
                        f"{self._versions[vid].work_id}; cannot map to work {record.work_id}"
                    )

        # stable_id across works: same rule.
        if record.stable_id:
            for vid in self._by_stable.get(record.stable_id, []):
                if self._versions[vid].work_id != record.work_id:
                    raise ValueError(
                        f"stable_id {record.stable_id!r} already mapped to work "
                        f"{self._versions[vid].work_id}; cannot map to work {record.work_id}"
                    )

        # --- All checks passed; now mutate ---
        stored = copy.deepcopy(record)
        if stored.created_seq <= 0:
            stored.created_seq = self._next_seq()
        self._versions[stored.source_version_id] = stored
        self._version_order.append(stored.source_version_id)
        self._by_ref_fp[ref_fp_key] = stored.source_version_id
        if stored.normalized_doi:
            self._by_doi.setdefault(stored.normalized_doi, []).append(stored.source_version_id)
        if stored.stable_id:
            self._by_stable.setdefault(stored.stable_id, []).append(stored.source_version_id)
        if stored.normalized_title:
            self._by_title.setdefault(stored.normalized_title, []).append(stored.source_version_id)
        return copy.deepcopy(stored)

    def append_work(self, work: WorkRecord) -> WorkRecord:
        existing = self._works.get(work.work_id)
        if existing is not None:
            # Same work_id + same material -> idempotent; contradictory -> fail closed.
            if (
                existing.created_evidence == work.created_evidence
                and existing.trace_id == work.trace_id
                and existing.provenance_id == work.provenance_id
            ):
                return copy.deepcopy(existing)
            raise ValueError(f"conflicting work_id material: {work.work_id}")
        stored = copy.deepcopy(work)
        if stored.created_seq <= 0:
            stored.created_seq = self._next_seq()
        self._works[stored.work_id] = stored
        self._work_order.append(stored.work_id)
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
