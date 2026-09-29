"""Phase 4.3 tests: EvidenceRetrievalService, normalization, guards, MCP tools."""

from __future__ import annotations

import pytest

from knowledge_curator.adapters import FakeMechanismValidator
from knowledge_curator.adapters.in_memory_retrieval import (
    FakeReranker,
    InMemoryKeywordSearch,
    InMemoryVectorSearch,
)
from knowledge_curator.ports.evidence_store import CitationMetadata
from knowledge_curator.ports.retrieval import RankedHit, RetrievalChannel
from knowledge_curator.retrieval.evidence_models import (
    build_evidence_anchor,
    normalize_hit_to_record,
)
from knowledge_curator.retrieval.evidence_service import (
    EvidenceRequest,
    EvidenceRetrievalService,
)
from knowledge_curator.retrieval.guard_service import ClaimGuardService, ProposedClaimInput
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk


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


def _hit(chunk, rank=1, channels=None):
    return RankedHit(
        chunk=chunk,
        rrf_score=1.0 / (60 + rank),
        channels=channels or [RetrievalChannel.VECTOR, RetrievalChannel.KEYWORD],
        rank=rank,
    )


def _service(chunks):
    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    return EvidenceRetrievalService(
        vector_port=InMemoryVectorSearch(chunks),
        keyword_port=InMemoryKeywordSearch(chunks),
        reranker=FakeReranker(),
        # Unit tests may run fine-only corpora; production smoke uses False.
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
    )


# ---- evidence normalization fail-closed ----

def test_normalize_missing_confidence_not_guardable():
    rec = normalize_hit_to_record(_hit(_chunk("A", "REF-1", confidence=None)))
    assert rec.guardable_as_anchor is False
    assert "missing_confidence" in rec.unguardable_reasons
    assert build_evidence_anchor(rec) is None


def test_normalize_missing_locator_not_guardable():
    rec = normalize_hit_to_record(_hit(_chunk("A", "REF-1", locator=None)))
    assert rec.guardable_as_anchor is False
    assert "missing_locator" in rec.unguardable_reasons
    assert build_evidence_anchor(rec) is None


def test_normalize_guardable_high_record():
    rec = normalize_hit_to_record(_hit(_chunk("A", "REF-1")))
    assert rec.guardable_as_anchor is True
    anchor = build_evidence_anchor(rec)
    assert anchor is not None
    assert anchor.confidence == Confidence.HIGH
    assert anchor.evidence_type.value == "literature"


def test_never_infer_graph_from_channel():
    """RetrievalChannel.GRAPH must not imply EvidenceType.GRAPH."""
    rec = normalize_hit_to_record(
        _hit(_chunk("A", "REF-1"), channels=[RetrievalChannel.GRAPH])
    )
    assert rec.evidence_type.value != "graph"
    assert rec.evidence_type.value == "literature"


def test_explicit_provenance_evidence_type_wins():
    c = _chunk("A", "REF-1", provenance={"evidence_type": "experiment", "locator": "p.1"})
    rec = normalize_hit_to_record(_hit(c))
    assert rec.evidence_type.value == "experiment"


# ---- EvidenceRetrievalService ----

def test_service_requires_backends():
    svc = EvidenceRetrievalService()
    with pytest.raises(RuntimeError, match="retrieval_unavailable"):
        svc.retrieve(EvidenceRequest(query="q"))


def test_service_indexes_and_returns_bundle():
    chunks = [
        _chunk("CA", "REF-A", "alpha coarse", level=ChunkLevel.COARSE),
        _chunk("FA", "REF-A", "alpha fine"),
    ]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="alpha", top_k=5))
    assert bundle.bundle_id.startswith("evb_")
    assert bundle.evidence_records
    assert any(r.chunk_id == "FA" for r in bundle.evidence_records)
    assert bundle.abstain.retrieval_support_checked is False


