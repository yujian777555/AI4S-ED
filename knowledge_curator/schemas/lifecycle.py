"""Internal temporary lifecycle models for docs/03 §7 (Phase 5.0).

temporary compatibility model
Not the frozen cross-team public schema. Do not extend Confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class DocumentLifecycleStatus(str, Enum):
    ACTIVE = "active"
    RETRACTED = "retracted"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class AssertionLifecycleStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


class LifecycleReason(str, Enum):
    RETRACTION = "retraction"
    CORRIGENDUM = "corrigendum"
    MANUAL_CORRECTION = "manual_correction"
    CONFLICT_RESOLUTION = "conflict_resolution"
    CASE_FEEDBACK = "case_feedback"
    STRONGER_EVIDENCE = "stronger_evidence"
    PREPRINT_TO_JOURNAL = "preprint_to_journal"
    ROLLBACK = "rollback"
    RESTORE = "restore"


class RiskDecision(str, Enum):
    AUTO_RULE_REVIEW_ELIGIBLE = "auto_rule_review_eligible"
    MANUAL_ADJUDICATION_REQUIRED = "manual_adjudication_required"


class LifecycleEventType(str, Enum):
    KB_DOCUMENT_RETRACTED = "kb_document_retracted"
    KB_ASSERTIONS_ARCHIVED = "kb_assertions_archived"
    KB_ASSERTIONS_SUPERSEDED = "kb_assertions_superseded"
    KB_REVISION_PUBLISHED = "kb_revision_published"
    KB_VERSION_ROLLED_BACK = "kb_version_rolled_back"
    KB_CORRIGENDUM_PUBLISHED = "kb_corrigendum_published"


@dataclass
class DocumentLifecycleRecord:
    """Append-only document lifecycle event record."""

    lifecycle_id: str
    ref_id: str
    status: DocumentLifecycleStatus
    reason: LifecycleReason
    effective_version_id: Optional[str] = None
    prior_lifecycle_id: Optional[str] = None
    source_fingerprint: Optional[str] = None
    affected_assertion_ids: list[str] = field(default_factory=list)
    rationale: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    trace_id: str = ""
    provenance_id: str = ""
    created_seq: int = 0
    revision_id: Optional[str] = None

    def identity_key(self) -> str:
        return self.lifecycle_id


@dataclass
class AssertionLifecycleRecord:
    """Append-only assertion lifecycle event record."""

    assertion_id: str
    ref_id: str
    status: AssertionLifecycleStatus
    lifecycle_id: str
    revision_id: Optional[str] = None
    superseded_by_assertion_id: Optional[str] = None
    effective_version_id: Optional[str] = None
    created_seq: int = 0

    def identity_key(self) -> str:
        return f"{self.lifecycle_id}:{self.assertion_id}"


@dataclass
class RevisionDraft:
    """Curator §7.3 draft before publication."""

    revision_id: str
    ref_id: str
    trigger: LifecycleReason
    base_version_id: Optional[str]
    affected_assertion_ids: list[str] = field(default_factory=list)
    archive_actions: list[str] = field(default_factory=list)
    supersede_actions: dict[str, str] = field(default_factory=dict)  # old_id -> new_id
    replacement_assertion_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    rationale: str = ""
    manual_adjudication_required: bool = False
    risk_decision: RiskDecision = RiskDecision.MANUAL_ADJUDICATION_REQUIRED
    trace_id: str = ""
    provenance_id: str = ""
    verified_external_trigger: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LifecycleEvent:
    """Internal append-only outbox event (CG-018)."""

    event_id: str
    event_type: LifecycleEventType
    ref_id: str
    affected_assertion_ids: list[str] = field(default_factory=list)
    old_version_id: Optional[str] = None
    new_version_id: Optional[str] = None
    lifecycle_id: Optional[str] = None
    revision_id: Optional[str] = None
    trace_id: str = ""
    provenance_id: str = ""
    payload_schema_version: str = "1"
    payload: dict[str, Any] = field(default_factory=dict)
    created_seq: int = 0
    delivered: bool = False


@dataclass
class LifecycleEligibility:
    """Visibility / eligibility answer for a document or assertion."""

    visible_for_retrieval: bool
    eligible_for_training: bool
    status: str
    reason: str = ""
    at_version_id: Optional[str] = None
