"""Real retrieval smoke harness (Phase 4.2.2).

KC_RUN_REAL_RETRIEVAL=1 python -m knowledge_curator.retrieval.real_smoke

Uses the real hybrid_retrieve pipeline:
fixture -> BGE-M3 -> FAISS + Jieba BM25 -> coarse RRF -> fine -> RRF -> bge-reranker -> hits

Smoke status: PASS / NOT_RUN_ENV / FAILED only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def preflight() -> tuple[bool, str]:
    """Check dependencies and model availability before real execution."""
    missing = []
    for mod in ("numpy", "faiss", "jieba", "torch", "FlagEmbedding"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return False, f"missing modules: {', '.join(missing)}"
    return True, "ok"


def run_smoke() -> dict:
    result = {
        "status": "NOT_RUN_ENV",
        "embedding_dimension": None,
        "device": None,
        "flagembedding_version": None,
        "faiss_version": None,
        "numpy_version": None,
        "jieba_version": None,
        "torch_version": None,
        "recall_at_1": None,
        "recall_at_3": None,
        "mrr": None,
        "per_query": [],
        "errors": [],
        "warnings": [],
    }

    ok, reason = preflight()
    if not ok:
        result["errors"].append(reason)
        return result

    try:
        import numpy as np
        import faiss
        import jieba
        import torch
        import FlagEmbedding
        import importlib.metadata as md

        result["numpy_version"] = np.__version__
        result["faiss_version"] = faiss.__version__
        result["torch_version"] = torch.__version__
        result["device"] = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            result["flagembedding_version"] = md.version("FlagEmbedding")
        except Exception:
            result["flagembedding_version"] = "unknown"

        from knowledge_curator.retrieval.bm25 import BM25KeywordSearch, JiebaKeywordTokenizer
        from knowledge_curator.retrieval.embedder import BgeM3DenseEmbedder
        from knowledge_curator.retrieval.faiss_index import FaissVectorSearch
        from knowledge_curator.retrieval.fixture import build_fixture
        from knowledge_curator.retrieval.hybrid import RetrievalConfig, hybrid_retrieve
        from knowledge_curator.retrieval.reranker import BgeReranker
        from knowledge_curator.ports.retrieval import RetrievalQuery
        from knowledge_curator.schemas.chunk import ChunkLevel

        chunks, queries = build_fixture()

        # Load real models
        m3_path = os.environ.get("KC_BGE_M3_MODEL") or "BAAI/bge-m3"
        reranker_path = os.environ.get("KC_BGE_RERANKER_MODEL") or "BAAI/bge-reranker-v2-m3"

        embedder = BgeM3DenseEmbedder(model_name_or_path=m3_path)
        result["embedding_dimension"] = embedder.dimension

        vector_port = FaissVectorSearch(embedder)
        vector_port.add_chunks(chunks)

        keyword_port = BM25KeywordSearch(tokenizer=JiebaKeywordTokenizer())
        keyword_port.add_chunks(chunks)

        reranker = BgeReranker(model_name_or_path=reranker_path)

        config = RetrievalConfig(
            allow_fine_fallback_without_coarse=True,
            coarse_top_k=10,
            top_k=5,
        )

        # Build coarse and fine indexes
        coarse_chunks = [c for c in chunks if c.level == ChunkLevel.COARSE]
        fine_chunks = [c for c in chunks if c.level == ChunkLevel.FINE]

        coarse_vector = FaissVectorSearch(embedder)
        coarse_vector.add_chunks(coarse_chunks)
        coarse_keyword = BM25KeywordSearch(tokenizer=JiebaKeywordTokenizer())
        coarse_keyword.add_chunks(coarse_chunks)

        fine_vector = FaissVectorSearch(embedder)
        fine_vector.add_chunks(fine_chunks)
        fine_keyword = BM25KeywordSearch(tokenizer=JiebaKeywordTokenizer())
        fine_keyword.add_chunks(fine_chunks)

        # Evaluate each query
        recall_1_hits = 0
        recall_3_hits = 0
        mrr_sum = 0.0
        for fq in queries:
            q = RetrievalQuery(text=fq.text, level=ChunkLevel.FINE, top_k=5)
            res = hybrid_retrieve(
                q,
                vector_port=fine_vector,
                keyword_port=fine_keyword,
                reranker=reranker,
                config=config,
            )
            returned_refs = [h.chunk.ref_id for h in res.hits]
            expected_set = set(fq.expected_ref_ids)

            # Recall@k: fraction of expected refs in top-k
            top1 = set(returned_refs[:1])
            top3 = set(returned_refs[:3])
            top5 = set(returned_refs[:5])

            r1 = len(top1 & expected_set) / len(expected_set) if expected_set else 0
            r3 = len(top3 & expected_set) / len(expected_set) if expected_set else 0
            recall_1_hits += 1 if r1 > 0 else 0
            recall_3_hits += 1 if r3 > 0 else 0

            # MRR: reciprocal rank of first expected ref
            rr = 0.0
            for i, ref in enumerate(returned_refs):
                if ref in expected_set:
                    rr = 1.0 / (i + 1)
                    break
            mrr_sum += rr

            result["per_query"].append({
                "query_id": fq.query_id,
                "query": fq.text,
                "expected_ref_ids": fq.expected_ref_ids,
                "returned_top_k": returned_refs,
                "recall_at_1": round(r1, 4),
                "recall_at_3": round(r3, 4),
                "reciprocal_rank": round(rr, 4),
            })

            # Any query with zero expected evidence in final top-k -> FAILED
            if expected_set and not (set(returned_refs) & expected_set):
                result["errors"].append(
                    f"query {fq.query_id}: no expected evidence in final top-k"
                )

        n = len(queries)
        result["recall_at_1"] = round(recall_1_hits / n, 4) if n else 0
        result["recall_at_3"] = round(recall_3_hits / n, 4) if n else 0
        result["mrr"] = round(mrr_sum / n, 4) if n else 0

        if result["errors"]:
            result["status"] = "FAILED"
        else:
            result["status"] = "PASS"

    except Exception as exc:
        # Preflight succeeded but execution failed -> FAILED (not NOT_RUN_ENV)
        result["status"] = "FAILED"
        result["errors"].append(f"{type(exc).__name__}: {exc}")

    return result


def main():
    result = run_smoke()
    out = Path("results/phase-04-2-2-real-smoke.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
