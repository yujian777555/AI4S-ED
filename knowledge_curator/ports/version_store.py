"""Version store port — KB version / snapshot / rollback boundary.

create_snapshot must be idempotent by deterministic manifest content hash
so post-side-effect retries cannot orphan duplicate snapshots (P2.2-02).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.commit import SnapshotManifest


@dataclass
class SnapshotRecord:
    snapshot_id: str
    manifest: SnapshotManifest


@dataclass
class VersionRecord:
    version_id: str
    snapshot_id: str
    prior_version_id: Optional[str]
    published: bool = True


@runtime_checkable
class VersionStore(Protocol):
    """Snapshot/version publish and visibility boundary."""

    def create_snapshot(self, manifest: SnapshotManifest) -> SnapshotRecord:
        """Create or reuse a snapshot for a deterministic content-hash manifest.

        Idempotent: same manifest content_hash returns the same snapshot.
        """
        ...

    def get_snapshot_by_hash(self, content_hash: str) -> Optional[SnapshotRecord]:
        """Lookup an existing snapshot by deterministic content hash."""
        ...

    def publish_version(self, snapshot_id: str) -> VersionRecord:
        """Publish exactly one KB version for a snapshot (idempotent)."""
        ...

    def get_version(self, version_id: str) -> Optional[VersionRecord]:
        """Lookup a version record (published or historical)."""
        ...

    def get_version_by_snapshot(self, snapshot_id: str) -> Optional[VersionRecord]:
        """Lookup the published version for a snapshot, if any."""
        ...

    def get_snapshot(self, snapshot_id: str) -> Optional[SnapshotRecord]:
        """Lookup a snapshot record."""
        ...

    def list_published_versions(self) -> list[VersionRecord]:
        """Downstream-facing read: only published versions."""
        ...

    def current_version(self) -> Optional[VersionRecord]:
        """Currently visible published version pointer."""
        ...

    def rollback_to(self, version_id: str) -> VersionRecord:
        """Switch the visible version pointer to an existing published version.

        Must not physically delete later historical versions.
        Raises ValueError for nonexistent/unpublished targets.
        """
        ...
