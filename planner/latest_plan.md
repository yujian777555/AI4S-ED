# Phase 5.2-R1 Plan — Delta Input Integrity + Extraction Completion + Material Idempotency

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Close the seven correctness blockers in:
planner/phase-05-2-review.md

Do not start Phase 5.3.

## 1. Scope freeze

Do not redesign:
- exact-only content alignment;
- UNCHANGED/MODIFIED/ADDED/REMOVED semantics;
- semantic slot matching;
- FULL_REEXTRACT fallback decision;
- Phase 5.0 lifecycle core;
- Phase 5.1 source lineage;
- public MCP contracts.

## 2. Deep-copy carried assertions

carry_forward_unchanged must create a fully independent Assertion graph.

Deep-copy:
- Subject;
- ObjectValue;
- each Condition;
- any mutable value/metadata nested inside scientific payload where applicable.

Rebuild Provenance:
- locator = new unit locator;
- sentence may be copied by value.

Never reuse mutable nested objects from prior Assertion.

Mandatory regression:
- carry old -> new;
- mutate new.subject.original_mention;
- mutate new.object.value;
- mutate new.conditions[0].value;
- old assertion remains byte/material unchanged.

Replace the vacuous:
... == ... or True
with a real semantic equality assertion.

## 3. Validate source-version/material identity before delta

Add pure validators called at the beginning of RevisionPackageBuilder.build.

### prior manifest
Require:
- prior_manifest.source_version_id == prior.source_version_id;
- prior_manifest.ref_id == prior.ref_id;
- prior_manifest.source_fingerprint == prior.source_fingerprint.

### new manifest
Require:
- new_manifest.source_version_id == new.source_version_id;
- new_manifest.ref_id == new.ref_id;
- new_manifest.source_fingerprint == new.source_fingerprint.

### prior inventory
Require:
- source_version_id == prior.source_version_id;
- ref_id == prior.ref_id.

### delta batch
Require:
- source_version_id == new.source_version_id;
- ref_id == new.ref_id.

Any mismatch => fail closed before carry-forward/transition/package id generation.

## 4. Validate intent relation + prior KB binding

In validate_intent/build context require:
- new.relation == intent.relation;
- new.prior_source_version_id == prior.source_version_id;
- prior.kb_version_id is non-empty;
- prior.snapshot_id is non-empty.

This phase prepares lifecycle upgrade from an already published prior source version.

Do NOT require new.kb_version_id; target content is not published yet.

Add tests:
- intent relation differs from new.relation -> reject;
- prior unbound -> reject;
- prior bound -> proceed.

Update fixtures to bind prior version explicitly using SourceVersionRegistry.bind_source_version.

## 5. Prior inventory validation

Add validator:
validate_prior_inventory(inventory, prior_manifest).

Require:
- unique assertion ids;
- every assertion.ref_id == inventory.ref_id;
- every assertion id has one unit-map entry;
- every mapped unit exists in prior manifest;
- assertion_unit_map contains no unknown assertion ids.

No silent skip for missing mapping.

If unsafe mapping prevents delta carry-forward, choose:
- structural invalidity -> fail closed;
- explicitly declared upstream identity reset -> FULL_REEXTRACT_REQUIRED.

Do not silently drop assertions.

## 6. Extraction completion evidence

Extend INTERNAL DeltaAssertionBatch with:
processed_unit_ids: list[str] = field(default_factory=list)

This is CG-020 internal compatibility only.

Validation:

### DELTA_SAFE
required processed scope =
set(plan.extraction_unit_ids)

Require:
- every required unit is processed;
- processed units are all in new manifest;
- processed units do not include unchanged/out-of-scope units unless an explicit future mode says full extraction.

Prefer exact equality for Phase 5.2-R1.

### FULL_REEXTRACT_REQUIRED
required processed scope =
all new manifest unit ids.

Require exact coverage.

Why:
zero extracted assertions from a processed unit is valid;
an unprocessed unit is not equivalent to zero assertions.

## 7. Delta batch structural validation in ALL modes

Always validate:
- unique assertion ids;
- assertion.ref_id == batch.ref_id;
- every assertion id has a unit mapping;
- no dangling map entry;
- mapped unit exists in new manifest;
- mapped unit is in processed_unit_ids.

