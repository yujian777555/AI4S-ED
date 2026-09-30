# Phase 5.2 Planner Review — MOSTLY PASS, Input/Material Integrity Hardening Required

Implementation CODE SHA: 6638077519f447cab8c387e268db3460bbbc6adc
origin/main bookkeeping tip: 765bd1c4fdfbd8ae45caa7bf09367b348cb94471

Verdict: MOSTLY PASS / Phase 5.2 is not frozen yet.

## Accepted

- exact-only content-unit alignment is implemented;
- UNCHANGED / MODIFIED / ADDED / REMOVED classification is correct for covered cases;
- unsafe segmentation/inventory cases can fall back to FULL_REEXTRACT_REQUIRED;
- DELTA_SAFE extraction scope is modified+added only;
- modified-unit assertion matching uses deterministic semantic slots and duplicate-slot ambiguity is review-gated;
- RevisionPackage identity is deterministic for identical current inputs;
- package_to_revision_draft does not call lifecycle publication;
- Phase 5.0/5.1 frozen code was not modified;
- reported baselines remain green.

## BLOCKER R1-01 — carried assertions still share mutable nested objects

carry_forward_unchanged creates a new Assertion object but reuses:
- subject=prior_a.subject;
- object=prior_a.object;
- Condition objects inside conditions.

This violates the Phase 5.2 requirement:
"Create a NEW assertion for the new source version, not a mutable alias of the old assertion."

A later mutation to the carried assertion's subject/object/condition can mutate historical prior-version material.

Required:
- deep-copy all nested scientific material;
- provenance rebuilt with new locator;
- prior assertion and all nested objects remain independent.

The current test contains:
semantic_payload_hash(new_a) == semantic_payload_hash(old_a) or True
which is vacuous and must be fixed.

## BLOCKER R1-02 — manifest/inventory/batch identity is not validated against registry lineage

RevisionPackageBuilder validates that intent source versions exist, but does NOT require:

Prior manifest:
- source_version_id == prior.source_version_id;
- ref_id == prior.ref_id;
- source_fingerprint == prior.source_fingerprint.

New manifest:
- source_version_id == new.source_version_id;
- ref_id == new.ref_id;
- source_fingerprint == new.source_fingerprint.

Prior inventory:
- source_version_id == prior.source_version_id;
- ref_id == prior.ref_id.

Delta batch:
- source_version_id == new.source_version_id;
- ref_id == new.ref_id.

Without these checks, content/assertions from another source version can be assembled under a valid VersionUpgradeIntent.

Required: fail closed before delta/package construction.

## BLOCKER R1-03 — intent relation and prior KB binding are under-validated

The Phase 5.2 plan required:
- relation matches records;
- prior source version has a bound KB version when preparing lifecycle upgrade.

Current validate_intent does not require:
intent.relation == new.relation

and does not require:
prior.kb_version_id / prior.snapshot_id

for a lifecycle RevisionPackage.

Required:
- new.relation must equal intent.relation;
- new.prior_source_version_id must match prior (already present);
- for RevisionPackage generation, prior must have a stable published binding represented by non-empty kb_version_id and snapshot_id;
- contradiction/missing binding => fail closed.

Do not require the NEW source version to be bound yet; publication happens later.

## BLOCKER R1-04 — assertion inventory/batch completeness and unit bindings are too weak

Prior inventory currently lacks a dedicated validator.

Required prior inventory invariants:
- unique assertion IDs;
- every assertion.ref_id == inventory.ref_id;
- every assertion has exactly one assertion_unit_map entry;
- every mapped unit exists in prior manifest;
- no dangling assertion_unit_map entry for an unknown assertion.

Delta batch currently validates assertions only, but not dangling map entries or extraction completion.

More importantly, there is no way to distinguish:
"extractor ran on unit U2 and produced zero assertions"
from
"extractor never processed U2."

This is unsafe: an incomplete empty batch for a modified unit can cause old assertions to be archived.

Add internal extraction-completion evidence, recommended:
DeltaAssertionBatch.processed_unit_ids: list[str]

For DELTA_SAFE:
processed_unit_ids must cover exactly (or at minimum all of) plan.extraction_unit_ids and may not claim unchanged/out-of-scope units.

For FULL_REEXTRACT_REQUIRED:
processed_unit_ids must cover all new manifest unit_ids.

Assertions in the batch must map only to processed units.

This is INTERNAL CG-020 compatibility data, not a public schema change.

## BLOCKER R1-05 — FULL_REEXTRACT_REQUIRED batch is effectively unvalidated

RevisionPackageBuilder currently runs validate_delta_batch only when DELTA_SAFE.
In FULL_REEXTRACT_REQUIRED, arbitrary:
- duplicate assertion IDs;
- wrong ref_id;
- unknown unit bindings;
- incomplete extraction coverage

can enter target_assertions.

Required:
- validate all batch structural invariants in all modes;
- mode changes only the allowed/required unit scope.

FULL_REEXTRACT target must use only validated full-new-version extraction output.
No carry-forward.

## BLOCKER R1-06 — package_id does not identify scientific target material

Current package_id hashes:
- work/version IDs;
- mode/extraction unit ids;
- carried assertion ids;
- transition action IDs.

It does NOT hash the target assertions' scientific material.

Counterexample:
- same new assertion id A1N;
- same slot/action old A1 -> A1N;
- value changes 2.0 -> 3.0.

Current package_id can remain identical.

That package_id becomes revision_id downstream, so materially different revisions can collide and be treated idempotently.

Required package material identity must include canonical hashes of at least:
- prior/new manifest identities and content hashes/alignment;
- target assertion material (semantic payload + ref + provenance locator as relevant);
- transition mapping;
- archive/add sets;
- delta mode;
- processed extraction scope;
- relation/work/version lineage.

Same material -> same package_id.
Different scientific material -> different package_id.

## BLOCKER R1-07 — RevisionDraft replacement_assertion_ids is incomplete

package_to_revision_draft currently sets:
replacement_assertion_ids = added_assertion_ids

but replacement assertions also include every NEW target in supersede_actions.values().

Required:
replacement_assertion_ids =
unique(
  supersede_actions.values()
  + added_assertion_ids
)

affected_assertion_ids may include old affected ids plus new replacements as appropriate, but must be deterministic and documented.

## Decision

Do not start Phase 5.3.

Execute one narrow Phase 5.2-R1 hardening pass:
1. deep-copy carry-forward;
2. strict version/material identity validation;
3. extraction completion coverage;
4. FULL_REEXTRACT validation;
5. package material hash;
6. complete RevisionDraft replacement ids.

After R1 passes, freeze Phase 5.2 and begin publication orchestration.
