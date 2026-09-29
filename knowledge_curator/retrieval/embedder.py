"""DenseEmbedderPort + BgeM3DenseEmbedder (Phase 4.2).

Lazy import/load so `import knowledge_curator` never crashes without FlagEmbedding/numpy.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class DenseEmbedderPort(Protocol):
    """Dense embedding contract."""

    def embed(self, texts: list[str]):
        """Return float32 normalized embeddings of shape (n, dim)."""
        ...

    @property
    def dimension(self) -> int:
        ...


class BgeM3DenseEmbedder:
    """BGE-M3 dense embedder via FlagEmbedding (lazy load, configurable)."""

    def __init__(
        self,
        model_name_or_path: str = "BAAI/bge-m3",
        device: Optional[str] = None,
        batch_size: int = 8,
        fp16: bool = False,
        normalize: bool = True,
    ) -> None:
        self._model_name = model_name_or_path
        self._device = device  # None = auto (CUDA if available, else CPU)
        self._batch_size = batch_size
        self._fp16 = fp16
        self._normalize = normalize
        self._model = None
        self._dim: Optional[int] = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError as exc:
            raise RuntimeError(
                "FlagEmbedding is required for BgeM3DenseEmbedder. "
                "Install via: pip install -r knowledge_curator/requirements-retrieval.txt"
            ) from exc
        device = self._device
        if device is None:
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        self._model = BGEM3FlagModel(
            self._model_name,
            device=device,
            use_fp16=self._fp16,
        )
        self._device = device

    @property
    def dimension(self) -> int:
        if self._dim is None:
            self._ensure_loaded()
            # Probe with a short text
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
        assert np.isfinite(arr).all(), "embedding contains non-finite values"
        return arr
