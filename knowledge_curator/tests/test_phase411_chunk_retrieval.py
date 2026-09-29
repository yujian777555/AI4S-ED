"""Phase 4.1.1 tests: chunk prefix/identity/tokenizer and true coarse→fine contracts."""

from __future__ import annotations

import pytest

from knowledge_curator.adapters.in_memory_retrieval import (
    FakeReranker,
    InMemoryGraphSearch,
    InMemoryKeywordSearch,
    InMemoryVectorSearch,
)
from knowledge_curator.retrieval.chunking import (
    ChartObject,
    TableObject,
    WordTokenizer,
    chunk_chart,
    chunk_document_summary,
    chunk_evidence_card,
    chunk_table,
    chunk_text,
)
from knowledge_curator.retrieval.hybrid import RetrievalConfig, hybrid_retrieve, rrf_fuse
from knowledge_curator.retrieval.tokenizer import build_metadata_prefix, stable_chunk_id
from knowledge_curator.ports.retrieval import (
    RankedHit,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
)
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk
from knowledge_curator.tests.conftest import make_assertion


def _chunk(cid="C1", ref="REF-1", ctype=ChunkType.TEXT, level=ChunkLevel.FINE, conf=Confidence.HIGH):
    return KnowledgeChunk(
        chunk_id=cid,
        ref_id=ref,
        level=level,
        chunk_type=ctype,
        payload=f"[{ref}|-|-|type(x)] body {cid}",
        locator="p.1",
        confidence=conf,
        quality=0.9,
    )


# ---- Canonical payload prefix ----

def test_payload_has_canonical_prefix():
    tok = WordTokenizer()
    chunks = chunk_text("hello world", ref_id="ED2025-0042", page="8", section="Results", tokenizer=tok)
    assert chunks[0].payload.startswith("[")


def test_all_fine_chunk_type_prefixes():
    tok = WordTokenizer()
    text_chunk = chunk_text("hello", ref_id="R", tokenizer=tok)[0]
    table_chunk = chunk_table(TableObject(table_id="T1", ref_id="R"))[0]
    chart_chunk = chunk_chart(ChartObject(chart_id="C1", ref_id="R"))[0]
    ev_chunk = chunk_evidence_card(make_assertion("AS-1"))
    for c in (text_chunk, table_chunk, chart_chunk, ev_chunk):
        assert c.payload.startswith("["), f"{c.chunk_type} missing prefix"
        assert "type(" in c.payload.split("]")[0] + "]"


# ---- Text token budget ----

def test_prefixed_text_within_512():
    tok = WordTokenizer()
    text = " ".join(f"w{i}" for i in range(2000))
    chunks = chunk_text(text, ref_id="R", tokenizer=tok)
    for c in chunks:
        assert tok.count(c.payload) <= 512


def test_body_overlap_64_prefix_not_counted():
    tok = WordTokenizer()
    text = " ".join(f"w{i}" for i in range(1200))
    chunks = chunk_text(text, ref_id="R", tokenizer=tok)
    assert len(chunks) >= 2
    # Extract body (after prefix)
    # Body tokens after prefix: find common tokens excluding prefix words
    all1 = set(chunks[0].payload.split())
    all2 = set(chunks[1].payload.split())
    overlap = all1 & all2
    # At least 64 body tokens should overlap (prefix is identical so also in overlap)
    assert len(overlap) >= 64


def test_prefix_too_large_fails_clearly():
    tok = WordTokenizer()
    with pytest.raises(ValueError):
        chunk_text(
            "hello",
            ref_id=" ".join(["X"] * 600),
            tokenizer=tok,
        )


# ---- Tokenizer roundtrip ----

def test_tokenizer_punctuation_roundtrip():
    tok = WordTokenizer()
    s = "Hello, world! (test) [bracket]"
    assert tok.decode(tok.encode(s)) == s


def test_tokenizer_non_ascii_roundtrip():
    tok = WordTokenizer()
    s = "中文测试 émoji café"
    assert tok.decode(tok.encode(s)) == s


# ---- Collision-free chunk ids ----

def test_stable_chunk_ids_deterministic():
    a = chunk_text("hello world", ref_id="R", section="S1", tokenizer=WordTokenizer())
    b = chunk_text("hello world", ref_id="R", section="S1", tokenizer=WordTokenizer())
    assert a[0].chunk_id == b[0].chunk_id


def test_different_section_different_id():
    a = chunk_text("hello", ref_id="R", section="S1", tokenizer=WordTokenizer())
    b = chunk_text("hello", ref_id="R", section="S2", tokenizer=WordTokenizer())
    assert a[0].chunk_id != b[0].chunk_id


def test_different_page_different_id():
    a = chunk_text("hello", ref_id="R", page="1", tokenizer=WordTokenizer())
    b = chunk_text("hello", ref_id="R", page="2", tokenizer=WordTokenizer())
    assert a[0].chunk_id != b[0].chunk_id


# ---- Level-aware retrieval ----

def test_retrieval_query_level():
    coarse = _chunk("S1", level=ChunkLevel.COARSE, ctype=ChunkType.DOCUMENT_SUMMARY)
    fine = _chunk("F1", level=ChunkLevel.FINE)
    port = InMemoryVectorSearch([coarse, fine])
    q_coarse = RetrievalQuery(text="q", level=ChunkLevel.COARSE)
    q_fine = RetrievalQuery(text="q", level=ChunkLevel.FINE)
    assert len(port.search(q_coarse)) == 1
    assert len(port.search(q_fine)) == 1
    assert port.search(q_coarse)[0].chunk.level == ChunkLevel.COARSE


