# Phase 5.2-R1 Planner Review — MOSTLY PASS, Final FULL_REEXTRACT/Material Closure Required

Implementation CODE SHA: a16db3b614ba5552a5f9c59abcb1a1ac4ffee96b
origin/main bookkeeping tip: 7084bc0783356587dbcb77b98d8d1401a907b97a

Verdict: MOSTLY PASS.

## Accepted

- manifest/inventory/batch source identity is checked against registry lineage;
- intent.relation must equal new source-version relation;
- prior source version requires KB/snapshot binding;
- extraction completion is represented with processed_unit_ids;
- DELTA_SAFE and FULL_REEXTRACT processed scopes are validated;
- FULL_REEXTRACT target no longer carries old assertions;
- scientific target material now contributes to package_id;
- replacement_assertion_ids includes supersede targets + added ids;
- lifecycle publication is still not performed;
- Phase 5.0/5.1 frozen behavior is untouched;
- reported baselines remain green.

## BLOCKER R2-01 — FULL_REEXTRACT transition set is empty

For segmentation_reset=True, compute_content_delta returns:
- mode=FULL_REEXTRACT_REQUIRED;
- extraction_unit_ids=all new units;
- no unchanged/modified/added/removed categories.

compute_transitions has no FULL_REEXTRACT branch. Therefore:
- prior assertions are not archived;
- new fully re-extracted assertions are not marked added;
- RevisionPackage supersede/archive/added can all be empty.

This is unsafe for Phase 5.3.

Required safe semantics for FULL_REEXTRACT_REQUIRED when no exact old→new alignment is available:
- every prior assertion => ARCHIVE;
- every new target assertion => ADDED;
- no automatic supersede;
- requires_manual_review remains false unless another ambiguity/review condition exists.

If a future/full fallback retains explicitly proven exact unit alignment, only proven transitions may be used; do not fuzzy infer.

For Phase 5.2-R2, simplest safe behavior:
FULL_REEXTRACT_REQUIRED => archive all prior assertions + add all validated new assertions.

## BLOCKER R2-02 — nested scientific values are not deeply copied

The new Subject/ObjectValue/Condition dataclasses are reconstructed, but:
- ObjectValue.value is assigned directly;
- Condition.value is assigned directly.

Those fields are Any and may be mutable (e.g. RANGE list, dict/list structured condition values).

Therefore carried assertions can still share nested mutable scientific payload with historical assertions.

Required:
use copy.deepcopy (or equivalent recursive copy) for all nested scientific values.

Regression must use mutable values, not only scalar floats:
- ObjectValue.value=[1.0,2.0] or dict;
- Condition.value=[...]/dict;
- mutate carried value;
- prior value unchanged.

## BLOCKER R2-03 — builder still permits malformed prior inventory unit references

RevisionPackageBuilder calls:
validate_prior_inventory(... allow_unresolvable_units=True)

R1 plan required structural input integrity to fail closed. An assertion_unit_map referencing a unit absent from the prior manifest is malformed source material, not merely a changed-content ambiguity.

Required in RevisionPackageBuilder:
- strict prior inventory validation;
- mapped prior unit must exist;
- malformed inventory => fail closed.

FULL_REEXTRACT_REQUIRED should be triggered by an explicit safe reason such as segmentation_reset, not by corrupt prior inventory.

The low-level compute_content_delta fallback behavior may remain for isolated helper compatibility, but the publication-bound RevisionPackageBuilder must not accept structurally malformed inventory.

## BLOCKER R2-04 — package material hash does not preserve prior/new side identity or assertion-unit binding

Current package_id contains one combined list:
prior_manifest.units + new_manifest.units
with only {id, hash}.

Problems:
1. prior/new units are not side-labelled. For same unit_id, swapping old/new hashes can serialize to the same multiset;
2. unit locator/kind/prior_unit_id alignment material is absent;
3. target assertion -> content unit binding is absent.

Required canonical package material must distinguish:

prior_units:
- unit_id;
- content_hash;
- locator;
- kind;
- prior_unit_id if present.

new_units:
- same fields.

target assertions:
- assertion id;
- ref_id;
- semantic payload hash;
- provenance;
- bound new unit id.

Also include explicit delta pairs/categories or equivalent canonical alignment payload.

Regression:
- same IDs/hashes but swap prior/new unit hashes => different package_id;
- same target assertion material but move binding U1 -> U2 => different package_id.

## BLOCKER R2-05 — package identity should include trace/provenance under current material policy

Current SourceVersion/Lifecycle material equality treats trace_id/provenance_id as material.

RevisionPackage later uses package_id as revision_id while package_to_revision_draft carries trace/provenance.

If two packages have identical scientific payload but different trace/provenance, current code can produce the same package_id while lifecycle material differs, causing a deterministic revision-id collision during publication.

Required:
include package trace_id/provenance_id in package material identity under the current repository material-equality policy.

Same trace/provenance => deterministic replay.
Different trace/provenance => different package_id.

## Decision

Do not start Phase 5.3.

Execute one final narrow Phase 5.2-R2:
1. FULL_REEXTRACT transition semantics;
2. recursive scientific deep-copy;
3. strict builder prior-inventory integrity;
4. side-labelled/unit-bound package material identity;
5. trace/provenance identity consistency.

After R2 passes, freeze Phase 5.2 and begin publication orchestration.
