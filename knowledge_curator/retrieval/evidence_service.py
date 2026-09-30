"""EvidenceRetrievalService (Phase 4.3) — runtime-independent composition.

Delegates ranking ONLY to the frozen hybrid_retrieve. Normalizes hits into
guardable EvidenceRecords (fail closed) and computes coverage/Abstain state.

No prose answers. No second ranking implementation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from knowledge_curator.ports.retrieval import (
    KeywordSearchPort,
    RankedHit,
    RerankerPort,
    RetrievalQuery,
    VectorSearchPort,
)
from knowledge_curator.retrieval.abstain import (
    AbstainConfig,
    AbstainReason,
    evaluate_abstain,
)
from knowledge_curator.retrieval.evidence_models import (
    CoverageState,
    EvidenceBundle,
    QueryAbstainResult,
    RetrievalEvidenceRecord,
    SubqueryCoverage,
    UnguardableHit,
    build_evidence_anchor,
    compute_bundle_id,
    normalize_hit_to_record,
)
from knowledge_curator.retrieval.hybrid import RetrievalConfig, hybrid_retrieve
from knowledge_curator.schemas.chunk import ChunkLevel
from knowledge_curator.schemas.evidence import Claim, EvidenceType


@dataclass
class EvidenceRequest:
    """Input for EvidenceRetrievalService."""

    query: str
    subqueries: Optional[list[str]] = None
    top_k: int = 5
    coarse_top_k: int = 10
    allowed_ref_ids: Optional[list[str]] = None
    coverage_keys: Optional[list[str]] = None
    required_coverage_keys: Optional[list[str]] = None
    private_data_unauthorized: bool = False
    # CG-017: only used when explicitly calibrated. Never feed raw retrieval scores.
    calibrated_support: Optional[float] = None
    integration_fixture: bool = False
    # Phase 5.0-R1: INTERNAL explicit historical version selector.
    at_version_id: Optional[str] = None


class _EligibilityFilteredPort:
    """Progressive pre-cutoff lifecycle filter (R2-A + R2-C).

    Expands backend depth until enough lifecycle-eligible candidates are
    obtained or the backend is proven exhausted. Applies BOTH document and
    assertion-level eligibility. Preserves backend rank order and does not
    re-rank.
    """

    # Deterministic progressive depths. Start small, grow geometrically.
    _INITIAL_DEPTH = 50
    _MAX_STEPS = 12  # safety bound: 50 * 2^11 is enormous

    def __init__(self, inner: Any, visibility: Any, at_version_id: Optional[str] = None) -> None:
        self._inner = inner
        self._visibility = visibility
        self._at_version_id = at_version_id

    def _is_eligible(self, candidate: Any) -> bool:
        chunk = getattr(candidate, "chunk", candidate)
        doc = self._visibility.document_eligibility(
            chunk.ref_id, at_version_id=self._at_version_id
        )
        if not doc.visible_for_retrieval:
            return False
        assertion_id = getattr(chunk, "assertion_id", None)
        if assertion_id is not None:
            a_elig = self._visibility.assertion_eligibility(
                assertion_id, chunk.ref_id, at_version_id=self._at_version_id
            )
            if not a_elig.visible_for_retrieval:
                return False
        return True

    def search(self, query: RetrievalQuery) -> list[Any]:
        target = max(int(query.top_k or 1), 1)
        depth = self._INITIAL_DEPTH
        best_out: list[Any] = []
        prev_eligible_ids: frozenset = frozenset()

        for _step in range(self._MAX_STEPS):
            expanded_query = RetrievalQuery(
                text=query.text,
                level=query.level,
                top_k=depth,
                allowed_ref_ids=query.allowed_ref_ids,
                subquestion_id=query.subquestion_id,
            )
            cands = self._inner.search(expanded_query)
            if not cands:
                break

            out = [c for c in cands if self._is_eligible(c)]
            eligible_ids = frozenset(
                getattr(c, "chunk", c).chunk_id for c in out
            )

            # Keep the deepest successful eligible set (preserves backend order).
            if len(out) >= len(best_out):
                best_out = out

            if len(out) >= target:
                return out

            # Exhaustion A: backend returned fewer than requested depth.
            if len(cands) < depth:
                break

            # Exhaustion B: expanding produced no new eligible identities.
            if depth > self._INITIAL_DEPTH and eligible_ids == prev_eligible_ids:
                break
            prev_eligible_ids = eligible_ids

            depth = depth * 2

        return best_out


class EvidenceRetrievalService:
    """Compose frozen retrieval into an EvidenceBundle."""

    def __init__(
        self,
        *,
        vector_port: Optional[VectorSearchPort] = None,
        keyword_port: Optional[KeywordSearchPort] = None,
        reranker: Optional[RerankerPort] = None,
        retrieval_config: Optional[RetrievalConfig] = None,
        default_evidence_type: Optional[EvidenceType] = EvidenceType.LITERATURE,
        lifecycle_visibility: Optional[Any] = None,
    ) -> None:
        self._vector_port = vector_port
        self._keyword_port = keyword_port
        self._reranker = reranker
        self._config = retrieval_config or RetrievalConfig(
            allow_fine_fallback_without_coarse=False,
            coarse_top_k=10,
            top_k=5,
        )
        self._default_evidence_type = default_evidence_type
        self._lifecycle_visibility = lifecycle_visibility

    def retrieve(self, request: EvidenceRequest) -> EvidenceBundle:
        if self._vector_port is None and self._keyword_port is None:
            raise RuntimeError("retrieval_unavailable: no retrieval backends configured")

        subqueries = list(request.subqueries or [])
        if not request.query and not subqueries:
            raise ValueError("query or subqueries is required")
        if not subqueries:
            subqueries = [request.query]

        coverage_keys = list(request.coverage_keys or [])
        if not coverage_keys:
            coverage_keys = [f"sq{i+1}" for i in range(len(subqueries))]
        if len(coverage_keys) != len(subqueries):
            raise ValueError("coverage_keys length must match subqueries length")
        required = (
            set(request.required_coverage_keys)
            if request.required_coverage_keys is not None
            else set(coverage_keys)
        )

        allowed = set(request.allowed_ref_ids) if request.allowed_ref_ids else None
        # Lifecycle composition (Phase 5.0): restrict allowed refs BEFORE frozen
        # hybrid_retrieve so retracted refs cannot enter candidates at all.
        at_version = request.at_version_id
        vector_port = self._vector_port
        keyword_port = self._keyword_port
        if self._lifecycle_visibility is not None:
            if allowed is not None:
                eligible = set(
                    self._lifecycle_visibility.eligible_ref_ids(
                        list(allowed), at_version_id=at_version
                    )
                )
                allowed = eligible if eligible else set()
            else:
                vector_port = (
                    _EligibilityFilteredPort(
                        self._vector_port, self._lifecycle_visibility, at_version_id=at_version
                    )
                    if self._vector_port is not None
                    else None
                )
                keyword_port = (
                    _EligibilityFilteredPort(
                        self._keyword_port, self._lifecycle_visibility, at_version_id=at_version
                    )
                    if self._keyword_port is not None
                    else None
                )

        all_hits: list[RankedHit] = []
        diagnostics: list[dict] = []
        records: list[RetrievalEvidenceRecord] = []
        unguardable: list[UnguardableHit] = []
        coverage: list[SubqueryCoverage] = []

        cfg = RetrievalConfig(
            rrf_k=self._config.rrf_k,
            top_k=request.top_k,
            coarse_top_k=request.coarse_top_k,
            allow_fine_fallback_without_coarse=self._config.allow_fine_fallback_without_coarse,
        )

        for key, sq_text in zip(coverage_keys, subqueries):
            q = RetrievalQuery(
                text=sq_text,
                level=ChunkLevel.FINE,
                top_k=request.top_k,
                allowed_ref_ids=allowed,
                subquestion_id=key,
            )
            res = hybrid_retrieve(
                q,
                vector_port=vector_port,
                keyword_port=keyword_port,
                reranker=self._reranker,
                config=cfg,
            )
            d = res.diagnostics
            diagnostics.append(
                {
                    "coverage_key": key,
                    "query_text": sq_text,
                    "coarse_backend_present": d.coarse_backend_present,
                    "coarse_status": d.coarse_status,
                    "coarse_filter_applied": d.coarse_filter_applied,
                    "coarse_channels_attempted": [c.value for c in d.coarse_channels_attempted],
                    "coarse_channels_with_hits": [c.value for c in d.coarse_channels_with_hits],
                    "coarse_fused_hit_count": d.coarse_fused_hit_count,
                    "fallback_used": d.fallback_used,
                    "channels_used": [c.value for c in d.channels_used],
                    "hit_count": len(res.hits),
                }
            )

            guardable_n = 0
            for hit in res.hits:
                all_hits.append(hit)
                rec = normalize_hit_to_record(hit, default_evidence_type=self._default_evidence_type)
                records.append(rec)
                # Coverage counts only records that can actually produce an anchor.
                if rec.guardable_as_anchor and build_evidence_anchor(rec) is not None:
                    guardable_n += 1
                else:
                    unguardable.append(
                        UnguardableHit(
                            chunk_id=rec.chunk_id,
                            ref_id=rec.ref_id,
                            reasons=list(rec.unguardable_reasons),
                        )
                    )

            state = (
                CoverageState.COVERED
                if guardable_n >= 1
                else CoverageState.NOT_COVERED
            )
            coverage.append(
                SubqueryCoverage(
                    coverage_key=key,
                    query_text=sq_text,
                    state=state,
                    guardable_count=guardable_n,
                    hit_count=len(res.hits),
                )
            )

        covered_keys = {c.coverage_key for c in coverage if c.state == CoverageState.COVERED}

        # Query-level Abstain using a dummy claim-shaped object (coverage + privacy gates).
        dummy_claim = Claim(claim_id="bundle", text=request.query, anchors=[])
        # CG-017: only use calibrated_support when explicitly provided.
        support_checked = request.calibrated_support is not None
        support_value = request.calibrated_support if support_checked else 1.0

        decision = evaluate_abstain(
            dummy_claim,
            retrieval_support=support_value,
            covered_keys=covered_keys,
            required_keys=required,
            is_critical_numeric=False,
            mechanism_supported=True,
            private_data_unauthorized=request.private_data_unauthorized,
            config=AbstainConfig(require_coverage=True),
        )
        abstain = QueryAbstainResult(
            abstain=decision.abstain,
            reasons=[r.value for r in decision.reasons],
            missing_evidence=[
                {
                    "kind": m.kind,
                    "detail": m.detail,
                    "coverage_key": m.coverage_key,
                }
                for m in decision.missing_evidence
            ],
            recommended_gap_kinds=list(decision.recommended_gap_kinds),
            retrieval_support_checked=support_checked,
            calibrated_support=request.calibrated_support,
        )

        hit_ids = [h.chunk.chunk_id for h in all_hits]
        bundle_id = compute_bundle_id(request.query, subqueries, hit_ids)

        return EvidenceBundle(
            bundle_id=bundle_id,
            original_query=request.query,
            subqueries=subqueries,
            coverage_keys=coverage_keys,
            top_k=request.top_k,
            allowed_ref_ids=list(request.allowed_ref_ids) if request.allowed_ref_ids else None,
            ranked_hits=all_hits,
            evidence_records=records,
            unguardable_hits=unguardable,
            coverage=coverage,
            retrieval_diagnostics=diagnostics,
            abstain=abstain,
            trace={
                "pipeline": "hybrid_retrieve",
                "reranker_used": self._reranker is not None,
                "default_evidence_type": (
                    self._default_evidence_type.value if self._default_evidence_type else None
                ),
                "record_count": len(records),
                "guardable_count": sum(1 for r in records if r.guardable_as_anchor),
            },
            integration_fixture=request.integration_fixture,
        )
