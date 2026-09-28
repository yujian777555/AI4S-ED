# Phase 2.1 Plan — Persistence, Recovery & Rollback Correctness

**Planner:** ChatGPT  
**Executor:** MiMo  
**State:** READY_FOR_EXECUTOR  
**Base implementation:** `dee9ba4a881096349a65eecb40df2544164dfd29`

## 0. Read first

1. `docs/01-总体架构与数据流设计.md`
2. `docs/03-文献自动调研与知识入库流水线.md`
3. `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`
4. `planner/phase-02-review.md`
5. `planner/CONTRACT_GAPS.md`
6. `status.json`

Phase 1 §5.1–§5.3 remains frozen.

This round only closes §5.4 persistence/recovery correctness. Do not start §6 or §7.

## 1. Separate lifecycle state from structural knowledge persistence

The current `DocumentCommitStore` is the lifecycle/idempotency store. Do not count `record.admitted` as the actual graph/assertion write.

Add an **internal temporary structural knowledge Port** (name is flexible, e.g. `StructuralKnowledgeStore`) with the minimum semantics needed for §5.4:

- stage one document's admitted assertion records + document metadata;
- commit/finalize the staged document;
- abort/discard an uncommitted stage;
- retrieve committed records for tests/audit;
- staged records must not appear in committed/downstream-visible reads.

Use an in-memory adapter only. Do not hard-code SQLite.

Do not modify the Phase 1 conflict-query semantics except where an adapter can later bridge the same production L2 backend.

## 2. Stage/commit visibility for USDO

Refactor the internal USDO Port/adapter so records can be staged and then made committed/visible with the document structural commit, or can be aborted/compensated before publish.

Required invariant:

> Before structural commit succeeds, no downstream-visible API may return the document's staged assertion/metadata/USDO payloads.

A failed pre-structural commit may retain a lifecycle/audit record, but committed knowledge reads must remain clean.

## 3. Structural commit orchestration

Required conceptual order:

```text
validate CommitRequest binding
  -> create lifecycle record
  -> build admission set
  -> stage structural assertions + metadata
  -> stage USDO
  -> finalize structural visibility as one document boundary
  -> mark STRUCTURAL_COMMITTED
  -> vector upsert
  -> snapshot
  -> idempotent version publish
```

If any failure occurs before structural visibility finalization:
- abort staged structural/USDO state;
- no committed structural knowledge;
- no snapshot/version.

You may implement a small internal transaction token/stage id; do not invent a project-wide public API.

## 4. Strong CommitRequest integrity validation

Before creating any staged data, validate deterministically:

- source fingerprint is non-empty;
- `source.ref_id == assertion_set.ref_id == report.source_ref_id`;
- assertion ids in the AssertionSet are unique;
- decision ids in the report are unique;
- exactly one decision exists for every assertion in the AssertionSet;
- no decision references an assertion outside the AssertionSet.

On failure:
- fail closed;
- no commit record that looks publishable;
- no structural/USDO/vector/snapshot/version side effects.

Add explicit regression tests for each mismatch class.

## 5. Version-safe vector identities

Vector ids must be immutable per committed document version/content.

Do not use only:
`ref_id + assertion_id`.

Include a stable version discriminator such as:
- source fingerprint,
- commit content hash,
- assertion content hash,
or a combination.

Requirements:
- same exact retry reuses the same vector ids;
- same ref_id + different fingerprint does not overwrite old vectors;
- older snapshot vector ids remain resolvable after newer versions publish.

Extend the in-memory vector adapter with the minimum read method needed to assert the stored payload by id.

## 6. Idempotent version publication

Make `publish_version` idempotent for the same snapshot/document commit.

Recommended internal semantics:
- a snapshot can map to at most one published version;
- repeated publish for the same snapshot returns the existing version;
- version publication can accept an internal idempotency key if needed.

Handle failures explicitly:
- snapshot creation failure should remain resumable at the appropriate pre-snapshot state; do not relabel it as a vector failure unless vector is actually missing;
- publish failure should leave `SNAPSHOT_CREATED` resumable;
- retry must not create duplicate versions.

