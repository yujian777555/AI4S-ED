# Phase 5.0-R1 Plan — Lifecycle Recovery + Retrieval Correctness Hardening

Planner: ChatGPT  
Executor: Kimi/Codex  
State: READY_FOR_EXECUTOR

## 0. Goal

Repair the five blocking Phase 5.0 defects identified in:
`planner/phase-05-0-review.md`

Do **not** start Phase 5.1.

The target remains docs/03 §7 lifecycle core only.

## 1. Scope freeze

Do not:
- change frozen §6 ranking/RRF/reranker/Abstain semantics;
- add Crossref/RetractionWatch or publisher polling;
- add external Kafka/Redis/HTTP event transport;
- add public lifecycle mutation MCP tools;
- add preprint fuzzy matching;
- change CG-018;
- add unrelated abstractions.

## 2. R1-A — crash-safe idempotent lifecycle finalization

Fix `LifecycleRevisionCoordinator.apply_retraction()` and `apply_revision()`.

A deterministic existing lifecycle ID is not automatically “done”.

Classify existing state:

### FINALIZED
- lifecycle record bound to a published version;
- deterministic snapshot/version exists;
- required lifecycle records are bound;
- required outbox events exist with matching material payload.

Result:
- return idempotently;
- do not duplicate snapshot/version/events.

### STAGED / PARTIAL
- lifecycle record exists but effective_version_id is missing; or
- snapshot/version exists but binding is incomplete; or
- binding exists but one or more required events are missing.

Result:
- resume deterministic finalization;
- never create a second semantic revision;
- converge to the same final state.

### CONFLICT
Same deterministic lifecycle/revision/event identity but material content differs.

Result:
- fail closed.

Use existing deterministic manifest hash and VersionStore lookup APIs.
Only add the smallest internal helper/Port extension if absolutely required.

## 3. Failure matrix

Add deterministic retry tests for both retraction and generic revision where applicable.

At minimum test:

1. fail before `version.create_snapshot`;
2. fail after `version.create_snapshot`;
3. fail before `version.publish`;
4. fail after `version.publish`;
5. fail after lifecycle bind but before all required outbox events are complete.

For every case:
- first attempt raises;
- no half-applied lifecycle state is visible incorrectly;
- retry succeeds;
- exactly one semantic snapshot/version is published;
- lifecycle records bind to the published version;
- all required events exist exactly once;
- current visibility matches the final revision;
- historical version remains resolvable.

Critical regression:
`fail_after("version.publish")` must not leave current version advanced with an unbound lifecycle revision after recovery.

## 4. R1-B — base-version validation

An explicit `draft.base_version_id` must resolve to a published VersionRecord.

Missing base -> fail before staging/publish.

For Phase 5.0 keep branch semantics simple:
- if `base_version_id` is supplied, require it to equal `VersionStore.current_version().version_id` at publication time;
- after rollback, the rolled-back version is current and can therefore be the base of a new revision.

Do not silently publish from a nonexistent or stale base.

Add tests:
- nonexistent base -> rejected;
- stale non-current base -> rejected;
- rollback then revise from new current base -> allowed.

## 5. R1-C — strict material idempotency

Define material equality for:
- DocumentLifecycleRecord;
- AssertionLifecycleRecord;
- LifecycleEvent.

Same deterministic ID is idempotent only when material content matches.

At minimum include:
- ref/status/reason;
- revision/lifecycle identity;
- source fingerprint;
- affected assertion IDs;
- supersede target;
- evidence refs/rationale;
- trace/provenance IDs;
- old/new version IDs;
- event payload/schema version.

Ignore only explicitly non-material transport/staging fields such as created sequence or delivered flag, and document why.

Add regressions:
- same event_id + altered payload -> conflict;
- same lifecycle_id + altered evidence/rationale/source fingerprint -> conflict;
- same assertion identity + altered ref/revision/supersede target -> conflict.

## 6. R1-D — lifecycle eligibility before effective retrieval cutoff

Current wrapper may filter only after backend top-k.

Repair so an ineligible top hit cannot hide an eligible lower-ranked hit.

For Phase 5.0 deterministic/in-memory integration, an implementation may:
- pass an exact eligible ref-id restriction into the backend when a finite candidate universe is available; or
- deterministically expand backend retrieval until enough eligible candidates are obtained or backend exhaustion is established.

Do not change hybrid ranking formulas.

Required regression:
- requested top_k = 1;
- backend rank #1 = retracted REF-A;
- backend rank #2 = eligible REF-B;
- final EvidenceBundle contains REF-B.

Add equivalent coverage for vector + keyword composition if both are active.

## 7. R1-E — real historical retrieval integration

Add an INTERNAL explicit version selector for lifecycle retrieval.

Preferred:
- optional `at_version_id` on `EvidenceRequest` if that model is internal; or
- equivalent service-scoped internal parameter.

Propagate it into lifecycle eligibility filtering.

Required end-to-end regression:

1. V1 active REF-A;
2. V2 retracts REF-A;
3. current retrieval excludes REF-A;
4. retrieval explicitly at V1 returns REF-A when ranking selects it.

Do not satisfy this by directly calling `document_eligibility()`; the assertion must go through `EvidenceRetrievalService.retrieve()`.

## 8. Append-only clarification

Staged `effective_version_id` binding may remain an internal finalization mutation only if:
- staged records are invisible;
- status/reason/evidence content never changes after append;
- once bound, the binding cannot be changed to another version.

No physical deletion or historical rewrite.

## 9. Tests / acceptance

Keep existing baselines green:
- integration/dsh >= 90 passed / 0 failed;
- knowledge_curator >= 329 passed / 0 failed.

R1 must add tests for every blocker above.

Acceptance requires:
- retry recovery works after post-side-effect failures;
- no current version/lifecycle visibility split-brain remains;
- backend top-k lifecycle under-fill regression is closed;
- actual historical retrieval works end-to-end;
- material ID conflicts fail closed;
- invalid/stale base versions fail closed;
- public contracts changed = NO unless Planner explicitly approves otherwise.

## 10. Deliverables

Update:
- implementation/tests;
- `results/phase-05-0-r1-executor-report.md`;
- `status.json`.

Completion report:
- implementation CODE SHA;
- origin/main SHA;
- failure-recovery matrix PASS/FAILED;
- post-publish retry PASS/FAILED;
- retrieval pre-cutoff regression PASS/FAILED;
- historical retrieval E2E PASS/FAILED;
- strict material idempotency PASS/FAILED;
- base-version validation PASS/FAILED;
- exact test counts;
- public contracts changed YES/NO;
- CONTRACT_GAPS added/changed.

Push main and STOP.

Do not start Phase 5.1.
