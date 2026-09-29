"""Phase 4.1.2 tests: tokenizer, payload budget, RRF best-rank, coarse fusion, fallback."""

from __future__ import annotations

import pytest

from knowledge_curator.adapters.in_memory_retrieval import (
    InMemoryKeywordSearch,
    InMemoryVectorSearch,
)
from knowledge_curator.retrieval.chunking import WordTokenizer, chunk_text
from knowledge_curator.retrieval.hybrid import RetrievalConfig, hybrid_retrieve, rrf_fuse
from knowledge_curator.retrieval.tokenizer import build_metadata_prefix
from knowledge_curator.ports.retrieval import (
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
)
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk


def _chunk(cid="C1", ref="REF-1", level=ChunkLevel.FINE, ctype=ChunkType.TEXT):
    return KnowledgeChunk(
        chunk_id=cid,
        ref_id=ref,
        level=level,
        chunk_type=ctype,
        payload=f"[{ref}|-|-|type(x)] body {cid}",
        locator="p.1",
    )


# ---- Tokenizer exact roundtrip ----

def test_tokenizer_repeated_spaces_roundtrip():
    tok = WordTokenizer()
    s = "a  b   c"
    assert tok.decode(tok.encode(s)) == s


def test_tokenizer_newline_roundtrip():
    tok = WordTokenizer()
    s = "line1\nline2\n\nline3"
    assert tok.decode(tok.encode(s)) == s


def test_tokenizer_chinese_non_ascii_roundtrip():
    tok = WordTokenizer()
    s = "中文测试 émoji café 日本語"
    assert tok.decode(tok.encode(s)) == s


def test_tokenizer_punctuation_roundtrip():
    tok = WordTokenizer()
    s = "Hello, world! (test) [bracket] {brace}"
    assert tok.decode(tok.encode(s)) == s


# ---- Full payload token budget ----

def test_full_payload_within_max_tokens():
    tok = WordTokenizer()
    text = " ".join(f"w{i}" for i in range(2000))
    chunks = chunk_text(text, ref_id="R", tokenizer=tok)
    for c in chunks:
        assert tok.count(c.payload) <= 512


def test_boundary_sensitive_tokenizer_shrinks_safely():
    """Fake tokenizer where count(prefix+body) != count(prefix)+count(body)."""

    class BoundaryTokenizer:
        def encode(self, text: str) -> list[str]:
            return text.split()

        def decode(self, tokens: list[str]) -> str:
            return " ".join(tokens)

        def count(self, text: str) -> int:
            # Boundary-sensitive: combined tokens cost more
            n = len(text.split())
            return n + (2 if len(text.split()) > 1 else 0)

    tok = BoundaryTokenizer()
    text = " ".join(f"w{i}" for i in range(600))
    chunks = chunk_text(text, ref_id="R", tokenizer=tok)
    for c in chunks:
        assert tok.count(c.payload) <= 512


def test_prefix_too_large_fails():
    tok = WordTokenizer()
    with pytest.raises(ValueError):
        chunk_text("hi", ref_id=" ".join(["X"] * 600), tokenizer=tok)


# ---- RRF best-rank duplicate ----

def test_rrf_duplicate_rank5_then_rank1_uses_best():
    c = _chunk("A")
    candidates = {
        RetrievalChannel.VECTOR: [
            RetrievalCandidate(chunk=c, channel=RetrievalChannel.VECTOR, rank=5),
            RetrievalCandidate(chunk=c, channel=RetrievalChannel.VECTOR, rank=1),
        ],
    }
    hits = rrf_fuse(candidates, k=60, top_k=10)
    assert len(hits) == 1
    expected = 1.0 / (60 + 1)  # best rank = 1
    assert abs(hits[0].rrf_score - expected) < 1e-9


def test_rrf_duplicate_rank1_then_rank5_same_result():
    c = _chunk("A")
    candidates = {
        RetrievalChannel.VECTOR: [
            RetrievalCandidate(chunk=c, channel=RetrievalChannel.VECTOR, rank=1),
            RetrievalCandidate(chunk=c, channel=RetrievalChannel.VECTOR, rank=5),
        ],
    }
    hits = rrf_fuse(candidates, k=60, top_k=10)
    expected = 1.0 / (60 + 1)
    assert abs(hits[0].rrf_score - expected) < 1e-9


def test_rrf_order_independent():
    c = _chunk("A")
    r1 = rrf_fuse(
        {RetrievalChannel.VECTOR: [
            RetrievalCandidate(chunk=c, channel=RetrievalChannel.VECTOR, rank=5),
            RetrievalCandidate(chunk=c, channel=RetrievalChannel.VECTOR, rank=1),
        ]},
        k=60,
    )
    r2 = rrf_fuse(
        {RetrievalChannel.VECTOR: [
            RetrievalCandidate(chunk=c, channel=RetrievalChannel.VECTOR, rank=1),
            RetrievalCandidate(chunk=c, channel=RetrievalChannel.VECTOR, rank=5),
        ]},
        k=60,
    )
    assert r1[0].rrf_score == r2[0].rrf_score


