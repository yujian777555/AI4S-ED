"""End-to-end KnowledgeCurator tests (latest_plan T01–T10)."""

from __future__ import annotations

import asyncio
import sys

from knowledge_curator.adapters import FakeMechanismValidator
from knowledge_curator.schemas.assertions import (
    Condition,
    Confidence,
    QualityGrade,
    SourceClaimOrigin,
    ValueType,
)
from knowledge_curator.schemas.curation import CurationAction
from knowledge_curator.tests.conftest import (
    make_assertion,
    make_assertion_set,
    make_curator,
    make_meta,
)


def _run(coro):
    return asyncio.run(coro)


def test_t01_normal_assertion_set_successful_curation():
    """T01: normal AssertionSet -> successful curation."""
    curator = make_curator()
    aset = make_assertion_set(
        [make_assertion("AS-001", confidence=Confidence.MEDIUM)],
    )
    report = _run(curator.curate(aset))
    assert report.status == "successful"
    assert report.accepted_count == 1
    assert report.quality is not None
    assert 0.0 <= report.quality.total <= 1.0
    assert report.completeness.metadata_valid is True
    assert report.commit_id is None  # Phase 1 must not fabricate commits
    assert report.kb_version is None


def test_t02_stable_id_without_doi_accepted():
    """T02: no DOI but stable_id -> metadata valid, curation proceeds."""
    curator = make_curator()
    aset = make_assertion_set(
        metadata=make_meta(doi=None, stable_id="ST-777"),
    )
    report = _run(curator.curate(aset))
    assert report.completeness.metadata_valid is True
    assert report.status == "successful"
    assert report.returned_upstream_count == 0


def test_t03_missing_doi_and_stable_id_return_upstream():
    """T03: DOI/stable_id both missing -> return_upstream."""
    curator = make_curator()
    aset = make_assertion_set(
        metadata=make_meta(doi=None, stable_id=None),
    )
    report = _run(curator.curate(aset))
    assert report.status == "return_upstream"
    assert report.returned_upstream_count >= 1
    assert all(d.action == CurationAction.RETURN_UPSTREAM for d in report.decisions)


def test_t04_missing_unit_downgrades_to_hypothesis():
    """T04: numeric assertion missing unit -> downgrade / manual handling."""
    curator = make_curator()
    aset = make_assertion_set(
        [make_assertion("AS-U1", unit=None, missing_unit=True)],
    )
    report = _run(curator.curate(aset))
    decision = report.decisions[0]
    assert decision.action == CurationAction.DOWNGRADE
    assert decision.confidence == Confidence.HYPOTHESIS
    assert report.downgraded_count == 1


def test_t05_missing_locator_downgrades_to_hypothesis_with_warning():
    """T05: locator missing -> hypothesis + warning."""
    curator = make_curator()
    aset = make_assertion_set(
        [make_assertion("AS-L1", locator=None)],
    )
    report = _run(curator.curate(aset))
    decision = report.decisions[0]
    assert decision.action == CurationAction.DOWNGRADE
    assert decision.confidence == Confidence.HYPOTHESIS
    assert decision.warnings


def test_t06_overlapping_same_condition_consistent_accept():
    """T06: same conditions, overlapping -> consistent and accept."""
    old = make_assertion(
        "AS-OLD",
        value=1.40,
        uncertainty=0.10,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
        ref_id="ED-OLD",
    )
    new = make_assertion(
        "AS-NEW",
        value=1.42,
        uncertainty=0.10,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
    )
    curator = make_curator(seed=[old])
    report = _run(curator.curate(make_assertion_set([new])))
    decision = report.decisions[0]
    assert decision.action == CurationAction.ACCEPT
    assert decision.conflict_type.value == "consistent"
    assert decision.confidence == Confidence.HIGH  # multi-source elevate


def test_t07_different_conditions_condition_difference_accept():
    """T07: different conditions -> condition_difference, not numeric_conflict."""
    old = make_assertion(
        "AS-OLD",
        value=1.40,
        uncertainty=0.0,
        conditions=[Condition(eddo_class="Temperature", value=298.15, unit="K")],
        ref_id="ED-OLD",
    )
    new = make_assertion(
        "AS-NEW",
        value=3.20,
        uncertainty=0.0,
        conditions=[Condition(eddo_class="Temperature", value=333.15, unit="K")],
    )
    curator = make_curator(seed=[old])
    report = _run(curator.curate(make_assertion_set([new])))
    decision = report.decisions[0]
    assert decision.action == CurationAction.ACCEPT
    assert decision.conflict_type.value == "condition_difference"
    assert decision.conflict_type.value != "numeric_conflict"
    conflict_types = [f.conflict_type.value for f in report.conflicts]
    assert "numeric_conflict" not in conflict_types


