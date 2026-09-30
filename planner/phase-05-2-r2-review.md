# Phase 5.2-R2 Planner Review — MOSTLY PASS, P2J Lifecycle Subject Direction Fix Required

Implementation CODE SHA: ea03c1365a2f54bc2acc21174de8b95c8932bb0e
origin/main bookkeeping tip: d40681d0586969074465e6ffd33a41620f499a40

Verdict: MOSTLY PASS.

## Accepted

- FULL_REEXTRACT_REQUIRED now archives all prior assertions and adds all new assertions, with no automatic supersede;
- recursive deep-copy covers mutable ObjectValue.value / Condition.value;
- RevisionPackageBuilder uses strict prior inventory validation;
- package identity distinguishes prior/new unit material;
- assertion-to-unit binding is included in package identity;
- trace_id/provenance_id are included in package identity;
- FULL_REEXTRACT RevisionDraft actions are complete;
- lifecycle publication remains unperformed;
- reported baselines remain green.

These Phase 5.2 mechanics are accepted.

## BLOCKER R3-01 — P2J lifecycle draft targets the NEW ref instead of the PRIOR ref

package_to_revision_draft currently uses:

ref_id = package.new_ref_id

But LifecycleRevisionCoordinator.apply_revision has explicit semantics:

if trigger == PREPRINT_TO_JOURNAL:
    document status = SUPERSEDED

Therefore current composition means:
- the newly committed journal ref is marked SUPERSEDED;
- the prior preprint document itself receives no document-level supersede record.

This is backwards.

The revision actions in RevisionPackage are transitions FROM prior assertions TO new assertions. The lifecycle subject for P2J must therefore be the prior source document/ref.

Required for PREPRINT_TO_JOURNAL:
- RevisionDraft.ref_id = package.prior_ref_id;
- old assertion lifecycle records therefore remain associated with the prior document identity;
- new journal ref remains active after its content commit;
- prior preprint ref becomes SUPERSEDED after lifecycle revision publication.

For generic revision relationships, prefer prior_ref_id as the lifecycle subject whenever the actions archive/supersede prior assertions. Same-ref revisions are unaffected.

## R3-02 — tests must encode intended visibility direction

Add regression at minimum:
- P1 ref = ARXIV-1;
- J1 ref = JOURNAL-1;
- package_to_revision_draft(P2J).ref_id == ARXIV-1;
- draft.trigger == PREPRINT_TO_JOURNAL;
- replacement ids still point to J1 assertion ids;
- evidence refs retain prior/new source-version ids.

If composing with lifecycle coordinator in a test, use an explicitly valid risk/approval fixture rather than fabricating production evidence:
- after publication, prior ref is superseded/ineligible;
- new journal ref remains active/eligible.

Do not make P2J draft target new_ref_id.

## R3-03 — no risk-gate bypass in Phase 5.2

package_to_revision_draft may remain manual-adjudication-required by default.

Do NOT set:
- high_confidence=true;
- multi_source=true;
- manual_adjudication_required=false

just to make Phase 5.3 easier.

docs/03 §7.3 explicitly allows high-risk L0 manual approval. Phase 5.3 must model an explicit auditable approval input instead of faking low-risk evidence.

## Decision

Execute one very small Phase 5.2-R3:
1. correct lifecycle subject ref to prior_ref_id;
2. add P2J direction regression;
3. leave risk approval for Phase 5.3.

After R3 passes, freeze Phase 5.2 and begin final publication orchestration.
