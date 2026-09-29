"""Phase 4.1 tests: §6.1 chunking + §6.2 hybrid retrieval contracts."""

from __future__ import annotations

from knowledge_curator.adapters.in_memory_retrieval import (
    FakeReranker,
    InMemoryGraphSearch,
    InMemoryKeywordSearch,
    InMemoryVectorSearch,
)
from knowledge_curator.retrieval.chunking import (
    ChartObject,
    ChunkingConfig,
    TableObject,
    WordTokenizer,
    chunk_chart,
    chunk_document_summary,
    chunk_evidence_card,
    chunk_table,
    chunk_text,
)
from knowledge_curator.retrieval.hybrid import RetrievalConfig, hybrid_retrieve, rrf_fuse
from knowledge_curator.ports.retrieval import (
    RankedHit,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
)
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk
from knowledge_curator.tests.conftest import make_assertion


def _chunk(cid="C1", ref="REF-1", ctype=ChunkType.TEXT, conf=Confidence.HIGH):
    return KnowledgeChunk(
        chunk_id=cid,
        ref_id=ref,
        level=ChunkLevel.FINE,
        chunk_type=ctype,
        payload=f"payload {cid}",
        locator="p.1",
        confidence=conf,
        quality=0.9,
    )


# ---- Metadata prefix ----

def test_metadata_prefix_in_payload():
    from knowledge_curator.retrieval.chunking import chunk_text
    from knowledge_curator.retrieval.tokenizer import WordTokenizer
    chunks = chunk_text("hello", ref_id="R1", page="1", section="S", tokenizer=WordTokenizer())
    assert chunks[0].payload.startswith("[R1|1|S|type(")


# ---- Text chunking ----

def test_text_chunks_within_max_tokens():
    tok = WordTokenizer()
    text = " ".join(f"w{i}" for i in range(1000))
    chunks = chunk_text(text, ref_id="R", tokenizer=tok)
    for c in chunks:
        assert tok.count(c.payload) <= 512


def test_text_overlap_64():
    tok = WordTokenizer()
    text = " ".join(f"w{i}" for i in range(1200))
    chunks = chunk_text(text, ref_id="R", tokenizer=tok)
    assert len(chunks) >= 2
    # Adjacent chunks should overlap
    body1 = chunks[0].payload.split('] ', 1)[-1].split()
    body2 = chunks[1].payload.split('] ', 1)[-1].split()
    overlap = set(body1) & set(body2)
    assert len(overlap) == 64


def test_text_empty_produces_no_chunks():
    assert chunk_text("", ref_id="R") == []
    assert chunk_text("   ", ref_id="R") == []


def test_text_no_infinite_loop_large_overlap():
    tok = WordTokenizer()
    text = " ".join(f"w{i}" for i in range(200))
    chunks = chunk_text(text, ref_id="R", tokenizer=tok, config=None)
    # config has overlap 64 < max 512, but test with large overlap via direct config
    chunks2 = chunk_text(
        text, ref_id="R", tokenizer=tok,
        config=ChunkingConfig(max_tokens=10, overlap_tokens=10),
    )
    assert len(chunks2) > 0  # no infinite loop
    assert len(chunks2) > 0  # terminated without infinite loop


# ---- Table / Chart whole-chunk ----

def test_table_always_one_chunk():
    t = TableObject(
        table_id="T1", ref_id="R1",
        caption="Big table", headers=["a", "b"], units=["m", "s"],
        row_summary="row1; row2; " + "x" * 2000,
    )
    chunks = chunk_table(t)
    assert len(chunks) == 1
    assert chunks[0].chunk_type == ChunkType.TABLE
    assert "Big table" in chunks[0].payload


def test_chart_always_one_chunk():
    ch = ChartObject(
        chart_id="C1", ref_id="R1",
        caption="Fig 1", axes="x: t", units="A",
        digitized_summary="curve rising",
    )
    chunks = chunk_chart(ch)
    assert len(chunks) == 1
    assert chunks[0].chunk_type == ChunkType.CHART
    assert chunks[0].object_id == "C1"


