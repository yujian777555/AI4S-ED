"""Deterministic claim guard orchestration (Phase 4.3).

Composes frozen Phase 4.0 guards. Claims select evidence ONLY by
anchor_chunk_ids from the current retrieval set — never by fabricated
ref_id/locator/confidence. No prose answers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from knowledge_curator.ports.evidence_store import CitationMetadata, EvidenceMetadataPort
from knowledge_curator.ports.mechanism_validator import MechanismValidator
from knowledge_curator.retrieval.abstain import (
    AbstainConfig,
    AbstainDecision,
    MissingEvidence,
    evaluate_abstain,
)
from knowledge_curator.retrieval.evidence_guard import classify_claim_policy
from knowledge_curator.retrieval.evidence_models import (
    ClaimGuardResult,
    EvidenceBundle,
    RetrievalEvidenceRecord,
    build_evidence_anchor,
)
from knowledge_curator.retrieval.hallucination import (
    H3Result,
    H3Status,
    detect_h1_with_status,
    detect_h2,
    detect_h3,
)
from knowledge_curator.retrieval.retrieval_metadata import RetrievalSetMetadata
from knowledge_curator.schemas.assertions import Assertion, Confidence
from knowledge_curator.schemas.evidence import Claim, SurfacePolicy


@dataclass
class ProposedClaimInput:
    """Client-proposed claim. Must select evidence by chunk identity only."""

    claim_id: str
    text: str
    anchor_chunk_ids: list[str] = field(default_factory=list)
    is_critical_numeric: bool = False
    coverage_key: Optional[str] = None
    # Optional structured assertion for H3 (MechanismValidator).
    assertion: Optional[Assertion] = None
    numeric_source_ranges: Optional[list[tuple[float, float]]] = None
    cited: Optional[CitationMetadata] = None
    private_data_unauthorized: bool = False
    mechanism_supported: Optional[bool] = None


class H2CheckedStatus(str, Enum):
    """INTERNAL H2 check status (Phase 4.3.1)."""

    CHECKED = "checked"
    PARTIAL = "partial"
    METADATA_UNAVAILABLE = "metadata_unavailable"
    NOT_APPLICABLE = "not_applicable"


def evaluate_h2_checked(
    *,
    cited: Optional[CitationMetadata],
    metadata: EvidenceMetadataPort,
    ref_ids: list[str],
) -> tuple[bool, H2CheckedStatus, Optional[str]]:
    """Honest H2 checked semantics (Phase 4.3.1).

    - No cited DOI/title requested -> ref-existence scope is checked.
    - cited DOI supplied -> checked only if KB metadata has DOI and comparison ran.
    - cited title supplied -> same for title.
    - Both supplied -> both must be available for full checked.
    - Unavailable metadata is NOT an H2 finding; it is not-checked/partial.
    """
    if cited is None:
        # Only ref-existence was requested; RetrievalSetMetadata can check that.
        if not ref_ids:
            return False, H2CheckedStatus.NOT_APPLICABLE, None
        return True, H2CheckedStatus.CHECKED, None

    want_doi = bool(cited.cited_doi and str(cited.cited_doi).strip())
    want_title = bool(cited.cited_title and str(cited.cited_title).strip())
    if not want_doi and not want_title:
        return True, H2CheckedStatus.CHECKED, None

    ref_meta = metadata.get_ref_metadata(cited.ref_id) if cited.ref_id else None
    if ref_meta is None:
        return (
            False,
            H2CheckedStatus.METADATA_UNAVAILABLE,
            "ref metadata unavailable",
        )

    missing: list[str] = []
    if want_doi and not (ref_meta.doi and str(ref_meta.doi).strip()):
        missing.append("DOI")
    if want_title and not (ref_meta.title and str(ref_meta.title).strip()):
        missing.append("title")

    if not missing:
        return True, H2CheckedStatus.CHECKED, None

    reason = f"{'/'.join(missing)} metadata unavailable"
    if want_doi and want_title:
        # Both requested, at least one missing -> not fully checked.
        return False, H2CheckedStatus.PARTIAL, reason
    return False, H2CheckedStatus.METADATA_UNAVAILABLE, reason


class ClaimGuardService:
    """Validate proposed claims against one EvidenceBundle (retrieval-set bound)."""

    def __init__(
        self,
        *,
        metadata: Optional[EvidenceMetadataPort] = None,
        mechanism_validator: Optional[MechanismValidator] = None,
        ref_metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self._metadata = metadata
        self._mechanism_validator = mechanism_validator
        self._ref_metadata = ref_metadata or {}

    def validate_claims(
        self,
        bundle: EvidenceBundle,
        claims: list[ProposedClaimInput],
    ) -> list[ClaimGuardResult]:
        records_by_id = {r.chunk_id: r for r in bundle.evidence_records}
        # Also index ranked hit chunks (unguardable hits still exist as context).
        metadata = self._metadata or RetrievalSetMetadata(
            bundle.evidence_records,
            ref_metadata=self._ref_metadata,
        )

        results: list[ClaimGuardResult] = []
        for pc in claims:
            results.append(self._validate_one(pc, records_by_id, metadata, bundle))
        return results

    def _validate_one(
        self,
        pc: ProposedClaimInput,
        records_by_id: dict[str, RetrievalEvidenceRecord],
        metadata: EvidenceMetadataPort,
        bundle: EvidenceBundle,
    ) -> ClaimGuardResult:
        resolved = []
        unresolved: list[str] = []

        for cid in pc.anchor_chunk_ids:
            rec = records_by_id.get(cid)
            anchor = build_evidence_anchor(rec) if rec else None
            if anchor is None:
                unresolved.append(cid)
            else:
                resolved.append(anchor)

        claim = Claim(
            claim_id=pc.claim_id,
            text=pc.text,
            anchors=resolved,
            is_numeric=pc.is_critical_numeric,
            coverage_key=pc.coverage_key,
        )

        policy = classify_claim_policy(
            claim, numeric_source_ranges=pc.numeric_source_ranges
        )

        # CG-017: never feed raw retrieval scores. Only explicit calibrated_support.
        support = 1.0  # gate disabled unless caller supplies calibrated value
        retrieval_support_checked = False
        # calibrated_support lives on the bundle abstain result for query-level;
        # per-claim low-support is only evaluated when explicitly provided later.

        # Coverage: claim-level required keys from its coverage_key when present.
        required_keys = {pc.coverage_key} if pc.coverage_key else None
        covered_keys = None
        if required_keys:
            covered_keys = {
                c.coverage_key
                for c in bundle.coverage
                if c.guardable_count >= 1
            }

        # mechanism_supported: explicit, or H3 later; default True unless claim
        # explicitly unsupported.
        mechanism_supported = (
            True if pc.mechanism_supported is None else bool(pc.mechanism_supported)
        )

        abstain = evaluate_abstain(
            claim,
            retrieval_support=support,
            covered_keys=covered_keys,
            required_keys=required_keys,
            is_critical_numeric=pc.is_critical_numeric,
            mechanism_supported=mechanism_supported,
            private_data_unauthorized=pc.private_data_unauthorized,
            config=AbstainConfig(require_coverage=True),
        )

        # Fail closed: no valid retrieval-set anchor => Abstain (H1 path).
        if not resolved:
            abstain = AbstainDecision(
                abstain=True,
                reasons=abstain.reasons,
                missing_evidence=list(abstain.missing_evidence)
                + [
                    MissingEvidence(
                        kind="anchor",
                        detail="no valid retrieval-set evidence anchor",
                    )
                ],
                recommended_gap_kinds=list(abstain.recommended_gap_kinds) + ["evidence"],
            )

        h1 = detect_h1_with_status(claim, metadata)

        # H2: keep detect_h2 frozen. Unavailable metadata is NOT a hallucination
        # finding — only real DOI/title mismatch is. checked/status is honest.
        h2_findings = detect_h2(claim, metadata, pc.cited)
        h2_ref_ids = [a.ref_id for a in resolved] or [cid for cid in pc.anchor_chunk_ids]
        h2_checked, h2_status, h2_unavailable = evaluate_h2_checked(
            cited=pc.cited,
            metadata=metadata,
            ref_ids=h2_ref_ids,
        )
        if not bundle.evidence_records and not resolved:
            h2_checked = False
            h2_status = H2CheckedStatus.METADATA_UNAVAILABLE
            h2_unavailable = h2_unavailable or "metadata service unavailable: empty retrieval set"

        # H3
        if pc.assertion is not None and self._mechanism_validator is not None:
            h3 = detect_h3([pc.assertion], self._mechanism_validator)
        elif pc.assertion is not None and self._mechanism_validator is None:
            h3 = H3Result(status=H3Status.MECHANISM_UNAVAILABLE)
        else:
            h3 = H3Result(status=H3Status.NOT_CHECKED)

        numeric_conflict_policy = (
            policy.policy if policy.policy == SurfacePolicy.CONFLICT_DISCLOSURE_REQUIRED else None
        )

        return ClaimGuardResult(
            claim_id=pc.claim_id,
            claim_text=pc.text,
            resolved_anchors=resolved,
            unresolved_anchor_chunk_ids=unresolved,
            policy=policy,
            abstain=abstain,
            h1=h1,
            h2_findings=h2_findings,
            h2_checked=h2_checked,
            h2_status=h2_status.value,
            h2_unavailable_reason=h2_unavailable,
            h3=h3,
            numeric_conflict_policy=numeric_conflict_policy,
            retrieval_support_checked=retrieval_support_checked,
        )