def test_t08_non_overlapping_same_condition_pending_review():
    """T08: same conditions, disjoint intervals -> numeric_conflict + pending_review."""
    old = make_assertion(
        "AS-OLD",
        value=0.35,
        uncertainty=0.05,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
        ref_id="ED-OLD",
    )
    new = make_assertion(
        "AS-NEW",
        value=2.50,
        uncertainty=0.05,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
    )
    curator = make_curator(seed=[old])
    report = _run(curator.curate(make_assertion_set([new])))
    decision = report.decisions[0]
    assert decision.action == CurationAction.PENDING_REVIEW
    assert decision.conflict_type.value == "numeric_conflict"
    assert report.pending_count == 1
    assert report.status == "pending_review"


def test_t09_mechanism_violation_rejects():
    """T09: FakeMechanismValidator violation -> mechanism_violation + reject."""
    fake = FakeMechanismValidator(
        violated_ids=["AS-M1"],
        ok=False,
        messages=["current efficiency exceeds 100%"],
    )
    curator = make_curator(mechanism=fake)
    aset = make_assertion_set([make_assertion("AS-M1")])
    report = _run(curator.curate(aset))
    decision = report.decisions[0]
    assert decision.action == CurationAction.REJECT
    assert decision.conflict_type.value == "mechanism_violation"
    assert report.rejected_count == 1


def test_t10_core_does_not_depend_on_dsh_runtime():
    """T10: core modules must not import DSH runtime."""
    forbidden = (
        "deepseek",
        "dsh_sdk",
        "dsh.runtime",
        "dsh.agent",
        "@dsh",
    )
    core_modules = [
        "knowledge_curator.core.curator",
        "knowledge_curator.core.completeness",
        "knowledge_curator.core.conflict",
        "knowledge_curator.core.quality",
        "knowledge_curator.core.decision",
        "knowledge_curator.schemas.assertions",
        "knowledge_curator.schemas.curation",
        "knowledge_curator.ports.knowledge_repository",
        "knowledge_curator.ports.mechanism_validator",
        "knowledge_curator.ports.ontology_service",
        "knowledge_curator.adapters.in_memory_repository",
        "knowledge_curator.config",
    ]
    for name in core_modules:
        mod = sys.modules.get(name)
        if mod is None:
            __import__(name)
            mod = sys.modules[name]
        src = open(mod.__file__, encoding="utf-8").read().lower()
        for token in forbidden:
            # Allow comments mentioning future DSH, but no import statements.
            if f"import {token}" in src or f"from {token}" in src:
                raise AssertionError(f"{name} must not import DSH token {token}")


def test_secondary_origin_cannot_auto_reach_high():
    curator = make_curator()
    aset = make_assertion_set(
        [
            make_assertion(
                "AS-SEC",
                origin=SourceClaimOrigin.SECONDARY,
                confidence=Confidence.HIGH,
            )
        ],
    )
    report = _run(curator.curate(aset))
    decision = report.decisions[0]
    assert decision.action == CurationAction.ACCEPT
    assert decision.confidence == Confidence.MEDIUM


def test_verified_is_not_auto_granted():
    """P1-01: single-source verified must not remain verified/high."""
    curator = make_curator()
    aset = make_assertion_set(
        [make_assertion("AS-V", confidence=Confidence.VERIFIED)],
    )
    report = _run(curator.curate(aset))
    decision = report.decisions[0]
    assert decision.confidence not in (Confidence.VERIFIED, Confidence.HIGH)
    assert decision.confidence == Confidence.MEDIUM
    assert any("verified" in w.lower() for w in decision.warnings)


def test_report_counts_and_trace_fields():
    curator = make_curator()
    aset = make_assertion_set(
        [
            make_assertion("A1"),
            make_assertion("A2", unit=None, missing_unit=True),
            make_assertion("A3", locator=None),
        ],
    )
    report = _run(curator.curate(aset))
    assert report.accepted_count + report.downgraded_count + report.rejected_count == 3
    assert "pipeline" in report.trace
    assert report.source_ref_id == "ED-2025-0042"
    assert report.report_id.startswith("cr-")