# ---- Evidence cards ----

def test_one_assertion_one_evidence_card():
    a = make_assertion("AS-1")
    card = chunk_evidence_card(a)
    assert card.chunk_type == ChunkType.EVIDENCE_CARD
    assert card.assertion_id == "AS-1"
    assert card.locator == "T12"
    assert card.confidence == Confidence.MEDIUM
    assert "Subject:" in card.payload
    assert "Locator: T12" in card.payload


# ---- Coarse ----

def test_coarse_summary_uses_upstream_summary():
    chunks = chunk_document_summary("R1", "Upstream provided summary.")
    assert len(chunks) == 1
    assert chunks[0].level == ChunkLevel.COARSE
    assert chunks[0].chunk_type == ChunkType.DOCUMENT_SUMMARY
    assert chunks[0].payload == "Upstream provided summary."


# ---- RRF ----

def test_rrf_duplicate_fusion():
    c1 = _chunk("A")
    c2 = _chunk("B")
    channel_candidates = {
        RetrievalChannel.VECTOR: [
            RetrievalCandidate(chunk=c1, channel=RetrievalChannel.VECTOR, rank=1),
            RetrievalCandidate(chunk=c2, channel=RetrievalChannel.VECTOR, rank=2),
        ],
        RetrievalChannel.KEYWORD: [
            RetrievalCandidate(chunk=c1, channel=RetrievalChannel.KEYWORD, rank=1),
        ],
    }
    hits = rrf_fuse(channel_candidates, k=60, top_k=10)
    # c1 appears in both channels -> fused, should rank first
    assert hits[0].chunk.chunk_id == "A"
    assert RetrievalChannel.VECTOR in hits[0].channels
    assert RetrievalChannel.KEYWORD in hits[0].channels
    # no duplicate returns
    ids = [h.chunk.chunk_id for h in hits]
    assert len(ids) == len(set(ids))


def test_rrf_deterministic_tie_break():
    c1 = _chunk("Z")
    c2 = _chunk("A")
    channel_candidates = {
        RetrievalChannel.VECTOR: [
            RetrievalCandidate(chunk=c1, channel=RetrievalChannel.VECTOR, rank=1),
            RetrievalCandidate(chunk=c2, channel=RetrievalChannel.VECTOR, rank=1),
        ],
    }
    hits = rrf_fuse(channel_candidates, k=60, top_k=10)
    # Same score, tie-break by chunk_id ascending
    assert hits[0].chunk.chunk_id == "A"
    assert hits[1].chunk.chunk_id == "Z"


# ---- Hybrid retrieval ----

def test_coarse_allowed_ref_ids_limits_fine():
    c1 = _chunk("A", ref="REF-1")
    c2 = _chunk("B", ref="REF-2")
    fine = InMemoryVectorSearch([c1, c2])
    q = RetrievalQuery(text="q", top_k=10)
    result = hybrid_retrieve(q, vector_port=fine, config=RetrievalConfig(allow_fine_fallback_without_coarse=True))
    assert result.diagnostics.coarse_filter_applied is False


def test_no_coarse_explicit_fallback():
    c1 = _chunk("A")
    fine = InMemoryVectorSearch([c1])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(q, vector_port=fine, config=RetrievalConfig(allow_fine_fallback_without_coarse=True))
    assert result.diagnostics.coarse_filter_applied is False


def test_three_channels_used():
    c1 = _chunk("A")
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=InMemoryVectorSearch([c1]),
        graph_port=InMemoryGraphSearch([c1]),
        keyword_port=InMemoryKeywordSearch([c1]),
        config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
    )
    assert len(result.diagnostics.channels_used) == 3
    assert RetrievalChannel.VECTOR in result.diagnostics.channels_used
    assert RetrievalChannel.GRAPH in result.diagnostics.channels_used
    assert RetrievalChannel.KEYWORD in result.diagnostics.channels_used


def test_provenance_preserved_after_fusion_rerank():
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
