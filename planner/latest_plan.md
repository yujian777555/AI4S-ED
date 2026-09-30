# Phase 5.3-R2 Plan — Final Publication Material Lock

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Close the final publication-material consistency gaps documented in:
planner/phase-05-3-r1-review.md

This is a narrow final correction.
Do not add features.
Do not create Phase 5.4.

## 1. Freeze everything else

Do not redesign:
- async publication API;
- approval model;
- publication journal;
- DocumentCommitCoordinator;
- LifecycleRevisionCoordinator;
- SourceVersionRegistry;
- Phase 5.2 delta/package logic;
- DSH/MCP.

## 2. Typed canonical scientific values

Add one deterministic helper for arbitrary scientific values.

Recommended:
canonical_value(value)

Rules:
- None/bool/int/float/str remain their native JSON primitive type;
- list -> recursively canonicalized list;
- tuple -> explicit typed representation, e.g. {"__type__":"tuple","items":[...]};
- dict -> recursively canonicalized mapping with deterministic key ordering;
- Enum -> explicit value/type representation if needed;
- non-JSON exotic objects -> explicit typed fallback:
  {"__type__": fully-qualified/class name, "repr": deterministic representation}
  rather than plain str alone.

Do not collapse different primitive types.

Use this helper for:
- Assertion.object.value;
- Assertion.object.uncertainty if structured;
- Condition.value;
- any nested scientific payload included in canonical_assertion_material.

## 3. Canonical assertion material

Update canonical_assertion_material so package/request equality is truly material-exact.

Conditions should preserve:
- eddo_class;
- canonical typed value;
- unit.

Sort conditions deterministically by canonical JSON, not by str(value).

Regression:
- Condition(value=1) vs Condition(value="1") => different material;
- Condition(value=[1,2]) vs Condition(value="[1, 2]") => different;
- same dict with different insertion order => same canonical material;
- nested dict/list exact replay => same.

## 4. Expected decision material from CommitRequest

Build a deterministic map:
assertion_id -> expected publication admission

For Phase 5.3 allowed actions:

ACCEPT:
- action = ACCEPT;
- confidence = decision.confidence;
- visibility = ACTIVE.

DOWNGRADE:
- action = DOWNGRADE;
- confidence = decision.confidence;
- visibility = DOWNGRADED.

No other actions are allowed by the curation gate.

Use request.report as the source of truth.

## 5. Existing target commit guard signature

Change guard to accept the validated CommitRequest, not only package/ref/fingerprint.

Recommended:
_existing_commit_guard(package, request)

Read existing commit by:
request.source.ref_id,
request.source.source_fingerprint.

If no existing record:
- return no conflict.

If existing record exists:
- fail closed on store error;
- compare exact material below.

## 6. Existing admitted assertion material

For every existing AdmittedAssertion require:
- exact assertion ID set == package target ID set;
- canonical assertion material == package/request assertion material;
- item.action == expected decision action;
- item.confidence == expected decision confidence;
- item.visibility == expected visibility.

Any mismatch => CONFLICT.

Regression:
same assertion/value but existing ACCEPT vs new DOWNGRADE => CONFLICT.
same action but changed decision confidence => CONFLICT.
same assertion but wrong visibility => CONFLICT.

## 7. Metadata hash guard

Compute expected metadata hash using exactly the frozen commit fields:

{
  "title": metadata.title,
  "authors": list(metadata.authors),
  "year": metadata.year,
  "source": metadata.source,
  "doi": metadata.doi,
  "stable_id": metadata.stable_id
}

Use the same canonical JSON + SHA256 semantics as DocumentCommitCoordinator.

If existing.metadata_hash is non-empty:
- require existing.metadata_hash == expected.

If existing.manifest exists:
- require existing.manifest.metadata_hash == expected.

Mismatch => CONFLICT.

Add test:
same ref/fingerprint/assertions but year/authors/source changed -> existing commit conflict.

