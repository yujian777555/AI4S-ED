"""Confidence gate / evidence guard (docs/03 §6). Deterministic policy, no prose."""

from __future__ import annotations

from dataclasses import dataclass, field

from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.evidence import (
    Claim,
    ClaimPolicy,
    EvidenceAnchor,
    SurfacePolicy,
)


def classify_claim_policy(
    claim: Claim,
    *,
    numeric_source_ranges: list[tuple[float, float]] | None = None,
) -> ClaimPolicy:
    """Classify how a claim may be surfaced based on its anchors.

    Policy:
      verified/high -> FACTUAL_ALLOWED
      medium        -> CAVEATED_ONLY
      hypothesis    -> PENDING_HYPOTHESIS_ONLY
      no anchors    -> ABSTAIN (handled by H1/Abstain separately)
      unresolved numeric conflict -> CONFLICT_DISCLOSURE_REQUIRED
    """
    if not claim.anchors:
        return ClaimPolicy(
            claim_id=claim.claim_id,
            policy=SurfacePolicy.ABSTAIN,
            effective_confidence=None,
            reasons=["no evidence anchors"],
        )

    # Numeric conflict check from L2/graph source ranges
    if numeric_source_ranges and len(numeric_source_ranges) >= 2:
        if _ranges_disjoint(numeric_source_ranges):
            return ClaimPolicy(
                claim_id=claim.claim_id,
                policy=SurfacePolicy.CONFLICT_DISCLOSURE_REQUIRED,
                effective_confidence=_min_confidence(claim.anchors),
                reasons=["unresolved numeric conflict: disjoint source ranges"],
            )

    # Do not elevate confidence; use the weakest anchor
    eff = _min_confidence(claim.anchors)
    if eff in (Confidence.VERIFIED, Confidence.HIGH):
        return ClaimPolicy(
            claim_id=claim.claim_id,
            policy=SurfacePolicy.FACTUAL_ALLOWED,
            effective_confidence=eff,
            reasons=[f"effective confidence {eff.value}"],
        )
    if eff == Confidence.MEDIUM:
        return ClaimPolicy(
            claim_id=claim.claim_id,
            policy=SurfacePolicy.CAVEATED_ONLY,
            effective_confidence=eff,
            reasons=["medium = single-source/unverified; must caveat"],
        )
    return ClaimPolicy(
        claim_id=claim.claim_id,
        policy=SurfacePolicy.PENDING_HYPOTHESIS_ONLY,
        effective_confidence=eff,
        reasons=["hypothesis = pending only; not factual"],
    )


def _min_confidence(anchors: list[EvidenceAnchor]) -> Confidence:
    order = {
        Confidence.HYPOTHESIS: 0,
        Confidence.MEDIUM: 1,
        Confidence.HIGH: 2,
        Confidence.VERIFIED: 3,
    }
    return min((a.confidence for a in anchors), key=lambda c: order[c])


def _ranges_disjoint(ranges: list[tuple[float, float]]) -> bool:
    """True when any two intervals are completely non-overlapping."""
    sorted_r = sorted(ranges)
    for i in range(len(sorted_r) - 1):
        _, hi1 = sorted_r[i]
        lo2, _ = sorted_r[i + 1]
        if hi1 < lo2:
            return True
    return False
