"""Phase 4.1.3 tests: tokenizer-driven windows, format preservation, coarse diagnostics."""

from __future__ import annotations

import pytest

from knowledge_curator.adapters.in_memory_retrieval import (
    InMemoryKeywordSearch,
    InMemoryVectorSearch,
)
from knowledge_curator.retrieval.chunking import WordTokenizer, chunk_text
from knowledge_curator.retrieval.hybrid import (
    COARSE_ABSENT,
    COARSE_HIT,
    COARSE_ZERO,
    RetrievalConfig,
    hybrid_retrieve,
)
from knowledge_curator.retrieval.tokenizer import build_metadata_prefix
from knowledge_curator.ports.retrieval import RetrievalQuery
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


# ---- Format preservation ----

def test_repeated_spaces_preserved():
    tok = WordTokenizer()
    s = "a  b   c"
    chunks = chunk_text(s, ref_id="R", tokenizer=tok)
    body = chunks[0].payload.split("] ", 1)[-1]
    assert body == "a  b   c"


def test_newlines_preserved():
    tok = WordTokenizer()
    s = "line1\nline2\n\nline3"
    chunks = chunk_text(s, ref_id="R", tokenizer=tok)
    body = chunks[0].payload.split("] ", 1)[-1]
    assert "line1\nline2\n\nline3" in body


def test_non_ascii_preserved():
    tok = WordTokenizer()
    s = "中文测试 émoji café"
    chunks = chunk_text(s, ref_id="R", tokenizer=tok)
    body = chunks[0].payload.split("] ", 1)[-1]
    assert body == "中文测试 émoji café"


# ---- Tokenizer-driven windows ----

def test_encode_controls_window_not_str_split():
    """Overlapping windows must use encoded tokens, not Python words."""
    tok = WordTokenizer()
    # 200 encoded tokens (whitespace+words interleaved)
    text = " ".join(f"w{i}" for i in range(200))
    chunks = chunk_text(text, ref_id="R", tokenizer=tok, config=None)
    # Verify body is reconstructed from encoded windows
    all_body = " ".join(c.payload.split("] ", 1)[-1] for c in chunks)
    # Original text should be recoverable from chunks (allowing overlap)
    assert "w0" in all_body
    assert "w199" in all_body


# ---- 64-token overlap on encoded tokens ----

def test_overlap_uses_encoded_tokens():
    tok = WordTokenizer()
    text = " ".join(f"w{i}" for i in range(1200))
    chunks = chunk_text(text, ref_id="R", tokenizer=tok)
    assert len(chunks) >= 2
    # Extract body encoded tokens from each chunk
    body1 = tok.encode(chunks[0].payload.split("] ", 1)[-1])
    body2 = tok.encode(chunks[1].payload.split("] ", 1)[-1])
    # Last 64 tokens of body1 should appear at start of body2
    tail = body1[-64:]
    head = body2[:64]
    assert tail == head


# ---- Full payload budget ----

def test_full_payload_budget_valid():
    tok = WordTokenizer()
    text = " ".join(f"w{i}" for i in range(3000))
    chunks = chunk_text(text, ref_id="R", tokenizer=tok)
    for c in chunks:
        assert tok.count(c.payload) <= 512


# ---- Coarse backend diagnostics ----

def test_coarse_configured_zero_hits_present_true_status_zero():
    fine = InMemoryVectorSearch([_chunk("F1")])
    kport = InMemoryKeywordSearch([_chunk("F1")])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=fine,
        keyword_port=kport,
        config=RetrievalConfig(allow_fine_fallback_without_coarse=False),
    )
    d = result.diagnostics
    assert d.coarse_backend_present is True
    assert d.coarse_status == COARSE_ZERO
    assert len(d.coarse_channels_attempted) == 2
    assert d.coarse_channels_with_hits == []


def test_no_coarse_backend_present_false_status_absent():
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        config=RetrievalConfig(allow_fine_fallback_without_coarse=False),
    )
    d = result.diagnostics
    assert d.coarse_backend_present is False
    assert d.coarse_status == COARSE_ABSENT


def test_coarse_with_hits_present_true_status_hit():
    coarse_c = _chunk("S1", ref="REF-1", level=ChunkLevel.COARSE, ctype=ChunkType.DOCUMENT_SUMMARY)
    fine_c = _chunk("F1", ref="REF-1")
    port = InMemoryVectorSearch([coarse_c, fine_c])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(q, vector_port=port)
    d = result.diagnostics
    assert d.coarse_backend_present is True
    assert d.coarse_status == COARSE_HIT
    assert d.coarse_fused_hit_count >= 1
    assert RetrievalChannel_VECTOR_in(d)


def RetrievalChannel_VECTOR_in(d):
    from knowledge_curator.ports.retrieval import RetrievalChannel

    return RetrievalChannel.VECTOR in d.coarse_channels_with_hits


def test_attempted_and_with_hits_channels_recorded():
    coarse_c = _chunk("S1", ref="REF-1", level=ChunkLevel.COARSE, ctype=ChunkType.DOCUMENT_SUMMARY)
    fine_c = _chunk("F1", ref="REF-1")
    port = InMemoryVectorSearch([coarse_c, fine_c])
    kport = InMemoryKeywordSearch([coarse_c, fine_c])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(q, vector_port=port, keyword_port=kport)
    d = result.diagnostics
    assert len(d.coarse_channels_attempted) == 2
    assert len(d.coarse_channels_with_hits) == 2


# ---- Fallback consistency ----

def test_absent_fallback_false_zero_hits():
    fine = InMemoryVectorSearch([_chunk("F1")])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=fine,
        config=RetrievalConfig(allow_fine_fallback_without_coarse=False),
    )
    assert result.hits == []
    assert result.diagnostics.fallback_used is False


def test_absent_fallback_true_fine_retrieval():
    fine = InMemoryVectorSearch([_chunk("F1")])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=fine,
        config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
    )
    assert len(result.hits) >= 1
    assert result.diagnostics.fallback_used is True


def test_zero_hit_fallback_false_zero_hits():
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


def test_zero_hit_fallback_true_fine_retrieval():
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


# ---- Provenance ----

def test_provenance_unchanged():
    c = _chunk("A", ref="REF-1")
    port = InMemoryVectorSearch([c])
    q = RetrievalQuery(text="q")
    result = hybrid_retrieve(
        q,
        vector_port=port,
        config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
    )
    h = result.hits[0]
    assert h.chunk.ref_id == "REF-1"
    assert h.chunk.locator == "p.1"
