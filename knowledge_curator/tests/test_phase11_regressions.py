"""Phase 1.1 regression tests for Planner review blockers P1-01..P1-04."""

from __future__ import annotations

import asyncio

from knowledge_curator.adapters import (
    FakeMechanismValidator,
    InMemoryKnowledgeRepository,
    SimpleOntologyService,
)
from knowledge_curator.core.completeness import check_completeness
from knowledge_curator.core.conflict import compare_pair, detect_conflicts
from knowledge_curator.config import ConflictConfig
from knowledge_curator.schemas.assertions import (
    ChartObjectInfo,
    Condition,
    Confidence,
    SourceClaimOrigin,
    ValueType,
)
from knowledge_curator.schemas.curation import ConflictType
from knowledge_curator.tests.conftest import (
    make_assertion,
    make_assertion_set,
    make_curator,
)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# P1-01 / P1-02 — confidence gate
# ---------------------------------------------------------------------------

def test_p11_single_primary_upstream_high_caps_to_medium():
    """P1-01: clean single-source primary upstream high -> medium."""
    curator = make_curator()
    aset = make_assertion_set(
        [
            make_assertion(
                "AS-S1",
                confidence=Confidence.HIGH,
                origin=SourceClaimOrigin.PRIMARY,
            )
        ],
    )
    report = _run(curator.curate(aset))
    decision = report.decisions[0]
    assert decision.confidence == Confidence.MEDIUM
    assert decision.confidence != Confidence.HIGH


def test_p11_single_primary_upstream_verified_not_verified_or_high():
    """P1-01: single primary upstream verified -> not verified/high."""
    curator = make_curator()
    aset = make_assertion_set(
        [
            make_assertion(
                "AS-S2",
                confidence=Confidence.VERIFIED,
                origin=SourceClaimOrigin.PRIMARY,
            )
        ],
    )
    report = _run(curator.curate(aset))
    decision = report.decisions[0]
    assert decision.confidence not in (Confidence.VERIFIED, Confidence.HIGH)
    assert decision.confidence == Confidence.MEDIUM


def test_p11_secondary_consistent_existing_not_high():
    """P1-02: secondary + consistent existing -> not high."""
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=1.40,
        uncertainty=0.10,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
        origin=SourceClaimOrigin.PRIMARY,
    )
    new = make_assertion(
        "AS-SEC",
        value=1.42,
        uncertainty=0.10,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
        origin=SourceClaimOrigin.SECONDARY,
        confidence=Confidence.HIGH,
    )
    curator = make_curator(seed=[old])
    report = _run(curator.curate(make_assertion_set([new])))
    decision = report.decisions[0]
    assert decision.conflict_type == ConflictType.CONSISTENT
    assert decision.confidence != Confidence.HIGH
    assert decision.confidence == Confidence.MEDIUM


def test_p11_primary_consistent_independent_existing_high():
    """P1-02/plan §A: primary + compatible independent existing -> high."""
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=1.40,
        uncertainty=0.10,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
        origin=SourceClaimOrigin.PRIMARY,
    )
    new = make_assertion(
        "AS-NEW",
        value=1.42,
        uncertainty=0.10,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
        origin=SourceClaimOrigin.PRIMARY,
    )
    curator = make_curator(seed=[old])
    report = _run(curator.curate(make_assertion_set([new])))
    decision = report.decisions[0]
    assert decision.conflict_type == ConflictType.CONSISTENT
    assert decision.confidence == Confidence.HIGH


def test_p11_single_secondary_clean_caps_to_medium():
    curator = make_curator()
    aset = make_assertion_set(
        [
            make_assertion(
                "AS-SEC2",
                origin=SourceClaimOrigin.SECONDARY,
                confidence=Confidence.HIGH,
            )
        ],
    )
    report = _run(curator.curate(aset))
    decision = report.decisions[0]
    assert decision.confidence == Confidence.MEDIUM


# ---------------------------------------------------------------------------
# P1-03 — condition compatibility before relation/enum contradiction
# ---------------------------------------------------------------------------

def test_p11_enum_opposite_under_different_conditions_is_condition_difference():
    """P1-03: ENUM yes under cond A, ENUM no under cond B -> condition_difference."""
    cond_a = [Condition(eddo_class="Temperature", value=298.15, unit="K")]
    cond_b = [Condition(eddo_class="Temperature", value=333.15, unit="K")]
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value="yes",
        unit=None,
        value_type=ValueType.ENUM,
        uncertainty=None,
        conditions=cond_a,
    )
    new = make_assertion(
        "AS-NEW",
        value="no",
        unit=None,
        value_type=ValueType.ENUM,
        uncertainty=None,
        conditions=cond_b,
    )
    finding = compare_pair(
        new,
        old,
        SimpleOntologyService(),
        ConflictConfig(),
    )
    assert finding is not None
    assert finding.conflict_type == ConflictType.CONDITION_DIFFERENCE
    assert finding.conflict_type != ConflictType.RELATION_CONFLICT


