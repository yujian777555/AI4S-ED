"""BM25KeywordSearch — real Okapi BM25 with Chinese tokenization (Phase 4.2)."""

from __future__ import annotations

import math
from collections import Counter
from typing import Optional, Protocol, runtime_checkable

from knowledge_curator.ports.retrieval import (
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
)
from knowledge_curator.schemas.chunk import ChunkLevel, KnowledgeChunk


@runtime_checkable
class KeywordTokenizerPort(Protocol):
    """Keyword tokenizer for BM25 indexing."""

    def tokenize(self, text: str) -> list[str]:
        ...


class JiebaKeywordTokenizer:
    """Chinese-capable tokenizer using jieba (lazy import)."""

    def __init__(self) -> None:
        self._jieba = None

    def _ensure(self):
        if self._jieba is None:
            try:
                import jieba
            except ImportError as exc:
                raise RuntimeError(
                    "jieba is required for JiebaKeywordTokenizer. "
                    "Install via: pip install -r knowledge_curator/requirements-retrieval.txt"
                ) from exc
            self._jieba = jieba

    def tokenize(self, text: str) -> list[str]:
        self._ensure()
        return [t.strip() for t in self._jieba.lcut(text) if t.strip()]


class BM25KeywordSearch:
    """Standard Okapi BM25 adapter (Phase 4.2).

    Real BM25 scoring, not fake preset ranking.
    Supports Chinese + English/alphanumeric, level filter, allowed_ref_ids, top_k.
    """

    def __init__(
        self,
        tokenizer: Optional[KeywordTokenizerPort] = None,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self._tokenizer = tokenizer or JiebaKeywordTokenizer()
        self._k1 = k1
        self._b = b
        self._chunks: list[KnowledgeChunk] = []
        self._doc_freqs: list[Counter] = []
        self._doc_lens: list[int] = []
        self._avgdl: float = 0.0
        self._df: Counter = Counter()

    def add_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        for c in chunks:
            tokens = self._tokenizer.tokenize(c.payload)
            freq = Counter(tokens)
            self._chunks.append(c)
            self._doc_freqs.append(freq)
            self._doc_lens.append(len(tokens))
            for term in freq:
                self._df[term] += 1
        self._avgdl = (sum(self._doc_lens) / len(self._doc_lens)) if self._doc_lens else 0.0

    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        if not self._chunks:
            return []
        q_tokens = self._tokenizer.tokenize(query.text)
        if not q_tokens:
            return []
        n = len(self._chunks)
        scores: list[float] = []
        for i, freq in enumerate(self._doc_freqs):
            score = 0.0
            dl = self._doc_lens[i] or 1
            for term in q_tokens:
                if term not in freq:
                    continue
                tf = freq[term]
                df = self._df.get(term, 0)
                idf = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
                denom = tf + self._k1 * (1 - self._b + self._b * dl / (self._avgdl or 1))
                score += idf * (tf * (self._k1 + 1)) / denom
            scores.append(score)

        # Filter by level/ref, sort by score desc, assign 1-based ranks
        candidates = []
        for i, score in enumerate(scores):
            chunk = self._chunks[i]
            if chunk.level != query.level:
                continue
            if query.allowed_ref_ids is not None and chunk.ref_id not in query.allowed_ref_ids:
                continue
            if score <= 0:
                continue  # zero-overlap must not return false positives
            candidates.append((score, chunk))
        candidates.sort(key=lambda x: (-x[0], x[1].chunk_id))
        return [
            RetrievalCandidate(
                chunk=c,
                channel=RetrievalChannel.KEYWORD,
                rank=i + 1,
                raw_score=s,
            )
            for i, (s, c) in enumerate(candidates[: query.top_k])
        ]