Then apply mode-specific processed scope rules.

FULL_REEXTRACT_REQUIRED must no longer bypass validate_delta_batch.

## 8. FULL_REEXTRACT behavior

When mode == FULL_REEXTRACT_REQUIRED:
- carried assertions = [];
- carried_records = [];
- target assertions = validated full extraction batch only;
- transitions must be computed against the complete new extraction.

Because content-unit alignment may be unavailable in a segmentation reset, do NOT use modified_pairs that do not exist to infer old->new automatically.

Safe default:
- prior assertions are ARCHIVE candidates;
- new assertions are ADDED candidates;
- if upstream supplies no exact old->new unit alignment, do not invent supersede pairs.

If an exact alignment still exists in a non-segmentation fallback, deterministic transition matching may be used only where alignment is explicitly present.

Never fuzzy match.

## 9. Material package identity

Introduce canonical package material payload.

package_id must change when any materially relevant input/output changes.

Include at least:
- work_id;
- prior/new source version ids;
- relation;
- prior/new ref/fingerprint;
- prior bound KB version/snapshot;
- content delta categories and pair identities;
- content hashes for involved units;
- processed_unit_ids;
- target assertion canonical material;
- supersede/archive/added transitions;
- trace/provenance only if current project identity policy treats them as semantic.

For target assertion material include a deterministic canonical structure containing:
- assertion id;
- ref_id;
- semantic_payload_hash;
- provenance locator/sentence where evidence identity matters;
- bound unit id.

Do not rely only on assertion IDs.

Regression:
same IDs/actions but value 2.0 vs 3.0 -> different package_id.

Same exact material -> same package_id.

## 10. RevisionDraft replacement ids

package_to_revision_draft:

replacement_assertion_ids =
sorted(unique(
  list(package.supersede_actions.values())
  + package.added_assertion_ids
))

No old assertion id belongs in replacement_assertion_ids.

Add regression with:
- one carried/modified supersede;
- one added assertion;
- both NEW ids appear exactly once.

## 11. Ambiguity/manual review

Keep current duplicate-slot review gate.

If package.requires_manual_review:
- package_to_revision_draft may produce a MANUAL_ADJUDICATION_REQUIRED draft;
- it must not fabricate risk metadata to make it auto-rule eligible.

Do not call apply_revision.

## 12. Tests

Maintain:
- knowledge_curator >= 442 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add at least:
1. carried assertion nested mutation does not mutate prior;
2. real semantic payload equality after carry;
3. prior manifest version/ref/fingerprint mismatch -> reject;
4. new manifest version/ref/fingerprint mismatch -> reject;
5. prior inventory identity mismatch -> reject;
6. delta batch identity mismatch -> reject;
7. intent relation mismatch -> reject;
8. prior unbound KB -> reject;
9. prior bound KB -> pass;
10. prior inventory duplicate id -> reject;
11. prior inventory missing unit map -> reject;
12. prior inventory dangling map -> reject;
13. DELTA_SAFE processed scope incomplete -> reject;
14. DELTA_SAFE processed out-of-scope -> reject;
15. FULL_REEXTRACT incomplete processed scope -> reject;
16. FULL_REEXTRACT wrong ref/unknown unit/duplicate id -> reject;
17. processed unit with zero assertions is valid;
18. FULL_REEXTRACT has no carry-forward;
19. package scientific value change changes package_id;
20. identical material preserves package_id;
21. replacement_assertion_ids includes supersede targets + added ids.

## 13. Deliverable

Create:
results/phase-05-2-r1-executor-report.md

Report:
- deep-copy carry-forward: PASS/FAILED;
- manifest/inventory/batch identity validation: PASS/FAILED;
- intent relation/prior binding validation: PASS/FAILED;
- prior inventory integrity: PASS/FAILED;
- extraction completion coverage: PASS/FAILED;
- FULL_REEXTRACT validation: PASS/FAILED;
- material package identity: PASS/FAILED;
- complete draft replacement ids: PASS/FAILED;
- lifecycle publication performed: NO;
- integration tests;
- knowledge_curator tests;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 14. Completion

Update status.json:
- phase = 5.2-R1
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-2-r1-executor-report.md

Push main and STOP.
Do not start Phase 5.3.
