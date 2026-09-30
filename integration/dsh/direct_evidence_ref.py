"""Direct reference results for lane325 comparison (Phase 4.3.2).

Usage:
    python -m integration.dsh.direct_evidence_ref retrieve
    python -m integration.dsh.direct_evidence_ref validate

Prints one JSON object to stdout. No secrets.
Uses the same integration fixture runtime as KC_EVIDENCE_INTEGRATION_FIXTURE=1.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE_QUERY = "双极膜电渗析 能耗"
CLAIMS_PAYLOAD = [
    {
        "claim_id": "C1",
        "text": "BPM energy about 1.4 kWh/m3",
        "anchor_chunk_ids": ["R1-F1"],
    },
    {
        "claim_id": "C2",
        "text": "fabricated",
        "anchor_chunk_ids": ["NO-SUCH-CHUNK"],
    },
]


def _service():
    from knowledge_curator.mcp_server.evidence_runtime import build_fixture_evidence_service

    return build_fixture_evidence_service()


def _bundle_identity(bundle) -> dict:
    return {
        "bundle_id": bundle.bundle_id,
        "chunk_ids": [r.chunk_id for r in bundle.evidence_records],
        "coverage_keys": [c.coverage_key for c in bundle.coverage],
        "coverage_states": {c.coverage_key: c.state.value for c in bundle.coverage},
        "abstain": bundle.abstain.abstain,
        "abstain_reasons": list(bundle.abstain.reasons),
        "integration_fixture": bundle.integration_fixture,
    }


def do_retrieve() -> dict:
    from knowledge_curator.retrieval.evidence_service import EvidenceRequest

    svc = _service()
    bundle = svc.retrieve(
        EvidenceRequest(
            query=FIXTURE_QUERY,
            top_k=5,
            coverage_keys=["sq1"],
            required_coverage_keys=["sq1"],
            integration_fixture=True,
        )
    )
    return {"ok": True, "mode": "retrieve", "identity": _bundle_identity(bundle)}


def do_validate() -> dict:
    from knowledge_curator.mcp_server.evidence_codec import parse_proposed_claims
    from knowledge_curator.retrieval.evidence_service import EvidenceRequest
    from knowledge_curator.retrieval.guard_service import ClaimGuardService

    svc = _service()
    bundle = svc.retrieve(
        EvidenceRequest(
            query=FIXTURE_QUERY,
            top_k=5,
            coverage_keys=["sq1"],
            required_coverage_keys=["sq1"],
            integration_fixture=True,
        )
    )
    claims = parse_proposed_claims(CLAIMS_PAYLOAD)
    results = ClaimGuardService().validate_claims(bundle, claims)
    by_id = {r.claim_id: r for r in results}
    c1 = by_id.get("C1")
    c2 = by_id.get("C2")
    return {
        "ok": True,
        "mode": "validate",
        "bundle_id": bundle.bundle_id,
        "identity": {
            "C1": {
                "policy": c1.policy.policy.value if c1 else None,
                "abstain": c1.abstain.abstain if c1 else None,
            },
            "C2": {
                "unresolved": list(c2.unresolved_anchor_chunk_ids) if c2 else None,
                "policy": c2.policy.policy.value if c2 else None,
                "abstain": c2.abstain.abstain if c2 else None,
                "h1_types": [f.type.value for f in c2.h1.findings] if c2 else None,
            },
        },
    }


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "retrieve"
    os.environ.setdefault("KC_EVIDENCE_INTEGRATION_FIXTURE", "1")
    if mode == "retrieve":
        out = do_retrieve()
    elif mode == "validate":
        out = do_validate()
    else:
        out = {"ok": False, "error": f"unknown mode {mode}"}
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
