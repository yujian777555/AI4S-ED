# Phase 4.0 Planner Review — Evidence Guard Foundation Mostly Accepted

Implementation: 2af6b019d4267c24f4b5813b43cb28587fba63b6
origin/main bookkeeping tip: ca6c844f635f0c8c97e8351517451f67d84c3474
knowledge_curator tests: 151 passed / 0 failed
integration/dsh tests: 70 passed / 0 failed
Verdict: MOSTLY PASS — confidence/Abstain/H3/coverage/numeric guard accepted; H1/H2 need one narrow closure round.

## Accepted
- EvidenceType / EvidenceAnchor / EvidenceRecord / Claim / SurfacePolicy / ClaimPolicy are correctly marked temporary compatibility models.
- evidence vocabulary maps to 文献 / 图谱 / 仿真 / 实验 without creating a new public schema.
- Confidence enum is reused unchanged.
- verified/high -> FACTUAL_ALLOWED.
- medium -> CAVEATED_ONLY.
- hypothesis -> PENDING_HYPOTHESIS_ONLY.
- no anchors -> ABSTAIN.
- unresolved disjoint numeric ranges -> CONFLICT_DISCLOSURE_REQUIRED.
- Abstain reasons cover docs/03 §6.3 required conditions.
- H3 correctly reuses MechanismValidator; unavailable validator does not pretend PASS.
- coverage guard explicitly exposes uncovered subquestions.
- no final QA generator or new top-level Agent was introduced.
- no full FAISS/BM25/RRF/reranker was pulled in early.
- DSH live regression now requires exactly one call, one linked result and A==B==C.
- B structured parse failure can no longer be converted into PASS by copying A.

## Blocker P4.0.1-01 — H1 does not validate locator existence
detect_h1 currently checks:
- anchors exist;
- ref_id is non-empty;
- ref_id exists in KB;
- locator string is non-empty.

But it never calls EvidenceMetadataPort.anchor_exists(ref_id, locator).
Therefore an anchor such as a real ref_id plus a fabricated page/table/object locator can pass H1 as long as the locator string is non-empty.
This violates docs/03 §6.5 H1 anchor-alignment intent.

The current InMemoryEvidenceStore.anchor_exists is also only ref_exists + non-empty locator, so it cannot distinguish a known locator from an invented one.

## Blocker P4.0.1-02 — H2 local DOI/title mismatch path is stubbed
detect_h2 contains a local metadata branch but ends in pass.
Phase 4.0 promised local DOI/title comparison when cited metadata is available.
Current Claim/EvidenceAnchor models do not carry emitted citation DOI/title metadata, so the check is impossible today.

Phase 4.0.1 must add an internal temporary citation-metadata input and compare it to KB RefMetadata.
No Crossref/web call belongs in core.

## Important non-blockers
- H2 ref_id existence is correctly limited to literature anchors.
- H3 exception/unavailable behavior is conservative.
- weakest-anchor confidence policy matches the Phase 4.0 plan and should not be changed in this closure round.
- numeric conflict handling here is a consumption/surface guard and does not mutate frozen §5 truth adjudication.

## Next
Proceed to Phase 4.0.1 only.
After H1 locator validation and H2 local metadata mismatch checks pass, §6 deterministic evidence foundation can be frozen and Phase 4.1 may begin chunking/retrieval contracts.