## 8. Existing published manifest guard

When existing.phase == PUBLISHED or version_id is present, validate if available:
- existing.manifest is not None;
- manifest.ref_id == request.source.ref_id;
- manifest.source_fingerprint == request.source.source_fingerprint;
- manifest.metadata_hash == expected metadata hash;
- manifest assertion hashes correspond to existing admitted assertions using frozen commit assertion hash semantics;
- decision_hashes correspond to existing admitted action/confidence/visibility material.

Do not mutate frozen CommitCoordinator.
A small shared/local deterministic helper duplicating its frozen hashing contract is acceptable; document that it mirrors Phase 2 stable material.

## 9. Post-target result/store agreement

After await commit returns PUBLISHED or IDEMPOTENT_HIT:

Read DocumentCommitStore again.

Require:
- record exists;
- record.phase == PUBLISHED;
- record.version_id == result.version_id;
- record.snapshot_id == result.snapshot_id;
- record.manifest exists;
- record.manifest.content_hash == resolved snapshot.manifest.content_hash;
- record.manifest.ref_id/fingerprint == resolved target snapshot manifest;
- record metadata/decision/admitted material still matches request.

Any disagreement => CONFLICT/FAILED before lifecycle.

Do not continue on an unreadable commit store.

## 10. Approval scope/material use same typed canonical helper

Ensure compute_publication_scope_hash uses the corrected canonical_assertion_material.

Regression:
same assertion ID, condition int 1 -> string "1" changes scope hash.

Changing nested scientific condition dict/list changes scope.
Dict insertion-order-only change does not change scope.

## 11. First-run vs replay result semantics

Track whether this invocation:
- created a new publication journal and completed the saga now;
versus
- replayed/resumed existing side effects.

Final result:
- first fresh happy path: idempotent=False, resumed=False;
- exact finalized replay: idempotent=True;
- crash recovery path: resumed=True and idempotent=True where appropriate.

Do not alter persistence semantics solely for this cosmetic result field.

## 12. Tests

Maintain:
- knowledge_curator >= 489 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add at least:

1. condition int vs string material differs;
2. list vs string material differs;
3. dict insertion order canonicalizes equally;
4. nested condition change changes approval scope;
5. existing ACCEPT vs requested DOWNGRADE => CONFLICT;
6. existing decision confidence mismatch => CONFLICT;
7. existing visibility mismatch => CONFLICT;
8. existing metadata_hash mismatch => CONFLICT;
9. existing manifest metadata mismatch => CONFLICT;
10. post-commit store version mismatch => fail closed;
11. post-commit store snapshot mismatch => fail closed;
12. post-commit store missing/unreadable => fail closed;
13. real P2J E2E still FINALIZED;
14. fresh E2E reports idempotent=False;
15. exact replay reports idempotent=True;
16. post-bind journal recovery still passes.

## 13. Deliverable

Create:
results/phase-05-3-r2-executor-report.md

Report exactly:

Phase 5.3-R2 implementation CODE SHA:

typed canonical scientific material:
PASS / FAILED

existing decision/action/confidence/visibility guard:
PASS / FAILED

existing metadata/manifest guard:
PASS / FAILED

post-target commit-store agreement:
PASS / FAILED

approval scope typed-material lock:
PASS / FAILED

fresh-vs-replay result semantics:
PASS / FAILED

real P2J E2E:
PASS / FAILED

post-bind recovery:
PASS / FAILED

integration tests:
X passed / 0 failed

knowledge_curator tests:
X passed / Y skipped / 0 failed

public contracts changed:
NO

origin/main SHA:

新增/修改 CONTRACT_GAPS:
YES / NO

## 14. Completion

Update status.json:
- phase = 5.3-R2
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-3-r2-executor-report.md

Push main and STOP.

Do not create Phase 5.4.
Planner will immediately perform final freeze after this review.
