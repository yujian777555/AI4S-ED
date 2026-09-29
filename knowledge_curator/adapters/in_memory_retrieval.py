"""In-memory retrieval adapters for tests only (not real FAISS/BM25)."""

from __future__ import annotations

from typing import Optional

from knowledge_curator.ports.retrieval import (
    RankedHit,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
)
from knowledge_curator.schemas.chunk import KnowledgeChunk


class InMemoryVectorSearch:
    """Test-only: returns preset vector candidates."""

    def __init__(self, chunks: Optional[list[KnowledgeChunk]] = None) -> None:
        self._chunks = list(chunks or [])

    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        results = []
        for i, c in enumerate(self._chunks):
            if query.allowed_ref_ids is not None and c.ref_id not in query.allowed_ref_ids:
                continue
            results.append(
                RetrievalCandidate(chunk=c, channel=RetrievalChannel.VECTOR, rank=i + 1, raw_score=1.0 / (i + 1))
            )
        return results


class InMemoryGraphSearch:
    """Test-only: returns preset graph candidates."""

    def __init__(self, chunks: Optional[list[KnowledgeChunk]] = None) -> None:
        self._chunks = list(chunks or [])

    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        results = []
        for i, c in enumerate(self._chunks):
            if query.allowed_ref_ids is not None and c.ref_id not in query.allowed_ref_ids:
                continue
            results.append(
                RetrievalCandidate(chunk=c, channel=RetrievalChannel.GRAPH, rank=i + 1, raw_score=1.0 / (i + 1))
            )
        return results


class InMemoryKeywordSearch:
    """Test-only: returns preset keyword candidates."""

    def __init__(self, chunks: Optional[list[KnowledgeChunk]] = None) -> None:
        self._chunks = list(chunks or [])

    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        results = []
        for i, c in enumerate(self._chunks):
            if query.allowed_ref_ids is not None and c.ref_id not in query.allowed_ref_ids:
                continue
            results.append(
                RetrievalCandidate(chunk=c, channel=RetrievalChannel.KEYWORD, rank=i + 1, raw_score=1.0 / (i + 1))
            )
        return results


class FakeReranker:
    """Test-only: optional stable sort by rrf_score descending."""

    def rerank(self, hits: list[RankedHit], query: RetrievalQuery) -> list[RankedHit]:
        return sorted(hits, key=lambda h: (-h.rrf_score, h.chunk.chunk_id))