Add deterministic failure tests for:
1. publish operation fails before side effect;
2. publish side effect succeeds but lifecycle acknowledgement/update fails;
3. retry returns/uses exactly the original version.

To test post-side-effect failures, improve `FailureInjection` if necessary (e.g. fail-on-nth-call or explicit after-side-effect hook). Do not rely on mutable object aliasing.

## 7. In-memory persistence semantics must model real boundaries

`InMemoryDocumentCommitStore` currently stores mutable record objects by reference.

That can make a local mutation appear "persisted" even if `update()` fails, which weakens failure tests.

Use copy-on-write/deep-copy semantics at the store boundary so:
- `create/update` persists a copy;
- `find_by_key` returns a safe copy;
- a failed update does not magically mutate the persisted record.

Tests must demonstrate this.

## 8. SUPERSEDE safety

Do not persist `CurationAction.SUPERSEDE` as ACTIVE.

Until CG-008 is frozen:
- retain it in a non-active historical/superseded visibility, or fail it closed from the active surface;
- preserve auditability;
- do not physically delete it.

This is an internal visibility rule, not a new public confidence value.

## 9. Snapshot hash completeness

Keep the manifest deterministic, but make the assertion record hash cover all stable scientific fields that materially define the committed assertion, including at least:

- subject canonical id and relevant stable subject fields;
- property;
- object value/unit/value_type/**uncertainty**;
- conditions;
- provenance locator and stable sentence/cell pointer if present;
- claim type;
- source claim origin;
- assertion quality if it is part of the persisted assertion record.

Decision confidence/visibility/action may remain in decision hashes.

Exclude ephemeral runtime fields.

Add a test showing a change in uncertainty or stable provenance changes the manifest content hash.

## 10. Required regression tests

Keep all existing **85** tests green and add tests for:

### Structural persistence
- successful publish has committed structural assertions/metadata in the structural store;
- lifecycle record alone is not used as proof of structural persistence;
- failed pre-structural stage leaves no committed structural data.

### USDO visibility
- staged USDO not visible before commit;
- failure after USDO staging aborts/hides it;
- successful structural commit exposes it exactly once.

### Request binding
- ref_id mismatch fails closed;
- empty fingerprint fails closed;
- missing decision fails closed;
- extra/foreign decision fails closed;
- duplicate assertion/decision ids fail closed.

### Vector immutability/versioning
- V1 and V2 same ref_id + same assertion id + changed content have distinct vector ids;
- both vector payloads remain retrievable;
- V1 snapshot still references V1 vector after V2 publish.

### Publish failure window
- publish failure returns a recoverable result/state;
- retry publishes once;
- simulated publish-success/lifecycle-update-failure does not create a second version on retry.

### Store copy semantics
- mutating a fetched lifecycle record without successful `update()` does not change persisted state.

### Supersede
- SUPERSEDE is never ACTIVE.

### Manifest
- stable assertion-field change (e.g. uncertainty) changes manifest hash.

### Rollback
- after V1/V2 publish, rollback to V1 leaves V2 historical and V1 snapshot dependencies resolvable.

## 11. CG-012 / CG-013

Keep both unless an architecture owner changes them.

Do not create a new CONTRACT_GAP merely for an implementation bug fixed in this round.

If a genuinely new cross-team ambiguity is discovered, document it.

## 12. DeepSeek / DSH

DeepSeek API remains approved for future reasoning behind an adapter.

**Do not use DeepSeek or DSH in Phase 2.1.**

## 13. Completion report

Create:

`results/phase-02-1-executor-report.md`

Include:
- exact persistence model;
- structural/USDO stage-commit-abort behavior;
- vector identity format;
- version publish idempotency;
- failure-window behavior;
- request-binding validation;
- snapshot hash coverage;
- test totals;
- CONTRACT_GAPS changes;
- whether public contracts changed (must be NO);
- implementation commit SHA.

Update `status.json`:
- phase = "2.1"
- actor = "executor"
- state = "executor_complete"
- latest_commit = actual implementation SHA
- result_expected = results/phase-02-1-executor-report.md

Stop after Phase 2.1. Do not begin §6.
