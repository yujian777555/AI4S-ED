# Phase 5.1-R1 Plan — Identity Precedence, Explicit Lineage, Registry Invariants

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Close the five identity correctness blockers in:
planner/phase-05-1-review.md

Do not start Phase 5.2.

## 1. Freeze accepted behavior

Do not change:
- safe DOI/title/stable-id normalization rules;
- title-only REVIEW_REQUIRED behavior;
- no-fuzzy matching policy;
- Phase 5.0 lifecycle semantics;
- public schemas/contracts;
- bind-only-after-published behavior except for direct bug fixes.

## 2. Cross-identifier checks before positive returns

In prepare(), compute:
- doi_works;
- stable_works;
- title_works.

Before returning SAME_WORK_NEW_VERSION from DOI or stable_id:

### DOI invariant
If len(doi_works) > 1:
- IDENTITY_CONFLICT.

### stable-id invariant
If len(stable_works) > 1:
- IDENTITY_CONFLICT.

### DOI/stable disagreement
If len(doi_works)==1 and len(stable_works)==1 and the work ids differ:
- IDENTITY_CONFLICT;
- match_evidence includes exact_doi + exact_stable_id;
- ambiguity_candidates includes both works.

Only after these checks may DOI/stable positive classification occur.

## 3. Regression for currently unreachable mismatch

Create Work A with DOI X.
Create Work B with stable_id Y.
Candidate contains DOI X + stable_id Y.

Required:
IDENTITY_CONFLICT.

It must never return Work A merely because DOI precedence comes first.

## 4. Prior-only explicit lineage

Call explicit-lineage classification when:

candidate.explicit_work_id is not None
OR
candidate.explicit_prior_version_id is not None

Rules:
- valid prior, no explicit work -> inherit prior.work_id;
- invalid prior -> IDENTITY_CONFLICT;
- prior/work mismatch -> IDENTITY_CONFLICT;
- exact DOI/stable mapping contradicting inherited work -> IDENTITY_CONFLICT.

Add regression:
- valid prior-only lineage -> SAME_WORK_NEW_VERSION in prior work.

## 5. PREPRINT_TO_JOURNAL compatibility

If explicit_relation == PREPRINT_TO_JOURNAL:

Require:
- explicit_prior_version_id is present;
- prior exists;
- resolved work exists;
- prior.work_id == resolved work;
- prior.source_kind == PREPRINT;
- candidate.source_kind == JOURNAL.

If any condition fails:
IDENTITY_CONFLICT with explicit diagnostic.

Valid case:
- produces SAME_WORK_NEW_VERSION;
- VersionUpgradeIntent exists;
- prior/new versions preserved in same work.

Invalid cases:
- no prior;
- prior JOURNAL;
- candidate PREPRINT;
- prior from another work.

No fuzzy fallback.

## 6. Other explicit relations

For REVISION_OF / CORRECTED_VERSION:
- if explicit_prior_version_id is supplied, validate it belongs to resolved work.
- do not invent a prior when absent.

EXPLICIT_SAME_WORK may resolve with explicit_work_id alone.

VersionRelation.NONE must not override a meaningful explicit lineage relation accidentally.

Keep semantics deterministic and minimal.

## 7. Registry uniqueness: ref+fingerprint

In append_source_version():

Before inserting, check _by_ref_fp[(ref_id,fingerprint)].

If an existing version id is present:
- identical material -> return idempotently if it is truly the same source-version record;
- different source_version_id/work/material -> raise ValueError.

Do not overwrite the index silently.

## 8. Registry uniqueness: DOI across works

If normalized_doi is non-empty:
- existing versions with that DOI may all belong to the SAME work;
- if any belong to a different work_id than the incoming record -> reject.

Multiple versions in one work sharing the DOI are valid.

## 9. Registry uniqueness: stable_id across works

Same rule:
- repeated stable_id within one work is valid;
- same stable_id across different works -> reject.

## 10. Append atomicity

Perform all conflict checks BEFORE mutating:
- _versions;
- _version_order;
- _by_ref_fp;
- _by_doi;
- _by_stable;
- _by_title.

A rejected append must leave registry state unchanged.

Add test proving failed append does not partially mutate indexes.

## 11. WorkRecord idempotency

If practical, harden append_work:
- same work_id + same material -> idempotent;
- same work_id + contradictory created_evidence/trace/provenance -> fail closed.

This is recommended but secondary to source-version invariants.

Do not make created_seq material.

## 12. Tests

Maintain:
- knowledge_curator >= 379 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add at least:
1. DOI Work A + stable Work B -> conflict;
2. stable_id mapped to multiple works -> conflict/fail closed;
3. valid prior-only explicit lineage;
4. invalid prior-only lineage;
5. prior-only lineage contradicted by DOI -> conflict;
6. PREPRINT_TO_JOURNAL without prior -> conflict;
7. PREPRINT_TO_JOURNAL prior JOURNAL -> conflict;
8. PREPRINT_TO_JOURNAL candidate PREPRINT -> conflict;
9. valid PREPRINT_TO_JOURNAL remains PASS;
10. duplicate ref+fingerprint across work -> adapter reject;
11. DOI reused across different work -> adapter reject;
12. stable_id reused across different work -> adapter reject;
13. same DOI across versions of same work -> allowed;
14. failed append leaves indexes unchanged.

## 13. Deliverable

Create:
results/phase-05-1-r1-executor-report.md

Report:
- DOI/stable precedence conflict: PASS/FAILED;
- stable multi-work invariant: PASS/FAILED;
- prior-only explicit lineage: PASS/FAILED;
- preprint->journal compatibility: PASS/FAILED;
- ref+fingerprint uniqueness: PASS/FAILED;
- DOI/stable registry uniqueness: PASS/FAILED;
- append atomicity: PASS/FAILED;
- exact tests;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 14. Completion

Update status.json:
- phase = 5.1-R1
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-1-r1-executor-report.md

Push main and STOP.
Do not start Phase 5.2.
