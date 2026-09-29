"""BgeReranker — real FlagReranker (Phase 4.2.2/4.2.3).

Constructor uses devices= (FlagEmbedding 1.4.2 signature).
compute_score() return shapes are normalized to list[float] with finite checks.
"""

from __future__ import annotations

import math
import os
from typing import Any, Optional, Sequence

from knowledge_curator.ports.retrieval import RankedHit, RetrievalQuery


def _to_float_list(raw: Any, expected: int) -> list[float]:
    """Normalize FlagEmbedding compute_score output to a flat list[float].

    Accepts scalar, list, tuple, or ndarray-like for one or many pairs.
    Raises ValueError on count mismatch or non-finite scores.
    """
    # numpy scalar / 0-dim array
    if hasattr(raw, "item") and getattr(raw, "ndim", 1) == 0:
        values: list[Any] = [raw.item()]
    elif hasattr(raw, "tolist"):
        values = raw.tolist()
    elif isinstance(raw, (list, tuple)):
        values = list(raw)
    else:
        # scalar int/float or anything convertible
        values = [raw]

    # Nested sequences (e.g. [[0.1], [0.2]]) -> flatten one level of singletons
    flat: list[float] = []
    for v in values:
        if isinstance(v, (list, tuple)):
            if len(v) != 1:
                raise ValueError(f"unexpected nested score shape: {v!r}")
            v = v[0]
        elif hasattr(v, "item"):
            v = v.item()
        try:
            f = float(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"non-numeric reranker score: {v!r}") from exc
        if not math.isfinite(f):
            raise ValueError(f"non-finite reranker score: {f}")
        flat.append(f)

    if len(flat) != expected:
        raise ValueError(
            f"reranker score count {len(flat)} != candidate count {expected}"
        )
    return flat


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

    @property
    def model_name(self) -> str:
        return self._model_name

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
        raw = self._model.compute_score(pairs, normalize=True)
        scores = _to_float_list(raw, expected=len(hits))
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
