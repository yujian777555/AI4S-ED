"""§6.2 deterministic hybrid retrieval service (port-driven).

coarse -> allowed_ref_ids -> fine (vector/graph/keyword) -> RRF -> optional rerank -> top-k
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from knowledge_curator.ports.retrieval import (
    GraphSearchPort,
    KeywordSearchPort,
    QueryExpansionPort,
    RankedHit,
    RerankerPort,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
    VectorSearchPort,
)
from knowledge_curator.schemas.chunk import ChunkLevel, KnowledgeChunk


@dataclass
class RetrievalConfig:
    rrf_k: int = 60  # configurable; not a frozen hyperparameter
    top_k: int = 10


@dataclass
class RetrievalDiagnostics:
    coarse_filter_applied: bool = False
    coarse_backend_present: bool = False
    fallback_fine_retrieval: bool = False
    channels_used: list[RetrievalChannel] = field(default_factory=list)


@dataclass
class RetrievalResult:
    hits: list[RankedHit]
    diagnostics: RetrievalDiagnostics


def rrf_fuse(
    channel_candidates: dict[RetrievalChannel, list[RetrievalCandidate]],
    *,
    k: int = 60,
    top_k: int = 10,
) -> list[RankedHit]:
    """Deterministic Reciprocal Rank Fusion.

    score(chunk) = sum 1 / (k + rank_channel)
    rank starts at 1. Same chunk across channels is fused.
    Tie-break: stable sort by (-score, chunk_id, ref_id).
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, KnowledgeChunk] = {}
    channel_map: dict[str, list[RetrievalChannel]] = {}

    for channel, candidates in channel_candidates.items():
        for cand in candidates:
            cid = cand.chunk.chunk_id
            if cid not in scores:
                scores[cid] = 0.0
                chunk_map[cid] = cand.chunk
                channel_map[cid] = []
            scores[cid] += 1.0 / (k + cand.rank)
            if channel not in channel_map[cid]:
                channel_map[cid].append(channel)

    # Stable deterministic tie-break
    ranked = sorted(
        scores.items(),
        key=lambda x: (-x[1], chunk_map[x[0]].chunk_id, chunk_map[x[0]].ref_id),
    )
    hits: list[RankedHit] = []
    for i, (cid, score) in enumerate(ranked[:top_k]):
        hits.append(
            RankedHit(
                chunk=chunk_map[cid],
                rrf_score=score,
                channels=list(channel_map[cid]),
                rank=i + 1,
            )
        )
    return hits


def hybrid_retrieve(
    query: RetrievalQuery,
    *,
    vector_port: Optional[VectorSearchPort] = None,
    graph_port: Optional[GraphSearchPort] = None,
    keyword_port: Optional[KeywordSearchPort] = None,
    expansion_port: Optional[QueryExpansionPort] = None,
    reranker: Optional[RerankerPort] = None,
    coarse_candidates: Optional[list[KnowledgeChunk]] = None,
    config: Optional[RetrievalConfig] = None,
) -> RetrievalResult:
    """Port-driven deterministic retrieval service.

    If no coarse backend, explicitly records coarse_filter_applied=False
    and falls back to fine retrieval without faking coarse execution.
    """
    cfg = config or RetrievalConfig()
    diag = RetrievalDiagnostics()

    # Optional query expansion
    effective_query = query
    if expansion_port is not None:
        expansions = expansion_port.expand(query)
        if expansions:
            # Expanded terms are appended to query text for fine channels
            effective_query = RetrievalQuery(
                text=query.text + " " + " ".join(expansions),
                top_k=query.top_k,
                allowed_ref_ids=query.allowed_ref_ids,
                subquestion_id=query.subquestion_id,
            )

    # Coarse filter
    if coarse_candidates is not None:
        diag.coarse_backend_present = True
        allowed = {c.ref_id for c in coarse_candidates}
        if query.allowed_ref_ids is not None:
            allowed = allowed & query.allowed_ref_ids
        effective_query = RetrievalQuery(
            text=effective_query.text,
            top_k=effective_query.top_k,
            allowed_ref_ids=allowed,
            subquestion_id=effective_query.subquestion_id,
        )
        diag.coarse_filter_applied = True
    else:
        diag.coarse_filter_applied = False
        diag.fallback_fine_retrieval = True

    # Fine channels
    channel_candidates: dict[RetrievalChannel, list[RetrievalCandidate]] = {}
    if vector_port is not None:
        cands = vector_port.search(effective_query)
        channel_candidates[RetrievalChannel.VECTOR] = cands
        diag.channels_used.append(RetrievalChannel.VECTOR)
    if graph_port is not None:
        cands = graph_port.search(effective_query)
        channel_candidates[RetrievalChannel.GRAPH] = cands
        diag.channels_used.append(RetrievalChannel.GRAPH)
    if keyword_port is not None:
        cands = keyword_port.search(effective_query)
        channel_candidates[RetrievalChannel.KEYWORD] = cands
        diag.channels_used.append(RetrievalChannel.KEYWORD)

    # RRF fusion
    hits = rrf_fuse(channel_candidates, k=cfg.rrf_k, top_k=cfg.top_k)

    # Optional reranker
    if reranker is not None:
        hits = reranker.rerank(hits, effective_query)

    return RetrievalResult(hits=hits, diagnostics=diag)
