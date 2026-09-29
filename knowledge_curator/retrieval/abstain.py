"""Abstain decision logic (docs/03 §6.3). Deterministic, no LLM."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from knowledge_curator.schemas.evidence import Claim, EvidenceAnchor


class AbstainReason(str, Enum):
    LOW_RETRIEVAL_SUPPORT = "low_retrieval_support"
    SUBQUESTION_NOT_COVERED = "subquestion_not_covered"
    CRITICAL_NUMERIC_ONLY_HYPOTHESIS_OR_PENDING = (
        "critical_numeric_only_hypothesis_or_pending"
    )
    UNSUPPORTED_INFERENCE_NO_MECHANISM = "unsupported_inference_no_mechanism"
    PRIVATE_DATA_UNAUTHORIZED = "private_data_unauthorized"


@dataclass
class MissingEvidence:
    """Structured missing-evidence item."""

    kind: str
    detail: str = ""
    coverage_key: Optional[str] = None


@dataclass
class AbstainDecision:
    """Structured Abstain decision for one claim/subquestion."""

    abstain: bool
    reasons: list[AbstainReason] = field(default_factory=list)
    missing_evidence: list[MissingEvidence] = field(default_factory=list)
    recommended_gap_kinds: list[str] = field(default_factory=list)


@dataclass
class AbstainConfig:
    """Configuration-driven thresholds (temporary until 07/05 freeze)."""

    min_retrieval_support: float = 0.3
    require_coverage: bool = True


def evaluate_abstain(
    claim: Claim,
    *,
    retrieval_support: float = 1.0,
    covered_keys: Optional[set[str]] = None,
    required_keys: Optional[set[str]] = None,
    is_critical_numeric: bool = False,
    mechanism_supported: bool = True,
    private_data_unauthorized: bool = False,
    config: Optional[AbstainConfig] = None,
) -> AbstainDecision:
    """Evaluate §6.3 Abstain conditions deterministically."""
    cfg = config or AbstainConfig()
    reasons: list[AbstainReason] = []
    missing: list[MissingEvidence] = []
    gaps: list[str] = []

    if private_data_unauthorized:
        reasons.append(AbstainReason.PRIVATE_DATA_UNAUTHORIZED)
        missing.append(MissingEvidence(kind="authorization", detail="private data unauthorized"))

    if retrieval_support < cfg.min_retrieval_support:
        reasons.append(AbstainReason.LOW_RETRIEVAL_SUPPORT)
        missing.append(MissingEvidence(kind="retrieval_support", detail=f"support={retrieval_support:.3f}"))
        gaps.append("evidence")

    if cfg.require_coverage and required_keys:
        covered = covered_keys or set()
        uncovered = required_keys - covered
        if uncovered:
            reasons.append(AbstainReason.SUBQUESTION_NOT_COVERED)
            for key in sorted(uncovered):
                missing.append(MissingEvidence(kind="coverage", coverage_key=key))
            gaps.append("coverage")

    if is_critical_numeric:
        # Critical numeric with only hypothesis/pending evidence (or no anchors)
        from knowledge_curator.schemas.assertions import Confidence

        has_non_hypo = any(a.confidence != Confidence.HYPOTHESIS for a in claim.anchors)
        if not has_non_hypo:
            reasons.append(AbstainReason.CRITICAL_NUMERIC_ONLY_HYPOTHESIS_OR_PENDING)
            missing.append(MissingEvidence(kind="numeric_evidence", detail="critical numeric lacks verified evidence"))
            gaps.append("numeric_evidence")

    if not mechanism_supported:
        reasons.append(AbstainReason.UNSUPPORTED_INFERENCE_NO_MECHANISM)
        missing.append(MissingEvidence(kind="mechanism", detail="no mechanism support"))
        gaps.append("mechanism")

    return AbstainDecision(
        abstain=bool(reasons),
        reasons=reasons,
        missing_evidence=missing,
        recommended_gap_kinds=gaps,
    )
