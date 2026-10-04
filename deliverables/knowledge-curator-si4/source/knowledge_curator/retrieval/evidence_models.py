"""INTERNAL temporary evidence-retrieval models (Phase 4.3).

Not the frozen cross-team public schema. Composition of
frozen Phase 4.2 retrieval + Phase 4.0 evidence guard.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from knowledge_curator.ports.retrieval import RankedHit, RetrievalChannel
from knowledge_curator.retrieval.abstain import AbstainDecision
from knowledge_curator.retrieval.evidence_guard import ClaimPolicy
from knowledge_curator.retrieval.hallucination import (
    H1CheckResult,
    H3Result,
    HallucinationFinding,
)
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.chunk import ChunkType, KnowledgeChunk
from knowledge_curator.schemas.evidence import (
    Claim,
    EvidenceAnchor,
    EvidenceType,
    SurfacePolicy,
)


class CoverageState(str, Enum):
    COVERED = "covered"
    NOT_COVERED = "not_covered"
    NOT_REQUIRED = "not_required"


@dataclass
class RetrievalEvidenceRecord:
    """Normalized guardable evidence record from one fine hit (fail closed)."""

    chunk_id: str
    ref_id: str
    locator: Optional[str]
    page_or_object_id: Optional[str]
    confidence: Optional[Confidence]
    quality: Optional[float]
    access_pointer: Optional[str]
    sentence_or_cell: Optional[str]
    chunk_type: ChunkType
    provenance: dict[str, Any]
    evidence_type: Optional[EvidenceType]
    channels: list[RetrievalChannel]
    rank: int
    rrf_score: float
    payload_excerpt: str
    # True only when build_evidence_anchor(record) can succeed.
    guardable_as_anchor: bool = False
    # Why this hit cannot authorize a factual claim.
    unguardable_reasons: list[str] = field(default_factory=list)


@dataclass
class UnguardableHit:
    chunk_id: str
    ref_id: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class SubqueryCoverage:
    coverage_key: str
    query_text: str
    state: CoverageState
    guardable_count: int = 0
    hit_count: int = 0


@dataclass
class QueryAbstainResult:
    abstain: bool
    reasons: list[str] = field(default_factory=list)
    missing_evidence: list[dict[str, Any]] = field(default_factory=list)
    recommended_gap_kinds: list[str] = field(default_factory=list)
    retrieval_support_checked: bool = False
    calibrated_support: Optional[float] = None


@dataclass
class EvidenceBundle:
    """INTERNAL temporary evidence bundle for one retrieval request."""

    bundle_id: str
    original_query: str
    subqueries: list[str]
    coverage_keys: list[str]
    top_k: int
    allowed_ref_ids: Optional[list[str]]
    ranked_hits: list[RankedHit]
    evidence_records: list[RetrievalEvidenceRecord]
    unguardable_hits: list[UnguardableHit]
    coverage: list[SubqueryCoverage]
    retrieval_diagnostics: list[dict[str, Any]]
    abstain: QueryAbstainResult
    trace: dict[str, Any]
    integration_fixture: bool = False


@dataclass
class ClaimGuardResult:
    """Deterministic guard outcome for one proposed claim."""

    claim_id: str
    claim_text: str
    resolved_anchors: list[EvidenceAnchor]
    unresolved_anchor_chunk_ids: list[str]
    policy: ClaimPolicy
    abstain: AbstainDecision
    h1: H1CheckResult
    h2_findings: list[HallucinationFinding]
    h2_checked: bool
    h2_status: str
    h2_unavailable_reason: Optional[str]
    h3: H3Result
    numeric_conflict_policy: Optional[SurfacePolicy]
    retrieval_support_checked: bool


@dataclass
class ValidateClaimsResult:
    bundle: EvidenceBundle
    claim_results: list[ClaimGuardResult]
    all_policies: list[dict[str, Any]]


def compute_bundle_id(
    query: str,
    subqueries: list[str],
    hit_ids: list[str],
) -> str:
    payload = json.dumps(
        {"q": query, "s": subqueries, "h": hit_ids},
        sort_keys=True,
        ensure_ascii=False,
    )
    return "evb_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def normalize_evidence_type(chunk: KnowledgeChunk, default: Optional[EvidenceType]) -> tuple[Optional[EvidenceType], Optional[str]]:
    """EvidenceType from explicit provenance only. Never infer GRAPH from channel.

    Returns (evidence_type, error_reason). error_reason is
    missing_evidence_type / invalid_evidence_type when type is unusable.
    """
    prov_type = chunk.provenance.get("evidence_type") if chunk.provenance else None
    if prov_type is not None and str(prov_type).strip():
        try:
            return EvidenceType(str(prov_type).strip().lower()), None
        except Exception:
            # Explicit but invalid: do not silently fall back to default/GRAPH.
            return None, "invalid_evidence_type"
    if default is not None:
        return default, None
    return None, "missing_evidence_type"


def evaluate_anchorability(
    *,
    ref_id: str,
    locator: Optional[str],
    confidence: Optional[Confidence],
    evidence_type: Optional[EvidenceType],
    evidence_type_error: Optional[str] = None,
) -> tuple[bool, list[str]]:
    """Single source of truth: can a valid EvidenceAnchor be built?

    Required: non-empty ref_id, non-empty locator, confidence present,
    valid evidence_type present.
    """
    reasons: list[str] = []
    if not ref_id or not str(ref_id).strip():
        reasons.append("missing_ref_id")
    if not locator or not str(locator).strip():
        reasons.append("missing_locator")
    if confidence is None:
        reasons.append("missing_confidence")
    if evidence_type is None:
        reasons.append(evidence_type_error or "missing_evidence_type")
    return (not reasons), reasons


def normalize_hit_to_record(
    hit: RankedHit,
    *,
    default_evidence_type: Optional[EvidenceType] = EvidenceType.LITERATURE,
) -> RetrievalEvidenceRecord:
    """Fail-closed normalization of one fine hit into an evidence record."""
    chunk = hit.chunk

    locator = (chunk.locator or "").strip() or None
    confidence = chunk.confidence

    page_or_object = chunk.page or chunk.object_id or None
    sentence = chunk.section or None
    # Prefer explicit sentence pointer when present in provenance.
    if chunk.provenance:
        sentence = (
            chunk.provenance.get("sentence")
            or chunk.provenance.get("sentence_or_cell")
            or sentence
        )
        page_or_object = (
            chunk.provenance.get("page")
            or chunk.provenance.get("object_id")
            or page_or_object
        )

    evidence_type, et_error = normalize_evidence_type(chunk, default_evidence_type)

    guardable, reasons = evaluate_anchorability(
        ref_id=chunk.ref_id,
        locator=locator,
        confidence=confidence,
        evidence_type=evidence_type,
        evidence_type_error=et_error,
    )

    return RetrievalEvidenceRecord(
        chunk_id=chunk.chunk_id,
        ref_id=chunk.ref_id,
        locator=locator,
        page_or_object_id=page_or_object,
        confidence=confidence,
        quality=chunk.quality,
        access_pointer=chunk.provenance.get("access_pointer") if chunk.provenance else None,
        sentence_or_cell=sentence if isinstance(sentence, str) else None,
        chunk_type=chunk.chunk_type,
        provenance=dict(chunk.provenance or {}),
        evidence_type=evidence_type,
        channels=list(hit.channels),
        rank=hit.rank,
        rrf_score=hit.rrf_score,
        payload_excerpt=(chunk.payload or "")[:240],
        guardable_as_anchor=guardable,
        unguardable_reasons=reasons,
    )


def build_evidence_anchor(record: RetrievalEvidenceRecord) -> Optional[EvidenceAnchor]:
    """Construct EvidenceAnchor only when the record is guardable.

    Invariant: succeeds iff record.guardable_as_anchor is True.
    """
    guardable, _ = evaluate_anchorability(
        ref_id=record.ref_id,
        locator=record.locator,
        confidence=record.confidence,
        evidence_type=record.evidence_type,
    )
    if not guardable or not record.guardable_as_anchor:
        return None
    return EvidenceAnchor(
        evidence_type=record.evidence_type,  # type: ignore[arg-type]
        ref_id=record.ref_id,
        locator=record.locator or "",
        confidence=record.confidence,  # type: ignore[arg-type]
        quality=record.quality,
        access_pointer=record.access_pointer,
    )
