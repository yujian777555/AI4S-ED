# Phase 5.0-R1 Planner Review — MOSTLY PASS, Three Lifecycle Retrieval Gaps Remain

Implementation CODE SHA: b7793b60d22dc327879e7ca169e95a286d15a0a9
origin/main bookkeeping tip: 5f471e09c0779454df80cd78e864d962dfcdf722

Verdict: MOSTLY PASS / Phase 5.0 lifecycle core is not frozen yet.

## Accepted

The R1 repair successfully addresses the original crash/idempotency/base-version defects:

- deterministic FINALIZED / STAGED / CONFLICT handling exists;
- retry after version.publish side effect can resume and bind the existing lifecycle revision;
- missing/stale explicit base versions fail closed;
- material identity checks are substantially stricter for lifecycle records and outbox events;
- an INTERNAL at_version_id selector now reaches EvidenceRetrievalService;
- reported baselines remain green.

These accepted areas should not be rewritten without need.

## BLOCKER R2-01 — fixed 10x/50 eligibility expansion is still not correctness-complete

_ElegibilityFilteredPort currently does:

expanded = max(query.top_k * 10, 50)
inner.search(top_k=expanded)
drop lifecycle-ineligible candidates

This closes only shallow under-fill.

Counterexample:
- requested top_k = 1;
- backend ranks #1..#50 are retracted/ineligible;
- rank #51 is eligible.

Current implementation can return zero even though an eligible result exists immediately below the fixed expansion cutoff.

This violates the Phase 5.0 requirement:
continue until enough eligible candidates are found OR backend exhaustion is established.

Required repair:
- progressively increase requested backend depth, e.g. 50 -> 100 -> 200 ...;
- stop when requested eligible top_k is obtained, or the backend returns fewer candidates than requested / repeats the full candidate set indicating exhaustion;
- impose a deterministic safety bound only if the backend contract exposes corpus size or an explicit maximum;
- never silently treat one fixed oversampling factor as proof of exhaustion.

Do not change frozen ranking scores/order.

Add regression:
- top_k=1;
- at least 60 candidates;
- first 55 are retracted;
- #56 is eligible;
- final result must return #56.

## BLOCKER R2-02 — historical retrieval test does not use the same lifecycle history

test_historical_retrieval_e2e_via_service currently creates a fresh empty InMemoryLifecycleStore for the historical retrieval service.

That proves:
"retrieval with no lifecycle records sees REF-A."

It does NOT prove:
"the SAME lifecycle history containing a V2 retraction, viewed at at_version_id=V1, sees REF-A."

Required regression:
- use the exact same LifecycleStore containing the V2 retraction record;
- use the same version-aware visibility object;
- current retrieval excludes REF-A;
- EvidenceRequest(at_version_id=V1) through the same service/visibility returns REF-A.

Do not swap in a fresh empty lifecycle store.

## BLOCKER R2-03 — assertion-level supersede/archive is not applied to retrieval

KnowledgeChunk has assertion_id.

However the lifecycle retrieval wrapper currently checks only:
document_eligibility(chunk.ref_id)

For a corrigendum:
- document may stay ACTIVE;
- assertion A1 may become SUPERSEDED;
- A1's old chunk therefore remains retrievable today.

This violates §7.3 and Phase 5.0 requirements that SUPERSEDED / ARCHIVED assertions are not current retrieval/training evidence while historical provenance remains.

Required repair:
for lifecycle-filtered candidates:
1. check document_eligibility(ref_id, at_version_id);
2. if chunk.assertion_id is present, also check assertion_eligibility(assertion_id, ref_id, at_version_id);
3. candidate is eligible only if both permit retrieval.

Coarse document-summary chunks may have no assertion_id; document eligibility remains sufficient for those.

Add regressions:
- active document, A1 superseded, A2 active;
- current fine retrieval excludes A1 and can return A2;
- historical retrieval at pre-corrigendum version can return A1;
- coarse document summary may remain available when the document itself is active.

Also verify training eligibility uses assertion state where assertion identity is available.

## Decision

Do not begin Phase 5.1.

Execute one narrow Phase 5.0-R2:
1. progressive/exhaustive pre-cutoff lifecycle filtering;
2. true same-history historical retrieval E2E;
3. assertion-level lifecycle filtering for retrieval/training.

After these pass, Phase 5.0 can be frozen.
