"""Internal temporary source-version identity models (Phase 5.1).

temporary compatibility model — not the frozen cross-team public schema (CG-019).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SourceKind(str, Enum):
    PREPRINT = "preprint"
    JOURNAL = "journal"
    CONFERENCE = "conference"
    STANDARD = "standard"
    PATENT = "patent"
    OTHER = "other"


class IntakeDisposition(str, Enum):
    EXACT_REPLAY = "exact_replay"
    SAME_WORK_NEW_VERSION = "same_work_new_version"
    NEW_WORK = "new_work"
    REVIEW_REQUIRED = "review_required"
    IDENTITY_CONFLICT = "identity_conflict"


class VersionRelation(str, Enum):
    REVISION_OF = "revision_of"
    PREPRINT_TO_JOURNAL = "preprint_to_journal"
    CORRECTED_VERSION = "corrected_version"
    EXPLICIT_SAME_WORK = "explicit_same_work"
    NONE = "none"


@dataclass
class SourceCandidate:
    """Already-discovered source candidate from upstream (not crawled here)."""

    ref_id: str
    source_fingerprint: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    source: str = ""
    doi: Optional[str] = None
    stable_id: Optional[str] = None
    source_kind: SourceKind = SourceKind.OTHER
    explicit_work_id: Optional[str] = None
    explicit_prior_version_id: Optional[str] = None
    explicit_relation: Optional[VersionRelation] = None
    trace_id: str = ""
    provenance_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkRecord:
    """Append-only work-family record."""

    work_id: str
    created_evidence: str = ""
    created_seq: int = 0
    trace_id: str = ""
    provenance_id: str = ""


@dataclass
class SourceVersionRecord:
    """Append-only source version record within a work family."""

    source_version_id: str
    work_id: str
    ref_id: str
    source_fingerprint: str
    normalized_doi: Optional[str] = None
    normalized_title: Optional[str] = None
    stable_id: Optional[str] = None
    source_kind: SourceKind = SourceKind.OTHER
    relation: VersionRelation = VersionRelation.NONE
    prior_source_version_id: Optional[str] = None
    kb_version_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    raw_title: str = ""
    raw_doi: Optional[str] = None
    trace_id: str = ""
    provenance_id: str = ""
    created_seq: int = 0

    def identity_key(self) -> str:
        return self.source_version_id


@dataclass
class VersionUpgradeIntent:
    """Structured follow-up for Phase 5.2 (not executed in 5.1)."""

    work_id: str
    prior_source_version_id: str
    new_source_version_id: str
    relation: VersionRelation
    base_kb_version_id: Optional[str] = None
    requires_delta_extraction: bool = True
    lifecycle_reason: str = "preprint_to_journal"


@dataclass
class IntakeDecision:
    """Deterministic classification result for one source candidate."""

    disposition: IntakeDisposition
    work_id: Optional[str] = None
    existing_source_version_id: Optional[str] = None
    prepared_source_version_id: Optional[str] = None
    match_evidence: list[str] = field(default_factory=list)
    ambiguity_candidates: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    proceed_to_commit: bool = False
    upgrade_intent: Optional[VersionUpgradeIntent] = None
    trace_id: str = ""
    provenance_id: str = ""


def source_version_material_equal(
    a: "SourceVersionRecord", b: "SourceVersionRecord"
) -> bool:
    """Material identity for idempotent replay. Ignores created_seq and binding fields."""
    return (
        a.source_version_id == b.source_version_id
        and a.work_id == b.work_id
        and a.ref_id == b.ref_id
        and a.source_fingerprint == b.source_fingerprint
        and a.normalized_doi == b.normalized_doi
        and a.normalized_title == b.normalized_title
        and a.stable_id == b.stable_id
        and a.source_kind == b.source_kind
        and a.relation == b.relation
        and a.prior_source_version_id == b.prior_source_version_id
        and a.raw_title == b.raw_title
        and a.raw_doi == b.raw_doi
        and a.trace_id == b.trace_id
        and a.provenance_id == b.provenance_id
    )
