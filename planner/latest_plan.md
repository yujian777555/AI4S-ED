# Phase 5.3-R1 Plan — Real Frozen-Component Integration + Final Recovery Closure

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Close the real-integration blockers in:
planner/phase-05-3-review.md

This is the final implementation correction.

Do not create Phase 5.4.

## 1. Preserve architecture

Keep the Phase 5.3 saga and journal design.

Do not redesign frozen:
- DocumentCommitCoordinator;
- LifecycleRevisionCoordinator;
- SourceVersionRegistry;
- RevisionPackage;
- retrieval;
- MCP/DSH.

Fix only orchestration correctness and real integration.

## 2. Make publication async

Change main entry to:

async def publish(...)

_run_target_commit must also be async or await the commit in the main path.

Call:
result = await self._commit.commit(request)

Do not use asyncio.run inside library code.

All publication tests invoking real/fake async commit must await publish.

Provide AsyncFakeCommitCoordinator only for narrow synthetic branches if needed.

## 3. Require a real CommitRequest

target_commit_request is mandatory.

At the start, before approval/journal/commit side effects:
- reject None;
- use knowledge_curator.schemas.commit.CommitRequest;
- run validate_commit_request(request).

Binding errors => fail closed.

Do not maintain a second independent curation_report as authoritative material.

Preferred API:
await publish(
    package=package,
    target_commit_request=request,
    approval=approval,
)

Use request.report everywhere.

## 4. Exact request/package material validator

Add canonical assertion publication payload helper shared by:
- package-vs-request validation;
- approval scope hash;
- existing commit guard.

Include at least:
- id/ref_id;
- subject class/entity/original mention;
- property;
- object value/unit/value_type/uncertainty;
- conditions canonicalized deterministically;
- provenance locator/sentence;
- claim_type;
- source_claim_origin;
- confidence;
- quality;
- missing_unit/speculative_wording/chart_quality_low.

Require package.target_assertions and request.assertion_set.assertions to have identical ID set and identical material per ID.

## 5. Source/metadata validation

Before side effects require:
- request.source.ref_id == package.new_ref_id == new.ref_id;
- request.source.source_fingerprint == new.source_fingerprint;
- assertion_set.ref_id == new.ref_id;
- report.source_ref_id == new.ref_id.

Using frozen Phase 5.1 normalizers:
- non-empty metadata.title must normalize to new.normalized_title when registry title exists;
- non-empty metadata.doi must normalize to new.normalized_doi when registry DOI exists;
- non-empty metadata.stable_id must match new.stable_id.

No fuzzy correction.

## 6. Curation gate uses request.report only

Run validate_commit_request first.

Then require for every target assertion exactly one decision.

Allowed:
- CurationAction.ACCEPT;
- CurationAction.DOWNGRADE.

Reject:
- PENDING_REVIEW;
- REJECT;
- RETURN_UPSTREAM;
- SUPERSEDE.

Also reject if:
- report.returned_upstream_count > 0;
- report.status == return_upstream/pending_review/rejected or otherwise inconsistent with all decisions being ACCEPT/DOWNGRADE.

Do not accept string synonyms such as "accepted" unless they are actual frozen enum values.

## 7. Approval scope binds actual CommitRequest

compute_publication_scope_hash(package, request) must include:

### source
- ref_id;
- fingerprint.

### AssertionSet metadata
- title;
- authors;
- year;
- source;
- doi;
- stable_id;
- quality_grade;
- no_structured_data;
- schema counts;
- charts/extra only where deterministic and publication-significant.

### assertions
canonical exact publication payload.

### report decisions
- assertion_id;
- action.value;
- confidence.value.

### report publication gates
- status;
- returned_upstream_count.

Exclude only known ephemeral values like random report_id.

Remove curation_decisions as an independent override.

Changing metadata/decision/source with same package must invalidate approval scope.

## 8. Approval logic

First build package draft to determine whether manual adjudication is required.

If manual-required:
- require explicit APPROVED approval with exact package/scope/approver.

If auto-rule-eligible in a future valid package:
- approval may be absent.

For current P2J path, manual approval remains expected.

Approval trace/provenance should be included in request material identity if carried into audit state.

## 9. Publication request material hash

Hash:
- package_id;
- exact scope hash;
- exact approval material including approval_id/package/scope/decision/approver/rationale/trace/provenance;
- package trace/provenance.

Same full request -> same.
Any audited approval/material change -> conflict.

## 10. Existing commit guard must be material-exact

DocumentCommitStore inspection is mandatory when configured for real publication.

Do not swallow store errors.

For existing record compare:
- ref/fingerprint;
- admitted assertion canonical material;
- exact admitted ID set;
- action;
- confidence;
- visibility;
- metadata_hash against expected request metadata hash or equivalent deterministic recomputation;
- published manifest where present.

Same IDs with changed value/unit/provenance/quality/action/confidence => CONFLICT.

If record is partially staged with same material, allow frozen DocumentCommitCoordinator to resume.

## 11. Real target commit

Use real await DocumentCommitCoordinator.commit.

Accept only:
- PUBLISHED;
- IDEMPOTENT_HIT.

Pending statuses stop without lifecycle/bind.

After success validate:
- version_id and snapshot_id present;
- VersionStore.get_version(version_id) exists and published;
- version.snapshot_id == result.snapshot_id;
- VersionStore.get_snapshot(snapshot_id) exists;
- commit store record exists for request key;
- commit record.version_id/snapshot_id agree when phase is published;
- snapshot manifest ref/fingerprint equal new source identity.

