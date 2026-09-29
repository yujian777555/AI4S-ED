"""Phase 4.3.1 tests: guardability invariant, coverage consistency, H2 truthfulness."""

from __future__ import annotations

import pytest

from knowledge_curator.adapters.in_memory_retrieval import (
    FakeReranker,
    InMemoryKeywordSearch,
    InMemoryVectorSearch,
)
from knowledge_curator.ports.evidence_store import CitationMetadata, RefMetadata
from knowledge_curator.retrieval.evidence_models import (
    build_evidence_anchor,
    evaluate_anchorability,
    normalize_hit_to_record,
)
from knowledge_curator.retrieval.evidence_service import (
    EvidenceRequest,
    EvidenceRetrievalService,
)
from knowledge_curator.retrieval.guard_service import (
    ClaimGuardService,
    H2CheckedStatus,
    ProposedClaimInput,
    evaluate_h2_checked,
)
from knowledge_curator.retrieval.retrieval_metadata import RetrievalSetMetadata
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk
from knowledge_curator.schemas.evidence import EvidenceType
from knowledge_curator.ports.retrieval import RankedHit, RetrievalChannel


def _chunk(cid, ref, payload="text", level=ChunkLevel.FINE, **kwargs):
    defaults = dict(
        chunk_id=cid,
        ref_id=ref,
        level=level,
        chunk_type=ChunkType.TEXT,
        payload=payload,
        locator="p.1",
        confidence=Confidence.HIGH,
        quality=0.9,
        provenance={"evidence_type": "literature", "locator": "p.1"},
    )
    defaults.update(kwargs)
    return KnowledgeChunk(**defaults)


def _hit(chunk, rank=1):
    return RankedHit(
        chunk=chunk,
        rrf_score=1.0 / (60 + rank),
        channels=[RetrievalChannel.VECTOR],
        rank=rank,
    )


def _service(chunks, default_evidence_type=EvidenceType.LITERATURE):
    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    return EvidenceRetrievalService(
        vector_port=InMemoryVectorSearch(chunks),
        keyword_port=InMemoryKeywordSearch(chunks),
        reranker=FakeReranker(),
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
        default_evidence_type=default_evidence_type,
    )


# ---- guardable_as_anchor == build_evidence_anchor succeeds ----

def test_guardable_iff_build_anchor_succeeds():
    cases = [
        _chunk("A", "REF-1"),
        _chunk("B", "REF-1", confidence=None),
        _chunk("C", "REF-1", locator=None),
        _chunk("D", "REF-1", provenance={}),  # no evidence_type, default will apply
        _chunk("E", "REF-1", provenance={"evidence_type": "not-a-type", "locator": "p.1"}),
    ]
    for c in cases:
        rec = normalize_hit_to_record(_hit(c), default_evidence_type=EvidenceType.LITERATURE)
        assert (build_evidence_anchor(rec) is not None) == rec.guardable_as_anchor, c.chunk_id


def test_missing_evidence_type_without_default_unguardable():
    rec = normalize_hit_to_record(
        _hit(_chunk("A", "REF-1", provenance={})),
        default_evidence_type=None,
    )
    assert rec.guardable_as_anchor is False
    assert "missing_evidence_type" in rec.unguardable_reasons
    assert build_evidence_anchor(rec) is None


def test_invalid_explicit_evidence_type_unguardable():
    rec = normalize_hit_to_record(
        _hit(_chunk("A", "REF-1", provenance={"evidence_type": "bogus", "locator": "p.1"})),
        default_evidence_type=EvidenceType.LITERATURE,  # default must NOT rescue invalid explicit
    )
    assert rec.guardable_as_anchor is False
    assert "invalid_evidence_type" in rec.unguardable_reasons
    assert build_evidence_anchor(rec) is None


def test_valid_literature_default_makes_guardable():
    rec = normalize_hit_to_record(
        _hit(_chunk("A", "REF-1", provenance={})),
        default_evidence_type=EvidenceType.LITERATURE,
    )
    assert rec.guardable_as_anchor is True
    assert rec.evidence_type == EvidenceType.LITERATURE
    assert build_evidence_anchor(rec) is not None


def test_evaluate_anchorability_requires_all_fields():
    ok, reasons = evaluate_anchorability(
        ref_id="R", locator="p.1", confidence=Confidence.HIGH, evidence_type=EvidenceType.LITERATURE
    )
    assert ok is True and reasons == []
    ok, reasons = evaluate_anchorability(
        ref_id="R", locator="p.1", confidence=Confidence.HIGH, evidence_type=None,
        evidence_type_error="missing_evidence_type",
    )
    assert ok is False and "missing_evidence_type" in reasons


