# Phase 5.2-R3 Plan — P2J Lifecycle Subject Direction Closure

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Fix the final Phase 5.2 composition bug:
PREPRINT_TO_JOURNAL lifecycle revision must target the PRIOR source ref, not the NEW journal ref.

Do not start Phase 5.3.

## 1. Freeze everything else

Do not redesign:
- content delta;
- FULL_REEXTRACT transitions;
- deep-copy;
- package material identity;
- processed-unit coverage;
- source lineage;
- lifecycle coordinator internals;
- risk gate.

## 2. package_to_revision_draft lifecycle subject

Current incorrect behavior:
- P2J package prior_ref_id=ARXIV-1;
- new_ref_id=JOURNAL-1;
- draft.ref_id=JOURNAL-1;
- LifecycleRevisionCoordinator marks JOURNAL-1 SUPERSEDED.

Fix:

For a RevisionPackage whose actions archive/supersede prior-version assertions:
- draft.ref_id = package.prior_ref_id.

At minimum PREPRINT_TO_JOURNAL MUST use prior_ref_id.

Preferred simple rule in Phase 5.2-R3:
- package_to_revision_draft uses package.prior_ref_id as lifecycle subject for all current supported upgrade relations, because all transition actions are old/prior assertion transitions.

Same-ref revisions remain unchanged naturally.

## 3. Keep replacement/new identities unchanged

Only lifecycle subject ref changes.

Do NOT rewrite:
- supersede_actions old->new;
- replacement_assertion_ids;
- added_assertion_ids;
- evidence_refs;
- package_id;
- new target assertion ref_ids.

New assertions remain bound to package.new_ref_id.

## 4. P2J direction regression

Fixture:
- prior source P1 ref_id = ARXIV-1;
- new source J1 ref_id = JOURNAL-1;
- relation = PREPRINT_TO_JOURNAL;
- at least one old->new supersede and/or archive.

Required:
- draft.ref_id == ARXIV-1;
- draft.trigger == PREPRINT_TO_JOURNAL;
- draft.supersede_actions still maps old prior assertion -> new journal assertion;
- replacement_assertion_ids contains new journal assertion ids;
- evidence_refs contains prior_source_version_id and new_source_version_id.

## 5. Optional lifecycle visibility integration regression

If practical without broad changes:
- publish a base/current version fixture;
- construct a rule-eligible TEST draft or explicitly controlled test approval fixture;
- apply revision;
- assert prior ref becomes document_status=SUPERSEDED/ineligible;
- assert new journal ref has no superseded document lifecycle record and remains eligible.

Do not change production risk semantics just for the test.

## 6. Risk gate remains honest

Do not inject fake:
- high_confidence;
- multi_source;
- no_controversy.

Phase 5.2 output can remain manual-adjudication-required by default.

CG-021 records the missing public approval contract.
Phase 5.3 will implement an INTERNAL explicit RevisionApproval path.

## 7. Tests

Maintain:
- knowledge_curator >= 470 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add at least:
1. P2J draft targets prior_ref_id;
2. new assertion replacement IDs remain unchanged/new-ref assertions;
3. same-ref revision remains correct;
4. package_id unchanged by draft-target helper change;
5. no lifecycle publication is performed in Phase 5.2.

## 8. Deliverable

Create:
results/phase-05-2-r3-executor-report.md

Report:
- P2J lifecycle subject = prior ref: PASS/FAILED;
- new journal identities preserved: PASS/FAILED;
- same-ref compatibility: PASS/FAILED;
- risk gate bypassed: NO;
- lifecycle publication performed: NO;
- integration tests;
- knowledge_curator tests;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 9. Completion

Update status.json:
- phase = 5.2-R3
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-2-r3-executor-report.md

Push main and STOP.
Do not start Phase 5.3.
