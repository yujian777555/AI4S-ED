"""FaissVectorSearch — real FAISS flat exact search (Phase 4.2).

Independent from §5 VectorIndex commit semantics. Lazy heavy imports.
"""

from __future__ import annotations

from typing import Optional

from knowledge_curator.ports.retrieval import (
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
)
from knowledge_curator.retrieval.embedder import DenseEmbedderPort
from knowledge_curator.schemas.chunk import ChunkLevel, KnowledgeChunk


class FaissVectorSearch:
    """FAISS-backed vector search honouring level/ref/top_k (Phase 4.2)."""

    def __init__(self, embedder: DenseEmbedderPort) -> None:
        self._embedder = embedder
        self._chunks: list[KnowledgeChunk] = []
        self._vectors: Optional[np.ndarray] = None
        self._index = None

    def add_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        import numpy as np

        if not chunks:
            return
        texts = [c.payload for c in chunks]
        vecs = self._embedder.embed(texts)
        if vecs.shape[1] != self._embedder.dimension:
            raise ValueError(
                f"dimension mismatch: got {vecs.shape[1]}, expected {self._embedder.dimension}"
            )
        self._chunks.extend(chunks)
        combined = vecs if self._vectors is None else np.vstack([self._vectors, vecs])
        self._vectors = combined
        self._rebuild_index()

    def _rebuild_index(self):
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError(
                "faiss is required for FaissVectorSearch. "
                "Install via: pip install -r knowledge_curator/requirements-retrieval.txt"
            ) from exc
        dim = self._embedder.dimension
        self._index = faiss.IndexFlatIP(dim)  # inner product on normalized = cosine
        if self._vectors is not None and len(self._vectors) > 0:
            self._index.add(self._vectors.astype(np.float32))

    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        import numpy as np

        if self._index is None or not self._chunks:
            return []
        qvec = self._embedder.embed([query.text])
        if qvec.shape[1] != self._embedder.dimension:
            raise ValueError("query dimension mismatch")
        # Search a wider pool then filter level/ref, ensuring enough results
        pool_size = min(len(self._chunks), max(query.top_k * 10, 100))
        scores, indices = self._index.search(qvec.astype(np.float32), pool_size)
        results: list[RetrievalCandidate] = []
        rank = 0
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._chunks):
                continue
            chunk = self._chunks[idx]
            if chunk.level != query.level:
                continue
            if query.allowed_ref_ids is not None and chunk.ref_id not in query.allowed_ref_ids:
                continue
            rank += 1
            results.append(
                RetrievalCandidate(
                    chunk=chunk,
                    channel=RetrievalChannel.VECTOR,
                    rank=rank,
                    raw_score=float(score),
                )
            )
            if rank >= query.top_k:
                break
        return results
