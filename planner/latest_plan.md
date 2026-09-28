# Phase 2.2 Plan — Final §5.4 Atomic Visibility & Versioned Read Closure

**Planner:** ChatGPT  
**Executor:** MiMo  
**State:** READY_FOR_EXECUTOR  
**Base implementation:** `3d6e49e51995eec8bff6dd9e6a467ebd61166903`

## 0. Read first

1. `docs/01-总体架构与数据流设计.md`
2. `docs/03-文献自动调研与知识入库流水线.md`
3. `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`
4. `planner/phase-02-1-review.md`
5. `planner/CONTRACT_GAPS.md`
6. `status.json`

This is the **final §5.4 closure round**. Do not start §6 or §7.

## 1. Fix structural + USDO atomic visibility

Current sequential finalization can expose one store when the other fails.

Implement one of these internal approaches:

### Preferred: explicit compensation
Both stores support:
- stage
- commit/finalize
- compensate/uncommit **only for an unpublished failed document**
- abort staged state

Coordinator behavior:
1. stage structural
2. stage USDO
3. finalize structural
4. finalize USDO
5. only then mark lifecycle `STRUCTURAL_COMMITTED`

If any failure occurs before lifecycle `STRUCTURAL_COMMITTED` is durably acknowledged:
- compensate any already-finalized structural/USDO side effects;
- abort remaining staged state;
- no committed-visible structural/USDO data may remain.

Compensation of a pre-publish failed document does **not** violate append-only published history because no KB version was ever published.

A shared internal visibility token/gate is also acceptable if it is simpler and all committed-read methods honor it.

### Required tests
- structural commit succeeds, USDO commit fails-before -> neither visible
- structural commit succeeds, USDO commit fails-after-side-effect -> neither visible
- structural commit fail-after-side-effect -> neither visible
- lifecycle `STRUCTURAL_COMMITTED` acknowledgement fails -> failed/retryable state does not leak half-visible knowledge
- successful commit exposes structural+USDO exactly once

## 2. Make snapshot creation idempotent

Use deterministic manifest `content_hash` or another stable internal idempotency key.

Required:
- same manifest retry returns/reuses the same snapshot;
- `create_snapshot` fail-after-side-effect followed by retry does not create a second snapshot;
- snapshot lookup by content hash/idempotency identity is available internally;
- no duplicate/orphan snapshot from retry windows.

Do not invent a project-wide final snapshot id format.

## 3. Allow exact retry after transient FAILED pre-publish commit

For an existing lifecycle record with:
- same `(ref_id, fingerprint)`;
- no published version;
- no irrecoverable published side effect;
- failed structural staging/finalization already compensated;

the next exact commit request should restart/resume safely rather than returning permanently FAILED.

Required:
- same commit id may be reused, or lifecycle may enter an explicit retry generation; choose the simpler internal design;
- structural/USDO/vector/version records must not duplicate;
- all request-binding validation still runs before retry.

Add tests for transient:
- structural.stage failure then exact retry;
- usdo.commit failure then exact retry;
- lifecycle structural-ack failure then exact retry.

## 4. Add a minimal version-scoped storage read view

This is **not §6 retrieval/RAG**. It is only §5.4 storage/version resolution.

Add an internal runtime-independent component such as:

```text
VersionedKnowledgeView / SnapshotResolver
```

Given:
- an explicit `version_id`, or
- the current visible version pointer,

it must resolve exactly the immutable storage dependencies of that snapshot:

- structural document record id(s);
- USDO record id(s);
- vector payload id(s);
- manifest/snapshot metadata.

If necessary, extend the internal temporary `SnapshotManifest` with stable storage identities such as:
- structural record/stage id(s);
- USDO record id(s).

These are internal temporary commit fields, not a public cross-team schema.

Add store accessors needed for exact id-based resolution.

### Required V1/V2/rollback test

Use the same `ref_id` and same `assertion_id`, but changed fingerprint/content:

```text
V1 -> publish
V2 -> publish
current = V2
rollback_to(V1)
current = V1
```

Then assert:
- current view resolves V1 structural record;
- current view resolves V1 USDO record;
- current view resolves V1 vector payload;
- none of those identities are substituted by V2;
- explicit resolve(V2) still returns V2 historical dependencies.

This is the acceptance test for rollback reproducibility.

## 5. Separate recovery statuses

Keep:
- `PENDING_VECTOR` only when vector write/replay is required.

Add an internal status such as:
- `PENDING_FINALIZE`

for:
- snapshot creation recovery;
- version publish recovery;
- lifecycle acknowledgement after publish.

The phase field should still communicate the exact state (`VECTOR_COMMITTED`, `SNAPSHOT_CREATED`, etc.).

Update existing tests accordingly.

Do not change the global confidence vocabulary.

## 6. Clean staged state

On successful structural/USDO finalization:
- remove stale staged copies;
- retain committed copies/history.

Tests should confirm no stale prepared bucket remains if the adapter exposes diagnostic counts.

## 7. Failure injection

Use the existing before/after-side-effect injection to cover the real failure windows.

Do not add tests that only fail before the side effect if the bug is specifically a post-side-effect window.

## 8. Preserve current guarantees

Keep all current behavior:

- Phase 1 confidence/conflict rules frozen;
- exact published retry is idempotent;
- version-safe vectors;
- SUPERSEDE non-active;
- deterministic assertion/manifest hashing;
- version publish idempotent;
- no public contract changes;
- CG-012/CG-013 remain documented.

## 9. Test requirements

Keep all **109** current tests green and add regression tests for all items above.

Mechanically report the real per-file counts. Note: Phase 2.1 added **24** tests in `test_phase21_persistence.py`, not 26.

## 10. DeepSeek / DSH

Do not use DeepSeek or DSH in Phase 2.2.

DeepSeek remains allowed later behind an adapter when §6 genuinely needs semantic reasoning.

## 11. Completion report

Create:

`results/phase-02-2-executor-report.md`

Include:
- atomic visibility/compensation design;
- snapshot idempotency;
- FAILED exact-retry behavior;
- version-scoped read-view design;
- V1/V2/rollback resolution proof;
- recovery status semantics;
- full test count;
- CONTRACT_GAPS;
- public contract changed? -> NO;
- implementation commit SHA.

Update `status.json`:
- phase = "2.2"
- actor = "executor"
- state = "executor_complete"
- latest_commit = actual implementation SHA
- result_expected = results/phase-02-2-executor-report.md

Stop after Phase 2.2. Do not begin §6.
