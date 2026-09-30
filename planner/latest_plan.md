# Phase 5.3 Plan — Recoverable Revision Publication Orchestration

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Implement the final publication layer for docs/03 §7.1/§7.3:

RevisionPackage
+ already-curated target CommitRequest
+ explicit RevisionApproval when required
→ publish target new-source content
→ publish lifecycle transition against the target KB version
→ bind new SourceVersion to the FINAL lifecycle KB version
→ recover safely across retries/crashes.

This is the final implementation phase before Planner final acceptance/freeze.

## 1. Freeze existing layers

Do NOT redesign:
- Phase 2 DocumentCommitCoordinator;
- Phase 5.0 LifecycleRevisionCoordinator;
- Phase 5.1 SourceVersionRegistry identity semantics;
- Phase 5.2 RevisionPackage/delta semantics;
- retrieval;
- DSH/MCP public tools.

Phase 5.3 is an orchestration layer above them.

## 2. No fake ACID

CG-013 still applies.

Do not claim target commit + lifecycle + source binding are one physical cross-store transaction.

Implement a recoverable saga:
1. validate all material + approval before KB side effects;
2. target document publish;
3. lifecycle publish;
4. source-version final bind.

Each completed step must be replay-safe.

## 3. Internal publication models

Add INTERNAL temporary schemas, recommended:
knowledge_curator/schemas/revision_publication.py

### RevisionApprovalDecision
- APPROVED
- REJECTED

### RevisionApproval
At least:
- approval_id;
- package_id;
- scope_hash;
- decision;
- approver;
- rationale;
- trace_id;
- provenance_id.

No implicit approval.
No synthetic high_confidence/multi_source flags.

### RevisionPublicationPhase
Recommended monotonic success phases:
- PREPARED
- TARGET_PUBLISHED
- LIFECYCLE_PUBLISHED
- FINALIZED

Track last_error separately rather than moving backwards.

### RevisionPublicationRecord
At least:
- publication_id = deterministic from package_id;
- package_id;
- request_material_hash;
- phase;
- target_commit_id;
- target_version_id;
- target_snapshot_id;
- lifecycle_id;
- final_version_id;
- final_snapshot_id;
- approval_id;
- last_error.

### RevisionPublicationResult
At least statuses:
- APPROVAL_REQUIRED / APPROVAL_REJECTED;
- PACKAGE_REVIEW_REQUIRED;
- TARGET_PENDING;
- LIFECYCLE_PENDING;
- CONFLICT;
- FAILED;
- FINALIZED.

Include target/final version ids and idempotent/resumed flags.

## 4. Internal publication journal Port

Add INTERNAL:
knowledge_curator/ports/revision_publication_store.py
and in-memory adapter.

Requirements:
- get(publication_id);
- create(record);
- update(record);
- same publication_id + same request material is idempotent;
- same publication_id + different request_material_hash => conflict;
- phase updates monotonic;
- copy-on-write in-memory adapter.

No external DB choice in this phase.

## 5. Publication input

Recommended coordinator input:
- RevisionPackage;
- target CommitRequest produced by the existing §5 KnowledgeCurator path;
- optional/required RevisionApproval.

Do not accept raw uncurated assertions and silently fabricate CurationReport.

E2E tests should actually use KnowledgeCurator.curate() to produce the CommitRequest.

## 6. Publication-resolved package gate

Before ANY KB side effect:

Require:
- package.requires_manual_review == False.

An approval token does NOT resolve ambiguous Phase 5.2 semantic-slot matching.

If true:
- return PACKAGE_REVIEW_REQUIRED;
- no target commit;
- caller must rebuild a deterministic package after adjudication.

This separates content/diff ambiguity from governance approval.

## 7. Validate SourceVersion lineage

Fetch prior/new source versions.

Require:
- both exist;
- work/version/ref lineage matches package;
- prior.kb_version_id == package.prior_bound_kb_version_id;
- prior.snapshot_id non-empty;
- new relation/prior/work match package.

