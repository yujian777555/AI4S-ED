# Phase 5.0-R2 Plan — Exhaustive Eligibility + True Historical View + Assertion-Level Filtering

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Close the final three Phase 5.0 lifecycle correctness gaps from:
planner/phase-05-0-r1-review.md

Do not start Phase 5.1.

## 1. Scope freeze

Do not modify:
- §6 ranking/RRF/reranker/guard semantics;
- lifecycle crash-recovery logic accepted in R1 unless required by a failing regression;
- event transport boundary / CG-018;
- public MCP contract;
- Crossref/RetractionWatch/publisher polling;
- preprint fuzzy matching.

## 2. R2-A — progressive lifecycle filtering until enough eligible or exhaustion

Replace fixed:
max(top_k * 10, 50)

with a deterministic progressive strategy.

Required semantics for one backend search:
- requested output target = original query.top_k;
- fetch an initial backend depth;
- filter candidates by lifecycle eligibility;
- if eligible count < target and backend may contain more:
  - request a larger depth;
  - re-filter deterministically;
- stop only when:
  A. target eligible count is available; or
  B. backend proves exhaustion, e.g. returned_count < requested_depth; or
  C. returned candidate identities stop growing between expanded calls.

Preserve backend order and raw scores exactly for surviving candidates.
Return enough candidates for the frozen hybrid layer to apply its own cutoff.

Do not invent new ranking.

## 3. Large-depth regression

Mandatory:
- >= 60 same-level candidates;
- first 55 belong to lifecycle-ineligible refs;
- candidate #56 is eligible;
- query top_k=1;
- final EvidenceRetrievalService bundle returns #56.

Test vector path.
If keyword path is active in the same composition, cover it too or use a shared wrapper test proving the behavior for arbitrary SearchPort.

Also test backend exhaustion:
- all candidates ineligible;
- wrapper terminates and returns [] without infinite expansion.

## 4. R2-B — same-history historical retrieval E2E

Use ONE VersionStore + ONE LifecycleStore containing:
- V1 active REF-A;
- V2 retraction of REF-A.

Use the SAME InMemoryLifecycleVisibility instance (or same underlying store) for both requests.

Through EvidenceRetrievalService.retrieve():

Current request:
- at_version_id=None;
- REF-A absent.

Historical request:
- at_version_id=V1;
- REF-A present when ranking selects it.

Assert the store still contains the retraction record during both requests.
Do not construct an empty replacement LifecycleStore.

## 5. R2-C — assertion-level retrieval eligibility

Update lifecycle candidate eligibility helper:

eligible(chunk, at_version_id):
1. document_eligibility(chunk.ref_id, at_version_id) must be visible;
2. if chunk.assertion_id is not None:
   assertion_eligibility(chunk.assertion_id, chunk.ref_id, at_version_id) must also be visible;
3. only then include candidate.

Coarse summary chunks without assertion_id use document eligibility only.

Do not derive assertion ids from chunk text or chunk_id conventions.

## 6. Corrigendum retrieval regression

Create:
- one active document REF-A;
- fine chunk F1 assertion_id=A1;
- fine chunk F2 assertion_id=A2;
- V2 corrigendum supersedes A1 only.

Required:
- current retrieval never returns F1/A1;
- current retrieval can return F2/A2;
- explicit V1 historical retrieval can return F1/A1;
- document coarse summary remains eligible because the document is not retracted.

Use actual EvidenceRetrievalService retrieval, not direct visibility calls only.

## 7. Assertion training eligibility

If Phase 5.0 exposes training eligibility by document/assertion, prove:
- A1 superseded => false;
- A2 unchanged => true;
- V1 historical assertion eligibility for A1 remains true where applicable.

Do not create a separate training-export system.

## 8. Progressive search safety

Prevent infinite loops.

Track stable candidate identities or returned length.
If increasing depth produces no additional candidates, treat backend as exhausted.

Do not assume every backend honors arbitrarily large top_k perfectly.

Add a regression with a backend that caps output and repeats the same candidate list.

## 9. Preserve filters

Progressive wrapper must preserve:
- query.text;
- query.level;
- allowed_ref_ids;
- subquestion_id.

If allowed_ref_ids is already finite and lifecycle visibility can filter it before backend search, keep the existing exact pre-filter path.

## 10. Tests

Maintain:
- knowledge_curator >= 344 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add tests for all R2 cases.

No skipped core lifecycle tests.

## 11. Deliverables

Create:
results/phase-05-0-r2-executor-report.md

Report:
- progressive pre-cutoff lifecycle filtering: PASS/FAILED;
- deep-rank eligible recovery (>50): PASS/FAILED;
- backend exhaustion termination: PASS/FAILED;
- same-history historical retrieval E2E: PASS/FAILED;
- assertion-level retrieval filtering: PASS/FAILED;
- corrigendum current/historical retrieval: PASS/FAILED;
- assertion training eligibility: PASS/FAILED;
- exact tests;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 12. Completion

Update status.json:
- phase = 5.0-R2
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-0-r2-executor-report.md

Push main and STOP.
Do not start Phase 5.1.
