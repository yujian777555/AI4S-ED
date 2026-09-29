"""§6.2 deterministic hybrid retrieval service (Phase 4.1.1).

True coarse -> fine pipeline:
query -> COARSE query -> coarse vector/keyword -> allowed_ref_ids
      -> FINE query -> vector+graph+keyword -> RRF -> optional reranker -> top_k
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
    rrf_k: int = 60
    top_k: int = 10
    coarse_top_k: int = 20
    allow_fine_fallback_without_coarse: bool = False


# Coarse filter status constants
COARSE_ABSENT = "coarse_backend_absent"
COARSE_HIT = "coarse_backend_ran_with_hits"
COARSE_ZERO = "coarse_backend_ran_zero_hits"
FALLBACK_USED = "fallback_fine_retrieval_used"
NO_FALLBACK = "fallback_not_allowed_no_coarse"


@dataclass
class RetrievalDiagnostics:
    coarse_filter_applied: bool = False
    coarse_backend_present: bool = False
    coarse_status: str = COARSE_ABSENT
    fallback_used: bool = False
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
    """Deterministic RRF with rank>=1 enforcement and duplicate protection.

    score(chunk) = sum 1/(k + rank_channel)
    Same chunk in one channel only counts once (best/first rank).
    Tie-break: (-score, chunk_id, ref_id).
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, KnowledgeChunk] = {}
    channel_map: dict[str, list[RetrievalChannel]] = {}
    best_rank: dict[tuple[str, RetrievalChannel], int] = {}

    for channel, candidates in channel_candidates.items():
        for cand in candidates:
            rank = cand.rank
            if rank < 1:
                continue  # invalid rank not accepted
            cid = cand.chunk.chunk_id
            key = (cid, channel)
            if key in best_rank:
                continue  # same-channel duplicate: only best/first rank counts
            best_rank[key] = rank
            if cid not in scores:
                scores[cid] = 0.0
                chunk_map[cid] = cand.chunk
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
    """True coarse -> fine deterministic retrieval (Phase 4.1.1)."""
    cfg = config or RetrievalConfig()
    diag = RetrievalDiagnostics()

    effective_text = query.text
    if expansion_port is not None:
        expansions = expansion_port.expand(query)
        if expansions:
            effective_text = query.text + " " + " ".join(expansions)

    # ---- Coarse stage ----
    coarse_query = RetrievalQuery(
        text=effective_text,
        level=ChunkLevel.COARSE,
        top_k=cfg.coarse_top_k,
        allowed_ref_ids=query.allowed_ref_ids,
        subquestion_id=query.subquestion_id,
    )
    coarse_candidates: list[RetrievalCandidate] = []
    coarse_available = vector_port is not None or keyword_port is not None
    if coarse_available:
        diag.coarse_backend_present = True
        if vector_port is not None:
            coarse_candidates.extend(vector_port.search(coarse_query))
        if keyword_port is not None:
            coarse_candidates.extend(keyword_port.search(coarse_query))
        # Filter to COARSE level only
        coarse_candidates = [c for c in coarse_candidates if c.chunk.level == ChunkLevel.COARSE]
        if coarse_candidates:
            diag.coarse_status = COARSE_HIT
            diag.coarse_filter_applied = True
        else:
            diag.coarse_status = COARSE_ZERO
    else:
        diag.coarse_status = COARSE_ABSENT

    # Determine allowed_ref_ids for fine stage
    fine_allowed: Optional[set[str]] = query.allowed_ref_ids
    if diag.coarse_filter_applied:
        coarse_refs = {c.chunk.ref_id for c in coarse_candidates}
        if fine_allowed is not None:
            fine_allowed = fine_allowed & coarse_refs
        else:
            fine_allowed = coarse_refs
    elif diag.coarse_status == COARSE_ZERO:
        if cfg.allow_fine_fallback_without_coarse:
            diag.fallback_used = True
            diag.coarse_status = FALLBACK_USED
            # fine_allowed stays as query.allowed_ref_ids (unrestricted if None)
        else:
            diag.coarse_status = NO_FALLBACK
            return RetrievalResult(hits=[], diagnostics=diag)
    elif diag.coarse_status == COARSE_ABSENT:
        if cfg.allow_fine_fallback_without_coarse:
            diag.fallback_used = True
        # else: no coarse, no fallback -> still allow fine if explicitly no coarse?
        # Per plan: "if no coarse backend, must explicitly record coarse_filter_applied=false"
        # and "allow configured fallback fine retrieval"
        if not cfg.allow_fine_fallback_without_coarse:
            diag.coarse_status = COARSE_ABSENT
            # still proceed with fine but mark not applied
            pass

    # ---- Fine stage ----
    fine_query = RetrievalQuery(
        text=effective_text,
        level=ChunkLevel.FINE,
        top_k=query.top_k,
        allowed_ref_ids=fine_allowed,
        subquestion_id=query.subquestion_id,
    )
    channel_candidates: dict[RetrievalChannel, list[RetrievalCandidate]] = {}
    if vector_port is not None:
        cands = vector_port.search(fine_query)
        channel_candidates[RetrievalChannel.VECTOR] = cands[: query.top_k]
        diag.channels_used.append(RetrievalChannel.VECTOR)
    if graph_port is not None:
        cands = graph_port.search(fine_query)
        channel_candidates[RetrievalChannel.GRAPH] = cands[: query.top_k]
        diag.channels_used.append(RetrievalChannel.GRAPH)
    if keyword_port is not None:
        cands = keyword_port.search(fine_query)
        channel_candidates[RetrievalChannel.KEYWORD] = cands[: query.top_k]
        diag.channels_used.append(RetrievalChannel.KEYWORD)

    hits = rrf_fuse(channel_candidates, k=cfg.rrf_k, top_k=query.top_k)

    if reranker is not None:
        hits = reranker.rerank(hits, fine_query)[: query.top_k]

    return RetrievalResult(hits=hits, diagnostics=diag)
