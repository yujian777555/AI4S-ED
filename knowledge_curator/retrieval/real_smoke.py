"""Real retrieval smoke harness (Phase 4.2.3).

KC_RUN_REAL_RETRIEVAL=1 python -m knowledge_curator.retrieval.real_smoke

Complete pipeline:
  fixture (COARSE+FINE) -> real BGE-M3 + FAISS + Jieba BM25
  -> coarse retrieval + RRF + allowed_ref_ids filter
  -> fine VECTOR/KEYWORD -> RRF -> real bge-reranker-v2-m3 -> final hits

Terminal status:
  PASS        — full-stack: coarse filter applied, no fallback, real reranker used,
                every labelled query hits expected evidence, all scores finite.
  NOT_RUN_ENV — missing deps, or reranker weights unavailable before load
                (full-stack). May also record degraded_without_reranker.
  FAILED      — execution error or acceptance rule violation.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

# Portable local defaults; env override wins. Source must not hard-require these.
_LOCAL_M3 = r"D:\models\bge-m3"
_LOCAL_RERANKER = r"D:\models\bge-reranker-v2-m3"


def preflight() -> tuple[bool, str]:
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


def _resolve_model(env_key: str, local_path: str, remote_name: str) -> tuple[str, bool]:
    """Return (path_or_id, is_local)."""
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val, os.path.isdir(env_val)
    if os.path.isdir(local_path):
        return local_path, True
    return remote_name, False


def _empty_result() -> dict:
    return {
        "status": "NOT_RUN_ENV",
        "full_stack_pass": False,
        "degraded_without_reranker": None,
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
        "reranker_candidate_pair_count": 0,
        "reranker_score_count": 0,
        "reranker_scores_finite": None,
        "real_bge_m3": False,
        "real_faiss": False,
        "real_bm25": False,
        "real_coarse_filter": False,
        "coarse_fallback_used": False,
        "load_seconds": None,
        "index_counts": {"coarse": 0, "fine": 0, "total": 0},
        "recall_at_1": None,
        "recall_at_3": None,
        "mrr": None,
        "per_query": [],
        "errors": [],
        "warnings": [],
    }


def _evaluate_queries(queries, fine_vector, fine_keyword, reranker, config, result):
    from knowledge_curator.ports.retrieval import RetrievalQuery
    from knowledge_curator.retrieval.hybrid import hybrid_retrieve
    from knowledge_curator.schemas.chunk import ChunkLevel

    recall_1_hits = 0
    recall_3_hits = 0
    mrr_sum = 0.0
    all_coarse_ok = True
    any_fallback = False
    any_missing_expected = False

    for fq in queries:
        q = RetrievalQuery(text=fq.text, level=ChunkLevel.FINE, top_k=5)
        res = hybrid_retrieve(
            q,
            vector_port=fine_vector,
            keyword_port=fine_keyword,
            reranker=reranker,
            config=config,
        )
        d = res.diagnostics
        returned_refs = [h.chunk.ref_id for h in res.hits]
        expected_set = set(fq.expected_ref_ids)

        top1 = set(returned_refs[:1])
        top3 = set(returned_refs[:3])
        r1 = len(top1 & expected_set) / len(expected_set) if expected_set else 0.0
        r3 = len(top3 & expected_set) / len(expected_set) if expected_set else 0.0
        recall_1_hits += 1 if r1 > 0 else 0
        recall_3_hits += 1 if r3 > 0 else 0

        rr = 0.0
        for i, ref in enumerate(returned_refs):
            if ref in expected_set:
                rr = 1.0 / (i + 1)
                break
        mrr_sum += rr

        coarse_ok = (
            d.coarse_backend_present
            and d.coarse_filter_applied
            and (not d.fallback_used)
            and d.coarse_fused_hit_count > 0
        )
        if not coarse_ok:
            all_coarse_ok = False
        if d.fallback_used:
            any_fallback = True

        # Pre-rerank refs: hits if no reranker else we don't have pre-rerank
        # recorded separately here; hybrid_retrieve only returns final hits.
        # Record coarse candidate refs from diagnostics counts.
        result["per_query"].append(
            {
                "query_id": fq.query_id,
                "query": fq.text,
                "expected_ref_ids": fq.expected_ref_ids,
                "expected_chunk_ids": fq.expected_chunk_ids,
                "coarse_backend_present": d.coarse_backend_present,
                "coarse_status": d.coarse_status,
                "coarse_filter_applied": d.coarse_filter_applied,
                "coarse_channels_attempted": [c.value for c in d.coarse_channels_attempted],
                "coarse_channels_with_hits": [c.value for c in d.coarse_channels_with_hits],
                "coarse_fused_hit_count": d.coarse_fused_hit_count,
                "fallback_used": d.fallback_used,
                "post_rerank_refs": returned_refs,
                "recall_at_1": round(r1, 4),
                "recall_at_3": round(r3, 4),
                "reciprocal_rank": round(rr, 4),
            }
        )

        if expected_set and not (set(returned_refs) & expected_set):
            any_missing_expected = True
            result["errors"].append(
                f"query {fq.query_id}: no expected evidence in final top-k"
            )

    n = len(queries)
    result["recall_at_1"] = round(recall_1_hits / n, 4) if n else 0
    result["recall_at_3"] = round(recall_3_hits / n, 4) if n else 0
    result["mrr"] = round(mrr_sum / n, 4) if n else 0
    result["real_coarse_filter"] = all_coarse_ok
    result["coarse_fallback_used"] = any_fallback
    return any_missing_expected


def run_smoke() -> dict:
    result = _empty_result()

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
        result["real_faiss"] = True
        try:
            result["flagembedding_version"] = md.version("FlagEmbedding")
        except Exception:
            result["flagembedding_version"] = "unknown"
        try:
            import jieba

            result["jieba_version"] = getattr(jieba, "__version__", "unknown")
            result["real_bm25"] = True
        except Exception:
            result["jieba_version"] = "unknown"

        from knowledge_curator.retrieval.bm25 import BM25KeywordSearch, JiebaKeywordTokenizer
        from knowledge_curator.retrieval.embedder import BgeM3DenseEmbedder
        from knowledge_curator.retrieval.faiss_index import FaissVectorSearch
        from knowledge_curator.retrieval.fixture import build_fixture
        from knowledge_curator.retrieval.hybrid import RetrievalConfig
        from knowledge_curator.retrieval.reranker import BgeReranker
        from knowledge_curator.schemas.chunk import ChunkLevel

        chunks, queries = build_fixture()
        coarse_chunks = [c for c in chunks if c.level == ChunkLevel.COARSE]
        fine_chunks = [c for c in chunks if c.level == ChunkLevel.FINE]
        result["index_counts"] = {
            "coarse": len(coarse_chunks),
            "fine": len(fine_chunks),
            "total": len(chunks),
        }

        m3_path, m3_local = _resolve_model("KC_BGE_M3_MODEL", _LOCAL_M3, "BAAI/bge-m3")
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
        result["real_bge_m3"] = True

        # Index COARSE + FINE together (RetrievalQuery.level filters at search time).
        vector_port = FaissVectorSearch(embedder)
        vector_port.add_chunks(coarse_chunks)
        vector_port.add_chunks(fine_chunks)

        keyword_port = BM25KeywordSearch(tokenizer=JiebaKeywordTokenizer())
        keyword_port.add_chunks(coarse_chunks)
        keyword_port.add_chunks(fine_chunks)

        # Reranker: full-stack PASS requires real weights. Missing -> NOT_RUN_ENV.
        reranker_path, reranker_local = _resolve_model(
            "KC_BGE_RERANKER_MODEL", _LOCAL_RERANKER, "BAAI/bge-reranker-v2-m3"
        )
        result["reranker_model_path"] = reranker_path

        reranker = None
        if reranker_local or os.environ.get("KC_BGE_RERANKER_MODEL"):
            try:
                reranker = BgeReranker(
                    model_name_or_path=reranker_path,
                    devices=result["device"],
                    fp16=use_fp16,
                )
                # Force load now so missing/corrupt weights fail before metrics.
                reranker._ensure_loaded()
                result["reranker_used"] = True
            except Exception as exc:
                result["errors"].append(
                    f"reranker load failed: {type(exc).__name__}: {exc}"
                )
                result["reranker_used"] = False
                reranker = None
        else:
            result["warnings"].append(
                "reranker weights not available locally and KC_BGE_RERANKER_MODEL not set"
            )

        config = RetrievalConfig(
            allow_fine_fallback_without_coarse=False,
            coarse_top_k=10,
            top_k=5,
        )
        result["load_seconds"] = round(time.time() - t_load, 2)

        # --- Run complete pipeline with/without reranker to capture pre-rerank ---
        # First pass without reranker to record pre-rerank top-k.
        from knowledge_curator.ports.retrieval import RetrievalQuery
        from knowledge_curator.retrieval.hybrid import hybrid_retrieve

        pre_rerank_by_q: dict[str, list[str]] = {}
        if queries:
            for fq in queries:
                q = RetrievalQuery(text=fq.text, level=ChunkLevel.FINE, top_k=5)
                res = hybrid_retrieve(
                    q,
                    vector_port=vector_port,
                    keyword_port=keyword_port,
                    reranker=None,
                    config=config,
                )
                pre_rerank_by_q[fq.query_id] = [h.chunk.ref_id for h in res.hits]

        # Full pipeline (reranker if available).
        any_missing = _evaluate_queries(
            queries, vector_port, keyword_port, reranker, config, result
        )

        # Attach pre-rerank refs
        for row in result["per_query"]:
            row["pre_rerank_refs"] = pre_rerank_by_q.get(row["query_id"], [])

        # Reranker execution evidence on a non-empty candidate set
        if result["reranker_used"] and queries:
            # Use the largest pre-rerank candidate list as the scored set.
            # hybrid_retrieve already reranked internally; score a real non-empty
            # candidate list explicitly for evidence.
            sample_q = queries[0]
            q = RetrievalQuery(text=sample_q.text, level=ChunkLevel.FINE, top_k=5)
            res = hybrid_retrieve(
                q,
                vector_port=vector_port,
                keyword_port=keyword_port,
                reranker=None,
                config=config,
            )
            candidates = res.hits
            if candidates:
                reranked = reranker.rerank(candidates, q)
                # Access scores via a direct compute for evidence
                pairs = [(q.text, h.chunk.payload) for h in candidates]
                raw = reranker._model.compute_score(pairs, normalize=True)
                from knowledge_curator.retrieval.reranker import _to_float_list

                scores = _to_float_list(raw, expected=len(candidates))
                result["reranker_candidate_pair_count"] = len(candidates)
                result["reranker_score_count"] = len(scores)
                result["reranker_scores_finite"] = all(math.isfinite(s) for s in scores)
                result.setdefault("reranker_sample_scores", [round(s, 6) for s in scores])
                result.setdefault(
                    "reranker_sample_pre_refs", [h.chunk.ref_id for h in candidates]
                )
                result.setdefault(
                    "reranker_sample_post_refs", [h.chunk.ref_id for h in reranked]
                )

        # --- Terminal status ---
        full_ready = (
            result["real_bge_m3"]
            and result["real_faiss"]
            and result["real_bm25"]
            and result["reranker_used"]
            and result["reranker_candidate_pair_count"] > 0
            and result["reranker_scores_finite"] is True
        )

        if not result["reranker_used"]:
            # Full-stack requires reranker. Run degraded diagnostic separately.
            result["status"] = "NOT_RUN_ENV"
            result["full_stack_pass"] = False
            result["degraded_without_reranker"] = (
                "PASS"
                if (result["real_coarse_filter"] and not result["coarse_fallback_used"] and not any_missing)
                else "FAILED"
            )
        elif not full_ready:
            result["status"] = "FAILED"
            result["full_stack_pass"] = False
        elif result["errors"] or any_missing:
            result["status"] = "FAILED"
            result["full_stack_pass"] = False
        elif not result["real_coarse_filter"] or result["coarse_fallback_used"]:
            result["status"] = "FAILED"
            result["full_stack_pass"] = False
        else:
            result["status"] = "PASS"
            result["full_stack_pass"] = True

    except Exception as exc:
        result["status"] = "FAILED"
        result["full_stack_pass"] = False
        result["errors"].append(f"{type(exc).__name__}: {exc}")

    return result


def main():
    result = run_smoke()
    out = Path("results/phase-04-2-3-real-smoke.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
