"""Document commit store port — idempotent document commit lifecycle.

Internal Phase 2 boundary for (ref_id, source_fingerprint) document commits.
Not the final cross-team L2 contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.commit import (
    AdmittedAssertion,
    CommitPhase,
    SnapshotManifest,
    USDORecord,
    VectorPayload,
)


@dataclass
class DocumentCommitRecord:
    """Persisted lifecycle record for one (ref_id, source_fingerprint) commit."""

    commit_id: str
    ref_id: str
    source_fingerprint: str
    phase: CommitPhase
    admitted: list[AdmittedAssertion] = field(default_factory=list)
    usdo_records: list[USDORecord] = field(default_factory=list)
    vector_payloads: list[VectorPayload] = field(default_factory=list)
    metadata_hash: str = ""
    snapshot_id: Optional[str] = None
    version_id: Optional[str] = None
    manifest: Optional[SnapshotManifest] = None
    error: Optional[str] = None


@runtime_checkable
class DocumentCommitStore(Protocol):
    """Idempotency + staging store for document-level structural commit."""

    def find_by_key(self, ref_id: str, source_fingerprint: str) -> Optional[DocumentCommitRecord]:
        """Lookup an existing commit record by idempotency key."""
        ...

    def create(self, record: DocumentCommitRecord) -> DocumentCommitRecord:
        """Create a new in-progress commit record."""
        ...

    def update(self, record: DocumentCommitRecord) -> DocumentCommitRecord:
        """Persist lifecycle updates for an existing commit record."""
        ...

    def count_structural_assertions(self, commit_id: str) -> int:
        """Number of structural assertion records for this commit (for dedup checks)."""
        ...
