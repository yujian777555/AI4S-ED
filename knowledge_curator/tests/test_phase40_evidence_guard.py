"""Phase 4.0 §6 evidence guard foundation tests (deterministic, keyless)."""

from __future__ import annotations

import pytest

from knowledge_curator.adapters.in_memory_evidence import InMemoryEvidenceStore
from knowledge_curator.adapters.in_memory_repository import FakeMechanismValidator
from knowledge_curator.retrieval.abstain import AbstainReason, evaluate_abstain
from knowledge_curator.retrieval.evidence_guard import classify_claim_policy
from knowledge_curator.retrieval.hallucination import (
    H3Status,
    HallucinationType,
    detect_h1,
    detect_h2,
    detect_h3,
)
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.evidence import (
    Claim,
    EvidenceAnchor,
    EvidenceType,
    SurfacePolicy,
)


def _anchor(conf=Confidence.HIGH, ref="REF-1", loc="p.1"):
    return EvidenceAnchor(
        evidence_type=EvidenceType.LITERATURE,
        ref_id=ref,
        locator=loc,
        confidence=conf,
    )


def _claim(anchors=None, claim_id="C1", is_numeric=False):
    return Claim(
        claim_id=claim_id,
        text="sample claim",
        anchors=list(anchors or []),
        is_numeric=is_numeric,
    )


# ---- Confidence gate ----

def test_verified_anchor_allows_factual():
    p = classify_claim_policy(_claim([_anchor(Confidence.VERIFIED)]))
    assert p.policy == SurfacePolicy.FACTUAL_ALLOWED


def test_high_anchor_allows_factual():
    p = classify_claim_policy(_claim([_anchor(Confidence.HIGH)]))
    assert p.policy == SurfacePolicy.FACTUAL_ALLOWED


def test_medium_caveated_only():
    p = classify_claim_policy(_claim([_anchor(Confidence.MEDIUM)]))
    assert p.policy == SurfacePolicy.CAVEATED_ONLY


def test_hypothesis_pending_only():
    p = classify_claim_policy(_claim([_anchor(Confidence.HYPOTHESIS)]))
    assert p.policy == SurfacePolicy.PENDING_HYPOTHESIS_ONLY


def test_no_anchor_abstain():
    p = classify_claim_policy(_claim([]))
    assert p.policy == SurfacePolicy.ABSTAIN


def test_anchors_do_not_elevate():
    # verified + hypothesis -> min = hypothesis
    p = classify_claim_policy(_claim([_anchor(Confidence.VERIFIED), _anchor(Confidence.HYPOTHESIS)]))
    assert p.policy == SurfacePolicy.PENDING_HYPOTHESIS_ONLY


def test_disjoint_numeric_ranges_conflict_disclosure():
    p = classify_claim_policy(
        _claim([_anchor()], is_numeric=True),
        numeric_source_ranges=[(0.1, 0.2), (2.0, 3.0)],
    )
    assert p.policy == SurfacePolicy.CONFLICT_DISCLOSURE_REQUIRED


def test_overlapping_ranges_no_forced_disclosure():
    p = classify_claim_policy(
        _claim([_anchor()], is_numeric=True),
        numeric_source_ranges=[(0.1, 0.5), (0.3, 0.8)],
    )
    assert p.policy == SurfacePolicy.FACTUAL_ALLOWED


# ---- H1 ----

def test_h1_no_anchor():
    store = InMemoryEvidenceStore()
    findings = detect_h1(_claim([]), store)
    assert any(f.type == HallucinationType.H1 for f in findings)


def test_h1_empty_locator():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1")
    findings = detect_h1(_claim([_anchor(loc="")]), store)
    assert any("locator" in f.reason for f in findings)


def test_h1_unresolvable_ref():
    store = InMemoryEvidenceStore()
    findings = detect_h1(_claim([_anchor(ref="GHOST")]), store)
    assert any("not resolvable" in f.reason for f in findings)


