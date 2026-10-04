"""Phase 4.2.3 tests: full real coarse→fine + reranker evidence semantics."""

from __future__ import annotations

import math

import pytest

from knowledge_curator.ports.retrieval import RankedHit, RetrievalChannel, RetrievalQuery
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk


def _chunk(cid: str, ref: str, payload: str, level=ChunkLevel.FINE):
    return KnowledgeChunk(
        chunk_id=cid,
        ref_id=ref,
        level=level,
        chunk_type=ChunkType.TEXT,
        payload=payload,
        locator="p.1",
    )


def _hit(cid: str, ref: str, payload: str, rank: int = 1, level=ChunkLevel.FINE):
    return RankedHit(
        chunk=_chunk(cid, ref, payload, level=level),
        rrf_score=1.0 / (60 + rank),
        channels=[RetrievalChannel.VECTOR],
        rank=rank,
    )


# ---- Reranker score normalization (pure, no FlagEmbedding) ----

def test_to_float_list_scalar():
    from knowledge_curator.retrieval.reranker import _to_float_list

    assert _to_float_list(0.5, expected=1) == [0.5]


def test_to_float_list_list():
    from knowledge_curator.retrieval.reranker import _to_float_list

    assert _to_float_list([0.1, 0.2], expected=2) == [0.1, 0.2]


def test_to_float_list_tuple():
    from knowledge_curator.retrieval.reranker import _to_float_list

    assert _to_float_list((0.1, 0.2), expected=2) == [0.1, 0.2]


def test_to_float_list_numpy_array():
    np = pytest.importorskip("numpy")
    from knowledge_curator.retrieval.reranker import _to_float_list

    out = _to_float_list(np.array([0.1, 0.2], dtype=np.float32), expected=2)
    assert len(out) == 2
    assert abs(out[0] - 0.1) < 1e-6


def test_to_float_list_numpy_scalar():
    np = pytest.importorskip("numpy")
    from knowledge_curator.retrieval.reranker import _to_float_list

    assert _to_float_list(np.float32(0.25), expected=1) == [pytest.approx(0.25)]


def test_to_float_list_count_mismatch_raises():
    from knowledge_curator.retrieval.reranker import _to_float_list

    with pytest.raises(ValueError, match="score count"):
        _to_float_list([0.1, 0.2], expected=3)


def test_to_float_list_non_finite_raises():
    from knowledge_curator.retrieval.reranker import _to_float_list

    with pytest.raises(ValueError, match="non-finite"):
        _to_float_list([0.1, float("nan")], expected=2)
    with pytest.raises(ValueError, match="non-finite"):
        _to_float_list([float("inf"), 0.1], expected=2)


def test_reranker_normalizes_and_rejects_non_finite(monkeypatch):
    """BgeReranker.rerank accepts list/array-like scores and rejects non-finite."""
    from knowledge_curator.retrieval.reranker import BgeReranker

    hits = [
        _hit("A", "REF-1", "alpha", rank=1),
        _hit("B", "REF-2", "beta", rank=2),
    ]
    query = RetrievalQuery(text="q")

    class FakeModel:
        def compute_score(self, pairs, normalize=True):
            return [0.1, 0.9]

    r = BgeReranker(model_name_or_path="fake")
    r._model = FakeModel()
    out = r.rerank(hits, query)
    assert out[0].chunk.ref_id == "REF-2"
    assert out[0].rank == 1
    assert out[0].rrf_score == hits[1].rrf_score
    assert out[0].channels == [RetrievalChannel.VECTOR]

    class BadModel:
        def compute_score(self, pairs, normalize=True):
            return [0.1, float("nan")]

    r2 = BgeReranker(model_name_or_path="fake")
    r2._model = BadModel()
    with pytest.raises(ValueError, match="non-finite"):
        r2.rerank(hits, query)


def test_reranker_scalar_single_candidate():
    from knowledge_curator.retrieval.reranker import BgeReranker

    hits = [_hit("A", "REF-1", "alpha")]
    query = RetrievalQuery(text="q")

    class ScalarModel:
        def compute_score(self, pairs, normalize=True):
            return 0.7

    r = BgeReranker(model_name_or_path="fake")
    r._model = ScalarModel()
    out = r.rerank(hits, query)
    assert len(out) == 1
    assert out[0].chunk.chunk_id == "A"


