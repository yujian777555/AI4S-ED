# Phase 5.1-R1 Planner Review — MOSTLY PASS, Final Lineage/Registry Integrity Closure Required

Implementation CODE SHA: c65cfb7466ad53f73ddee5e5f5f2640bce785f56
origin/main bookkeeping tip: e6074367c777056d3b44c9fac18dfb336c254d91

Verdict: MOSTLY PASS.

## Accepted

- DOI/stable cross-identifier conflicts now run before positive returns;
- prior-only explicit lineage enters classification;
- PREPRINT_TO_JOURNAL validates prior PREPRINT + candidate JOURNAL;
- ref+fingerprint / DOI / stable cross-work uniqueness checks exist;
- append conflict checks occur before index mutation;
- WorkRecord idempotency is hardened;
- reported baselines remain green.

These areas should remain unchanged unless a directly related test exposes a defect.

## BLOCKER R2-01 — exact replay can swallow contradictory explicit lineage

Exact ref_id + source_fingerprint is evaluated before explicit lineage.

_replay_material_conflict checks DOI/stable/title, but does not validate:
- explicit_work_id against existing.work_id;
- explicit_prior_version_id against existing work/version;
- explicit_relation compatibility.

Therefore an already-registered source version in Work A can be presented again with the same ref/fingerprint but explicit_work_id=Work B and still be returned as EXACT_REPLAY.

Required:
before EXACT_REPLAY is returned, any supplied explicit lineage evidence must be compatible with the existing source-version record/work family.

At minimum:
- explicit_work_id, if supplied, must equal existing.work_id;
- explicit_prior_version_id, if supplied, must exist and belong to existing.work_id;
- PREPRINT_TO_JOURNAL / REVISION_OF / CORRECTED_VERSION replay claims must not contradict the existing record's lineage/material.

Contradiction => IDENTITY_CONFLICT, never replay.

## BLOCKER R2-02 — explicit_relation alone is ignored

prepare() enters explicit-lineage handling only when work_id or prior_id is present.

Thus a candidate can set:
explicit_relation=PREPRINT_TO_JOURNAL
with no work/prior and the relation may be ignored by normal DOI/title/no-match classification.

Required:
non-NONE explicit_relation must be treated as explicit lineage intent and validated.

Rules:
- PREPRINT_TO_JOURNAL requires prior;
- REVISION_OF requires prior;
- CORRECTED_VERSION requires prior;
- EXPLICIT_SAME_WORK requires at least explicit_work_id or prior;
- relation-only requests lacking required target/prior => IDENTITY_CONFLICT.

Do not silently discard explicit relation input.

## BLOCKER R2-03 — VersionRelation.NONE can override meaningful lineage

Python Enum values are truthy. Current:
candidate.explicit_relation or default_relation
therefore preserves VersionRelation.NONE when explicitly supplied.

With an explicit prior/work, this can register SAME_WORK_NEW_VERSION while storing relation=NONE.

Required:
- if explicit lineage fields are supplied and explicit_relation=NONE, fail closed as contradictory, OR normalize deterministically to the appropriate default before any record/intent is created;
- preferred fail-closed semantics: explicit NONE + explicit lineage => IDENTITY_CONFLICT.

Omitted relation (None) continues to default:
- prior present -> REVISION_OF;
- work-only -> EXPLICIT_SAME_WORK.

## BLOCKER R2-04 — registry permits orphan source versions

InMemorySourceVersionRegistry.append_source_version does not require record.work_id to exist.

A direct Port caller can append a source version pointing to an unknown work and populate identity indexes.

Required:
- incoming record.work_id must exist before append;
- if prior_source_version_id is present, prior must exist and belong to the same work;
- all referential checks occur before any mutation;
- rejected append leaves indexes unchanged.

This is an internal registry invariant, not a public schema change.

## BLOCKER R2-05 — replay lineage material should be explicit in diagnostics/tests

Add direct tests proving:
- exact replay + contradictory explicit work -> conflict;
- exact replay + prior from another work -> conflict;
- exact replay + compatible explicit lineage remains replay;
- relation-only P2J/REVISION/CORRECTED fails without prior;
- explicit NONE + prior/work fails closed;
- omitted relation still defaults correctly;
- orphan work append rejected;
- missing/cross-work prior append rejected atomically.

## Decision

Do not start Phase 5.2.
Execute one final narrow Phase 5.1-R2.
After R2 passes, freeze Phase 5.1 and proceed to changed-content delta/revision orchestration.
