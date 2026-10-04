"""Phase 1.2 regression tests: confidence monotonicity & exact tolerance (P1.2-01/02)."""

from __future__ import annotations

import asyncio

from knowledge_curator.config import ConflictConfig
from knowledge_curator.core.conflict import compare_pair
from knowledge_curator.schemas.assertions import Condition, Confidence, SourceClaimOrigin, ValueType
from knowledge_curator.schemas.curation import ConflictType
from knowledge_curator.tests.conftest import make_assertion, make_assertion_set, make_curator

DEFAULT_COND = [
    Condition(eddo_class="Temperature", value=298.15, unit="K"),
    Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
]
ALT_COND = [Condition(eddo_class="Temperature", value=333.15, unit="K")]


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# P1.2-01 — confidence monotonicity (capping never increases)
# ---------------------------------------------------------------------------

def test_p12_primary_single_source_hypothesis_stays_hypothesis():
    curator = make_curator()
    aset = make_assertion_set(
        [
            make_assertion(
                "AS-H",
                confidence=Confidence.HYPOTHESIS,
                origin=SourceClaimOrigin.PRIMARY,
            )
        ],
    )
    report = _run(curator.curate(aset))
    assert report.decisions[0].confidence == Confidence.HYPOTHESIS


def test_p12_secondary_single_source_hypothesis_stays_hypothesis():
    curator = make_curator()
    aset = make_assertion_set(
        [
            make_assertion(
                "AS-HS",
                confidence=Confidence.HYPOTHESIS,
                origin=SourceClaimOrigin.SECONDARY,
            )
        ],
    )
    report = _run(curator.curate(aset))
    assert report.decisions[0].confidence == Confidence.HYPOTHESIS


def test_p12_condition_difference_hypothesis_stays_hypothesis():
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=1.0,
        conditions=DEFAULT_COND,
    )
    new = make_assertion(
        "AS-NEW",
        value=3.0,
        confidence=Confidence.HYPOTHESIS,
        conditions=ALT_COND,
    )
    curator = make_curator(seed=[old])
    report = _run(curator.curate(make_assertion_set([new])))
    decision = report.decisions[0]
    assert decision.conflict_type == ConflictType.CONDITION_DIFFERENCE
    assert decision.confidence == Confidence.HYPOTHESIS


def test_p12_primary_single_source_medium_stays_medium():
    curator = make_curator()
    aset = make_assertion_set(
        [
            make_assertion(
                "AS-M",
                confidence=Confidence.MEDIUM,
                origin=SourceClaimOrigin.PRIMARY,
            )
        ],
    )
    report = _run(curator.curate(aset))
    assert report.decisions[0].confidence == Confidence.MEDIUM


def test_p12_primary_single_source_high_caps_to_medium():
    curator = make_curator()
    aset = make_assertion_set(
        [
            make_assertion(
                "AS-HI",
                confidence=Confidence.HIGH,
                origin=SourceClaimOrigin.PRIMARY,
            )
        ],
    )
    report = _run(curator.curate(aset))
    assert report.decisions[0].confidence == Confidence.MEDIUM


def test_p12_primary_single_source_verified_caps_to_medium():
    curator = make_curator()
    aset = make_assertion_set(
        [
            make_assertion(
                "AS-V",
                confidence=Confidence.VERIFIED,
                origin=SourceClaimOrigin.PRIMARY,
            )
        ],
    )
    report = _run(curator.curate(aset))
    assert report.decisions[0].confidence == Confidence.MEDIUM


def test_p12_secondary_single_source_high_caps_to_medium_not_promoted():
    curator = make_curator()
    aset = make_assertion_set(
        [
            make_assertion(
                "AS-SH",
                confidence=Confidence.HIGH,
                origin=SourceClaimOrigin.SECONDARY,
            )
        ],
    )
    report = _run(curator.curate(aset))
    assert report.decisions[0].confidence == Confidence.MEDIUM


def test_p12_consistent_primary_hypothesis_does_not_jump_to_high():
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=1.40,
        uncertainty=0.10,
        conditions=DEFAULT_COND,
    )
    new = make_assertion(
        "AS-NEW",
        value=1.42,
        uncertainty=0.10,
        confidence=Confidence.HYPOTHESIS,
        origin=SourceClaimOrigin.PRIMARY,
        conditions=DEFAULT_COND,
    )
    curator = make_curator(seed=[old])
    report = _run(curator.curate(make_assertion_set([new])))
    decision = report.decisions[0]
    assert decision.conflict_type == ConflictType.CONSISTENT
    assert decision.confidence == Confidence.HYPOTHESIS
    assert decision.confidence != Confidence.HIGH


def test_p12_consistent_primary_medium_can_reach_high():
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=1.40,
        uncertainty=0.10,
        conditions=DEFAULT_COND,
    )
    new = make_assertion(
        "AS-NEW",
        value=1.42,
        uncertainty=0.10,
        confidence=Confidence.MEDIUM,
        origin=SourceClaimOrigin.PRIMARY,
        conditions=DEFAULT_COND,
    )
    curator = make_curator(seed=[old])
    report = _run(curator.curate(make_assertion_set([new])))
    assert report.decisions[0].confidence == Confidence.HIGH