def test_reranker_provenance_survives_rerank():
    from knowledge_curator.retrieval.reranker import BgeReranker

    hits = [
        _hit("A", "REF-1", "alpha", rank=1),
        _hit("B", "REF-2", "beta", rank=2),
    ]
    hits[0].channels = [RetrievalChannel.VECTOR, RetrievalChannel.KEYWORD]

    class ReverseModel:
        def compute_score(self, pairs, normalize=True):
            return [0.1, 0.9]

    r = BgeReranker(model_name_or_path="fake")
    r._model = ReverseModel()
    out = r.rerank(hits, RetrievalQuery(text="q"))
    # REF-2 wins on score but must keep its own provenance
    assert out[0].chunk.ref_id == "REF-2"
    assert out[0].channels == [RetrievalChannel.VECTOR]
    assert out[0].rrf_score == pytest.approx(hits[1].rrf_score)
    assert out[1].chunk.ref_id == "REF-1"
    assert out[1].channels == [RetrievalChannel.VECTOR, RetrievalChannel.KEYWORD]
    assert out[1].rrf_score == pytest.approx(hits[0].rrf_score)


# ---- Real smoke structure: coarse+fine indexing and PASS semantics ----

def test_real_smoke_fixture_contains_coarse_and_fine():
    from knowledge_curator.retrieval.fixture import build_fixture

    chunks, queries = build_fixture()
    levels = {c.level for c in chunks}
    assert ChunkLevel.COARSE in levels
    assert ChunkLevel.FINE in levels
    assert len(queries) >= 6


def test_real_smoke_indexes_both_levels_not_fine_only():
    """Smoke must add COARSE + FINE chunks to real backends (source check)."""
    src = open(
        "knowledge_curator/retrieval/real_smoke.py", encoding="utf-8"
    ).read()
    assert "ChunkLevel.COARSE" in src
    assert "ChunkLevel.FINE" in src
    # Must not index only fine chunks as the sole corpus
    assert "add_chunks(coarse_chunks)" in src
    assert "add_chunks(fine_chunks)" in src
    # Full-stack config must not rely on fine-only fallback
    assert "allow_fine_fallback_without_coarse=False" in src


def test_full_pass_requires_coarse_filter_and_reranker():
    """PASS semantics in real_smoke: no fallback, coarse filter, reranker used."""
    src = open(
        "knowledge_curator/retrieval/real_smoke.py", encoding="utf-8"
    ).read()
    assert "full_stack_pass" in src
    assert "coarse_filter_applied" in src
    assert "fallback_used" in src
    assert "reranker_used" in src
    assert "degraded_without_reranker" in src
    assert 'status"] = "NOT_RUN_ENV"' in src or "status'] = 'NOT_RUN_ENV'" in src


def test_hybrid_coarse_filter_blocks_wrong_refs():
    """coarse filter actually restricts fine retrieval to coarse-allowed refs."""
    from knowledge_curator.ports.retrieval import RetrievalCandidate
    from knowledge_curator.retrieval.hybrid import RetrievalConfig, hybrid_retrieve

    class StubVector:
        def search(self, query):
            if query.level == ChunkLevel.COARSE:
                return [
                    RetrievalCandidate(
                        chunk=_chunk("CA", "REF-A", "coarse A", level=ChunkLevel.COARSE),
                        channel=RetrievalChannel.VECTOR,
                        rank=1,
                        raw_score=1.0,
                    )
                ]
            cands = [
                RetrievalCandidate(
                    chunk=_chunk("FA", "REF-A", "fine A"),
                    channel=RetrievalChannel.VECTOR,
                    rank=1,
                    raw_score=1.0,
                ),
                RetrievalCandidate(
                    chunk=_chunk("FB", "REF-B", "fine B"),
                    channel=RetrievalChannel.VECTOR,
                    rank=2,
                    raw_score=0.9,
                ),
            ]
            if query.allowed_ref_ids is not None:
                cands = [c for c in cands if c.chunk.ref_id in query.allowed_ref_ids]
            return cands

    cfg = RetrievalConfig(allow_fine_fallback_without_coarse=False, coarse_top_k=5, top_k=5)
    res = hybrid_retrieve(
        RetrievalQuery(text="q", level=ChunkLevel.FINE, top_k=5),
        vector_port=StubVector(),
        config=cfg,
    )
    d = res.diagnostics
    assert d.coarse_backend_present is True
    assert d.coarse_filter_applied is True
    assert d.fallback_used is False
    assert d.coarse_fused_hit_count > 0
    assert all(h.chunk.ref_id == "REF-A" for h in res.hits)