# ---- H2 ----

def test_h2_nonexistent_ref():
    store = InMemoryEvidenceStore()
    findings = detect_h2(_claim([_anchor(ref="GHOST")]), store)
    assert any(f.type == HallucinationType.H2 for f in findings)


def test_h2_existing_ref_no_finding():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", doi="10.0/x")
    findings = detect_h2(_claim([_anchor(ref="REF-1")]), store)
    assert findings == []


def test_h2_non_literature_skipped():
    store = InMemoryEvidenceStore()
    a = EvidenceAnchor(evidence_type=EvidenceType.GRAPH, ref_id="G1", locator="n1", confidence=Confidence.HIGH)
    findings = detect_h2(_claim([a]), store)
    assert findings == []


# ---- H3 ----

def test_h3_violation():
    from knowledge_curator.tests.conftest import make_assertion

    v = FakeMechanismValidator(violated_ids=["AS-1"], ok=False, messages=["violation"])
    r = detect_h3([make_assertion("AS-1")], v)
    assert r.status == H3Status.CHECKED
    assert any(f.type == HallucinationType.H3 for f in r.findings)


def test_h3_validator_unavailable():
    r = detect_h3([], None)
    assert r.status == H3Status.MECHANISM_UNAVAILABLE


def test_h3_pass_when_ok():
    from knowledge_curator.tests.conftest import make_assertion

    v = FakeMechanismValidator(ok=True)
    r = detect_h3([make_assertion("AS-1")], v)
    assert r.status == H3Status.CHECKED
    assert r.findings == []


# ---- Abstain ----

def test_abstain_low_support():
    d = evaluate_abstain(_claim(), retrieval_support=0.1)
    assert d.abstain is True
    assert AbstainReason.LOW_RETRIEVAL_SUPPORT in d.reasons


def test_abstain_uncovered_subquestion():
    d = evaluate_abstain(
        _claim(),
        required_keys={"q1", "q2"},
        covered_keys={"q1"},
    )
    assert d.abstain is True
    assert AbstainReason.SUBQUESTION_NOT_COVERED in d.reasons
    assert any(m.coverage_key == "q2" for m in d.missing_evidence)


def test_abstain_critical_numeric_hypothesis_only():
    c = _claim([_anchor(Confidence.HYPOTHESIS)], is_numeric=True)
    d = evaluate_abstain(c, is_critical_numeric=True)
    assert d.abstain is True
    assert AbstainReason.CRITICAL_NUMERIC_ONLY_HYPOTHESIS_OR_PENDING in d.reasons


def test_abstain_no_mechanism():
    d = evaluate_abstain(_claim(), mechanism_supported=False)
    assert d.abstain is True
    assert AbstainReason.UNSUPPORTED_INFERENCE_NO_MECHANISM in d.reasons


def test_abstain_private_data():
    d = evaluate_abstain(_claim(), private_data_unauthorized=True)
    assert d.abstain is True
    assert AbstainReason.PRIVATE_DATA_UNAUTHORIZED in d.reasons


def test_no_abstain_when_covered():
    d = evaluate_abstain(
        _claim([_anchor()]),
        retrieval_support=0.9,
        required_keys={"q1"},
        covered_keys={"q1"},
        mechanism_supported=True,
    )
    assert d.abstain is False


# ---- DSH live regression hardening ----

def test_dsh_regression_no_b_from_a_inference():
    from pathlib import Path

    fp = Path(__file__).resolve().parents[2] / "integration" / "dsh" / "lane324_kc_roundtrip.e2e.ts"
    if not fp.exists():
        pytest.skip("live regression file not present")
    text = fp.read_text(encoding="utf-8")
    assert "inferred_from_tool_result_raw" not in text
    assert "tool_result_blob_matched" not in text
    assert "tool_call_count).toBe(1)" in text
    assert "abc_match).toBe(true)" in text