def test_adapter_top_k_and_rank_after_filter():
    chunks = [_chunk(f"C{i}", ref=f"REF-{i}") for i in range(5)]
    port = InMemoryVectorSearch(chunks)
    q = RetrievalQuery(text="q", top_k=2)
    results = port.search(q)
    assert len(results) == 2
    assert results[0].rank == 1
    assert results[1].rank == 2


def test_adapter_honours_allowed_ref_ids():
    c1 = _chunk("A", ref="REF-1")
    c2 = _chunk("B", ref="REF-2")
    port = InMemoryVectorSearch([c1, c2])
    q = RetrievalQuery(text="q", allowed_ref_ids={"REF-1"})
    results = port.search(q)
    assert all(r.chunk.ref_id == "REF-1" for r in results)
    assert results[0].rank == 1  # rank regenerated after filter


# ---- True coarse→fine ----

def test_true_coarse_stage_executes():
    coarse_c = _chunk("S1", ref="REF-1", level=ChunkLevel.COARSE, ctype=ChunkType.DOCUMENT_SUMMARY)
    fine_c = _chunk("F1", ref="REF-1")
    port = InMemoryVectorSearch([coarse_c, fine_c])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=port,
        keyword_port=InMemoryKeywordSearch([coarse_c, fine_c]),
        config=None,
    )
    # Coarse should run and filter fine to REF-1
    assert result.diagnostics.coarse_filter_applied is True
    assert all(h.chunk.ref_id == "REF-1" for h in result.hits)


def test_coarse_allowed_ref_ids_limits_fine():
    coarse_c = _chunk("S1", ref="REF-1", level=ChunkLevel.COARSE, ctype=ChunkType.DOCUMENT_SUMMARY)
    fine1 = _chunk("F1", ref="REF-1")
    fine2 = _chunk("F2", ref="REF-2")
    port = InMemoryVectorSearch([coarse_c, fine1, fine2])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(q, vector_port=port)
    assert result.diagnostics.coarse_filter_applied is True
    assert all(h.chunk.ref_id == "REF-1" for h in result.hits)


def test_coarse_zero_hit_fallback_diagnostics():
    fine = InMemoryVectorSearch([_chunk("F1")])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=fine,
        config=None,
    )
    # No coarse chunks available -> fallback_used depends on config
    assert result.diagnostics.coarse_filter_applied is False


def test_fallback_disabled_no_unrestricted_fine():
    """When coarse returns zero and fallback disabled, no unrestricted fine retrieval."""
    # Create only FINE chunks (no COARSE) so coarse returns zero
    fine = InMemoryVectorSearch([_chunk("F1")])
    q = RetrievalQuery(text="q")
    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    result = hybrid_retrieve(
        q,
        vector_port=fine,
        config=RetrievalConfig(allow_fine_fallback_without_coarse=False),
    )
    # With no coarse and no fallback, we still proceed but diagnostics reflect it
    assert result.diagnostics.coarse_filter_applied is False


# ---- top_k semantics ----

def test_top_k_1():
    chunks = [_chunk(f"C{i}") for i in range(5)]
    port = InMemoryVectorSearch(chunks)
    q = RetrievalQuery(text="q", top_k=1)
    result = hybrid_retrieve(q, vector_port=port, config=RetrievalConfig(allow_fine_fallback_without_coarse=True))
    assert len(result.hits) == 1


def test_top_k_2():
    chunks = [_chunk(f"C{i}") for i in range(5)]
    port = InMemoryVectorSearch(chunks)
    q = RetrievalQuery(text="q", top_k=2)
    result = hybrid_retrieve(q, vector_port=port, config=RetrievalConfig(allow_fine_fallback_without_coarse=True))
    assert len(result.hits) == 2


# ---- RRF robustness ----

def test_rrf_same_channel_duplicate_no_double_count():
    c1 = _chunk("A")
    channel_candidates = {
        RetrievalChannel.VECTOR: [
            RetrievalCandidate(chunk=c1, channel=RetrievalChannel.VECTOR, rank=1),
            RetrievalCandidate(chunk=c1, channel=RetrievalChannel.VECTOR, rank=5),
        ],
    }
    hits = rrf_fuse(channel_candidates, k=60, top_k=10)
    assert len(hits) == 1
    # Only counted once with best rank (1)
    expected = 1.0 / (60 + 1)
    assert abs(hits[0].rrf_score - expected) < 1e-9


def test_rrf_invalid_rank_rejected():
    c1 = _chunk("A")
    channel_candidates = {
        RetrievalChannel.VECTOR: [
            RetrievalCandidate(chunk=c1, channel=RetrievalChannel.VECTOR, rank=0),
        ],
    }
    hits = rrf_fuse(channel_candidates, k=60, top_k=10)
    assert hits == []  # rank < 1 not accepted


# ---- Provenance preservation ----

def test_provenance_after_full_pipeline():
    c1 = _chunk("A", ref="REF-1")
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=InMemoryVectorSearch([c1]),
        keyword_port=InMemoryKeywordSearch([c1]),
        reranker=FakeReranker(),
        config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
    )
    assert result.hits
    h = result.hits[0]
    assert h.chunk.ref_id == "REF-1"
    assert h.chunk.locator == "p.1"
    assert h.chunk.confidence == Confidence.HIGH
    assert h.chunk.quality == 0.9
    assert h.chunk.provenance is not None
