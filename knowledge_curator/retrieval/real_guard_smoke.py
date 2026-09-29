"""Real retrieval -> EvidenceBundle -> Evidence Guard smoke (Phase 4.3).

KC_RUN_REAL_GUARD_SMOKE=1 python -m knowledge_curator.retrieval.real_guard_smoke

Uses real BGE-M3 / FAISS / Jieba BM25 / coarse->fine / bge-reranker-v2-m3
from the frozen Phase 4.2 stack, then Phase 4.3 evidence bundle + guards.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_LOCAL_M3 = r"D:\models\bge-m3"
_LOCAL_RERANKER = r"D:\models\bge-reranker-v2-m3"


def run_smoke() -> dict:
    result = {
        "status": "NOT_RUN_ENV",
        "device": None,
        "real_bge_m3": False,
        "real_faiss": False,
        "real_bm25": False,
        "real_reranker": False,
        "evidence_normalization": None,
        "retrieval_set_anchor_binding": None,
        "confidence_policy": None,
        "abstain_coverage": None,
        "h1": None,
        "h2": None,
        "h3": None,
        "cases": [],
        "errors": [],
        "warnings": [],
        "provenance_trace": {},
    }

    # Env gate
    if os.environ.get("KC_RUN_REAL_GUARD_SMOKE") != "1":
        result["warnings"].append("set KC_RUN_REAL_GUARD_SMOKE=1 to execute")
        return result

    try:
        from knowledge_curator.retrieval.flag_compat import ensure_flagembedding_compat

        ensure_flagembedding_compat()
        import numpy  # noqa: F401
        import faiss  # noqa: F401
        import jieba  # noqa: F401
        import torch
        import FlagEmbedding  # noqa: F401
    except ImportError as exc:
        result["errors"].append(f"missing heavy dependency: {exc}")
        return result

    try:
        from knowledge_curator.adapters import FakeMechanismValidator
        from knowledge_curator.retrieval.bm25 import BM25KeywordSearch, JiebaKeywordTokenizer
        from knowledge_curator.retrieval.embedder import BgeM3DenseEmbedder
        from knowledge_curator.retrieval.evidence_models import build_evidence_anchor
        from knowledge_curator.retrieval.evidence_service import (
            EvidenceRequest,
            EvidenceRetrievalService,
        )
        from knowledge_curator.retrieval.faiss_index import FaissVectorSearch
        from knowledge_curator.retrieval.fixture import build_fixture
        from knowledge_curator.retrieval.guard_service import ClaimGuardService, ProposedClaimInput
        from knowledge_curator.retrieval.reranker import BgeReranker
        from knowledge_curator.ports.evidence_store import CitationMetadata
        from knowledge_curator.schemas.assertions import Confidence

        result["device"] = "cuda" if torch.cuda.is_available() else "cpu"
        m3_path = os.environ.get("KC_BGE_M3_MODEL") or (
            _LOCAL_M3 if os.path.isdir(_LOCAL_M3) else "BAAI/bge-m3"
        )
        rr_path = os.environ.get("KC_BGE_RERANKER_MODEL") or (
            _LOCAL_RERANKER if os.path.isdir(_LOCAL_RERANKER) else "BAAI/bge-reranker-v2-m3"
        )
        use_fp16 = result["device"] == "cuda"

        embedder = BgeM3DenseEmbedder(
            model_name_or_path=m3_path, devices=result["device"], fp16=use_fp16
        )
        _ = embedder.dimension
        result["real_bge_m3"] = True

        chunks, queries = build_fixture()
        vector_port = FaissVectorSearch(embedder)
        vector_port.add_chunks(chunks)
        result["real_faiss"] = True

        keyword_port = BM25KeywordSearch(tokenizer=JiebaKeywordTokenizer())
        keyword_port.add_chunks(chunks)
        result["real_bm25"] = True

        if not os.path.isdir(rr_path) and not os.environ.get("KC_BGE_RERANKER_MODEL"):
            result["warnings"].append("reranker weights missing; smoke NOT_RUN_ENV")
            return result
        reranker = BgeReranker(model_name_or_path=rr_path, devices=result["device"], fp16=use_fp16)
        reranker._ensure_loaded()
        result["real_reranker"] = True

        service = EvidenceRetrievalService(
            vector_port=vector_port,
            keyword_port=keyword_port,
            reranker=reranker,
        )
        guard = ClaimGuardService(mechanism_validator=FakeMechanismValidator())

        # ---- retrieval on a labelled query ----
        q1 = "双极膜电渗析 能耗"
        req = EvidenceRequest(query=q1, top_k=5, coverage_keys=["sq1"], required_coverage_keys=["sq1"])
        bundle = service.retrieve(req)

        # evidence normalization checks
        records = bundle.evidence_records
        guardable = [r for r in records if r.guardable_as_anchor]
        result["evidence_normalization"] = "PASS" if guardable else "FAILED"
        result["provenance_trace"] = {
            "bundle_id": bundle.bundle_id,
            "record_count": len(records),
            "guardable_count": len(guardable),
            "sample_chunk_ids": [r.chunk_id for r in records[:5]],
            "reranker_used": bundle.trace.get("reranker_used"),
        }

        # provenance survives: each record has channels + rank + ref_id
        prov_ok = all(r.ref_id and r.channels and r.rank >= 1 for r in records)
        if not prov_ok:
            result["errors"].append("provenance fields missing after rerank")

        # ---- Case A: HIGH claim -> FACTUAL_ALLOWED, no Abstain/H1 ----
        high_rec = next((r for r in guardable if r.confidence == Confidence.HIGH), None)
        if high_rec is None:
            result["errors"].append("no HIGH guardable record found")
            high_id = None
        else:
            high_id = high_rec.chunk_id

        claims = []
        if high_id:
            claims.append(ProposedClaimInput(
                claim_id="C-HIGH",
                text="BPM energy consumption is about 1.4 kWh/m3",
                anchor_chunk_ids=[high_id],
            ))
        # ---- Case B: MEDIUM claim -> CAVEATED_ONLY ----
        med_rec = next((r for r in guardable if r.confidence == Confidence.MEDIUM), None)
        if med_rec:
            claims.append(ProposedClaimInput(
                claim_id="C-MED",
                text="Membrane fouling reduces flux and needs cleaning",
                anchor_chunk_ids=[med_rec.chunk_id],
            ))
        # ---- Case C: unknown anchor -> H1 + Abstain ----
        claims.append(ProposedClaimInput(
            claim_id="C-UNKNOWN",
            text="Fabricated claim with fake anchor",
            anchor_chunk_ids=["NO-SUCH-CHUNK"],
        ))
        # ---- Case D: private unauthorized -> Abstain ----
        if high_id:
            claims.append(ProposedClaimInput(
                claim_id="C-PRIV",
                text="Private measurement",
                anchor_chunk_ids=[high_id],
                private_data_unauthorized=True,
            ))

        results = guard.validate_claims(bundle, claims)
        by_id = {r.claim_id: r for r in results}

        def _case(name, cid, expect_policy=None, expect_abstain=None, expect_h1=False):
            r = by_id.get(cid)
            if r is None:
                result["cases"].append({"name": name, "status": "MISSING"})
                return
            ok = True
            detail = {
                "policy": r.policy.policy.value,
                "abstain": r.abstain.abstain,
                "h1_findings": len(r.h1.findings),
                "h2_checked": r.h2_checked,
                "h3_status": r.h3.status.value,
            }
            if expect_policy and r.policy.policy.value != expect_policy:
                ok = False
            if expect_abstain is not None and r.abstain.abstain != expect_abstain:
                ok = False
            if expect_h1 and not r.h1.findings:
                ok = False
            result["cases"].append({"name": name, "claim_id": cid, "ok": ok, **detail})
            return ok

        a_ok = _case("HIGH->FACTUAL_ALLOWED", "C-HIGH", expect_policy="factual_allowed", expect_abstain=False)
        b_ok = _case("MEDIUM->CAVEATED_ONLY", "C-MED", expect_policy="caveated_only", expect_abstain=False)
        c_ok = _case("UNKNOWN->H1+Abstain", "C-UNKNOWN", expect_abstain=True, expect_h1=True)
        d_ok = _case("PRIVATE->Abstain", "C-PRIV", expect_abstain=True)

        result["confidence_policy"] = "PASS" if (a_ok and b_ok) else "FAILED"
        result["abstain_coverage"] = "PASS" if (c_ok and d_ok) else "FAILED"
        result["h1"] = "PASS" if c_ok else "FAILED"
        if not (a_ok and b_ok and c_ok and d_ok):
            result["errors"].append("one or more guard cases failed")

        # H2: literature anchors exist in retrieval set -> no finding
        high_res = by_id.get("C-HIGH")
        if high_res is not None and high_res.h2_checked and not high_res.h2_findings:
            result["h2"] = "PASS"
        elif high_res is not None and not high_res.h2_checked:
            result["h2"] = "PARTIAL"
        else:
            result["h2"] = "FAILED"

        # H3: no structured assertion -> NOT_CHECKED (explicit, not fake pass)
        if high_res is not None and high_res.h3.status.value in ("not_checked", "mechanism_unavailable"):
            result["h3"] = "PASS"
        else:
            result["h3"] = "PARTIAL"

        # retrieval-set anchor binding: unknown chunk not resolved
        if high_res is not None:
            unk = by_id.get("C-UNKNOWN")
            if unk is not None and unk.unresolved_anchor_chunk_ids == ["NO-SUCH-CHUNK"]:
                result["retrieval_set_anchor_binding"] = "PASS"
            else:
                result["retrieval_set_anchor_binding"] = "FAILED"

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
    out = Path("results/phase-04-3-guard-smoke.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