Before a new publication:
- new SourceVersion should be unbound.

Replay exception:
if publication journal already records lifecycle/final state and the new binding matches the recorded final version/snapshot, allow exact idempotent completion.

Any unrelated pre-existing binding => CONFLICT.

## 8. Validate target CommitRequest identity

Before commit:

Require:
- request.source.ref_id == package.new_ref_id;
- request.source.source_fingerprint == new.source_fingerprint;
- request.assertion_set.ref_id == package.new_ref_id;
- report.source_ref_id == package.new_ref_id.

Target assertions must match package.target_assertions EXACTLY as publication material.

Canonical comparison must include:
- id;
- ref_id;
- full scientific payload;
- confidence;
- quality;
- flags;
- provenance locator/sentence.

No missing or extra assertions.

## 9. Validate target metadata against SourceVersion

At minimum:
- normalized AssertionSet metadata title, when present, agrees with new.normalized_title;
- normalized DOI, when present, agrees with new.normalized_doi;
- stable_id, when present, agrees with new.stable_id.

Use frozen Phase 5.1 normalizers.
Do not fuzzy-correct.

Include full target AssertionSet metadata in publication material hashing.

## 10. CurationReport gate

Every target assertion must have exactly one decision.

Allowed Phase 5.3 publication actions:
- ACCEPT;
- DOWNGRADE.

Reject publication before commit if any target assertion is:
- PENDING_REVIEW;
- REJECT;
- RETURN_UPSTREAM;
- SUPERSEDE.

Also reject:
- missing decision;
- extra decision;
- returned_upstream_count > 0;
- report/status material inconsistent with ACCEPT/DOWNGRADE publication.

Reason:
old knowledge must not be superseded by a replacement assertion that §5 rejected or left pending.

## 11. Approval scope hash

Add:
compute_publication_scope_hash(package, target_commit_request)

Canonical scope includes at least:
- package.package_id;
- new SourceVersion identity;
- commit source ref/fingerprint;
- AssertionSet metadata;
- exact target assertion publication material;
- curation decision material that affects commit:
  assertion_id/action/confidence.

Exclude random report_id/timestamps.

Same semantic publication request => same scope hash.

## 12. Manual approval semantics

Current package_to_revision_draft is conservatively manual-adjudication-required.

Before ANY target commit side effect, when draft is manual-required:
- approval must exist;
- decision == APPROVED;
- approval.package_id == package.package_id;
- approval.scope_hash == computed scope hash;
- approval_id and approver non-empty.

REJECTED/missing/mismatched approval:
- no KB side effects.

Do not convert approval into scientific evidence.

## 13. Authorized draft

After approval validation, build draft from package.

At publication time:
- draft.base_version_id = target KB version id, only AFTER target commit succeeds.

For explicit manual approval:
- deep-copy draft;
- set manual_adjudication_required=False ONLY because approval was validated;
- KEEP risk_decision=MANUAL_ADJUDICATION_REQUIRED so the record still says rule-level auto eligibility was not established;
- append auditable evidence refs:
  approval:<approval_id>
  approval_scope:<scope_hash>
- append deterministic rationale mentioning approval id/approver.

Do not set fake AUTO_RULE_REVIEW_ELIGIBLE metadata.

## 14. Publication request identity

publication_id deterministic from package.package_id.

request_material_hash must include:
- package id;
- publication scope hash;
- approval material:
  approval_id/package_id/scope_hash/decision/approver/rationale;
- package trace/provenance identity.

Same publication id with changed target metadata, curation decisions, or approval => CONFLICT before further side effects.

## 15. Existing target commit material guard

DocumentCommitCoordinator exact retries can return IDEMPOTENT_HIT for the same (ref_id,fingerprint).

Therefore inspect DocumentCommitStore.find_by_key before trusting/resuming an existing commit.

If existing record contains admitted material:
- admitted assertion material must exactly match package.target_assertions;
- admitted ids exactly match target ids;
- admitted actions/confidence must be compatible with validated CommitRequest decisions.

