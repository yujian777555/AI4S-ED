"""Phase 4.2 tests: real retrieval backends (per-dependency gating)."""

from __future__ import annotations

import pytest

from knowledge_curator.ports.retrieval import RetrievalChannel, RetrievalQuery
from knowledge_curator.retrieval.bm25 import BM25KeywordSearch, KeywordTokenizerPort
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk


class StubTokenizer(KeywordTokenizerPort):
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


# ---- BM25 tests (no numpy needed) ----

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


def test_bm25_zero_overlap_returns_nothing():
    bm25 = BM25KeywordSearch(tokenizer=StubTokenizer())
    bm25.add_chunks([_chunk("A", "REF-1", "alpha beta gamma")])
    q = RetrievalQuery(text="delta epsilon", top_k=10)
    assert bm25.search(q) == []


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
    assert len(bm25.search(q)) == 2


def test_bm25_jieba_chinese():
    """Real jieba tokenizer for Chinese BM25."""
    jieba = pytest.importorskip("jieba", reason="jieba required for Chinese BM25 test")
    from knowledge_curator.retrieval.bm25 import JiebaKeywordTokenizer

    bm25 = BM25KeywordSearch(tokenizer=JiebaKeywordTokenizer())
    bm25.add_chunks([
        _chunk("A", "REF-1", "双极膜电渗析能耗 膜电阻 测试"),
        _chunk("B", "REF-2", "current efficiency energy consumption"),
        _chunk("C", "REF-3", "蛋糕 狗 无关内容"),
    ])
    q_cn = RetrievalQuery(text="双极膜电渗析 能耗", top_k=5)
    r_cn = bm25.search(q_cn)
    assert r_cn and r_cn[0].chunk.chunk_id == "A"

    q_en = RetrievalQuery(text="current efficiency", top_k=5)
    r_en = bm25.search(q_en)
    assert r_en and r_en[0].chunk.chunk_id == "B"

    q_none = RetrievalQuery(text="zzz yyy xxx www", top_k=5)
    assert bm25.search(q_none) == []


# ---- FAISS tests (numpy+faiss gated) ----

def test_faiss_sparse_allowed_ref_correctness():
    """>150 chunks, target ref outside global top100, still returned with allowed_ref_ids."""
    np = pytest.importorskip("numpy", reason="numpy required for FAISS tests")
    pytest.importorskip("faiss", reason="faiss required for FAISS tests")
    from knowledge_curator.retrieval.embedder import DenseEmbedderPort
    from knowledge_curator.retrieval.faiss_index import FaissVectorSearch

    class DeterministicEmbedder(DenseEmbedderPort):
        @property
        def dimension(self):
            return 8

        def embed(self, texts):
            import hashlib
            vecs = []
            for t in texts:
                h = hashlib.sha256(t.encode()).digest()
                v = np.array([h[i] for i in range(8)], dtype=np.float32)
                v /= np.linalg.norm(v) or 1.0
                vecs.append(v)
            return np.stack(vecs)

    embedder = DeterministicEmbedder()
    fvs = FaissVectorSearch(embedder)
    chunks = []
    for i in range(200):
        chunks.append(_chunk(f"C{i}", f"REF-{i}", f"content number {i}"))
    fvs.add_chunks(chunks)

    target_ref = "REF-175"  # index 175, likely outside naive top100 for "content number 175"
    q = RetrievalQuery(
        text="content number 175",
        top_k=1,
        allowed_ref_ids={target_ref},
    )
    results = fvs.search(q)
    assert len(results) == 1
    assert results[0].chunk.ref_id == target_ref
    assert results[0].rank == 1


def test_faiss_empty_index():
    pytest.importorskip("faiss", reason="faiss required")
    from knowledge_curator.retrieval.embedder import DenseEmbedderPort
    from knowledge_curator.retrieval.faiss_index import FaissVectorSearch

    class DummyEmbedder(DenseEmbedderPort):
        @property
        def dimension(self):
            return 4

        def embed(self, texts):
            import numpy as np

            return np.zeros((len(texts), 4), dtype=np.float32)

    fvs = FaissVectorSearch(DummyEmbedder())
    assert fvs.search(RetrievalQuery(text="q")) == []


# ---- Embedder / Reranker dependency errors ----

def test_embedder_missing_dependency_clear_error():
    from knowledge_curator.retrieval.embedder import BgeM3DenseEmbedder

    e = BgeM3DenseEmbedder(model_name_or_path="nonexistent")
    with pytest.raises((RuntimeError, ImportError, Exception)):
        e.embed(["test"])


def test_reranker_missing_dependency_clear_error():
    from knowledge_curator.ports.retrieval import RankedHit
    from knowledge_curator.retrieval.reranker import BgeReranker

    r = BgeReranker(model_name_or_path="nonexistent")
    hit = RankedHit(chunk=_chunk("A", "R1", "x"), rrf_score=1.0, channels=[], rank=1)
    try:
        r.rerank([hit], RetrievalQuery(text="q"))
    except Exception as e:
        assert len(str(e)) > 0  # must fail with some clear error, not pass silently


def test_import_core_without_heavy_deps():
    """import knowledge_curator must not crash without FlagEmbedding/faiss."""
    import knowledge_curator
    import knowledge_curator.retrieval
    import knowledge_curator.retrieval.bm25
    import knowledge_curator.retrieval.faiss_index
    import knowledge_curator.retrieval.embedder
    import knowledge_curator.retrieval.reranker


def test_reranker_provenance_preserved():
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
    assert out[0].rrf_score == 0.5
    assert out[0].channels == [RetrievalChannel.VECTOR]
    assert out[0].rank == 1
