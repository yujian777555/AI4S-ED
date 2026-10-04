"""Phase 4.0.2 tests: H1 finding vs locator validation status separation."""

from __future__ import annotations

from knowledge_curator.adapters.in_memory_evidence import InMemoryEvidenceStore
from knowledge_curator.retrieval.hallucination import (
    HallucinationType,
    LocatorCheckStatus,
    detect_h1,
    detect_h1_with_status,
    detect_h2,
)
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.evidence import Claim, EvidenceAnchor, EvidenceType


def _anchor(ref="REF-1", loc="p.1", etype=EvidenceType.LITERATURE):
    return EvidenceAnchor(evidence_type=etype, ref_id=ref, locator=loc, confidence=Confidence.HIGH)


def _claim(anchors=None):
    return Claim(claim_id="C1", text="t", anchors=list(anchors or []))


def test_valid_locator_verified_present_zero_h1():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", locators={"T12"})
    r = detect_h1_with_status(_claim([_anchor(loc="T12")]), store)
    assert r.findings == []
    assert r.locator_checks[0].status == LocatorCheckStatus.VERIFIED_PRESENT
    assert r.fully_checked is True


def test_fabricated_locator_verified_absent_one_h1():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", locators={"T12"})
    r = detect_h1_with_status(_claim([_anchor(loc="T999")]), store)
    assert len(r.findings) == 1
    assert r.findings[0].type == HallucinationType.H1
    assert r.locator_checks[0].status == LocatorCheckStatus.VERIFIED_ABSENT
    assert r.fully_checked is True


def test_unavailable_validator_not_checked_zero_h1():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1")  # no locator index
    r = detect_h1_with_status(_claim([_anchor(loc="T12")]), store)
    assert r.findings == []  # NOT_CHECKED must NOT produce H1
    assert r.locator_checks[0].status == LocatorCheckStatus.NOT_CHECKED
    assert r.fully_checked is False


def test_mixed_anchors_fully_checked_false():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", locators={"T12"})
    store.add_ref("REF-2")  # no locator index
    a1 = _anchor(ref="REF-1", loc="T12")
    a2 = _anchor(ref="REF-2", loc="p.1")
    r = detect_h1_with_status(_claim([a1, a2]), store)
    assert r.fully_checked is False
    assert len(r.locator_checks) == 2
    statuses = {c.status for c in r.locator_checks}
    assert LocatorCheckStatus.VERIFIED_PRESENT in statuses
    assert LocatorCheckStatus.NOT_CHECKED in statuses


def test_detect_h1_wrapper_only_returns_real_h1():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", locators={"T12"})
    store.add_ref("REF-2")  # no locator index
    a1 = _anchor(ref="REF-1", loc="T999")  # fabricated -> H1
    a2 = _anchor(ref="REF-2", loc="p.1")  # NOT_CHECKED -> no H1
    findings = detect_h1(_claim([a1, a2]), store)
    assert len(findings) == 1
    assert findings[0].type == HallucinationType.H1
    assert "verified absent" in findings[0].reason


def test_missing_ref_h1_and_h2_both():
    store = InMemoryEvidenceStore()
    a = _anchor(ref="GHOST", loc="p.1")
    r = detect_h1_with_status(_claim([a]), store)
    h2 = detect_h2(_claim([a]), store)
    assert any(f.type == HallucinationType.H1 for f in r.findings)
    assert any(f.type == HallucinationType.H2 for f in h2)


def test_no_anchor_h1():
    store = InMemoryEvidenceStore()
    r = detect_h1_with_status(_claim([]), store)
    assert len(r.findings) == 1
    assert r.fully_checked is False
