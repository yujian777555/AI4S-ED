"""JSON codec for Phase 4.3 evidence bundle / claim guard payloads."""

from __future__ import annotations

from typing import Any, Optional

from knowledge_curator.ports.evidence_store import CitationMetadata
from knowledge_curator.retrieval.evidence_models import (
    ClaimGuardResult,
    EvidenceBundle,
)
from knowledge_curator.retrieval.evidence_service import (
    EvidenceRequest,
    EvidenceRetrievalService,
)
from knowledge_curator.retrieval.guard_service import ClaimGuardService, ProposedClaimInput
from knowledge_curator.schemas.assertions import Assertion, Confidence


class EvidenceCodecError(ValueError):
    """Raised for malformed evidence/guard payloads."""


def _require_dict(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise EvidenceCodecError(f"{label} must be an object")
    return value


def parse_evidence_request(payload: dict[str, Any], *, integration_fixture: bool = False) -> EvidenceRequest:
    data = _require_dict(payload, "request")
    query = data.get("query") or ""
    subqueries = data.get("subqueries")
    if subqueries is not None:
        if not isinstance(subqueries, list) or not all(isinstance(s, str) for s in subqueries):
            raise EvidenceCodecError("subqueries must be a list of strings")
    top_k = int(data.get("top_k", 5))
    coarse_top_k = int(data.get("coarse_top_k", 10))
    allowed = data.get("allowed_ref_ids")
    if allowed is not None and not isinstance(allowed, list):
        raise EvidenceCodecError("allowed_ref_ids must be a list")
    coverage_keys = data.get("coverage_keys")
    required = data.get("required_coverage_keys")
    calibrated = data.get("calibrated_support")
    if calibrated is not None:
        try:
            calibrated = float(calibrated)
        except Exception as exc:
            raise EvidenceCodecError("calibrated_support must be a number") from exc

    return EvidenceRequest(
        query=query,
        subqueries=list(subqueries) if subqueries else None,
        top_k=top_k,
        coarse_top_k=coarse_top_k,
        allowed_ref_ids=list(allowed) if allowed else None,
        coverage_keys=list(coverage_keys) if coverage_keys else None,
        required_coverage_keys=list(required) if required else None,
        private_data_unauthorized=bool(data.get("private_data_unauthorized", False)),
        calibrated_support=calibrated,
        integration_fixture=integration_fixture,
    )


def parse_proposed_claims(items: Any) -> list[ProposedClaimInput]:
    if not isinstance(items, list):
        raise EvidenceCodecError("claims must be a list")
    out: list[ProposedClaimInput] = []
    for i, item in enumerate(items):
        d = _require_dict(item, f"claims[{i}]")
        cid = d.get("claim_id")
        if not cid or not isinstance(cid, str):
            raise EvidenceCodecError(f"claims[{i}].claim_id is required")
        text = str(d.get("text") or "")
        anchors = d.get("anchor_chunk_ids")
        if anchors is None:
            anchors = []
        if not isinstance(anchors, list) or not all(isinstance(a, str) for a in anchors):
            raise EvidenceCodecError(f"claims[{i}].anchor_chunk_ids must be a list of strings")

        cited = None
        if d.get("cited") is not None:
            cd = _require_dict(d["cited"], f"claims[{i}].cited")
            cited = CitationMetadata(
                ref_id=str(cd.get("ref_id") or ""),
                cited_title=cd.get("cited_title"),
                cited_doi=cd.get("cited_doi"),
            )

        assertion = None
        if d.get("assertion") is not None:
            # Minimal: only used for H3 id lookup when a validator is injected.
            ad = _require_dict(d["assertion"], f"claims[{i}].assertion")
            assertion = _stub_assertion(str(ad.get("id") or cid), str(ad.get("ref_id") or ""))

        ranges = d.get("numeric_source_ranges")
        if ranges is not None:
            parsed_ranges = []
            for r in ranges:
                if not isinstance(r, (list, tuple)) or len(r) != 2:
                    raise EvidenceCodecError(f"claims[{i}].numeric_source_ranges must be [low, high] pairs")
                parsed_ranges.append((float(r[0]), float(r[1])))
            ranges = parsed_ranges

        out.append(
            ProposedClaimInput(
                claim_id=cid,
                text=text,
                anchor_chunk_ids=list(anchors),
                is_critical_numeric=bool(d.get("is_critical_numeric", False)),
                coverage_key=d.get("coverage_key"),
                assertion=assertion,
                numeric_source_ranges=ranges,
                cited=cited,
                private_data_unauthorized=bool(d.get("private_data_unauthorized", False)),
                mechanism_supported=d.get("mechanism_supported"),
            )
        )
    return out


def _stub_assertion(aid: str, ref_id: str) -> Assertion:
    from knowledge_curator.schemas.assertions import (
        ClaimType,
        ObjectValue,
        SourceClaimOrigin,
        Subject,
        ValueType,
    )

    return Assertion(
        id=aid,
        ref_id=ref_id or "UNKNOWN",
        subject=Subject(eddo_class="Unknown", resolved_entity="unknown", original_mention=""),
        property="unknown",
        object=ObjectValue(value=None, unit=None, value_type=ValueType.TEXT),
        claim_type=ClaimType.RULE,
        source_claim_origin=SourceClaimOrigin.SECONDARY,
    )


def serialize_bundle(bundle: EvidenceBundle) -> dict[str, Any]:
    return {
        "bundle_id": bundle.bundle_id,
        "original_query": bundle.original_query,
        "subqueries": list(bundle.subqueries),
        "coverage_keys": list(bundle.coverage_keys),
        "top_k": bundle.top_k,
        "allowed_ref_ids": bundle.allowed_ref_ids,
        "integration_fixture": bundle.integration_fixture,
        "evidence_records": [
            {
                "chunk_id": r.chunk_id,
                "ref_id": r.ref_id,
                "locator": r.locator,
                "page_or_object_id": r.page_or_object_id,
                "confidence": r.confidence.value if r.confidence else None,
                "quality": r.quality,
                "access_pointer": r.access_pointer,
                "sentence_or_cell": r.sentence_or_cell,
                "chunk_type": r.chunk_type.value,
                "provenance": r.provenance,
                "evidence_type": r.evidence_type.value if r.evidence_type else None,
                "channels": [c.value for c in r.channels],
                "rank": r.rank,
                "rrf_score": r.rrf_score,
                "guardable_as_anchor": r.guardable_as_anchor,
                "unguardable_reasons": list(r.unguardable_reasons),
            }
            for r in bundle.evidence_records
        ],
        "unguardable_hits": [
            {
                "chunk_id": u.chunk_id,
                "ref_id": u.ref_id,
                "reasons": list(u.reasons),
            }
            for u in bundle.unguardable_hits
        ],
        "coverage": [
            {
                "coverage_key": c.coverage_key,
                "query_text": c.query_text,
                "state": c.state.value,
                "guardable_count": c.guardable_count,
                "hit_count": c.hit_count,
            }
            for c in bundle.coverage
        ],
        "retrieval_diagnostics": bundle.retrieval_diagnostics,
        "abstain": {
            "abstain": bundle.abstain.abstain,
            "reasons": list(bundle.abstain.reasons),
            "missing_evidence": bundle.abstain.missing_evidence,
            "recommended_gap_kinds": list(bundle.abstain.recommended_gap_kinds),
            "retrieval_support_checked": bundle.abstain.retrieval_support_checked,
            "calibrated_support": bundle.abstain.calibrated_support,
        },
        "trace": bundle.trace,
    }


def serialize_claim_result(r: ClaimGuardResult) -> dict[str, Any]:
    return {
        "claim_id": r.claim_id,
        "claim_text": r.claim_text,
        "resolved_anchors": [
            {
                "evidence_type": a.evidence_type.value,
                "ref_id": a.ref_id,
                "locator": a.locator,
                "confidence": a.confidence.value,
                "quality": a.quality,
                "access_pointer": a.access_pointer,
            }
            for a in r.resolved_anchors
        ],
        "unresolved_anchor_chunk_ids": list(r.unresolved_anchor_chunk_ids),
        "policy": {
            "policy": r.policy.policy.value,
            "effective_confidence": (
                r.policy.effective_confidence.value if r.policy.effective_confidence else None
            ),
            "reasons": list(r.policy.reasons),
        },
        "abstain": {
            "abstain": r.abstain.abstain,
            "reasons": [x.value for x in r.abstain.reasons],
            "missing_evidence": [
                {"kind": m.kind, "detail": m.detail, "coverage_key": m.coverage_key}
                for m in r.abstain.missing_evidence
            ],
            "recommended_gap_kinds": list(r.abstain.recommended_gap_kinds),
        },
        "h1": {
            "findings": [
                {
                    "type": f.type.value,
                    "claim_id": f.claim_id,
                    "reason": f.reason,
                    "anchor_ids": list(f.anchor_ids),
                    "detail": f.detail,
                }
                for f in r.h1.findings
            ],
            "locator_checks": [
                {"ref_id": c.ref_id, "locator": c.locator, "status": c.status.value}
                for c in r.h1.locator_checks
            ],
            "fully_checked": r.h1.fully_checked,
        },
        "h2": {
            "checked": r.h2_checked,
            "status": r.h2_status,
            "unavailable_reason": r.h2_unavailable_reason,
            "findings": [
                {
                    "type": f.type.value,
                    "claim_id": f.claim_id,
                    "reason": f.reason,
                    "anchor_ids": list(f.anchor_ids),
                    "detail": f.detail,
                }
                for f in r.h2_findings
            ],
        },
        "h3": {
            "status": r.h3.status.value,
            "findings": [
                {
                    "type": f.type.value,
                    "claim_id": f.claim_id,
                    "reason": f.reason,
                    "anchor_ids": list(f.anchor_ids),
                    "detail": f.detail,
                }
                for f in r.h3.findings
            ],
        },
        "numeric_conflict_policy": (
            r.numeric_conflict_policy.value if r.numeric_conflict_policy else None
        ),
        "retrieval_support_checked": r.retrieval_support_checked,
    }
