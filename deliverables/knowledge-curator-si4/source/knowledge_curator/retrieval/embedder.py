"""DenseEmbedderPort + BgeM3DenseEmbedder (Phase 4.2.2).

Real FlagEmbedding 1.4.2 constructor: devices= (not device=).
Lazy import/load. Model path from env or constructor, not hard-coded.
"""

from __future__ import annotations

import os
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class DenseEmbedderPort(Protocol):
    def embed(self, texts: list[str]):
        ...

    @property
    def dimension(self) -> int:
        ...


class BgeM3DenseEmbedder:
    """BGE-M3 dense embedder via FlagEmbedding (Phase 4.2.2)."""

    def __init__(
        self,
        model_name_or_path: Optional[str] = None,
        devices: Optional[str | list[str]] = None,
        batch_size: int = 8,
        fp16: bool = False,
        normalize: bool = True,
    ) -> None:
        self._model_name = (
            model_name_or_path
            or os.environ.get("KC_BGE_M3_MODEL")
            or "BAAI/bge-m3"
        )
        self._devices = devices
        self._batch_size = batch_size
        self._fp16 = fp16
        self._normalize = normalize
        self._model = None
        self._dim: Optional[int] = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        from knowledge_curator.retrieval.flag_compat import ensure_flagembedding_compat

        ensure_flagembedding_compat()
        try:
            from FlagEmbedding import BGEM3FlagModel
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
        self._model = BGEM3FlagModel(
            self._model_name,
            devices=devices,
            use_fp16=self._fp16,
        )
        self._devices = devices

    @property
    def dimension(self) -> int:
        if self._dim is None:
            self._ensure_loaded()
            emb = self._model.encode(["probe"], return_dense=True)["dense_vecs"]
            self._dim = int(emb.shape[1])
        return self._dim

    def embed(self, texts: list[str]):
        import numpy as np

        self._ensure_loaded()
        out = self._model.encode(
            texts,
            batch_size=self._batch_size,
            return_dense=True,
        )["dense_vecs"]
        arr = np.asarray(out, dtype=np.float32)
        if self._normalize:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            arr = arr / norms
        if not np.isfinite(arr).all():
            raise ValueError("embedding contains non-finite values")
        return arr
