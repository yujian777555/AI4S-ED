"""Internal temporary revision publication models (Phase 5.3).

Not a public cross-team schema. Orchestration layer above frozen
Phase 5.0 lifecycle / 5.1 lineage / 5.2 delta components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class PublicationPhase(str, Enum):
    PREPARED = "prepared"
    TARGET_PUBLISHED = "target_published"
    LIFECYCLE_PUBLISHED = "lifecycle_published"
    FINALIZED = "finalized"


class PublicationStatus(str, Enum):
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_REJECTED = "approval_rejected"
    PACKAGE_REVIEW_REQUIRED = "package_review_required"
    TARGET_PENDING = "target_pending"
    LIFECYCLE_PENDING = "lifecycle_pending"
    CONFLICT = "conflict"
    FAILED = "failed"
    FINALIZED = "finalized"


@dataclass
class RevisionApproval:
    """Explicit auditable manual approval (CG-021)."""

    approval_id: str
    package_id: str
    scope_hash: str
    decision: ApprovalDecision
    approver: str
    rationale: str = ""
    trace_id: str = ""
    provenance_id: str = ""


@dataclass
class RevisionPublicationRecord:
    """Append-only publication journal record."""

    publication_id: str
    package_id: str
    request_material_hash: str
    phase: PublicationPhase = PublicationPhase.PREPARED
    target_commit_id: Optional[str] = None
    target_version_id: Optional[str] = None
    target_snapshot_id: Optional[str] = None
    lifecycle_id: Optional[str] = None
    final_version_id: Optional[str] = None
    final_snapshot_id: Optional[str] = None
    approval_id: Optional[str] = None
    last_error: Optional[str] = None
    trace_id: str = ""
    provenance_id: str = ""

    def identity_key(self) -> str:
        return self.publication_id


@dataclass
class RevisionPublicationResult:
    """Outcome of one publication attempt."""

    status: PublicationStatus
    publication_id: str = ""
    target_version_id: Optional[str] = None
    target_snapshot_id: Optional[str] = None
    final_version_id: Optional[str] = None
    final_snapshot_id: Optional[str] = None
    lifecycle_id: Optional[str] = None
    idempotent: bool = False
    resumed: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)
    last_error: Optional[str] = None