def test_coverage_requires_guardable_evidence():
    chunks = [
        _chunk("CA", "REF-A", "alpha coarse", level=ChunkLevel.COARSE),
        _chunk("FA", "REF-A", "alpha fine", confidence=None),  # unguardable
        _chunk("FB", "REF-B", "beta fine"),
    ]
    svc = _service(chunks)
    bundle = svc.retrieve(
        EvidenceRequest(
            query="alpha",
            subqueries=["alpha", "beta"],
            coverage_keys=["sq1", "sq2"],
            required_coverage_keys=["sq1", "sq2"],
            top_k=5,
        )
    )
    states = {c.coverage_key: c.state.value for c in bundle.coverage}
    # sq1 only has unguardable confidence-missing hit -> not covered
    assert states["sq1"] == "not_covered"
    assert bundle.abstain.abstain is True
    assert "subquestion_not_covered" in bundle.abstain.reasons


def test_cg017_no_raw_score_as_support():
    chunks = [_chunk("FA", "REF-A", "alpha")]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="alpha"))
    assert bundle.abstain.retrieval_support_checked is False
    # Must not report low_retrieval_support from raw RRF scores
    assert "low_retrieval_support" not in bundle.abstain.reasons


def test_cg017_calibrated_support_can_trigger_low():
    chunks = [_chunk("FA", "REF-A", "alpha")]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="alpha", calibrated_support=0.1))
    assert bundle.abstain.retrieval_support_checked is True
    assert "low_retrieval_support" in bundle.abstain.reasons


# ---- Claim guard: anchor binding + policies ----

def test_high_evidence_factual_allowed():
    chunks = [_chunk("CA", "REF-A", "coarse", level=ChunkLevel.COARSE), _chunk("FA", "REF-A")]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="text"))
    guard = ClaimGuardService(mechanism_validator=FakeMechanismValidator())
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(claim_id="C1", text="claim", anchor_chunk_ids=["FA"])
    ])
    assert out[0].policy.policy.value == "factual_allowed"
    assert out[0].abstain.abstain is False
    assert out[0].h1.findings == []


def test_medium_evidence_caveated_only():
    chunks = [_chunk("FA", "REF-A", confidence=Confidence.MEDIUM)]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="text"))
    guard = ClaimGuardService()
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(claim_id="C1", text="claim", anchor_chunk_ids=["FA"])
    ])
    assert out[0].policy.policy.value == "caveated_only"


def test_hypothesis_critical_numeric_abstains():
    chunks = [_chunk("FA", "REF-A", confidence=Confidence.HYPOTHESIS)]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="text"))
    guard = ClaimGuardService()
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(
            claim_id="C1",
            text="critical numeric",
            anchor_chunk_ids=["FA"],
            is_critical_numeric=True,
        )
    ])
    assert out[0].abstain.abstain is True
    assert any(r.value == "critical_numeric_only_hypothesis_or_pending" for r in out[0].abstain.reasons)


def test_unknown_anchor_chunk_id_h1_and_unresolved():
    chunks = [_chunk("FA", "REF-A")]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="text"))
    guard = ClaimGuardService()
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(claim_id="C1", text="claim", anchor_chunk_ids=["NOPE"])
    ])
    assert out[0].unresolved_anchor_chunk_ids == ["NOPE"]
    assert out[0].resolved_anchors == []
    assert out[0].h1.findings  # no evidence anchor -> H1
    assert out[0].policy.policy.value == "abstain"


def test_missing_subquery_abstains():
    # Only unguardable hits (missing confidence) -> subquery is not covered.
    chunks = [
        _chunk("CA", "REF-A", "coarse", level=ChunkLevel.COARSE),
        _chunk("FA", "REF-A", confidence=None),
    ]
    svc = _service(chunks)
    bundle = svc.retrieve(
        EvidenceRequest(
            query="text",
            subqueries=["text"],
            coverage_keys=["sq1"],
            required_coverage_keys=["sq1"],
        )
    )
    states = {c.coverage_key: c.state.value for c in bundle.coverage}
    assert states["sq1"] == "not_covered"
    assert bundle.abstain.abstain is True
    assert "subquestion_not_covered" in bundle.abstain.reasons

    guard = ClaimGuardService()
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(
            claim_id="C1",
            text="claim",
            anchor_chunk_ids=["FA"],
            coverage_key="sq1",
        )
    ])
    # Claim references an uncovered subquery -> Abstain
    assert out[0].abstain.abstain is True


