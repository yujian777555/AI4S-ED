"""Quality scoring tests (docs/03 §5.3)."""

from __future__ import annotations

from knowledge_curator.core.completeness import check_completeness
from knowledge_curator.core.quality import evaluate_quality
from knowledge_curator.schemas.assertions import QualityGrade
from knowledge_curator.schemas.curation import ConflictFinding, ConflictType
from knowledge_curator.tests.conftest import make_assertion, make_assertion_set, make_meta


def test_quality_formula_components_present():
    aset = make_assertion_set(quality_grade=QualityGrade.A)
    completeness = check_completeness(aset)
    q = evaluate_quality(aset, completeness, [])
    assert 0.0 <= q.total <= 1.0
    assert q.p_parse == 1.0
    assert q.s_schema == 1.0
    assert q.penalty == 1.0


def test_grade_b_deducts_20_percent_parse_score():
    aset_a = make_assertion_set(quality_grade=QualityGrade.A)
    aset_b = make_assertion_set(quality_grade=QualityGrade.B)
    qa = evaluate_quality(aset_a, check_completeness(aset_a), [])
    qb = evaluate_quality(aset_b, check_completeness(aset_b), [])
    assert qb.p_parse == 0.8
    assert abs(qa.p_parse - qb.p_parse - 0.2) < 1e-9


def test_penalty_deducts_on_conflict_hang():
    aset = make_assertion_set()
    completeness = check_completeness(aset)
    conflicts = [
        ConflictFinding(
            conflict_type=ConflictType.NUMERIC_CONFLICT,
            new_assertion_id="AS-001",
            message="disjoint",
        )
    ]
    q = evaluate_quality(aset, completeness, conflicts)
    assert q.penalty < 1.0
    assert q.total < evaluate_quality(aset, completeness, []).total


def test_penalty_deducts_on_mechanism_and_chart_low():
    from knowledge_curator.schemas.assertions import ChartObjectInfo

    aset = make_assertion_set(
        charts=[ChartObjectInfo(id="C1", quality_low=True)],
    )
    completeness = check_completeness(aset)
    conflicts = [
        ConflictFinding(
            conflict_type=ConflictType.MECHANISM_VIOLATION,
            new_assertion_id="AS-001",
            message="violation",
        )
    ]
    q = evaluate_quality(aset, completeness, conflicts)
    assert q.penalty <= 1.0 - 0.3 - 0.2 + 1e-9


def test_n_novelty_higher_when_no_duplicates():
    aset = make_assertion_set()
    completeness = check_completeness(aset)
    q_new = evaluate_quality(aset, completeness, [])
    dup = [
        ConflictFinding(
            conflict_type=ConflictType.CONSISTENT,
            new_assertion_id="AS-001",
            message="dup",
        )
    ]
    q_dup = evaluate_quality(aset, completeness, dup)
    assert q_new.n_novelty >= q_dup.n_novelty


def test_schema_rate_used_when_tracked():
    aset = make_assertion_set(schema_valid_count=1, schema_total_count=2)
    completeness = check_completeness(aset)
    q = evaluate_quality(aset, completeness, [])
    assert abs(q.s_schema - 0.5) < 1e-9


def test_evidence_score_uses_locator_and_primary_ratio():
    from knowledge_curator.schemas.assertions import SourceClaimOrigin

    a1 = make_assertion("AS-1", locator="p1", origin=SourceClaimOrigin.PRIMARY)
    a2 = make_assertion("AS-2", locator="p2", origin=SourceClaimOrigin.PRIMARY)
    a2.provenance = None
    a2.source_claim_origin = SourceClaimOrigin.SECONDARY
    aset = make_assertion_set([a1, a2])
    completeness = check_completeness(aset)
    q = evaluate_quality(aset, completeness, [])
    # locator rate 0.5, primary rate 0.5 -> E = 0.5
    assert abs(q.e_evidence - 0.5) < 1e-9
