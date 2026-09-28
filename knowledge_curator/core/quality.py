"""Quality scoring (docs/03 §5.3).

Implements the document formula as-is:

    Q(doc) = w1*P_parse
           + w2*S_schema
           + w3*E_evidence
           + w4*N_novelty
           + w5*penalty

Defaults: w ≈ 0.25 / 0.25 / 0.30 / 0.10 / 0.10.
Do not "optimize" the requirement here; formula concerns go to CONTRACT_GAPS.
"""

from __future__ import annotations

from knowledge_curator.config import CuratorConfig, DEFAULT_CONFIG, QualityConfig
from knowledge_curator.schemas.assertions import AssertionSet, QualityGrade, SourceClaimOrigin
from knowledge_curator.schemas.curation import CompletenessResult, ConflictFinding, ConflictType, QualityBreakdown


def evaluate_quality(
    assertion_set: AssertionSet,
    completeness: CompletenessResult,
    conflicts: list[ConflictFinding],
    config: QualityConfig | None = None,
) -> QualityBreakdown:
    """Compute the §5.3 document quality score.

    Component definitions used for Phase 1:
      * P_parse: A=1.0, B=0.8 (B deducts 20%), C=0.4, D/E=0.0
      * S_schema: first-pass schema validation rate (default 1.0 if not tracked)
      * E_evidence: mean of locator completeness rate and primary-source ratio
      * N_novelty: 1 - duplication ratio against existing graph hits (consistent)
      * penalty: starts at 1.0; deducts for conflict-hang / mechanism / chart-low

    Args:
        assertion_set: Document extraction package.
        completeness: Completeness result for this document.
        conflicts: Conflict findings from §5.2.
        config: Quality scoring configuration.

    Returns:
        QualityBreakdown with per-component scores and weighted total in [0, 1].
    """
    cfg = config or DEFAULT_CONFIG.quality

    p_parse = _p_parse(assertion_set.quality_grade, cfg)
    s_schema = _s_schema(assertion_set)
    e_evidence = _e_evidence(assertion_set)
    n_novelty = _n_novelty(assertion_set, conflicts)
    penalty = _penalty(conflicts, assertion_set, cfg)

    w = cfg.weights
    total = (
        w.w1_p_parse * p_parse
        + w.w2_s_schema * s_schema
        + w.w3_e_evidence * e_evidence
        + w.w4_n_novelty * n_novelty
        + w.w5_penalty * penalty
    )
    # Keep Q in [0, 1] even if weights are misconfigured.
    total = max(0.0, min(1.0, total))

    return QualityBreakdown(
        p_parse=p_parse,
        s_schema=s_schema,
        e_evidence=e_evidence,
        n_novelty=n_novelty,
        penalty=penalty,
        total=total,
    )


def _p_parse(grade: QualityGrade, cfg: QualityConfig) -> float:
    if grade == QualityGrade.A:
        return cfg.p_parse_a
    if grade == QualityGrade.B:
        return cfg.p_parse_b
    if grade == QualityGrade.C:
        return cfg.p_parse_c
    return cfg.p_parse_d_e


def _s_schema(assertion_set: AssertionSet) -> float:
    total = assertion_set.schema_total_count
    valid = assertion_set.schema_valid_count
    if total is None or valid is None or total <= 0:
        # Not tracked upstream: treat as pass-through score of 1.0 for Phase 1.
        return 1.0
    return max(0.0, min(1.0, valid / total))


def _e_evidence(assertion_set: AssertionSet) -> float:
    assertions = assertion_set.assertions
    if not assertions:
        return 0.0
    locator_rate = sum(1 for a in assertions if a.has_locator) / len(assertions)
    primary_rate = sum(
        1 for a in assertions if a.source_claim_origin == SourceClaimOrigin.PRIMARY
    ) / len(assertions)
    return (locator_rate + primary_rate) / 2.0


def _n_novelty(assertion_set: AssertionSet, conflicts: list[ConflictFinding]) -> float:
    """Higher is better: less duplication against the existing graph.

    Duplication proxy for Phase 1 = fraction of assertions marked consistent
    with an existing graph assertion.
    """
    n = len(assertion_set.assertions)
    if n == 0:
        return 1.0
    consistent_ids = {
        f.new_assertion_id
        for f in conflicts
        if f.conflict_type == ConflictType.CONSISTENT
    }
    duplication = len(consistent_ids) / n
    return max(0.0, min(1.0, 1.0 - duplication))


def _penalty(
    conflicts: list[ConflictFinding],
    assertion_set: AssertionSet,
    cfg: QualityConfig,
) -> float:
    score = cfg.penalty_start
    hang_types = {
        ConflictType.NUMERIC_CONFLICT,
        ConflictType.RELATION_CONFLICT,
    }
    if any(f.conflict_type in hang_types for f in conflicts):
        score -= cfg.penalty_conflict_hang
    if any(f.conflict_type == ConflictType.MECHANISM_VIOLATION for f in conflicts):
        score -= cfg.penalty_mechanism_review
    if any(c.quality_low or c.not_digitizable for c in assertion_set.charts):
        score -= cfg.penalty_chart_low
    return max(0.0, score)