def test_disjoint_numeric_ranges_conflict_disclosure():
    chunks = [_chunk("FA", "REF-A")]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="text"))
    guard = ClaimGuardService()
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(
            claim_id="C1",
            text="numeric",
            anchor_chunk_ids=["FA"],
            numeric_source_ranges=[(1.0, 1.2), (2.0, 2.5)],
        )
    ])
    assert out[0].policy.policy.value == "conflict_disclosure_required"
    assert out[0].numeric_conflict_policy is not None


def test_h3_violation_finding():
    chunks = [_chunk("FA", "REF-A")]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="text"))
    validator = FakeMechanismValidator(violated_ids=["A1"], ok=False, messages=["bad mechanism"])
    guard = ClaimGuardService(mechanism_validator=validator)
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(
            claim_id="C1",
            text="mechanism claim",
            anchor_chunk_ids=["FA"],
            assertion=_assertion("A1", "REF-A"),
        )
    ])
    assert out[0].h3.status.value == "checked"
    assert out[0].h3.findings


def test_h3_unavailable_when_no_validator():
    chunks = [_chunk("FA", "REF-A")]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="text"))
    guard = ClaimGuardService(mechanism_validator=None)
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(
            claim_id="C1",
            text="m",
            anchor_chunk_ids=["FA"],
            assertion=_assertion("A1", "REF-A"),
        )
    ])
    assert out[0].h3.status.value == "mechanism_unavailable"


def test_private_unauthorized_abstain():
    chunks = [_chunk("FA", "REF-A")]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="text"))
    guard = ClaimGuardService()
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(
            claim_id="C1",
            text="private",
            anchor_chunk_ids=["FA"],
            private_data_unauthorized=True,
        )
    ])
    assert out[0].abstain.abstain is True
    assert any(r.value == "private_data_unauthorized" for r in out[0].abstain.reasons)


def test_h1_retrieval_set_binding_rejects_unretrieved_ref():
    """A real KB ref that was NOT in this retrieval set cannot be a valid anchor."""
    chunks = [_chunk("FA", "REF-IN-SET")]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="alpha"))
    # Fabricate an anchor pointing at REF-OUT which is not in the bundle
    guard = ClaimGuardService()
    out = guard.validate_claims(bundle, [
        ProposedClaimInput(claim_id="C1", text="x", anchor_chunk_ids=["FA"])
    ])
    # FA is in set -> ok
    assert out[0].resolved_anchors
    # Direct H1 against retrieval metadata: fake ref fails
    from knowledge_curator.retrieval.retrieval_metadata import RetrievalSetMetadata

    meta = RetrievalSetMetadata(bundle.evidence_records)
    assert meta.ref_exists("REF-IN-SET") is True
    assert meta.ref_exists("REF-OUT") is False
    assert meta.anchor_exists("REF-IN-SET", "p.1") is True
    assert meta.anchor_exists("REF-OUT", "p.8") is False


def test_provenance_survives_to_record():
    chunks = [
        _chunk(
            "FA",
            "REF-A",
            provenance={
                "evidence_type": "literature",
                "locator": "p.3",
                "sentence": "the sentence",
                "access_pointer": "https://example.org/a",
            },
            locator="p.3",
            section="Results",
        )
    ]
    svc = _service(chunks)
    bundle = svc.retrieve(EvidenceRequest(query="text"))
    rec = next(r for r in bundle.evidence_records if r.chunk_id == "FA")
    assert rec.sentence_or_cell == "the sentence"
    assert rec.access_pointer == "https://example.org/a"
    assert rec.locator == "p.3"
    assert rec.channels
    assert rec.rank >= 1


def _assertion(aid, ref_id):
    from knowledge_curator.schemas.assertions import (
        ClaimType,
        ObjectValue,
        SourceClaimOrigin,
        Subject,
        ValueType,
    )
    from knowledge_curator.schemas.assertions import Assertion

    return Assertion(
        id=aid,
        ref_id=ref_id,
        subject=Subject(eddo_class="X", resolved_entity="x", original_mention="x"),
        property="p",
        object=ObjectValue(value=1.0, unit=None, value_type=ValueType.NUMBER),
        claim_type=ClaimType.MEASUREMENT,
        source_claim_origin=SourceClaimOrigin.PRIMARY,
    )
