"""Curation decision rules (docs/03 §5 routing + latest_plan actions).

Phase 1.1 confidence gate (planner/phase-01-review.md P1-01/P1-02):
  * clean single-source primary -> at most medium
  * secondary source -> at most medium
  * high requires compatible multi-source evidence (non-self ref_id) + primary + no conflict
  * verified is never auto-granted
"""

from __future__ import annotations

from knowledge_curator.config import CuratorConfig, DEFAULT_CONFIG
from knowledge_curator.schemas.assertions import Assertion, Confidence, SourceClaimOrigin
from knowledge_curator.schemas.curation import (
    AssertionDecision,
    CompletenessResult,
    CompletenessStatus,
    ConflictFinding,
    ConflictType,
    CurationAction,
    QualityBreakdown,
)


def decide_assertion(
    assertion: Assertion,
    completeness: CompletenessResult,
    conflicts_for: list[ConflictFinding],
    quality: QualityBreakdown | None,
    config: CuratorConfig | None = None,
) -> AssertionDecision:
    """Decide the curation action for one assertion.

    Decision order is deterministic:
      1. document-level gates (return_upstream / exclude / manual)
      2. mechanism violation -> reject
      3. numeric/relation conflict -> pending_review
      4. missing unit / locator / speculative wording -> downgrade to hypothesis
      5. consistent multi-source / condition_difference -> accept (confidence gated)
      6. clean single-source -> accept at most medium

    Args:
        assertion: The assertion under review.
        completeness: Document-level completeness result.
        conflicts_for: Conflict findings involving this assertion.
        quality: Document quality breakdown (may be None).
        config: Curator configuration.

    Returns:
        AssertionDecision with action, confidence and reason.
    """
    cfg = config or DEFAULT_CONFIG
    warnings: list[str] = []

    # Document-level gate: metadata incomplete -> return_upstream
    if completeness.requires_return_upstream:
        return AssertionDecision(
            assertion_id=assertion.id,
            action=CurationAction.RETURN_UPSTREAM,
            confidence=Confidence.HYPOTHESIS,
            reason="document metadata incomplete (DOI and stable_id missing or other fields)",
            warnings=["return to lit_researcher for metadata repair"],
        )

    if completeness.status == CompletenessStatus.PARSED_DOC_NOT_FORMAL:
        return AssertionDecision(
            assertion_id=assertion.id,
            action=CurationAction.REJECT,
            confidence=Confidence.HYPOTHESIS,
            reason="ParsedDoc quality grade D/E — must not enter formal knowledge face",
        )

    if completeness.status == CompletenessStatus.EXPLICIT_NO_DATA:
        return AssertionDecision(
            assertion_id=assertion.id,
            action=CurationAction.REJECT,
            confidence=Confidence.HYPOTHESIS,
            reason="explicit no structured data — archive to observation bucket",
        )

    # Conflict-driven decisions first
    if any(f.conflict_type == ConflictType.MECHANISM_VIOLATION for f in conflicts_for):
        return AssertionDecision(
            assertion_id=assertion.id,
            action=CurationAction.REJECT,
            confidence=Confidence.HYPOTHESIS,
            reason="mechanism violation (L3 hard rule)",
            conflict_type=ConflictType.MECHANISM_VIOLATION,
            warnings=["do not enter verified/high face"],
        )

    if any(
        f.conflict_type in (ConflictType.NUMERIC_CONFLICT, ConflictType.RELATION_CONFLICT)
        for f in conflicts_for
    ):
        return AssertionDecision(
            assertion_id=assertion.id,
            action=CurationAction.PENDING_REVIEW,
            confidence=Confidence.HYPOTHESIS,
            reason="unresolved conflict with existing graph assertion — manual review",
            conflict_type=ConflictType.NUMERIC_CONFLICT
            if any(f.conflict_type == ConflictType.NUMERIC_CONFLICT for f in conflicts_for)
            else ConflictType.RELATION_CONFLICT,
            warnings=["must not participate in verified/high reasoning before human verdict"],
        )

    # Completeness / quality downgrade rules -> always hypothesis
    missing_unit = assertion.missing_unit or (
        assertion.is_numeric
        and (assertion.object.unit is None or str(assertion.object.unit).strip() == "")
    )
    if missing_unit:
        return AssertionDecision(
            assertion_id=assertion.id,
            action=CurationAction.DOWNGRADE,
            confidence=Confidence.HYPOTHESIS,
            reason="numeric assertion missing unit — cannot confirm dimension",
            warnings=["missing_unit flag; manual fix or keep hypothesis"],
        )

    if not assertion.has_locator:
        return AssertionDecision(
            assertion_id=assertion.id,
            action=CurationAction.DOWNGRADE,
            confidence=Confidence.HYPOTHESIS,
            reason="provenance locator missing — cannot anchor evidence",
            warnings=["locator missing; downgraded to hypothesis"],
        )

    if assertion.speculative_wording:
        return AssertionDecision(
            assertion_id=assertion.id,
            action=CurationAction.DOWNGRADE,
            confidence=Confidence.HYPOTHESIS,
            reason="speculative wording detected (possible/expected/suspected)",
            warnings=["treat as unverified hypothesis only"],
        )

    # Grade C documents require manual review for formal face
    if completeness.requires_manual_review and completeness.status == CompletenessStatus.MANUAL_REVIEW:
        return AssertionDecision(
            assertion_id=assertion.id,
            action=CurationAction.PENDING_REVIEW,
            confidence=Confidence.MEDIUM,
            reason="ParsedDoc quality grade C — manual review required",
            warnings=["manual review before formal knowledge face"],
        )

    consistent = [f for f in conflicts_for if f.conflict_type == ConflictType.CONSISTENT]
    condition_diff = [
        f for f in conflicts_for if f.conflict_type == ConflictType.CONDITION_DIFFERENCE
    ]
    is_primary = assertion.source_claim_origin == SourceClaimOrigin.PRIMARY

    # Multi-source consistent support (non-self ref_id is the Phase 1 independence proxy).
    if consistent:
        # P1-02: secondary evidence cannot reach high even when consistent.
        if not is_primary:
            return AssertionDecision(
                assertion_id=assertion.id,
                action=CurationAction.ACCEPT,
                confidence=Confidence.MEDIUM,
                reason="consistent with existing assertions but secondary origin (not high)",
                conflict_type=ConflictType.CONSISTENT,
                warnings=[
                    "secondary origin — at most medium until primary back-trace",
                    "source-family independence unavailable; non-self ref_id used as proxy",
                ],
            )
        # primary + independent existing evidence + no blocking conflict -> high
        return AssertionDecision(
            assertion_id=assertion.id,
            action=CurationAction.ACCEPT,
            confidence=Confidence.HIGH,
            reason="primary assertion consistent with independent existing evidence",
            conflict_type=ConflictType.CONSISTENT,
            warnings=[
                "high via multi-source consistency (non-self ref_id independence proxy)",
            ],
        )

    if condition_diff:
        # Condition difference is not support for the same conditional claim.
        return AssertionDecision(
            assertion_id=assertion.id,
            action=CurationAction.ACCEPT,
            confidence=_cap_single_source(assertion, is_primary, warnings),
            reason="condition_difference — conditional assertion, not a conflict",
            conflict_type=ConflictType.CONDITION_DIFFERENCE,
            warnings=warnings,
        )

    # Clean single-source acceptance — P1-01 confidence gate.
    confidence = _cap_single_source(assertion, is_primary, warnings)
    return AssertionDecision(
        assertion_id=assertion.id,
        action=CurationAction.ACCEPT,
        confidence=confidence,
        reason="completeness OK and no blocking conflict (single-source cap applied)",
        warnings=warnings,
    )


def _cap_single_source(
    assertion: Assertion,
    is_primary: bool,
    warnings: list[str],
) -> Confidence:
    """Apply Phase 1.1 single-source confidence caps.

    Semantics (03 §5.3 / latest_plan §A):
      * secondary -> at most medium
      * single-source primary -> at most medium
      * high requires multi-source consistency (handled in consistent branch)
      * verified is never auto-granted (no frozen trusted signal in Phase 1 model)
    """
    if assertion.confidence == Confidence.VERIFIED:
        warnings.append(
            "verified is not auto-granted; no frozen trusted human/experimental signal"
        )
    if not is_primary:
        warnings.append("secondary origin — at most medium until primary back-trace")
        return Confidence.MEDIUM
    warnings.append("single-source primary — at most medium (high needs multi-source)")
    return Confidence.MEDIUM


def _clamp_confidence(value: Confidence) -> Confidence:
    """Keep confidence inside the unified four-level ladder."""
    allowed = {
        Confidence.VERIFIED,
        Confidence.HIGH,
        Confidence.MEDIUM,
        Confidence.HYPOTHESIS,
    }
    return value if value in allowed else Confidence.MEDIUM
