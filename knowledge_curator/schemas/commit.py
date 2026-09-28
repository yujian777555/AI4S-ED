"""Internal temporary commit models for 03 §5.4 atomic ingest.

temporary compatibility model
Not the frozen cross-team public schema (CG-002). Phase 2 internal only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from knowledge_curator.schemas.assertions import Assertion, AssertionSet, Confidence
from knowledge_curator.schemas.curation import CurationAction, CurationReport


class CommitPhase(str, Enum):
    """Atomic visibility state progression for one document commit."""

    PREPARING = "preparing"
    STRUCTURAL_STAGED = "structural_staged"
    STRUCTURAL_COMMITTED = "structural_committed"
    VECTOR_PENDING = "vector_pending"
    VECTOR_COMMITTED = "vector_committed"
    SNAPSHOT_CREATED = "snapshot_created"
    PUBLISHED = "published"
    FAILED = "failed"


class AssertionVisibility(str, Enum):
    """How an admitted assertion is exposed after commit."""

    ACTIVE = "active"
    DOWNGRADED = "downgraded"
    PENDING = "pending"
    SUPERSEDED = "superseded"
    # REJECT is not admitted at all


class CommitStatus(str, Enum):
    PUBLISHED = "published"
    PENDING_VECTOR = "pending_vector"
    PENDING_FINALIZE = "pending_finalize"
    IDEMPOTENT_HIT = "idempotent_hit"
    NOT_PUBLISHABLE = "not_publishable"
    FAILED = "failed"


@dataclass
class SourceIdentity:
    """Idempotency identity of one source document version."""

    ref_id: str
    source_fingerprint: str


@dataclass
class AdmittedAssertion:
    """Assertion admitted into document commit with visibility metadata."""

    assertion: Assertion
    visibility: AssertionVisibility
    confidence: Confidence
    action: CurationAction


@dataclass
class USDORecord:
    """USDO / payload registration record for one document."""

    record_id: str
    ref_id: str
    content_hash: str
    payload_kind: str = "usdo_json"


@dataclass
class VectorPayload:
    """Vector index payload identity (no real embeddings required)."""

    vector_id: str
    ref_id: str
    assertion_id: str
    content_hash: str


@dataclass
class SnapshotManifest:
    """Deterministic content-hash manifest for a document commit."""

    ref_id: str
    source_fingerprint: str
    assertion_hashes: list[str]
    usdo_hashes: list[str]
    vector_ids: list[str]
    metadata_hash: str
    decision_hashes: list[str]
    content_hash: str = ""
    # Internal temporary storage identities for version-scoped resolution
    structural_stage_id: str = ""
    usdo_record_ids: list[str] = field(default_factory=list)

    def stable_payload(self) -> dict[str, Any]:
        """Canonical payload used for deterministic content hashing.

        Excludes ephemeral identifiers (random report_id, timestamps).
        """
        return {
            "ref_id": self.ref_id,
            "source_fingerprint": self.source_fingerprint,
            "assertion_hashes": sorted(self.assertion_hashes),
            "usdo_hashes": sorted(self.usdo_hashes),
            "vector_ids": sorted(self.vector_ids),
            "metadata_hash": self.metadata_hash,
            "decision_hashes": sorted(self.decision_hashes),
        }


@dataclass
class CommitRequest:
    """Input to the document commit coordinator."""

    source: SourceIdentity
    assertion_set: AssertionSet
    report: CurationReport
    metadata: dict[str, Any] = field(default_factory=dict)
    trace: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommitResult:
    """Outcome of one commit / replay / idempotent lookup."""

    status: CommitStatus
    commit_id: str
    phase: CommitPhase
    snapshot_id: Optional[str] = None
    version_id: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)
