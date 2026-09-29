"""BgeReranker — BGE reranker (Phase 4.2)."""

from __future__ import annotations

from typing import Optional

from knowledge_curator.ports.retrieval import RankedHit, RetrievalQuery


class BgeReranker:
    """BGE reranker via FlagEmbedding (lazy load, configurable)."""

    def __init__(
        self,
        model_name_or_path: str = "BAAI/bge-reranker-v2-m3",
        device: Optional[str] = None,
        fp16: bool = False,
    ) -> None:
        self._model_name = model_name_or_path
        self._device = device
        self._fp16 = fp16
        self._model = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        try:
            from FlagEmbedding import FlagReranker
        except ImportError as exc:
            raise RuntimeError(
                "FlagEmbedding is required for BgeReranker. "
                "Install via: pip install -r knowledge_curator/requirements-retrieval.txt"
            ) from exc
        device = self._device
        if device is None:
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        self._model = FlagReranker(
            self._model_name,
            device=device,
            use_fp16=self._fp16,
        )
        self._device = device

    def rerank(self, hits: list[RankedHit], query: RetrievalQuery) -> list[RankedHit]:
        if not hits:
            return []
        self._ensure_loaded()
        pairs = [(query.text, h.chunk.payload) for h in hits]
        scores = self._model.compute_score(pairs, normalize=True)
        if not isinstance(scores, list):
            scores = [scores]
        scored = list(zip(hits, scores))
        # Descending relevance, stable tie-break by chunk_id
        scored.sort(key=lambda x: (-x[1], x[0].chunk.chunk_id))
        out: list[RankedHit] = []
        for i, (hit, score) in enumerate(scored):
            out.append(
                RankedHit(
                    chunk=hit.chunk,
                    rrf_score=hit.rrf_score,  # preserved
                    channels=list(hit.channels),  # preserved
                    rank=i + 1,  # re-ranked
                )
            )
        return out