def test_p11_enum_opposite_same_conditions_is_relation_conflict():
    """P1-03: same conditions + opposite enum -> relation_conflict."""
    cond = [
        Condition(eddo_class="Temperature", value=298.15, unit="K"),
        Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
    ]
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value="yes",
        unit=None,
        value_type=ValueType.ENUM,
        uncertainty=None,
        conditions=cond,
    )
    new = make_assertion(
        "AS-NEW",
        value="no",
        unit=None,
        value_type=ValueType.ENUM,
        uncertainty=None,
        conditions=cond,
    )
    finding = compare_pair(new, old, SimpleOntologyService(), ConflictConfig())
    assert finding is not None
    assert finding.conflict_type == ConflictType.RELATION_CONFLICT


def test_p11_enum_agree_same_conditions_is_consistent():
    cond = [
        Condition(eddo_class="Temperature", value=298.15, unit="K"),
        Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
    ]
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value="yes",
        unit=None,
        value_type=ValueType.ENUM,
        uncertainty=None,
        conditions=cond,
    )
    new = make_assertion(
        "AS-NEW",
        value="yes",
        unit=None,
        value_type=ValueType.ENUM,
        uncertainty=None,
        conditions=cond,
    )
    finding = compare_pair(new, old, SimpleOntologyService(), ConflictConfig())
    assert finding is not None
    assert finding.conflict_type == ConflictType.CONSISTENT


# ---------------------------------------------------------------------------
# P1-04 — relative tolerance scales with actual magnitude (no 1.0 floor)
# ---------------------------------------------------------------------------

def test_p11_subunit_close_values_consistent():
    """P1-04: close sub-unit values inside relative tolerance -> consistent."""
    cond = [
        Condition(eddo_class="Temperature", value=298.15, unit="K"),
        Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
    ]
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=0.10,
        uncertainty=0.0,
        conditions=cond,
    )
    new = make_assertion(
        "AS-NEW",
        value=0.102,
        uncertainty=0.0,
        conditions=cond,
    )
    finding = compare_pair(new, old, SimpleOntologyService(), ConflictConfig())
    assert finding is not None
    assert finding.conflict_type == ConflictType.CONSISTENT


def test_p11_subunit_materially_different_is_numeric_conflict():
    """P1-04: sub-unit values far apart must not hide behind a 1.0 floor pad."""
    cond = [
        Condition(eddo_class="Temperature", value=298.15, unit="K"),
        Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
    ]
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=0.10,
        uncertainty=0.0,
        conditions=cond,
    )
    new = make_assertion(
        "AS-NEW",
        value=0.25,
        uncertainty=0.0,
        conditions=cond,
    )
    finding = compare_pair(new, old, SimpleOntologyService(), ConflictConfig())
    assert finding is not None
    assert finding.conflict_type == ConflictType.NUMERIC_CONFLICT


def test_p11_subunit_conflict_also_surfaces_in_curator():
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=0.10,
        uncertainty=0.0,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
    )
    new = make_assertion(
        "AS-NEW",
        value=0.25,
        uncertainty=0.0,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
    )
    curator = make_curator(seed=[old])
    report = _run(curator.curate(make_assertion_set([new])))
    decision = report.decisions[0]
    assert decision.conflict_type == ConflictType.NUMERIC_CONFLICT
    assert decision.action.value == "pending_review"


# ---------------------------------------------------------------------------
# D — validation side effects (non-mutating chart check)
# ---------------------------------------------------------------------------

def test_p11_chart_validation_does_not_mutate_input():
    """D: ChartObjectInfo remains unchanged after completeness validation."""
    chart = ChartObjectInfo(
        id="C1",
        caption_complete=False,
        axes_complete=True,
        units_complete=True,
        not_digitizable=False,
        quality_low=False,
    )
    snapshot = ChartObjectInfo(
        id=chart.id,
        caption_complete=chart.caption_complete,
        axes_complete=chart.axes_complete,
        units_complete=chart.units_complete,
        not_digitizable=chart.not_digitizable,
        quality_low=chart.quality_low,
    )
    aset = make_assertion_set(charts=[chart])
    result = check_completeness(aset)
    assert chart.quality_low is snapshot.quality_low
    assert chart.caption_complete is snapshot.caption_complete
    assert chart.axes_complete is snapshot.axes_complete
    assert chart.units_complete is snapshot.units_complete
    assert chart.not_digitizable is snapshot.not_digitizable
    assert any(i.code == "chart_quality_low" for i in result.issues)


def test_p11_incomplete_chart_still_penalizes_quality_without_mutation():
    from knowledge_curator.core.quality import evaluate_quality

    chart = ChartObjectInfo(id="C1", caption_complete=False, quality_low=False)
    aset = make_assertion_set(charts=[chart])
    completeness = check_completeness(aset)
    q = evaluate_quality(aset, completeness, [])
    assert chart.quality_low is False
    assert q.penalty < 1.0
