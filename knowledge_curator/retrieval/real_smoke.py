"""Real retrieval smoke harness (Phase 4.2.2).

KC_RUN_REAL_RETRIEVAL=1 python -m knowledge_curator.retrieval.real_smoke

Uses the real hybrid_retrieve pipeline:
fixture -> BGE-M3 -> FAISS + Jieba BM25 -> coarse RRF -> fine -> RRF -> optional bge-reranker -> hits

Smoke status: PASS / NOT_RUN_ENV / FAILED only.

Environment notes (Phase 4.2.2):
- Prefer local model dirs via KC_BGE_M3_MODEL / KC_BGE_RERANKER_MODEL.
- GPU is used automatically when torch.cuda.is_available().
- flag_compat must run before importing FlagEmbedding (tokenizer lazy-import crash).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Local model defaults (ASCII path avoids tokenizer path issues on this host).
_LOCAL_M3 = r"D:\models\bge-m3"
_LOCAL_RERANKER = r"D:\models\bge-reranker-v2-m3"


def preflight() -> tuple[bool, str]:
    """Check dependencies and model availability before real execution."""
    from knowledge_curator.retrieval.flag_compat import ensure_flagembedding_compat

    ensure_flagembedding_compat()
    missing = []
    for mod in ("numpy", "faiss", "jieba", "torch", "FlagEmbedding"):
        try:
            __import__(mod)
        except ImportError as exc:
            missing.append(f"{mod} ({exc})")
    if missing:
        return False, f"missing modules: {', '.join(missing)}"
    return True, "ok"


def _resolve_model(env_key: str, local_path: str, remote_name: str) -> str:
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val
    if os.path.isdir(local_path):
        return local_path
    return remote_name


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
        "m3_model_path": None,
        "reranker_model_path": None,
        "reranker_used": False,
        "load_seconds": None,
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
        import torch
        import importlib.metadata as md

        result["numpy_version"] = np.__version__
        result["faiss_version"] = faiss.__version__
        result["torch_version"] = torch.__version__
        result["device"] = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            result["flagembedding_version"] = md.version("FlagEmbedding")
        except Exception:
            result["flagembedding_version"] = "unknown"
        try:
            import jieba

            result["jieba_version"] = getattr(jieba, "__version__", "unknown")
        except Exception:
            result["jieba_version"] = "unknown"

        from knowledge_curator.retrieval.bm25 import BM25KeywordSearch, JiebaKeywordTokenizer
        from knowledge_curator.retrieval.embedder import BgeM3DenseEmbedder
        from knowledge_curator.retrieval.faiss_index import FaissVectorSearch
        from knowledge_curator.retrieval.fixture import build_fixture
        from knowledge_curator.retrieval.hybrid import RetrievalConfig, hybrid_retrieve
        from knowledge_curator.ports.retrieval import RetrievalQuery
        from knowledge_curator.schemas.chunk import ChunkLevel

        chunks, queries = build_fixture()

        m3_path = _resolve_model("KC_BGE_M3_MODEL", _LOCAL_M3, "BAAI/bge-m3")
        result["m3_model_path"] = m3_path

        use_fp16 = result["device"] == "cuda"
        t_load = time.time()
        embedder = BgeM3DenseEmbedder(
            model_name_or_path=m3_path,
            devices=result["device"],
            fp16=use_fp16,
            batch_size=8,
        )
        result["embedding_dimension"] = embedder.dimension

        # Reranker is optional: only used when a local/remote model is actually loadable.
        reranker = None
        reranker_path = _resolve_model(
            "KC_BGE_RERANKER_MODEL", _LOCAL_RERANKER, "BAAI/bge-reranker-v2-m3"
        )
        # Only auto-load reranker if a local directory exists (avoid HF download hang).
        if os.environ.get("KC_BGE_RERANKER_MODEL") or os.path.isdir(_LOCAL_RERANKER):
            try:
                from knowledge_curator.retrieval.reranker import BgeReranker

                reranker = BgeReranker(
                    model_name_or_path=reranker_path,
                    devices=result["device"],
                    fp16=use_fp16,
                )
                result["reranker_used"] = True
                result["reranker_model_path"] = reranker_path
            except Exception as exc:
                result["warnings"].append(
                    f"reranker unavailable, running without rerank: {type(exc).__name__}: {exc}"
                )
        else:
            result["warnings"].append(
                "reranker model not present locally; smoke runs hybrid_retrieve without reranker"
            )

        fine_chunks = [c for c in chunks if c.level == ChunkLevel.FINE]
        fine_vector = FaissVectorSearch(embedder)
        fine_vector.add_chunks(fine_chunks)
        fine_keyword = BM25KeywordSearch(tokenizer=JiebaKeywordTokenizer())
        fine_keyword.add_chunks(fine_chunks)

        config = RetrievalConfig(
            allow_fine_fallback_without_coarse=True,
            coarse_top_k=10,
            top_k=5,
        )
        result["load_seconds"] = round(time.time() - t_load, 2)

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

            top1 = set(returned_refs[:1])
            top3 = set(returned_refs[:3])

            r1 = len(top1 & expected_set) / len(expected_set) if expected_set else 0
            r3 = len(top3 & expected_set) / len(expected_set) if expected_set else 0
            recall_1_hits += 1 if r1 > 0 else 0
            recall_3_hits += 1 if r3 > 0 else 0

            rr = 0.0
            for i, ref in enumerate(returned_refs):
                if ref in expected_set:
                    rr = 1.0 / (i + 1)
                    break
            mrr_sum += rr

            result["per_query"].append(
                {
                    "query_id": fq.query_id,
                    "query": fq.text,
                    "expected_ref_ids": fq.expected_ref_ids,
                    "returned_top_k": returned_refs,
                    "recall_at_1": round(r1, 4),
                    "recall_at_3": round(r3, 4),
                    "reciprocal_rank": round(rr, 4),
                }
            )

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
