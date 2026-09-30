"""SourceVersionRegistry port (Phase 5.1, CG-019 internal only)."""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.source_versions import (
    SourceVersionRecord,
    WorkRecord,
)


@runtime_checkable
class SourceVersionRegistry(Protocol):
    """Append-only work/version family registry."""

    def lookup_by_ref_fingerprint(
        self, ref_id: str, source_fingerprint: str
    ) -> Optional[SourceVersionRecord]:
        ...

    def lookup_by_doi(self, normalized_doi: str) -> list[SourceVersionRecord]:
        ...

    def lookup_by_stable_id(self, stable_id: str) -> list[SourceVersionRecord]:
        ...

    def lookup_by_normalized_title(self, normalized_title: str) -> list[SourceVersionRecord]:
        ...

    def get_work(self, work_id: str) -> Optional[WorkRecord]:
        ...

    def get_source_version(self, source_version_id: str) -> Optional[SourceVersionRecord]:
        ...

    def list_versions(self, work_id: str) -> list[SourceVersionRecord]:
        ...

    def append_work(self, work: WorkRecord) -> WorkRecord:
        ...

    def append_source_version(self, record: SourceVersionRecord) -> SourceVersionRecord:
        ...

    def bind_source_version(
        self, source_version_id: str, kb_version_id: str, snapshot_id: str
    ) -> SourceVersionRecord:
        ...