Existing PUBLISHED same key + different material => CONFLICT.
Do not continue lifecycle.

## 16. Step A — target document commit

Call frozen:
DocumentCommitCoordinator.commit(target_commit_request)

Proceed ONLY when:
- PUBLISHED;
or
- IDEMPOTENT_HIT;

and version_id/snapshot_id are resolvable and consistent.

If:
- PENDING_VECTOR;
- PENDING_FINALIZE;
return TARGET_PENDING and stop.

If:
- NOT_PUBLISHABLE;
- FAILED;
return FAILED and stop.

Never apply lifecycle on a pending target commit.

Update journal to TARGET_PUBLISHED only after validating actual published material.

## 17. Target version validation

Validate:
- VersionStore.get_version(target_version_id) exists/published;
- version.snapshot_id == target_snapshot_id;
- target snapshot agrees with document commit record.

Do NOT bind new SourceVersion here.

## 18. Step B — lifecycle revision

Build draft from package:
- lifecycle subject remains package.prior_ref_id;
- replacement assertions remain new-source assertions.

Set:
draft.base_version_id = target_version_id.

Call:
LifecycleRevisionCoordinator.apply_revision(
    authorized_draft,
    source_fingerprint=prior.source_fingerprint
)

Important:
use PRIOR source fingerprint because lifecycle document record describes the prior ref.

Frozen lifecycle snapshot creation will preserve the TARGET base manifest ref/fingerprint/content.

## 19. Stale-base/interleaving behavior

Do not silently rebase.

For first lifecycle publication, frozen coordinator requires target_version_id to still be current.

If an unrelated version advances current before lifecycle begins:
- fail closed as CONFLICT / operator resolution;
- do not choose the newer current version;
- do not bind SourceVersion.

For retry of an already staged/finalized lifecycle revision:
use frozen coordinator resume/idempotent behavior.

## 20. Lifecycle failure recovery

If lifecycle fails before finalization:
- keep journal at TARGET_PUBLISHED;
- new SourceVersion remains unbound;
- return LIFECYCLE_PENDING/FAILED with recoverable detail.

Retry same publication material:
- target commit idempotent;
- lifecycle resumes staged state or returns finalized idempotent state.

No second revision id.

## 21. Resolve final lifecycle snapshot on replay

LifecyclePublishResult may return:
- version_id present;
- snapshot_id=None
for FINALIZED idempotent replay.

Therefore:
if snapshot_id is None and version_id exists:
- VersionStore.get_version(version_id);
- recover its snapshot_id.

Require final version + snapshot before SourceVersion bind.

## 22. Final version-chain validation

Before bind require:
- final lifecycle version exists/published;
- final snapshot exists;
- fresh final_version.prior_version_id == target_version_id.

For finalized retry:
preserve and verify recorded target/final chain.

Validate final snapshot preserves target document content identity:
- structural_stage_id;
- assertion_hashes;
- vector_ids;
- USDO ids/hashes;
and adds lifecycle identity.

Do not require final snapshot.ref_id == prior ref; frozen lifecycle intentionally preserves the target base manifest identity.

## 23. Step C — bind new SourceVersion

Only AFTER lifecycle finalization:

bind:
new_source_version_id
→ final lifecycle version_id
→ final lifecycle snapshot_id

Never bind to target intermediate version.

Prior SourceVersion binding remains unchanged.

Exact rebind => idempotent.
Different existing binding => CONFLICT.

## 24. Crash after lifecycle before bind

Required retry:
- target commit idempotent;
- lifecycle returns finalized/idempotent, possibly snapshot_id=None;
- resolve final snapshot from VersionStore;
- bind_source_version completes;
- FINALIZED.

## 25. Crash after bind before journal FINALIZED ack

On retry:
- journal may still be LIFECYCLE_PUBLISHED;
- new SourceVersion may already be bound to recorded final version/snapshot.