Only then journal TARGET_PUBLISHED.

## 12. Lifecycle authorization and publication

Keep prior-ref subject.

Set draft.base_version_id = V_target.

For validated manual approval:
- manual_adjudication_required=False;
- keep risk_decision=MANUAL_ADJUDICATION_REQUIRED;
- append approval audit evidence/rationale.

Call frozen lifecycle with prior.source_fingerprint.

No silent rebase.

## 13. Final snapshot validation

Resolve final snapshot even if LifecyclePublishResult.snapshot_id is None.

Require:
- final version exists/published;
- final version.snapshot_id == resolved final snapshot id;
- final snapshot exists;
- final version prior == V_target for fresh publication.

Load V_target snapshot and compare content-preserving fields exactly:
- ref_id;
- source_fingerprint;
- structural_stage_id;
- assertion_hashes;
- usdo_hashes;
- usdo_record_ids;
- vector_ids;
- metadata_hash;
- decision_hashes.

Final lifecycle fields may differ/add lifecycle identities.

If target scientific/storage identity changes unexpectedly => CONFLICT, no bind.

## 14. Correct post-bind recovery

At publish entry, if new SourceVersion is already bound:

### journal FINALIZED
exact final version/snapshot -> idempotent FINALIZED.

### journal LIFECYCLE_PUBLISHED
if binding exactly equals record.final_version_id/final_snapshot_id:
- this is crash-after-bind-before-journal-ack;
- update journal FINALIZED;
- return FINALIZED resumed/idempotent.

### any other state/binding
CONFLICT.

Do this before rejecting pre-existing binding.

## 15. Failure-injectable publication journal

Enhance InMemoryRevisionPublicationStore with optional deterministic failure injection or a focused test wrapper.

Must test failure AFTER the final bind side effect but BEFORE/ON journal FINALIZED persistence.

Retry must complete.

Do not weaken monotonic phase semantics.

## 16. Lineage exactness

_validate_lineage additionally requires:
- prior.ref_id == package.prior_ref_id;
- new.ref_id == package.new_ref_id;
- new.relation == package.relation;
- prior/new work match package.work_id;
- new.prior_source_version_id == prior.source_version_id;
- prior binding == package prior binding.

Any contradiction => CONFLICT before side effects.

## 17. Real E2E fixture

Build at least one true async P2J E2E using:

- InMemorySourceVersionRegistry;
- real KnowledgeCurator with existing in-memory repository/ontology adapters;
- await KnowledgeCurator.curate(...) or curate + construct real CommitRequest;
- real InMemoryDocumentCommitStore;
- real InMemoryStructuralKnowledgeStore;
- real InMemoryUSDOStore;
- real InMemoryVectorIndex;
- shared real InMemoryVersionStore;
- real DocumentCommitCoordinator;
- real LifecycleRevisionCoordinator;
- RevisionPublicationCoordinator.

Do not pre-create V_target manually.
V_target must come from the real document commit.

Prior source binding and VersionStore history must be mutually consistent in the same VersionStore fixture.

## 18. Real E2E assertions

Verify:
- target commit publishes V_target;
- lifecycle publishes V_final;
- V_final.prior_version_id == V_target;
- final snapshot preserves target content;
- new SourceVersion -> V_final/S_final;
- prior binding unchanged;
- prior preprint current visibility false;
- new journal visibility true;
- old assertion visibility false;
- current final version correct;
- historical prior version remains resolvable;
- replay exact request produces no duplicate version/event.

## 19. Recovery tests with real components

At least:
1. real pending vector/failure recovery using frozen FailureInjection;
2. lifecycle failure after target commit, retry succeeds;
3. stale-base interleaving fails closed;
4. bind failure before side effect, retry succeeds;
5. bind succeeds then journal FINALIZED persistence fails, retry finalizes;
6. lifecycle finalized replay with snapshot_id omitted path recovers snapshot;
7. existing published target same material resumes;
8. existing published target same IDs but changed assertion material conflicts.

## 20. Approval/material tests

Add:
- request None -> no side effect;
- source/ref/fingerprint mismatch -> no side effect;
- metadata title/DOI/stable mismatch -> no side effect;
- package/request assertion material mismatch -> no side effect;
- request.report pending/reject/return/supersede -> no side effect;
- changing metadata after approval changes scope hash;
- changing decision after approval changes scope hash;
- changing scientific value with same assertion ID changes scope hash.

## 21. Baselines

Maintain:
- all current knowledge_curator tests;
- integration/dsh >= 90 / 0 failed.

Expected knowledge_curator count >= 489, likely substantially higher.

## 22. Deliverable

Update existing Phase 5.3 implementation, do not create a new architecture.

Create:
results/phase-05-3-r1-executor-report.md

Report:
- real async DocumentCommitCoordinator integration: PASS/FAILED;
- exact CommitRequest/package gate: PASS/FAILED;
- approval scope binds source/metadata/report: PASS/FAILED;
- mandatory curation gate: PASS/FAILED;
- exact existing-commit material guard: PASS/FAILED;
- target version/snapshot validation: PASS/FAILED;
- final snapshot content preservation: PASS/FAILED;
- post-bind journal recovery: PASS/FAILED;
- real P2J E2E: PASS/FAILED;
- real full replay idempotency: PASS/FAILED;
- integration tests;
- knowledge_curator tests;
- public contracts changed: NO;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 23. Completion

Update status.json:
- phase = 5.3-R1
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-3-r1-executor-report.md

Push main and STOP.

Do not create Phase 5.4.
Planner performs final acceptance/freeze immediately after R1 review.
