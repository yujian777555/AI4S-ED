# Phase 5.1-R2 Plan — Replay Lineage Consistency + Explicit Relation State Machine + Registry Referential Integrity

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Close the final Phase 5.1 identity/lineage integrity gaps from:
planner/phase-05-1-r1-review.md

Do not start Phase 5.2.

## 1. Scope freeze

Do not change:
- normalization rules;
- DOI/stable precedence already fixed;
- title-only REVIEW_REQUIRED;
- no-fuzzy policy;
- Phase 5.0 lifecycle core;
- bind-after-publish semantics;
- public contracts / CG-019 boundary.

## 2. R2-A — exact replay must validate explicit lineage

Before returning EXACT_REPLAY for existing (ref_id, fingerprint), validate supplied explicit fields.

### explicit_work_id
If supplied:
- work must exist;
- it must equal existing.work_id.
Otherwise IDENTITY_CONFLICT.

### explicit_prior_version_id
If supplied:
- prior must exist;
- prior.work_id must equal existing.work_id.
Otherwise IDENTITY_CONFLICT.

### explicit_relation
If supplied and non-NONE:
- validate relation requirements from section 3;
- it must not contradict the existing record's material lineage.

For a pure replay with no explicit lineage fields, existing behavior remains.

## 3. R2-B — explicit relation state machine

Treat any non-NONE explicit_relation as explicit lineage intent even if work/prior are absent.

Required minimum:

### PREPRINT_TO_JOURNAL
- prior required;
- prior.source_kind == PREPRINT;
- candidate.source_kind == JOURNAL;
- resolved work == prior.work.

### REVISION_OF
- prior required;
- resolved work == prior.work.

### CORRECTED_VERSION
- prior required;
- resolved work == prior.work.

### EXPLICIT_SAME_WORK
- explicit_work_id OR explicit_prior_version_id required;
- if prior only, inherit work.

### NONE
If explicit_work_id or explicit_prior_version_id is supplied together with explicit_relation=NONE:
- IDENTITY_CONFLICT.
Do not persist SAME_WORK_NEW_VERSION with relation NONE.

If no explicit lineage fields exist and relation is omitted (None), normal identifier classification proceeds.

## 4. Omitted relation defaults

Keep deterministic defaults only when explicit_relation is truly omitted:

- prior present, relation omitted -> REVISION_OF;
- work only, relation omitted -> EXPLICIT_SAME_WORK.

Add tests distinguishing Python None from VersionRelation.NONE.

## 5. Replay compatibility details

For exact replay:

Compatible:
- explicit_work_id == existing.work_id;
- prior (if supplied) is in existing.work_id;
- no relation/material contradiction.

Contradictory:
- explicit work points elsewhere;
- prior points elsewhere;
- P2J claims a replay that is not compatible with PREPRINT->JOURNAL source kinds/lineage.

Return:
IDENTITY_CONFLICT with diagnostic explaining the conflicting explicit field.

Do not mutate registry on replay.

## 6. R2-C — registry work referential integrity

In append_source_version():

Before all mutations:
- get_work(record.work_id) / internal lookup must exist;
- otherwise raise ValueError("unknown work_id" or equivalent).

Do not auto-create work inside the adapter.

IncrementalIntakeService.proceed remains responsible for creating a new WorkRecord first.

## 7. Registry prior referential integrity

If record.prior_source_version_id is non-null:
- prior must exist;
- prior.work_id == record.work_id.

Otherwise reject before mutation.

Do not require prior for VersionRelation.NONE records with no prior.
Relation-state semantics are primarily service-level; registry enforces references it is given.

## 8. Atomicity

All new work/prior/replay conflict checks must occur before mutating:
- _versions;
- _version_order;
- _by_ref_fp;
- _by_doi;
- _by_stable;
- _by_title.

Failed append leaves all indexes and list_versions unchanged.

## 9. Tests

Maintain:
- knowledge_curator >= 392 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add at least:
1. exact replay + explicit different work -> conflict;
2. exact replay + prior from different work -> conflict;
3. exact replay + compatible work/prior -> replay;
4. relation-only PREPRINT_TO_JOURNAL -> conflict;
5. relation-only REVISION_OF -> conflict;
6. relation-only CORRECTED_VERSION -> conflict;
7. explicit NONE + prior -> conflict;
8. explicit NONE + work -> conflict;
9. omitted relation + prior -> REVISION_OF;
10. omitted relation + work -> EXPLICIT_SAME_WORK;
11. append source version with unknown work -> reject;
12. append source version with missing prior -> reject;
13. append source version with cross-work prior -> reject;
14. failed orphan/prior append leaves indexes unchanged.

## 10. Deliverable

Create:
results/phase-05-1-r2-executor-report.md

Report:
- replay explicit-lineage consistency: PASS/FAILED;
- relation-only validation: PASS/FAILED;
- explicit NONE fail-closed: PASS/FAILED;
- omitted-relation defaults: PASS/FAILED;
- registry work integrity: PASS/FAILED;
- registry prior integrity: PASS/FAILED;
- append atomicity: PASS/FAILED;
- exact tests;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 11. Completion

Update status.json:
- phase = 5.1-R2
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-1-r2-executor-report.md

Push main and STOP.
Do not start Phase 5.2.