Treat exact binding as idempotent and finalize journal.

Do not reject an exact post-side-effect retry.

## 26. Final invariants

FINALIZED requires:
- new SourceVersion bound to final lifecycle KB version;
- final version != target intermediate version;
- final version current on no-interleaving happy path;
- prior SourceVersion binding unchanged;
- prior P2J ref SUPERSEDED/ineligible currently;
- new journal ref ACTIVE/eligible;
- prior archived/superseded assertions ineligible;
- replacement assertions not lifecycle-blocked;
- outbox events emitted once;
- historical prior version still resolvable.

## 27. Empty/non-publishable target

If target AssertionSet cannot pass existing DocumentCommitCoordinator publishability:
- fail closed;
- do not apply prior lifecycle transitions;
- do not bind new SourceVersion.

Do not invent a metadata-only commit path in Phase 5.3.

## 28. Tests

Maintain:
- knowledge_curator >= 475 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add at least:

### pre-side-effect validation
1. package.requires_manual_review -> no commit;
2. missing approval -> no commit;
3. rejected approval -> no commit;
4. approval wrong package -> no commit;
5. approval wrong scope -> no commit;
6. target source ref/fingerprint mismatch -> no commit;
7. target assertion material mismatch -> no commit;
8. curation PENDING/REJECT/RETURN/SUPERSEDE -> no commit.

### target commit
9. valid target commit publishes V_target;
10. PENDING_VECTOR -> no lifecycle/no bind;
11. PENDING_FINALIZE -> no lifecycle/no bind;
12. existing target commit same material resumes/idempotent;
13. existing target commit different admitted material -> conflict.

### lifecycle
14. draft base == V_target;
15. lifecycle subject == prior ref;
16. prior fingerprint used for lifecycle record;
17. explicit approval evidence persisted;
18. stale target base due interleaving -> fail closed/no bind;
19. lifecycle failure leaves new SourceVersion unbound;
20. retry resumes lifecycle without duplicate events/version.

### final bind/recovery
21. V_final != V_target;
22. V_final.prior_version_id == V_target;
23. new SourceVersion binds V_final, not V_target;
24. prior binding unchanged;
25. lifecycle finalized then bind fails once -> retry completes;
26. finalized lifecycle snapshot_id=None -> recover snapshot from VersionStore;
27. bind succeeds then journal final update fails -> retry finalizes idempotently;
28. conflicting pre-existing new binding -> conflict.

### visibility / E2E
29. P2J prior ref becomes superseded/ineligible;
30. new journal ref remains eligible;
31. old assertion ineligible, replacement not lifecycle-blocked;
32. historical prior KB version remains resolvable;
33. exact full replay returns FINALIZED idempotent with no duplicate events.

## 29. Deliverables

Create:
- knowledge_curator/schemas/revision_publication.py
- knowledge_curator/ports/revision_publication_store.py
- knowledge_curator/adapters/in_memory_revision_publication.py
- knowledge_curator/core/revision_publication.py
- Phase 5.3 tests
- results/phase-05-3-executor-report.md

No public MCP tool yet.
No external DB/event transport selection.

## 30. Report

Report:
- Phase 5.3 implementation CODE SHA;
- approval-before-side-effects: PASS/FAILED;
- exact target material gate: PASS/FAILED;
- curation gate: PASS/FAILED;
- target commit recovery: PASS/FAILED;
- lifecycle recovery: PASS/FAILED;
- final source-version binding: PASS/FAILED;
- bind-after-lifecycle recovery: PASS/FAILED;
- stale-base fail-closed: PASS/FAILED;
- P2J visibility E2E: PASS/FAILED;
- idempotent full replay: PASS/FAILED;
- integration tests;
- knowledge_curator tests;
- public contracts changed: NO;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 31. Completion

Update status.json:
- phase = 5.3
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-3-executor-report.md

Push main and STOP.

Do not start Phase 5.4.
Planner performs final module acceptance/freeze after reviewing Phase 5.3.
