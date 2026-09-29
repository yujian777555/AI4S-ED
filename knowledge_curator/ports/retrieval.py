"""Retrieval Ports for §6.2 (runtime-independent, temporary)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.chunk import KnowledgeChunk


class RetrievalChannel(str, Enum):
    VECTOR = "vector"
    GRAPH = "graph"
    KEYWORD = "keyword"


@dataclass
class RetrievalQuery:
    """Internal retrieval query (temporary)."""

    text: str
    top_k: int = 10
    allowed_ref_ids: Optional[set[str]] = None
    subquestion_id: Optional[str] = None


@dataclass
class RetrievalCandidate:
    """One retrieval candidate with provenance preserved."""

    chunk: KnowledgeChunk
    channel: RetrievalChannel
    rank: int  # 1-based rank within channel
    raw_score: Optional[float] = None


@dataclass
class RankedHit:
    """Fused/reranked hit with provenance."""

    chunk: KnowledgeChunk
    rrf_score: float
    channels: list[RetrievalChannel]
    rank: int = 0


@runtime_checkable
class VectorSearchPort(Protocol):
    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        """Return vector channel candidates."""
        ...


@runtime_checkable
class GraphSearchPort(Protocol):
    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        """Return graph channel candidates."""
        ...


@runtime_checkable
class KeywordSearchPort(Protocol):
    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        """Return keyword channel candidates."""
        ...


@runtime_checkable
class QueryExpansionPort(Protocol):
    def expand(self, query: RetrievalQuery) -> list[str]:
        """Return expanded query terms. Empty list = no expansion."""
        ...


@runtime_checkable
class RerankerPort(Protocol):
    def rerank(self, hits: list[RankedHit], query: RetrievalQuery) -> list[RankedHit]:
        """Rerank fused hits. Default: pass through."""
        ...
