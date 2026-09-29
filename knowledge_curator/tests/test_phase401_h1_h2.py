"""Phase 4.0.1 tests: H1 locator reality + H2 local DOI/title validation."""

from __future__ import annotations

from knowledge_curator.adapters.in_memory_evidence import InMemoryEvidenceStore
from knowledge_curator.ports.evidence_store import CitationMetadata
from knowledge_curator.retrieval.hallucination import (
    HallucinationType,
    LocatorCheckStatus,
    detect_h1,
    detect_h2,
    normalize_doi,
    normalize_title,
)
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.evidence import Claim, EvidenceAnchor, EvidenceType


def _anchor(ref="REF-1", loc="p.1", etype=EvidenceType.LITERATURE, conf=Confidence.HIGH):
    return EvidenceAnchor(evidence_type=etype, ref_id=ref, locator=loc, confidence=conf)


def _claim(anchors=None, claim_id="C1"):
    return Claim(claim_id=claim_id, text="t", anchors=list(anchors or []))


# ---- H1 locator ----

def test_h1_valid_registered_locator_passes():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", locators={"p.1", "T12", "Fig.3"})
    findings = detect_h1(_claim([_anchor(loc="T12")]), store)
    assert findings == []


def test_h1_fabricated_locator_detected():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", locators={"p.1", "T12", "Fig.3"})
    findings = detect_h1(_claim([_anchor(loc="T999")]), store)
    assert any(f.type == HallucinationType.H1 for f in findings)
    assert any("verified absent" in f.reason for f in findings)
    assert any(f.detail.get("locator_status") == LocatorCheckStatus.VERIFIED_ABSENT.value for f in findings)


def test_h1_locator_validator_unavailable_not_checked():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1")  # no locator index
    findings = detect_h1(_claim([_anchor(loc="T12")]), store)
    assert any("NOT_CHECKED" in f.reason for f in findings)
    assert any(f.detail.get("locator_status") == LocatorCheckStatus.NOT_CHECKED.value for f in findings)


def test_h1_empty_locator_still_detected():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", locators={"p.1"})
    findings = detect_h1(_claim([_anchor(loc="")]), store)
    assert any("locator empty" in f.reason for f in findings)


def test_h1_no_anchor():
    store = InMemoryEvidenceStore()
    findings = detect_h1(_claim([]), store)
    assert any("no evidence anchor" in f.reason for f in findings)


# ---- H2 DOI ----

def test_h2_doi_normalized_match_passes():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", doi="https://doi.org/10.1000/xyz", title="My Paper")
    cit = CitationMetadata(ref_id="REF-1", cited_doi="10.1000/XYZ")
    findings = detect_h2(_claim([_anchor(ref="REF-1")]), store, cit)
    assert findings == []


def test_h2_doi_mismatch_detected():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", doi="10.1000/xyz")
    cit = CitationMetadata(ref_id="REF-1", cited_doi="10.1000/abc")
    findings = detect_h2(_claim([_anchor(ref="REF-1")]), store, cit)
    assert any("DOI mismatch" in f.reason for f in findings)


def test_h2_title_normalized_match_passes():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", title="  My   Paper  Title ")
    cit = CitationMetadata(ref_id="REF-1", cited_title="my paper title")
    findings = detect_h2(_claim([_anchor(ref="REF-1")]), store, cit)
    assert findings == []


def test_h2_title_mismatch_detected():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", title="My Paper Title")
    cit = CitationMetadata(ref_id="REF-1", cited_title="Completely Different Title")
    findings = detect_h2(_claim([_anchor(ref="REF-1")]), store, cit)
    assert any("title mismatch" in f.reason for f in findings)


def test_h2_missing_citation_metadata_no_metadata_check():
    store = InMemoryEvidenceStore()
    store.add_ref("REF-1", doi="10.1000/xyz")
    findings = detect_h2(_claim([_anchor(ref="REF-1")]), store, None)
    assert findings == []  # only existence checked, no metadata compare


def test_h2_nonexistent_ref():
    store = InMemoryEvidenceStore()
    findings = detect_h2(_claim([_anchor(ref="GHOST")]), store)
    assert any(f.type == HallucinationType.H2 for f in findings)


def test_h2_non_literature_skipped():
    store = InMemoryEvidenceStore()
    a = _anchor(ref="G1", etype=EvidenceType.GRAPH)
    findings = detect_h2(_claim([a]), store)
    assert findings == []


def test_h1_and_h2_can_both_hit():
    """Nonexistent literature ref produces both H1 and H2."""
    store = InMemoryEvidenceStore()
    a = _anchor(ref="GHOST", loc="p.1")
    h1 = detect_h1(_claim([a]), store)
    h2 = detect_h2(_claim([a]), store)
    assert any(f.type == HallucinationType.H1 for f in h1)
    assert any(f.type == HallucinationType.H2 for f in h2)


# ---- Normalize helpers ----

def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1000/XYZ") == "10.1000/xyz"
    assert normalize_doi("http://doi.org/10.1000/xyz") == "10.1000/xyz"
    assert normalize_doi("  10.1000/xyz  ") == "10.1000/xyz"
    assert normalize_doi(None) is None


def test_normalize_title():
    assert normalize_title("  My   Paper  Title ") == "my paper title"
    assert normalize_title(None) is None
