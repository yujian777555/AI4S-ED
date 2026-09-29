"""§6.2 hybrid retrieval with global coarse fusion (Phase 4.1.2)."""

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

COARSE_ABSENT = "coarse_backend_absent"
COARSE_HIT = "coarse_backend_ran_with_hits"
COARSE_ZERO = "coarse_backend_ran_zero_hits"
FALLBACK_USED = "fallback_fine_retrieval_used"
NO_FALLBACK = "fallback_not_allowed_no_coarse"


@dataclass
class RetrievalConfig:
    rrf_k: int = 60
    top_k: int = 10
    coarse_top_k: int = 20
    allow_fine_fallback_without_coarse: bool = False


@dataclass
class RetrievalDiagnostics:
    coarse_filter_applied: bool = False
    coarse_backend_present: bool = False
    coarse_status: str = COARSE_ABSENT
    fallback_used: bool = False
    channels_used: list[RetrievalChannel] = field(default_factory=list)
    coarse_channels_used: list[RetrievalChannel] = field(default_factory=list)
    coarse_fused_hit_count: int = 0


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
    """Deterministic RRF with best-rank duplicate handling.

    score(chunk) = sum 1/(k + rank_channel)
    Same chunk in one channel: use MIN(valid ranks) only, order-independent.
    rank < 1 is ignored. Tie-break: (-score, chunk_id, ref_id).
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, KnowledgeChunk] = {}
    channel_map: dict[str, list[RetrievalChannel]] = {}
    best_rank: dict[tuple[str, RetrievalChannel], int] = {}

    for channel, candidates in channel_candidates.items():
        for cand in candidates:
            rank = cand.rank
            if rank < 1:
                continue
            cid = cand.chunk.chunk_id
            key = (cid, channel)
            if key in best_rank:
                # Keep best (minimum) rank; do not double-count
                if rank < best_rank[key]:
                    best_rank[key] = rank
                    # Rescore with best rank
                    old_contrib = 1.0 / (k + best_rank[key])
                    # We need to recompute; simpler: store all ranks and compute at end
                continue
            best_rank[key] = rank

    # Recompute scores from best ranks (order-independent)
    for (cid, channel), rank in best_rank.items():
        if cid not in scores:
            scores[cid] = 0.0
            chunk_map[cid] = _find_chunk(channel_candidates, cid)
            channel_map[cid] = []
        scores[cid] += 1.0 / (k + rank)
        if channel not in channel_map[cid]:
            channel_map[cid].append(channel)

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


def _find_chunk(
    channel_candidates: dict[RetrievalChannel, list[RetrievalCandidate]],
    chunk_id: str,
) -> KnowledgeChunk:
    for candidates in channel_candidates.values():
        for c in candidates:
            if c.chunk.chunk_id == chunk_id:
                return c.chunk
    raise KeyError(chunk_id)


def hybrid_retrieve(
    query: RetrievalQuery,
    *,
    vector_port: Optional[VectorSearchPort] = None,
    graph_port: Optional[GraphSearchPort] = None,
    keyword_port: Optional[KeywordSearchPort] = None,
    expansion_port: Optional[QueryExpansionPort] = None,
    reranker: Optional[RerankerPort] = None,
    config: Optional[RetrievalConfig] = None,
) -> RetrievalResult:
    """True coarse→fine with global coarse fusion (Phase 4.1.2)."""
    cfg = config or RetrievalConfig()
    diag = RetrievalDiagnostics()

    effective_text = query.text
    if expansion_port is not None:
        expansions = expansion_port.expand(query)
        if expansions:
            effective_text = query.text + " " + " ".join(expansions)

    # ---- Coarse stage: VECTOR + KEYWORD fused via RRF ----
    coarse_query = RetrievalQuery(
        text=effective_text,
        level=ChunkLevel.COARSE,
        top_k=cfg.coarse_top_k,
        allowed_ref_ids=query.allowed_ref_ids,
        subquestion_id=query.subquestion_id,
    )
    coarse_channel_candidates: dict[RetrievalChannel, list[RetrievalCandidate]] = {}
    if vector_port is not None:
        cands = [c for c in vector_port.search(coarse_query) if c.chunk.level == ChunkLevel.COARSE]
        if cands:
            coarse_channel_candidates[RetrievalChannel.VECTOR] = cands
            diag.coarse_channels_used.append(RetrievalChannel.VECTOR)
    if keyword_port is not None:
        cands = [c for c in keyword_port.search(coarse_query) if c.chunk.level == ChunkLevel.COARSE]
        if cands:
            coarse_channel_candidates[RetrievalChannel.KEYWORD] = cands
            diag.coarse_channels_used.append(RetrievalChannel.KEYWORD)

    coarse_available = bool(coarse_channel_candidates)
    diag.coarse_backend_present = coarse_available

    # Global coarse fusion via RRF, then coarse_top_k
    coarse_hits = rrf_fuse(coarse_channel_candidates, k=cfg.rrf_k, top_k=cfg.coarse_top_k)
    diag.coarse_fused_hit_count = len(coarse_hits)

    if coarse_available and coarse_hits:
        diag.coarse_status = COARSE_HIT
        diag.coarse_filter_applied = True
        coarse_refs = {h.chunk.ref_id for h in coarse_hits}
        if query.allowed_ref_ids is not None:
            fine_allowed = query.allowed_ref_ids & coarse_refs
        else:
            fine_allowed = coarse_refs
    elif coarse_available and not coarse_hits:
        diag.coarse_status = COARSE_ZERO
        if cfg.allow_fine_fallback_without_coarse:
            diag.fallback_used = True
            diag.coarse_status = FALLBACK_USED
            fine_allowed = query.allowed_ref_ids
        else:
            diag.coarse_status = NO_FALLBACK
            return RetrievalResult(hits=[], diagnostics=diag)
    else:
        diag.coarse_status = COARSE_ABSENT
        if cfg.allow_fine_fallback_without_coarse:
            diag.fallback_used = True
            fine_allowed = query.allowed_ref_ids
        else:
            # Coarse absent, fallback disabled: no unrestricted fine
            return RetrievalResult(hits=[], diagnostics=diag)

    # ---- Fine stage ----
    fine_query = RetrievalQuery(
        text=effective_text,
        level=ChunkLevel.FINE,
        top_k=query.top_k,
        allowed_ref_ids=fine_allowed,
        subquestion_id=query.subquestion_id,
    )
    fine_channel_candidates: dict[RetrievalChannel, list[RetrievalCandidate]] = {}
    if vector_port is not None:
        cands = vector_port.search(fine_query)
        fine_channel_candidates[RetrievalChannel.VECTOR] = cands[: query.top_k]
        diag.channels_used.append(RetrievalChannel.VECTOR)
    if graph_port is not None:
        cands = graph_port.search(fine_query)
        fine_channel_candidates[RetrievalChannel.GRAPH] = cands[: query.top_k]
        diag.channels_used.append(RetrievalChannel.GRAPH)
    if keyword_port is not None:
        cands = keyword_port.search(fine_query)
        fine_channel_candidates[RetrievalChannel.KEYWORD] = cands[: query.top_k]
        diag.channels_used.append(RetrievalChannel.KEYWORD)

    hits = rrf_fuse(fine_channel_candidates, k=cfg.rrf_k, top_k=query.top_k)

    if reranker is not None:
        hits = reranker.rerank(hits, fine_query)[: query.top_k]

    return RetrievalResult(hits=hits, diagnostics=diag)