def test_p12_consistent_secondary_hypothesis_not_promoted_to_medium():
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=1.40,
        uncertainty=0.10,
        conditions=DEFAULT_COND,
    )
    new = make_assertion(
        "AS-NEW",
        value=1.42,
        uncertainty=0.10,
        confidence=Confidence.HYPOTHESIS,
        origin=SourceClaimOrigin.SECONDARY,
        conditions=DEFAULT_COND,
    )
    curator = make_curator(seed=[old])
    report = _run(curator.curate(make_assertion_set([new])))
    assert report.decisions[0].confidence == Confidence.HYPOTHESIS


def test_p12_cap_is_monotone_across_ladder():
    """Direct unit check: _at_most_medium never increases rank."""
    from knowledge_curator.core.decision import _at_most_medium

    assert _at_most_medium(Confidence.HYPOTHESIS) == Confidence.HYPOTHESIS
    assert _at_most_medium(Confidence.MEDIUM) == Confidence.MEDIUM
    assert _at_most_medium(Confidence.HIGH) == Confidence.MEDIUM
    assert _at_most_medium(Confidence.VERIFIED) == Confidence.MEDIUM


# ---------------------------------------------------------------------------
# P1.2-02 — exact tolerance semantics (expand reference only)
# ---------------------------------------------------------------------------

def _point(value: float, *, ref_id: str, aid: str, conditions=None):
    return make_assertion(
        aid,
        ref_id=ref_id,
        value=value,
        uncertainty=0.0,
        conditions=conditions or DEFAULT_COND,
    )


def _compare(new, old):
    return compare_pair(new, old, _ontology(), ConflictConfig())


def _ontology():
    from knowledge_curator.adapters import SimpleOntologyService

    return SimpleOntologyService()


def test_p12_existing_100_new_104_consistent():
    finding = _compare(_point(1.04, ref_id="ED-N", aid="AS-N"), _point(1.00, ref_id="ED-O", aid="AS-O"))
    assert finding is not None
    assert finding.conflict_type == ConflictType.CONSISTENT


def test_p12_existing_100_new_109_numeric_conflict():
    """5% tolerance must not become ~10% via double expansion."""
    finding = _compare(_point(1.09, ref_id="ED-N", aid="AS-N"), _point(1.00, ref_id="ED-O", aid="AS-O"))
    assert finding is not None
    assert finding.conflict_type == ConflictType.NUMERIC_CONFLICT


def test_p12_existing_00100_new_00104_consistent():
    finding = _compare(
        _point(0.0104, ref_id="ED-N", aid="AS-N"),
        _point(0.0100, ref_id="ED-O", aid="AS-O"),
    )
    assert finding is not None
    assert finding.conflict_type == ConflictType.CONSISTENT


def test_p12_existing_00100_new_00109_numeric_conflict():
    finding = _compare(
        _point(0.0109, ref_id="ED-N", aid="AS-N"),
        _point(0.0100, ref_id="ED-O", aid="AS-O"),
    )
    assert finding is not None
    assert finding.conflict_type == ConflictType.NUMERIC_CONFLICT


def test_p12_raw_overlapping_uncertainty_intervals_consistent():
    old = make_assertion(
        "AS-O",
        ref_id="ED-O",
        value=1.00,
        uncertainty=0.20,
        conditions=DEFAULT_COND,
    )
    new = make_assertion(
        "AS-N",
        ref_id="ED-N",
        value=1.15,
        uncertainty=0.20,
        conditions=DEFAULT_COND,
    )
    finding = _compare(new, old)
    assert finding is not None
    assert finding.conflict_type == ConflictType.CONSISTENT


def test_p12_raw_overlap_is_consistent_even_if_tolerance_would_matter():
    # Overlapping ranges: [0.9, 1.1] vs [1.05, 1.25] overlap raw.
    old = make_assertion(
        "AS-O",
        ref_id="ED-O",
        value=[0.9, 1.1],
        unit="kWh/m3",
        value_type=ValueType.RANGE,
        uncertainty=None,
        conditions=DEFAULT_COND,
    )
    new = make_assertion(
        "AS-N",
        ref_id="ED-N",
        value=[1.05, 1.25],
        unit="kWh/m3",
        value_type=ValueType.RANGE,
        uncertainty=None,
        conditions=DEFAULT_COND,
    )
    finding = _compare(new, old)
    assert finding is not None
    assert finding.conflict_type == ConflictType.CONSISTENT


def test_p12_new_inside_expanded_reference_is_consistent():
    # existing 2.00, pad 5% -> [1.90, 2.10]; new 2.08 is inside.
    finding = _compare(_point(2.08, ref_id="ED-N", aid="AS-N"), _point(2.00, ref_id="ED-O", aid="AS-O"))
    assert finding is not None
    assert finding.conflict_type == ConflictType.CONSISTENT


def test_p12_new_just_outside_expanded_reference_is_conflict():
    # existing 2.00, pad 5% -> [1.90, 2.10]; new 2.12 is outside.
    finding = _compare(_point(2.12, ref_id="ED-N", aid="AS-N"), _point(2.00, ref_id="ED-O", aid="AS-O"))
    assert finding is not None
    assert finding.conflict_type == ConflictType.NUMERIC_CONFLICT
