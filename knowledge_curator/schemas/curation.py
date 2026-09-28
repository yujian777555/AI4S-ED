"""Curation result temporary compatibility models.

temporary compatibility model
CurationReport is not the frozen cross-team public schema yet (CG-002).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from knowledge_curator.schemas.assertions import Confidence


class CurationAction(str, Enum):
    """Internal curation actions. These are actions, NOT confidence levels."""

    ACCEPT = "accept"
    DOWNGRADE = "downgrade"
    PENDING_REVIEW = "pending_review"
    SUPERSEDE = "supersede"
    REJECT = "reject"
    RETURN_UPSTREAM = "return_upstream"


class ConflictType(str, Enum):
    """Conflict detection outcomes from docs/03 §5.2."""

    CONSISTENT = "consistent"
    CONDITION_DIFFERENCE = "condition_difference"
    NUMERIC_CONFLICT = "numeric_conflict"
    RELATION_CONFLICT = "relation_conflict"
    MECHANISM_VIOLATION = "mechanism_violation"
    NONE = "none"


class CompletenessStatus(str, Enum):
    OK = "ok"
    METADATA_INCOMPLETE = "metadata_incomplete"
    NO_ASSERTIONS = "no_assertions"
    EXPLICIT_NO_DATA = "explicit_no_data"
    MISSING_UNITS = "missing_units"
    MISSING_LOCATORS = "missing_locators"
    CHART_QUALITY_LOW = "chart_quality_low"
    PARSED_DOC_NOT_FORMAL = "parsed_doc_not_formal"
    MANUAL_REVIEW = "manual_review"


@dataclass
class CompletenessIssue:
    """One completeness finding."""

    code: str
    message: str
    assertion_ids: list[str] = field(default_factory=list)


@dataclass
class CompletenessResult:
    """Outcome of docs/03 §5.1 completeness check."""

    status: CompletenessStatus
    issues: list[CompletenessIssue] = field(default_factory=list)
    metadata_valid: bool = True
    assertion_count: int = 0
    allows_formal_curation: bool = True
    requires_manual_review: bool = False
    requires_return_upstream: bool = False

    @property
    def ok(self) -> bool:
        return self.status == CompletenessStatus.OK and not self.issues


@dataclass
class ConflictFinding:
    """One conflict comparison result against the knowledge graph."""

    conflict_type: ConflictType
    new_assertion_id: str
    existing_assertion_id: Optional[str] = None
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityBreakdown:
    """Per-component quality score from docs/03 §5.3."""

    p_parse: float
    s_schema: float
    e_evidence: float
    n_novelty: float
    penalty: float
    total: float


@dataclass
class AssertionDecision:
    """Decision for a single assertion."""

    assertion_id: str
    action: CurationAction
    confidence: Confidence
    reason: str
    conflict_type: ConflictType = ConflictType.NONE
    warnings: list[str] = field(default_factory=list)


@dataclass
class CurationReport:
    """Full curation outcome for one AssertionSet.

    temporary compatibility model — not the frozen public schema.
    """

    report_id: str
    source_ref_id: str
    status: str
    completeness: CompletenessResult
    conflicts: list[ConflictFinding] = field(default_factory=list)
    decisions: list[AssertionDecision] = field(default_factory=list)
    quality: Optional[QualityBreakdown] = None
    accepted_count: int = 0
    downgraded_count: int = 0
    rejected_count: int = 0
    pending_count: int = 0
    superseded_count: int = 0
    returned_upstream_count: int = 0
    warnings: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)
    # Reserved for Phase 2+ atomic commit / KB version snapshot. Do not fabricate.
    commit_id: Optional[str] = None
    kb_version: Optional[str] = None
    snapshot_id: Optional[str] = None
