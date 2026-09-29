"""H1/H2/H3 hallucination detectors (docs/03 §6.5). Deterministic local checks.

H1 = unsupported/misaligned claim anchor (with real locator validation)
H2 = fabricated/nonexistent literature citation (KB local existence + DOI/title)
H3 = mechanism violation (via MechanismValidator Port)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from knowledge_curator.ports.evidence_store import CitationMetadata, EvidenceMetadataPort
from knowledge_curator.ports.mechanism_validator import MechanismValidator
from knowledge_curator.schemas.assertions import Assertion
from knowledge_curator.schemas.evidence import Claim, EvidenceType


class HallucinationType(str, Enum):
    H1 = "H1"
    H2 = "H2"
    H3 = "H3"


class LocatorCheckStatus(str, Enum):
    VERIFIED_PRESENT = "verified_present"
    VERIFIED_ABSENT = "verified_absent"
    NOT_CHECKED = "not_checked"


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


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    """Normalize DOI: trim, casefold, strip doi.org URL prefix. Do not rewrite path."""
    if not doi:
        return None
    s = doi.strip().casefold()
    for prefix in ("https://doi.org/", "http://doi.org/"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s or None


def normalize_title(title: Optional[str]) -> Optional[str]:
    """Normalize title: casefold, collapse whitespace, trim."""
    if not title:
        return None
    s = " ".join(title.casefold().split())
    return s or None


def detect_h1(claim: Claim, metadata: EvidenceMetadataPort) -> list[HallucinationFinding]:
    """H1: require valid anchors with real locator validation.

    anchor_exists returns:
      True  -> verified present
      False -> verified absent (H1 fabricated locator)
      None  -> adapter cannot validate (NOT_CHECKED, not H1 pass)
    """
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
        else:
            # Real locator validation
            check = metadata.anchor_exists(anchor.ref_id, anchor.locator)
            if check is False:
                findings.append(
                    HallucinationFinding(
                        type=HallucinationType.H1,
                        claim_id=claim.claim_id,
                        reason=f"locator verified absent: {anchor.locator}",
                        anchor_ids=[anchor.ref_id],
                        detail={"locator_status": LocatorCheckStatus.VERIFIED_ABSENT.value},
                    )
                )
            elif check is None:
                # Adapter cannot validate — record as NOT_CHECKED, not a pass
                findings.append(
                    HallucinationFinding(
                        type=HallucinationType.H1,
                        claim_id=claim.claim_id,
                        reason="locator validation unavailable (NOT_CHECKED)",
                        anchor_ids=[anchor.ref_id],
                        detail={"locator_status": LocatorCheckStatus.NOT_CHECKED.value},
                    )
                )
            # check is True -> verified present, no finding
    return findings


def detect_h2(
    claim: Claim,
    metadata: EvidenceMetadataPort,
    citation: Optional[CitationMetadata] = None,
) -> list[HallucinationFinding]:
    """H2: KB local existence + local DOI/title metadata comparison.

    No Crossref/web calls. If citation metadata is absent, only ref existence is checked.
    """
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
            continue

        # Local DOI/title comparison when cited metadata is provided
        if citation is not None and citation.ref_id == anchor.ref_id:
            ref_meta = metadata.get_ref_metadata(anchor.ref_id)
            if ref_meta is not None:
                # DOI comparison
                cited_doi = normalize_doi(citation.cited_doi)
                kb_doi = normalize_doi(ref_meta.doi)
                if cited_doi and kb_doi and cited_doi != kb_doi:
                    findings.append(
                        HallucinationFinding(
                            type=HallucinationType.H2,
                            claim_id=claim.claim_id,
                            reason="cited DOI mismatch with KB metadata",
                            anchor_ids=[anchor.ref_id],
                            detail={"cited_doi_norm": cited_doi, "kb_doi_norm": kb_doi},
                        )
                    )
                # Title comparison
                cited_title = normalize_title(citation.cited_title)
                kb_title = normalize_title(ref_meta.title)
                if cited_title and kb_title and cited_title != kb_title:
                    findings.append(
                        HallucinationFinding(
                            type=HallucinationType.H2,
                            claim_id=claim.claim_id,
                            reason="cited title mismatch with KB metadata",
                            anchor_ids=[anchor.ref_id],
                            detail={"cited_title_norm": cited_title, "kb_title_norm": kb_title},
                        )
                    )
    return findings


def detect_h3(
    assertions: list[Assertion],
    validator: Optional[MechanismValidator],
) -> H3Result:
    """H3: map MechanismValidator violations to findings.

    If validator is unavailable, return NOT_CHECKED / MECHANISM_UNAVAILABLE.
    """
    if validator is None:
        return H3Result(status=H3Status.MECHANISM_UNAVAILABLE)

    try:
        result = validator.check(assertions)
    except Exception:
        return H3Result(status=H3Status.MECHANISM_UNAVAILABLE, findings=[])

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