# ---- coverage-anchor consistency ----

def test_coverage_not_covered_when_evidence_type_missing_no_default():
    chunks = [
        _chunk("CA", "REF-A", "coarse", level=ChunkLevel.COARSE),
        _chunk("FA", "REF-A", provenance={}),  # no evidence_type
    ]
    svc = _service(chunks, default_evidence_type=None)
    bundle = svc.retrieve(EvidenceRequest(query="text", coverage_keys=["sq1"], required_coverage_keys=["sq1"]))
    assert {c.coverage_key: c.state.value for c in bundle.coverage}["sq1"] == "not_covered"
    rec = bundle.evidence_records[0]
    assert rec.guardable_as_anchor is False
    assert build_evidence_anchor(rec) is None


def test_coverage_covered_with_valid_default():
    chunks = [
        _chunk("CA", "REF-A", "coarse", level=ChunkLevel.COARSE),
        _chunk("FA", "REF-A", provenance={}),
    ]
    svc = _service(chunks, default_evidence_type=EvidenceType.LITERATURE)
    bundle = svc.retrieve(EvidenceRequest(query="text", coverage_keys=["sq1"], required_coverage_keys=["sq1"]))
    assert {c.coverage_key: c.state.value for c in bundle.coverage}["sq1"] == "covered"
    rec = bundle.evidence_records[0]
    assert rec.guardable_as_anchor is True
    assert build_evidence_anchor(rec) is not None


def test_coverage_invalid_evidence_type_not_covered():
    chunks = [
        _chunk("CA", "REF-A", "coarse", level=ChunkLevel.COARSE),
        _chunk("FA", "REF-A", provenance={"evidence_type": "nope", "locator": "p.1"}),
    ]
    svc = _service(chunks, default_evidence_type=EvidenceType.LITERATURE)
    bundle = svc.retrieve(EvidenceRequest(query="text", coverage_keys=["sq1"], required_coverage_keys=["sq1"]))
    assert {c.coverage_key: c.state.value for c in bundle.coverage}["sq1"] == "not_covered"


# ---- H2 honest checked semantics ----

def _meta(pairs):
    """Build RetrievalSetMetadata-like object with ref metadata."""
    records = []
    for ref, loc in pairs:
        records.append(
            normalize_hit_to_record(_hit(_chunk(f"{ref}-{loc}", ref, locator=loc, provenance={"evidence_type": "literature", "locator": loc})))
        )
    return records


def test_h2_no_citation_metadata_ref_existence_checked():
    meta = RetrievalSetMetadata(_meta([("REF-A", "p.1")]))
    checked, status, reason = evaluate_h2_checked(cited=None, metadata=meta, ref_ids=["REF-A"])
    assert checked is True
    assert status == H2CheckedStatus.CHECKED
    assert reason is None


def test_h2_cited_doi_same_no_finding():
    meta = RetrievalSetMetadata(
        _meta([("REF-A", "p.1")]),
        ref_metadata={"REF-A": RefMetadata(ref_id="REF-A", doi="10.1/abc", title="T")},
    )
    cited = CitationMetadata(ref_id="REF-A", cited_doi="10.1/abc")
    checked, status, reason = evaluate_h2_checked(cited=cited, metadata=meta, ref_ids=["REF-A"])
    assert checked is True and status == H2CheckedStatus.CHECKED
    from knowledge_curator.schemas.evidence import Claim, EvidenceAnchor, EvidenceType as ET

    claim = Claim(
        claim_id="C",
        text="t",
        anchors=[EvidenceAnchor(evidence_type=ET.LITERATURE, ref_id="REF-A", locator="p.1", confidence=Confidence.HIGH)],
    )
    from knowledge_curator.retrieval.hallucination import detect_h2

    findings = detect_h2(claim, meta, cited)
    assert findings == []


def test_h2_cited_doi_mismatch_is_finding():
    meta = RetrievalSetMetadata(
        _meta([("REF-A", "p.1")]),
        ref_metadata={"REF-A": RefMetadata(ref_id="REF-A", doi="10.1/abc", title="T")},
    )
    cited = CitationMetadata(ref_id="REF-A", cited_doi="10.1/zzz")
    checked, status, _ = evaluate_h2_checked(cited=cited, metadata=meta, ref_ids=["REF-A"])
    assert checked is True  # comparison actually happened
    from knowledge_curator.schemas.evidence import Claim, EvidenceAnchor, EvidenceType as ET
    from knowledge_curator.retrieval.hallucination import detect_h2

    claim = Claim(
        claim_id="C",
        text="t",
        anchors=[EvidenceAnchor(evidence_type=ET.LITERATURE, ref_id="REF-A", locator="p.1", confidence=Confidence.HIGH)],
    )
    findings = detect_h2(claim, meta, cited)
    assert findings and findings[0].reason == "cited DOI mismatch with KB metadata"


