# Phase 5.0-R3 Plan — Correct Exhaustion Detection + allowed_ref Assertion Filtering

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Close the last two lifecycle retrieval correctness defects from:
planner/phase-05-0-r2-review.md

Do not start Phase 5.1.

## 1. Scope

Only modify lifecycle retrieval eligibility composition/tests unless a directly related bug is exposed.

Do not change:
- §6 ranking/RRF/reranker/guard semantics;
- R1 lifecycle recovery/idempotency/base validation;
- lifecycle version model;
- event outbox/CG-018;
- public MCP contracts.

## 2. R3-A — backend exhaustion based on candidate growth

In _EligibilityFilteredPort.search():

Track identities for ALL candidates returned by the backend, not only eligible candidates.

At each expanded depth:
- call backend;
- preserve backend ordering/scores;
- filter eligible candidates;
- if enough eligible -> return;
- if len(cands) < requested_depth -> exhausted;
- otherwise compare the complete returned candidate identity set/list against the previous expanded call;
- if no new backend candidate identity appears -> exhausted;
- if backend candidates grew, continue expanding even if eligible count remains zero.

Do not stop merely because eligible IDs did not grow.

## 3. Deep regression beyond 100

Mandatory:
- >= 110 candidates;
- #1..#100 lifecycle-ineligible;
- #101 eligible;
- top_k=1;
- final result returns #101.

Assert requested backend depth advances beyond 100.

## 4. Safety bound semantics

The existing _MAX_STEPS may remain only as a resource safety guard.

If the guard is reached while backend candidate identities are still growing and target eligible count has not been met:
- do not label it exhausted;
- fail closed with an explicit retrieval eligibility exhaustion/limit diagnostic or exception.

Do not silently return an incomplete result as if search were exhaustive.

Prefer a configurable internal max depth/steps if needed, but do not create a public contract.

## 5. Capped/repeating backend

Keep/add regression:
- backend always returns the same capped candidate identities for larger top_k;
- wrapper detects no candidate growth and terminates;
- no infinite loop.

## 6. R3-B — allowed_ref_ids must not bypass assertion eligibility

When request.allowed_ref_ids is supplied:

1. prefilter those refs using lifecycle document eligibility at at_version_id;
2. pass the filtered finite set into RetrievalQuery.allowed_ref_ids;
3. still apply lifecycle candidate filtering to vector/keyword ports so chunk.assertion_id is checked;
4. progressive fill must continue within the allowed ref universe when early chunks are superseded/archived.

Document-level filtering and assertion-level filtering are both required.

## 7. allowed_ref corrigendum regression

Use the same lifecycle history:

- REF-A document ACTIVE;
- V1: A1 and A2 active;
- V2 corrigendum: A1 SUPERSEDED, A2 active.

Backend order:
- F1/A1 first;
- F2/A2 second.

Current:
EvidenceRequest(query=..., top_k=1, allowed_ref_ids=["REF-A"])
must return F2/A2, never F1/A1.

Historical V1:
same request with at_version_id=V1
may return F1/A1.

## 8. Empty finite allowed-ref set

If document prefilter turns allowed_ref_ids into an empty set:
- backend must not accidentally interpret empty set as “no restriction”;
- result must contain no lifecycle-ineligible refs.

Add regression if current backend/query semantics make this ambiguous.

## 9. Preserve query fields

Progressive wrapper continues preserving:
- text;
- level;
- allowed_ref_ids;
- subquestion_id.

No score/rank reinterpretation.

## 10. Tests

Maintain:
- knowledge_curator >= 351 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add tests for:
- #101 eligible recovery;
- candidate-growth exhaustion semantics;
- max-step/resource-guard fail-closed if applicable;
- allowed_ref assertion supersede filtering;
- historical allowed_ref retrieval;
- empty allowed-ref prefilter safety.

## 11. Deliverable

Create:
results/phase-05-0-r3-executor-report.md

Report:
- all-candidate exhaustion detection: PASS/FAILED;
- #101 eligible recovery: PASS/FAILED;
- capped backend termination: PASS/FAILED;
- resource guard fail-closed: PASS/FAILED;
- allowed_ref assertion filtering: PASS/FAILED;
- historical allowed_ref retrieval: PASS/FAILED;
- empty allowed-ref safety: PASS/FAILED;
- exact tests;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 12. Completion

Update status.json:
- phase = 5.0-R3
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-0-r3-executor-report.md

Push main and STOP.
Do not start Phase 5.1.
