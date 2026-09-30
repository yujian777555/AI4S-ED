# Phase 5.2-R2 Plan — FULL_REEXTRACT Transition + Final Material Identity Closure

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Close only the final five Phase 5.2 correctness gaps from:
planner/phase-05-2-r1-review.md

Do not start Phase 5.3.

## 1. Freeze accepted R1 behavior

Do not redesign:
- exact-only unit alignment;
- DELTA_SAFE classification;
- processed_unit_ids coverage;
- manifest/source identity validation;
- intent relation/prior KB binding;
- semantic-slot matching;
- RevisionDraft replacement-id logic;
- Phase 5.0 lifecycle core;
- Phase 5.1 source lineage.

## 2. FULL_REEXTRACT transition semantics

When:
plan.mode == FULL_REEXTRACT_REQUIRED

and the target batch has passed full extraction validation:

Required transitions:
- every prior_inventory assertion => ARCHIVE;
- every target/delta_batch assertion => ADDED;
- no automatic SUPERSEDE.

Reason strings should be explicit, e.g.:
- full_reextract_prior_archived;
- full_reextract_new_added.

No fuzzy matching.

This path must work for segmentation_reset=True.

The resulting RevisionPackage must therefore contain:
- archive_actions = all prior assertion ids;
- added_assertion_ids = all new assertion ids;
- supersede_actions = {}.

package_to_revision_draft must then expose all new assertion ids in replacement_assertion_ids.

## 3. FULL_REEXTRACT regression

Build:
- prior assertions A1, A2;
- segmentation_reset=True;
- new full extraction A1N, A3;
- processed_unit_ids covers ALL new units.

Required:
- A1/A2 archive;
- A1N/A3 added;
- no supersede;
- no carry-forward;
- target only new full extraction;
- RevisionDraft archive_actions={A1,A2};
- replacement_assertion_ids={A1N,A3}.

## 4. Recursive scientific deep-copy

Use copy.deepcopy or an equivalent recursive method for mutable scientific payload.

At minimum:
- Subject;
- ObjectValue, including ObjectValue.value;
- Condition, including Condition.value;
- nested list/dict/tuple-like scientific values where Python deepcopy applies.

Enums/strings/scalars may remain value-copied.

Provenance remains rebuilt:
- new locator;
- sentence copied.

Mandatory regression:
- old object.value=[1.0,2.0];
- old condition.value={"x":[1,2]};
- carry forward;
- mutate carried list/dict deeply;
- old remains unchanged.

Keep real semantic_payload_hash equality before mutation.

## 5. Strict prior inventory in RevisionPackageBuilder

Builder must call strict validation:
mapped unit must exist in prior_manifest.

Do NOT use allow_unresolvable_units=True for publication-bound package construction.

Malformed prior inventory:
- unknown unit id;
- missing map;
- dangling map;
=> fail closed.

If compute_content_delta helper still supports FULL_REEXTRACT fallback for a standalone unsafe inventory test, that is acceptable, but RevisionPackageBuilder must reject malformed input first.

FULL_REEXTRACT for real package construction should come from an explicit safe condition such as segmentation_reset=True.

## 6. Canonical package material payload

Refactor package_id input into a clear helper if useful.

Include side-labelled prior/new manifest material separately.

### prior_units
For every prior unit:
- unit_id;
- locator;
- kind.value;
- content_hash;
- prior_unit_id.

### new_units
Same.

Do NOT merge both sides into an unlabeled multiset.

### delta alignment
Include deterministic:
- mode;
- unchanged pair old/new;
- modified pair old/new;
- added unit ids;
- removed unit ids;
- extraction unit ids.

### extraction completion
Include:
- sorted processed_unit_ids.

### target assertion material
For each target assertion include:
- assertion id;
- ref_id;
- semantic_payload_hash;
- provenance locator;
- provenance sentence;
- bound new unit id from delta_batch map or carried_records.

For carried assertions, derive binding from CarriedAssertionRecord.unit_id.

### actions
Include:
- supersede;
- archive;
- added.

### lineage/binding
Include:
- work id;
- prior/new source version ids;
- relation;
- prior/new ref/fingerprint;
- prior KB version + snapshot.

## 7. Package id side-identity regressions

Add:
1. same unit id U1, prior hash h1/new h2 => package P1;
2. swap prior h2/new h1 with otherwise equivalent fixture => package id differs.

Also:
1. same target assertion id/semantic/provenance;
2. bind to U1 vs U2;
=> package id differs.

The fixture must remain valid with processed scopes.

## 8. trace/provenance identity

Include:
- RevisionPackage trace_id;
- RevisionPackage provenance_id

in deterministic package material, because current SourceVersion/Lifecycle material policy treats these as semantic for idempotency/conflict detection.

Regression:
same scientific material but different trace_id => different package_id.
same exact material + same trace/provenance => same package_id.

## 9. Determinism

No random UUID.

Canonical sort all set/map/list-like material before hashing.

Same complete material => same package_id across repeated builds.

## 10. Tests

Maintain:
- knowledge_curator >= 461 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add at least:
1. segmentation-reset FULL_REEXTRACT archives all prior;
2. segmentation-reset FULL_REEXTRACT adds all new;
3. FULL_REEXTRACT no supersede;
4. FULL_REEXTRACT draft replacement ids = all new ids;
5. nested ObjectValue.value deepcopy;
6. nested Condition.value deepcopy;
7. builder unknown prior unit -> reject;
8. prior/new same-id hash direction changes package id;
9. target assertion unit binding changes package id;
10. trace_id change changes package id;
11. identical full material remains deterministic.

## 11. Deliverable

Create:
results/phase-05-2-r2-executor-report.md

Report:
- FULL_REEXTRACT transition semantics: PASS/FAILED;
- recursive scientific deep-copy: PASS/FAILED;
- strict prior inventory: PASS/FAILED;
- side-labelled package material identity: PASS/FAILED;
- assertion-unit binding in package identity: PASS/FAILED;
- trace/provenance package identity: PASS/FAILED;
- RevisionDraft FULL_REEXTRACT actions: PASS/FAILED;
- lifecycle publication performed: NO;
- integration tests;
- knowledge_curator tests;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 12. Completion

Update status.json:
- phase = 5.2-R2
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-2-r2-executor-report.md

Push main and STOP.
Do not start Phase 5.3.
