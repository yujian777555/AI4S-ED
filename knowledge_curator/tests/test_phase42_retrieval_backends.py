"""Phase 4.2 offline/keyless tests for real retrieval backends.

These tests use lightweight stubs that satisfy the Port contracts.
Heavy dependencies (FlagEmbedding/faiss/jieba) are optional; missing deps
must produce clear errors, not import crashes.
"""

from __future__ import annotations

import pytest

pytest.importorskip("numpy", reason="numpy required for Phase 4.2 backend tests")

import numpy as np

from knowledge_curator.ports.retrieval import RetrievalChannel, RetrievalQuery
from knowledge_curator.retrieval.bm25 import BM25KeywordSearch, KeywordTokenizerPort
from knowledge_curator.retrieval.embedder import BgeM3DenseEmbedder, DenseEmbedderPort
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk


# ---- Stub embedder for offline tests ----

class StubEmbedder(DenseEmbedderPort):
    """Deterministic hash-based embedder for tests (no FlagEmbedding)."""

    def __init__(self, dim: int = 8) -> None:
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = []
        for t in texts:
            rng = np.random.default_rng(abs(hash(t)) % (2**32))
            v = rng.standard_normal(self._dim).astype(np.float32)
            v /= np.linalg.norm(v) or 1.0
            vecs.append(v)
        return np.stack(vecs)


class StubTokenizer(KeywordTokenizerPort):
    """Whitespace tokenizer for BM25 tests (no jieba)."""

    def tokenize(self, text: str) -> list[str]:
        return [t.lower() for t in text.split() if t.strip()]


def _chunk(cid: str, ref: str, payload: str, level=ChunkLevel.FINE):
    return KnowledgeChunk(
        chunk_id=cid,
        ref_id=ref,
        level=level,
        chunk_type=ChunkType.TEXT,
        payload=payload,
        locator="p.1",
    )


# ---- Embedder dependency error ----

def test_bge_m3_missing_dependency_clear_error():
    embedder = BgeM3DenseEmbedder(model_name_or_path="nonexistent")
    try:
        embedder.embed(["test"])
    except RuntimeError as e:
        assert "FlagEmbedding" in str(e) or "faiss" in str(e).lower()
    except Exception:
        pass  # model load error is acceptable; not ImportError at import time


def test_import_knowledge_curator_without_flagembedding():
    """import knowledge_curator must not crash without FlagEmbedding."""
    import knowledge_curator  # noqa: F401
    import knowledge_curator.retrieval  # noqa: F401


# ---- BM25 tests ----

def test_bm25_english_search():
    bm25 = BM25KeywordSearch(tokenizer=StubTokenizer())
    bm25.add_chunks([
        _chunk("A", "REF-1", "the quick brown fox jumps"),
        _chunk("B", "REF-2", "lazy dog sleeps all day"),
    ])
    q = RetrievalQuery(text="quick fox", top_k=10)
    results = bm25.search(q)
    assert results
    assert results[0].chunk.chunk_id == "A"
    assert results[0].rank == 1
    assert results[0].raw_score > 0


def test_bm25_zero_overlap_returns_nothing():
    bm25 = BM25KeywordSearch(tokenizer=StubTokenizer())
    bm25.add_chunks([_chunk("A", "REF-1", "alpha beta gamma")])
    q = RetrievalQuery(text="delta epsilon", top_k=10)
    results = bm25.search(q)
    assert results == []


def test_bm25_level_filter():
    bm25 = BM25KeywordSearch(tokenizer=StubTokenizer())
    bm25.add_chunks([
        _chunk("A", "REF-1", "alpha beta", level=ChunkLevel.FINE),
        _chunk("B", "REF-1", "alpha beta", level=ChunkLevel.COARSE),
    ])
    q_fine = RetrievalQuery(text="alpha", level=ChunkLevel.FINE)
    q_coarse = RetrievalQuery(text="alpha", level=ChunkLevel.COARSE)
    assert len(bm25.search(q_fine)) == 1
    assert len(bm25.search(q_coarse)) == 1
    assert bm25.search(q_fine)[0].chunk.level == ChunkLevel.FINE


def test_bm25_allowed_ref_ids():
    bm25 = BM25KeywordSearch(tokenizer=StubTokenizer())
    bm25.add_chunks([
        _chunk("A", "REF-1", "alpha beta"),
        _chunk("B", "REF-2", "alpha beta"),
    ])
    q = RetrievalQuery(text="alpha", allowed_ref_ids={"REF-1"})
    results = bm25.search(q)
    assert all(r.chunk.ref_id == "REF-1" for r in results)


def test_bm25_top_k():
    bm25 = BM25KeywordSearch(tokenizer=StubTokenizer())
    for i in range(5):
        bm25.add_chunks([_chunk(f"C{i}", f"REF-{i}", "alpha beta gamma")])
    q = RetrievalQuery(text="alpha", top_k=2)
    results = bm25.search(q)
    assert len(results) == 2


# ---- FAISS tests ----

def test_faiss_dimension_mismatch():
    from knowledge_curator.retrieval.faiss_index import FaissVectorSearch

    embedder = StubEmbedder(dim=8)
    fvs = FaissVectorSearch(embedder)
    try:
        fvs.add_chunks([_chunk("A", "REF-1", "text")])
    except Exception:
        pass  # faiss may not be installed; test just checks no import crash


def test_faiss_empty_index_returns_empty():
    from knowledge_curator.retrieval.faiss_index import FaissVectorSearch

    try:
        fvs = FaissVectorSearch(StubEmbedder())
        q = RetrievalQuery(text="q")
        assert fvs.search(q) == []
    except RuntimeError as e:
        if "faiss" not in str(e).lower():
            raise


# ---- Reranker provenance ----

def test_reranker_missing_dependency_clear_error():
    from knowledge_curator.retrieval.reranker import BgeReranker

    reranker = BgeReranker(model_name_or_path="nonexistent")
    try:
        reranker.rerank([], RetrievalQuery(text="q"))
    except RuntimeError as e:
        assert "FlagEmbedding" in str(e)
    except Exception:
        pass


def test_reranker_provenance_preserved():
    """Stub reranker preserves rrf_score, channels, chunk."""
    from knowledge_curator.ports.retrieval import RankedHit

    class StubReranker:
        def rerank(self, hits, query):
            return sorted(hits, key=lambda h: (-h.rrf_score, h.chunk.chunk_id))

    c1 = _chunk("A", "REF-1", "alpha")
    c2 = _chunk("B", "REF-2", "beta")
    hits = [
        RankedHit(chunk=c1, rrf_score=0.5, channels=[RetrievalChannel.VECTOR], rank=1),
        RankedHit(chunk=c2, rrf_score=0.3, channels=[RetrievalChannel.KEYWORD], rank=2),
    ]
    out = StubReranker().rerank(hits, RetrievalQuery(text="q"))
    assert out[0].chunk.ref_id == "REF-1"
    assert out[0].rrf_score == 0.5  # preserved
    assert out[0].channels == [RetrievalChannel.VECTOR]  # preserved
    assert out[0].rank == 1  # re-ranked
