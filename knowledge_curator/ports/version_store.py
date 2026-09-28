"""Version store port — KB version / snapshot / rollback boundary.

Opaque version ids. Do not invent project-wide final version format.
Do not hard-code production storage (CG-004).
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
        """Create a snapshot from a deterministic content-hash manifest."""
        ...

    def publish_version(self, snapshot_id: str) -> VersionRecord:
        """Publish exactly one KB version for a snapshot."""
        ...

    def get_version(self, version_id: str) -> Optional[VersionRecord]:
        """Lookup a version record (published or historical)."""
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