# ---- Coarse global fusion ----

def test_coarse_vector_keyword_global_fusion():
    coarse_c1 = _chunk("S1", ref="REF-1", level=ChunkLevel.COARSE, ctype=ChunkType.DOCUMENT_SUMMARY)
    coarse_c2 = _chunk("S2", ref="REF-2", level=ChunkLevel.COARSE, ctype=ChunkType.DOCUMENT_SUMMARY)
    fine1 = _chunk("F1", ref="REF-1")
    fine2 = _chunk("F2", ref="REF-2")
    port = InMemoryVectorSearch([coarse_c1, coarse_c2, fine1, fine2])
    kport = InMemoryKeywordSearch([coarse_c1, coarse_c2, fine1, fine2])
    q = RetrievalQuery(text="q", top_k=10)
    result = hybrid_retrieve(
        q,
        vector_port=port,
        keyword_port=kport,
        config=RetrievalConfig(coarse_top_k=10),
    )
    assert result.diagnostics.coarse_filter_applied is True
    assert RetrievalChannel.VECTOR in result.diagnostics.coarse_channels_used
    assert RetrievalChannel.KEYWORD in result.diagnostics.coarse_channels_used
    # Global coarse_top_k: fused hits limited to coarse_top_k
    assert result.diagnostics.coarse_fused_hit_count <= 10


def test_coarse_top_k_global_limit():
    coarse_chunks = [_chunk(f"S{i}", ref=f"REF-{i}", level=ChunkLevel.COARSE, ctype=ChunkType.DOCUMENT_SUMMARY) for i in range(5)]
    fine_chunks = [_chunk(f"F{i}", ref=f"REF-{i}") for i in range(5)]
    port = InMemoryVectorSearch(coarse_chunks + fine_chunks)
    q = RetrievalQuery(text="q", top_k=10)
    result = hybrid_retrieve(
        q,
        vector_port=port,
        keyword_port=InMemoryKeywordSearch(coarse_chunks + fine_chunks),
        config=RetrievalConfig(coarse_top_k=2),
    )
    # Only 2 coarse refs should pass filter
    assert result.diagnostics.coarse_fused_hit_count <= 2
    assert len({h.chunk.ref_id for h in result.hits}) <= 2


def test_coarse_duplicate_fusion():
    coarse_c = _chunk("S1", ref="REF-1", level=ChunkLevel.COARSE, ctype=ChunkType.DOCUMENT_SUMMARY)
    port = InMemoryVectorSearch([coarse_c])
    kport = InMemoryKeywordSearch([coarse_c])
    q = RetrievalQuery(text="q", top_k=10)
    result = hybrid_retrieve(q, vector_port=port, keyword_port=kport)
    # Same chunk in both coarse channels -> fused, not duplicated
    assert result.diagnostics.coarse_fused_hit_count == 1


# ---- Fallback consistency ----

def test_coarse_absent_fallback_false_zero_hits():
    fine = InMemoryVectorSearch([_chunk("F1")])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=fine,
        config=RetrievalConfig(allow_fine_fallback_without_coarse=False),
    )
    assert result.hits == []
    assert result.diagnostics.fallback_used is False


def test_coarse_absent_fallback_true_fine_retrieval():
    fine = InMemoryVectorSearch([_chunk("F1")])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=fine,
        config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
    )
    assert len(result.hits) >= 1
    assert result.diagnostics.fallback_used is True


def test_coarse_zero_hit_fallback_false_zero_hits():
    # Only FINE chunks exist -> coarse returns zero
    fine = InMemoryVectorSearch([_chunk("F1")])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=fine,
        keyword_port=InMemoryKeywordSearch([_chunk("F1")]),
        config=RetrievalConfig(allow_fine_fallback_without_coarse=False),
    )
    assert result.hits == []
    assert result.diagnostics.fallback_used is False


def test_coarse_zero_hit_fallback_true_fine_retrieval():
    fine = InMemoryVectorSearch([_chunk("F1")])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=fine,
        keyword_port=InMemoryKeywordSearch([_chunk("F1")]),
        config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
    )
    assert len(result.hits) >= 1
    assert result.diagnostics.fallback_used is True


# ---- Provenance preservation ----

def test_provenance_preserved():
    c = _chunk("A", ref="REF-1")
    port = InMemoryVectorSearch([c])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=port,
        config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
    )
    assert result.hits
    h = result.hits[0]
    assert h.chunk.ref_id == "REF-1"
    assert h.chunk.locator == "p.1"
    assert h.chunk.chunk_type == ChunkType.TEXT
