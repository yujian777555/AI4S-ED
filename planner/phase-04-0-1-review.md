# Phase 4.0.1 Planner Review — Locator/Metadata Validation Accepted, H1 Status Semantics Need One Final Closure

Implementation: fdba150afc1fb915aac20920e2d8c8290b05c90a
origin/main bookkeeping tip: 939f7efd71cd1c500b4a4609b9b025a2639f7509
knowledge_curator tests: 166 passed / 0 failed
integration/dsh tests: 70 passed / 0 failed
Verdict: MOSTLY PASS — real locator validation and H2 local DOI/title validation accepted; H1 unavailable-check semantics must be corrected before §6 foundation is frozen.

## Accepted
- EvidenceMetadataPort.anchor_exists now has tri-state semantics True / False / None.
- InMemoryEvidenceStore can register known locators per ref_id.
- existing ref + registered locator passes.
- existing ref + fabricated known-checkable locator produces H1.
- nonexistent ref can produce both H1 and H2.
- CitationMetadata is explicitly internal/temporary.
- DOI normalization is conservative and local only.
- title normalization is conservative and local only.
- DOI/title mismatches produce H2.
- non-literature evidence is excluded from literature H2 metadata checks.
- no Crossref/web/HTTP was added.
- no public contract changed.

## Final blocker P4.0.2-01 — NOT_CHECKED is currently emitted as an H1 hallucination finding
When anchor_exists returns None, detect_h1 appends:
HallucinationFinding(type=H1, reason='locator validation unavailable (NOT_CHECKED)').

This is semantically wrong for docs/03 §6.5 metrics.
H1 means an unsupported or misaligned anchor actually detected.
An unavailable locator validator means the system does not know whether alignment is valid.

If NOT_CHECKED remains inside the H1 findings list, downstream metric code can count unverifiable anchors as H1 hallucinations and inflate the H1 rate.

## Required correction
Separate:
- actual H1 findings;
- locator-check status/evidence.

Recommended API:
- detect_h1_with_status(...) -> H1CheckResult
- H1CheckResult.findings contains only real H1 violations;
- H1CheckResult.locator_checks records VERIFIED_PRESENT / VERIFIED_ABSENT / NOT_CHECKED per anchor;
- detect_h1(...) remains a compatibility wrapper returning only result.findings.

Then:
- real locator => no H1 finding, VERIFIED_PRESENT;
- fabricated locator => H1 finding, VERIFIED_ABSENT;
- validator unavailable => no H1 finding, NOT_CHECKED status;
- missing/unknown ref or empty locator => actual H1 finding.

## Why this needs closure before Phase 4.1
docs/03 §6.5 requires H1 occurrence rate as an evaluation metric.
The module must not confuse 'unable to check' with 'hallucination detected' before retrieval/ranking starts producing real evidence traffic.

## Next
Proceed to Phase 4.0.2 only.
After this semantic split, freeze §6 deterministic evidence guard and move to Phase 4.1 chunking/retrieval contracts.