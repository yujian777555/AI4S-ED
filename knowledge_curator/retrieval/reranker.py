"""BgeReranker — real FlagReranker (Phase 4.2.2).

Constructor uses devices= (FlagEmbedding 1.4.2 signature).
"""

from __future__ import annotations

import os
from typing import Optional

from knowledge_curator.ports.retrieval import RankedHit, RetrievalQuery


class BgeReranker:
    """BGE reranker via FlagEmbedding FlagReranker."""

    def __init__(
        self,
        model_name_or_path: Optional[str] = None,
        devices: Optional[str | list[str]] = None,
        fp16: bool = False,
    ) -> None:
        self._model_name = (
            model_name_or_path
            or os.environ.get("KC_BGE_RERANKER_MODEL")
            or "BAAI/bge-reranker-v2-m3"
        )
        self._devices = devices
        self._fp16 = fp16
        self._model = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        from knowledge_curator.retrieval.flag_compat import ensure_flagembedding_compat

        ensure_flagembedding_compat()
        try:
            from FlagEmbedding import FlagReranker
        except ImportError as exc:
            raise RuntimeError(
                "FlagEmbedding is required. Install: pip install FlagEmbedding"
            ) from exc
        devices = self._devices
        if devices is None:
            try:
                import torch

                devices = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                devices = "cpu"
        self._model = FlagReranker(
            self._model_name,
            devices=devices,
            use_fp16=self._fp16,
        )
        self._devices = devices

    def rerank(self, hits: list[RankedHit], query: RetrievalQuery) -> list[RankedHit]:
        if not hits:
            return []
        self._ensure_loaded()
        pairs = [(query.text, h.chunk.payload) for h in hits]
        scores = self._model.compute_score(pairs, normalize=True)
        if not isinstance(scores, list):
            scores = [scores]
        if len(scores) != len(hits):
            raise ValueError(f"reranker score count {len(scores)} != candidate count {len(hits)}")
        scored = list(zip(hits, scores))
        scored.sort(key=lambda x: (-x[1], x[0].chunk.chunk_id))
        out: list[RankedHit] = []
        for i, (hit, score) in enumerate(scored):
            out.append(
                RankedHit(
                    chunk=hit.chunk,
                    rrf_score=hit.rrf_score,
                    channels=list(hit.channels),
                    rank=i + 1,
                )
            )
        return out
