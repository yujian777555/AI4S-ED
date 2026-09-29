"""Retrieval package: §6 deterministic evidence guard foundation."""

from knowledge_curator.retrieval.abstain import (
    AbstainConfig,
    AbstainDecision,
    AbstainReason,
    MissingEvidence,
    evaluate_abstain,
)
from knowledge_curator.retrieval.evidence_guard import classify_claim_policy
from knowledge_curator.retrieval.hallucination import (
    H3Result,
    H3Status,
    HallucinationFinding,
    HallucinationType,
    LocatorCheckStatus,
    detect_h1,
    detect_h2,
    detect_h3,
    normalize_doi,
    normalize_title,
)

__all__ = [
    "AbstainConfig",
    "AbstainDecision",
    "AbstainReason",
    "H3Result",
    "H3Status",
    "HallucinationFinding",
    "HallucinationType",
    "LocatorCheckStatus",
    "MissingEvidence",
    "classify_claim_policy",
    "detect_h1",
    "detect_h2",
    "detect_h3",
    "evaluate_abstain",
    "normalize_doi",
    "normalize_title",
]