def test_h2_cited_doi_kb_unavailable_not_checked():
    meta = RetrievalSetMetadata(_meta([("REF-A", "p.1")]))  # no DOI in KB
    cited = CitationMetadata(ref_id="REF-A", cited_doi="10.1/abc")
    checked, status, reason = evaluate_h2_checked(cited=cited, metadata=meta, ref_ids=["REF-A"])
    assert checked is False
    assert status == H2CheckedStatus.METADATA_UNAVAILABLE
    assert reason and "DOI" in reason


def test_h2_cited_title_kb_unavailable_not_checked():
    meta = RetrievalSetMetadata(_meta([("REF-A", "p.1")]))  # no title in KB
    cited = CitationMetadata(ref_id="REF-A", cited_title="Some Title")
    checked, status, reason = evaluate_h2_checked(cited=cited, metadata=meta, ref_ids=["REF-A"])
    assert checked is False
    assert reason and "title" in reason.lower()


def test_h2_both_cited_one_missing_is_partial():
    meta = RetrievalSetMetadata(
        _meta([("REF-A", "p.1")]),
        ref_metadata={"REF-A": RefMetadata(ref_id="REF-A", doi="10.1/abc")},  # no title
    )
    cited = CitationMetadata(ref_id="REF-A", cited_doi="10.1/abc", cited_title="T")
    checked, status, reason = evaluate_h2_checked(cited=cited, metadata=meta, ref_ids=["REF-A"])
    assert checked is False
    assert status == H2CheckedStatus.PARTIAL
    assert reason and "title" in reason.lower()


def test_h2_empty_retrieval_set_unavailable():
    meta = RetrievalSetMetadata([])
    checked, status, reason = evaluate_h2_checked(cited=None, metadata=meta, ref_ids=[])
    assert checked is False
    assert status == H2CheckedStatus.NOT_APPLICABLE


def test_h2_unavailable_is_not_hallucination_finding():
    """Metadata unavailable must not produce an H2 finding."""
    chunks = [_chunk("FA", "REF-A")]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="text"))
    guard = ClaimGuardService()
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(
            claim_id="C1",
            text="claim",
            anchor_chunk_ids=["FA"],
            cited=CitationMetadata(ref_id="REF-A", cited_doi="10.1/abc"),
        )
    ])
    # KB metadata for REF-A has no DOI -> unavailable, not a finding
    assert out[0].h2_findings == []
    assert out[0].h2_checked is False
    assert out[0].h2_unavailable_reason
    assert out[0].h2_status in (
        H2CheckedStatus.METADATA_UNAVAILABLE.value,
        H2CheckedStatus.PARTIAL.value,
    )


def test_guard_service_h2_status_field_present():
    chunks = [_chunk("FA", "REF-A")]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="text"))
    guard = ClaimGuardService()
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(claim_id="C1", text="x", anchor_chunk_ids=["FA"])
    ])
    assert out[0].h2_status == H2CheckedStatus.CHECKED.value
    assert out[0].h2_checked is True


# ---- integration fixture env switch ----

def test_fixture_env_unset_returns_unavailable():
    from knowledge_curator.mcp_server.evidence_runtime import create_evidence_runtime_from_env

    rt = create_evidence_runtime_from_env(environ={})
    assert rt.retrieval_available is False
    assert rt.integration_fixture is False
    assert rt.unavailability_reason and "not_configured" in rt.unavailability_reason


def test_fixture_env_set_returns_labelled_fixture():
    from knowledge_curator.mcp_server.evidence_runtime import (
        INTEGRATION_FIXTURE_ENV,
        create_evidence_runtime_from_env,
    )

    rt = create_evidence_runtime_from_env(environ={INTEGRATION_FIXTURE_ENV: "1"})
    assert rt.retrieval_available is True
    assert rt.integration_fixture is True
    assert rt.retrieval is not None


def test_fixture_env_other_value_stays_unavailable():
    from knowledge_curator.mcp_server.evidence_runtime import create_evidence_runtime_from_env

    rt = create_evidence_runtime_from_env(environ={"KC_EVIDENCE_INTEGRATION_FIXTURE": "yes"})
    assert rt.retrieval_available is False


def test_app_py_has_no_mojibake():
    src = open("knowledge_curator/mcp_server/app.py", encoding="utf-8").read()
    for bad in ("搂5", "鈥", "撀", "€"):
        assert bad not in src, f"found mojibake {bad!r} in app.py"
    assert "§5.1" in src
