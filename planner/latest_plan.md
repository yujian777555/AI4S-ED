# Phase 5.1-R3 Plan — Exact Replay Material Consistency Closure

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Close only the exact-replay material consistency gaps from:
planner/phase-05-1-r2-review.md

Do not start Phase 5.2.

## 1. Freeze accepted R1/R2 behavior

Do not redesign:
- DOI/stable precedence;
- title-only REVIEW_REQUIRED for non-replay intake;
- explicit relation state machine;
- PREPRINT_TO_JOURNAL new-version classification;
- registry work/prior referential integrity;
- DOI/stable/ref-fingerprint uniqueness;
- Phase 5.0 lifecycle core;
- normalization rules.

## 2. Exact replay invariant

For an existing record selected by exact:
(ref_id, source_fingerprint)

EXACT_REPLAY is allowed only when all incoming material that is explicitly supplied is compatible with the existing SourceVersionRecord.

Omitted optional lineage fields do not create a contradiction.
Supplied fields must agree exactly after safe normalization.

## 3. Prior equality

If candidate.explicit_prior_version_id is supplied:
- prior must exist;
- candidate.explicit_prior_version_id == existing.prior_source_version_id.

Merely belonging to existing.work_id is NOT sufficient.

Cases:
- existing prior=P1, incoming prior=P1 -> compatible;
- existing prior=P1, incoming prior=P2 same work -> conflict;
- existing prior=None, incoming prior=P1 -> conflict;
- existing prior=P1, incoming prior omitted -> compatible replay.

This automatically rejects self-prior on a first/root version.

## 4. Relation equality

If candidate.explicit_relation is supplied, including VersionRelation.NONE:
- candidate.explicit_relation must equal existing.relation.

Examples:
- existing relation=REVISION_OF, incoming explicit REVISION_OF -> compatible;
- existing REVISION_OF, incoming EXPLICIT_SAME_WORK -> conflict;
- existing REVISION_OF, incoming explicit NONE -> conflict;
- existing NONE, incoming explicit NONE -> compatible;
- relation omitted -> no contradiction by itself.

Do not special-case replay by trying to reinterpret PREPRINT_TO_JOURNAL source kinds.

## 5. Source kind equality

For exact replay:
candidate.source_kind must equal existing.source_kind.

Mismatch => IDENTITY_CONFLICT.

This applies even if explicit_relation is omitted.

Do not permit the same ref+fingerprint to morph from PREPRINT to JOURNAL.

## 6. Correct P2J replay semantics

Build a valid fixture:

P1:
- PREPRINT;
- work W;
- relation NONE.

J1:
- JOURNAL;
- same work W;
- relation PREPRINT_TO_JOURNAL;
- prior=P1;
- different ref/fingerprint from P1.

Then replay J1 using the same J1 ref/fingerprint and optionally explicit:
- work=W;
- prior=P1;
- relation=PREPRINT_TO_JOURNAL;
- source_kind=JOURNAL.

Required:
EXACT_REPLAY.

Replay J1 with:
- prior=P2;
- relation=REVISION_OF;
- source_kind=PREPRINT;
must conflict as appropriate.

## 7. Normalized title equality for replay

If existing.normalized_title and incoming normalized_title are both non-null:
- they must be equal.

Because normalize_title already applies:
- NFKC;
- whitespace collapse;
- casefold;

these harmless formatting differences remain replay-compatible.

Actual normalized title change => IDENTITY_CONFLICT even if DOI/stable_id match.

If incoming title is missing/empty, do not invent a contradiction solely from omission.

## 8. Keep DOI/stable behavior

Existing replay checks remain:
- both present + DOI mismatch -> conflict;
- both present + stable_id mismatch -> conflict.

Do not fuzzy-correct identifiers.

## 9. Tests

Maintain:
- knowledge_curator >= 406 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add/replace tests for at least:
1. root replay + self prior -> conflict;
2. existing prior P1 + incoming P2 same work -> conflict;
3. existing prior P1 + incoming P1 -> replay;
4. existing prior P1 + omitted prior -> replay;
5. existing REVISION_OF + explicit different relation -> conflict;
6. existing REVISION_OF + explicit REVISION_OF -> replay;
7. existing relation NONE + explicit NONE -> replay;
8. source_kind mismatch -> conflict;
9. normalized title real change -> conflict;
10. title case/whitespace/NFKC-only difference -> replay;
11. valid PREPRINT_TO_JOURNAL target replay -> replay;
12. P2J target replay with wrong prior/relation/kind -> conflict.

Remove or rewrite the old invalid self-prior "compatible replay" test.

## 10. Deliverable

Create:
results/phase-05-1-r3-executor-report.md

Report:
- replay prior equality: PASS/FAILED;
- replay relation equality: PASS/FAILED;
- replay source_kind consistency: PASS/FAILED;
- replay normalized-title consistency: PASS/FAILED;
- valid P2J target replay: PASS/FAILED;
- invalid self-prior regression removed/fixed: PASS/FAILED;
- exact tests;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 11. Completion

Update status.json:
- phase = 5.1-R3
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-1-r3-executor-report.md

Push main and STOP.
Do not start Phase 5.2.
