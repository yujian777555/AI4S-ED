"""In-memory retrieval adapters for tests only (Phase 4.1.1 contract-aware)."""

from __future__ import annotations

from typing import Optional

from knowledge_curator.ports.retrieval import (
    RankedHit,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
)
from knowledge_curator.schemas.chunk import KnowledgeChunk


def _filter_and_rank(
    chunks: list[KnowledgeChunk],
    query: RetrievalQuery,
    channel: RetrievalChannel,
) -> list[RetrievalCandidate]:
    """Filter by level and allowed_ref_ids, then generate 1-based ranks.

    Filter first, then rank. Honour top_k.
    """
    filtered = []
    for c in chunks:
        if c.level != query.level:
            continue
        if query.allowed_ref_ids is not None and c.ref_id not in query.allowed_ref_ids:
            continue
        filtered.append(c)
    limited = filtered[: query.top_k]
    return [
        RetrievalCandidate(chunk=c, channel=channel, rank=i + 1, raw_score=1.0 / (i + 1))
        for i, c in enumerate(limited)
    ]


class InMemoryVectorSearch:
    """Test-only: returns preset vector candidates honouring level/top_k."""

    def __init__(self, chunks: Optional[list[KnowledgeChunk]] = None) -> None:
        self._chunks = list(chunks or [])

    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        return _filter_and_rank(self._chunks, query, RetrievalChannel.VECTOR)


class InMemoryGraphSearch:
    """Test-only: returns preset graph candidates honouring level/top_k."""

    def __init__(self, chunks: Optional[list[KnowledgeChunk]] = None) -> None:
        self._chunks = list(chunks or [])

    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        return _filter_and_rank(self._chunks, query, RetrievalChannel.GRAPH)


class InMemoryKeywordSearch:
    """Test-only: returns preset keyword candidates honouring level/top_k."""

    def __init__(self, chunks: Optional[list[KnowledgeChunk]] = None) -> None:
        self._chunks = list(chunks or [])

    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        return _filter_and_rank(self._chunks, query, RetrievalChannel.KEYWORD)


class FakeReranker:
    """Test-only: stable sort by rrf_score descending."""

    def rerank(self, hits: list[RankedHit], query: RetrievalQuery) -> list[RankedHit]:
        return sorted(hits, key=lambda h: (-h.rrf_score, h.chunk.chunk_id))
