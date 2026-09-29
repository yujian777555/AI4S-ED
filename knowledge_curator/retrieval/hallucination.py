"""H1/H2/H3 hallucination detectors (docs/03 §6.5). Deterministic local checks.

H1 = unsupported/misaligned claim anchor
H2 = fabricated/nonexistent literature citation (KB local existence only)
H3 = mechanism violation (via MechanismValidator Port)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from knowledge_curator.ports.evidence_store import EvidenceMetadataPort
from knowledge_curator.ports.mechanism_validator import MechanismValidator
from knowledge_curator.schemas.assertions import Assertion, Confidence
from knowledge_curator.schemas.evidence import Claim, EvidenceType


class HallucinationType(str, Enum):
    H1 = "H1"
    H2 = "H2"
    H3 = "H3"


class H3Status(str, Enum):
    CHECKED = "checked"
    NOT_CHECKED = "not_checked"
    MECHANISM_UNAVAILABLE = "mechanism_unavailable"


@dataclass
class HallucinationFinding:
    """One hallucination detector finding."""

    type: HallucinationType
    claim_id: str
    reason: str
    anchor_ids: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


@dataclass
class H3Result:
    """H3 check result with explicit unavailability state."""

    status: H3Status
    findings: list[HallucinationFinding] = field(default_factory=list)


def detect_h1(claim: Claim, metadata: EvidenceMetadataPort) -> list[HallucinationFinding]:
    """H1: require valid anchors for factual/numeric claims."""
    findings: list[HallucinationFinding] = []
    if not claim.anchors:
        findings.append(
            HallucinationFinding(
                type=HallucinationType.H1,
                claim_id=claim.claim_id,
                reason="no evidence anchor",
            )
        )
        return findings

    for anchor in claim.anchors:
        if not anchor.ref_id:
            findings.append(
                HallucinationFinding(
                    type=HallucinationType.H1,
                    claim_id=claim.claim_id,
                    reason="anchor ref_id empty",
                    anchor_ids=[],
                )
            )
            continue
        if not metadata.ref_exists(anchor.ref_id):
            # ref not in KB -> also H2 territory; H1 notes misalignment
            findings.append(
                HallucinationFinding(
                    type=HallucinationType.H1,
                    claim_id=claim.claim_id,
                    reason=f"anchor ref_id not resolvable: {anchor.ref_id}",
                    anchor_ids=[anchor.ref_id],
                )
            )
        if not anchor.locator or not anchor.locator.strip():
            findings.append(
                HallucinationFinding(
                    type=HallucinationType.H1,
                    claim_id=claim.claim_id,
                    reason="anchor locator empty",
                    anchor_ids=[anchor.ref_id],
                )
            )
    return findings


def detect_h2(claim: Claim, metadata: EvidenceMetadataPort) -> list[HallucinationFinding]:
    """H2: KB local existence check only (no Crossref/web)."""
    findings: list[HallucinationFinding] = []
    for anchor in claim.anchors:
        if anchor.evidence_type != EvidenceType.LITERATURE:
            continue
        if not metadata.ref_exists(anchor.ref_id):
            findings.append(
                HallucinationFinding(
                    type=HallucinationType.H2,
                    claim_id=claim.claim_id,
                    reason=f"literature ref_id not found in KB: {anchor.ref_id}",
                    anchor_ids=[anchor.ref_id],
                )
            )
        else:
            ref_meta = metadata.get_ref_metadata(anchor.ref_id)
            if ref_meta is not None and ref_meta.doi is not None:
                # Local DOI comparison only when metadata is available
                pass  # DOI cross-check against stored metadata when extended
    return findings


def detect_h3(
    assertions: list[Assertion],
    validator: Optional[MechanismValidator],
) -> H3Result:
    """H3: map MechanismValidator violations to findings.

    If validator is unavailable, return NOT_CHECKED / MECHANISM_UNAVAILABLE.
    Do not claim H3 pass when untested.
    """
    if validator is None:
        return H3Result(status=H3Status.MECHANISM_UNAVAILABLE)

    try:
        result = validator.check(assertions)
    except Exception as exc:
        return H3Result(
            status=H3Status.MECHANISM_UNAVAILABLE,
            findings=[],
        )

    if result.ok:
        return H3Result(status=H3Status.CHECKED, findings=[])

    findings = [
        HallucinationFinding(
            type=HallucinationType.H3,
            claim_id=aid,
            reason="mechanism violation",
            anchor_ids=[aid],
            detail={"messages": list(result.messages)},
        )
        for aid in (result.violated_assertion_ids or [a.id for a in assertions])
    ]
    return H3Result(status=H3Status.CHECKED, findings=findings)
