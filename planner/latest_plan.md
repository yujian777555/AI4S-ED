# Phase 2 Plan — §5.4 Atomic Ingest & KB Version Snapshot

**Planner:** ChatGPT  
**Executor:** MiMo  
**State:** READY_FOR_EXECUTOR  
**Accepted baseline:** `e88eabad1b42304d2a9ebade6308c9eb16c24573`

## 0. Read first

1. `docs/01-总体架构与数据流设计.md`
2. `docs/03-文献自动调研与知识入库流水线.md`
3. `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`
4. `planner/phase-01-2-review.md`
5. `planner/CONTRACT_GAPS.md`
6. `status.json`

Phase 1 §5.1–§5.3 behavior is frozen. Do not rewrite it while implementing §5.4.

## 1. Scope

Implement only the `knowledge_curator` side of **03 §5.4 原子入库与版本快照**.

Required document semantics:

- transaction boundary = one document;
- structural knowledge write + metadata + USDO registration form one document commit unit;
- vector upsert participates through staged/two-phase/compensation semantics;
- vector failure must be recoverable through `pending_vector` replay;
- idempotency key = `(ref_id, source_fingerprint)`;
- successful publish creates a KB version and snapshot with content-hash manifest;
- downstream must see only fully committed/published versions;
- rollback must restore a previously committed snapshot;
- do not physically delete historical versions.

Do **not** implement §6 retrieval/QA or §7 update governance in this phase.

## 2. Architecture rule

Production L2 APIs are still unfrozen, so do not hard-code SQLite/FAISS/filesystem.

Extend internal Ports/Adapters only as needed.

Recommended internal structure (names may vary slightly):

```text
knowledge_curator/
├── core/
│   ├── curator.py
│   └── commit.py              # document commit orchestration
├── schemas/
│   └── commit.py              # internal temporary commit models
├── ports/
│   ├── knowledge_repository.py
│   ├── vector_index.py
│   ├── usdo_store.py
│   └── version_store.py
├── adapters/
│   ├── in_memory_repository.py
│   ├── in_memory_vector_index.py
│   ├── in_memory_usdo_store.py
│   └── in_memory_version_store.py
└── tests/
    └── test_atomic_commit.py
```

Do not claim these internal Ports are the final cross-team L2 contract.

## 3. Commit input

The commit stage must consume the existing curated result rather than rerunning or bypassing §5.1–§5.3.

A commit request should contain enough information to bind:

- source `ref_id`;
- source fingerprint/hash;
- original/curated document identity;
- `CurationReport`;
- assertions and payloads required for this document;
- trace/provenance identifiers when available.

Do not invent a new public AssertionSet.

## 4. Eligibility rules

The commit coordinator must not blindly persist everything as an active fact.

At minimum:

- `RETURN_UPSTREAM` -> not publishable;
- all-rejected document -> not publishable;
- `ACCEPT` assertions -> eligible for normal persisted knowledge state;
- `DOWNGRADE` assertions may be persisted with their downgraded confidence/status, but must not be promoted;
- `PENDING_REVIEW` may be persisted as pending/auditable state, but must not be exposed as committed high/verified fact;
- `REJECT` assertions are not admitted to the active knowledge face.

Keep lifecycle/visibility metadata internal if the shared schema is not frozen.

Do not redesign §6 filtering in this phase.

## 5. Atomic visibility model

Because vector storage is not a relational transaction, implement **atomic visibility**, not fake cross-store ACID.

Required state progression:

```text
PREPARING
  -> STRUCTURAL_STAGED
  -> STRUCTURAL_COMMITTED
  -> VECTOR_PENDING / VECTOR_COMMITTED
  -> SNAPSHOT_CREATED
  -> PUBLISHED
```

Safe semantics:

### Before structural commit
Any failure:
- rollback staged structural metadata/assertion/USDO writes;
- no KB version published;
- no snapshot published.

### Vector failure after structural commit
- retain recoverable structural state;
- mark document commit `pending_vector`;
- do **not** expose a new published KB version to downstream;
- replay must retry vector work without duplicating structural records.

### Vector replay success
- clear `pending_vector`;
- create/finalize snapshot;
- publish exactly one KB version for the document commit.

This reconciles §5.4's rollback discipline with its explicit `pending_vector` replay rule without pretending FAISS can participate in SQLite ACID.

## 6. Idempotency

Use `(ref_id, source_fingerprint)` as the idempotency key.

Required behavior:

- a retry of the same in-progress `pending_vector` commit resumes/replays instead of duplicating structural records;
- a retry of an already published exact same fingerprint returns the existing committed result and must not duplicate assertions/vectors/snapshots;
- same `ref_id` with a **different fingerprint** is treated as a new source version and may produce a new KB version.

If the wording "重复提交仅做 merge/version bump" in §5.4 creates ambiguity for exact same fingerprint, record it in CONTRACT_GAPS rather than silently producing duplicate versions. For Phase 2, prefer safe exact-retry idempotency (no duplicate publish).

## 7. Content-hash manifest

A snapshot must contain a deterministic manifest of committed content, sufficient to audit/reproduce the document commit.

At minimum include stable hashes/identifiers for:
- source fingerprint;
- admitted assertion records;
- USDO/payload registration records;
- vector payload identities;
- metadata record;
- relevant curation report identity.

Do not hash ephemeral fields such as random report-generation timestamps unless intentionally part of the content identity.

Tests must prove identical content produces identical manifest hashes.

## 8. KB version

Do not invent a project-wide final version format.

The VersionStore Port may issue an opaque version id.

Requirements:
- exactly one version published per successful document commit;
- pending/failed commit is not listed as published;
- each published version points to its snapshot/manifest and prior committed version when available;
- downstream-facing read method returns only published versions.

## 9. Rollback

Implement rollback semantics in the in-memory adapter:

- rollback target must be an existing published snapshot/version;
- rollback changes the current visible KB version pointer;
- historical later snapshots remain retained/auditable;
- rollback must not physically delete versions or assertions;
- invalid/nonexistent rollback target fails explicitly.

Do not implement §7 revision workflows yet; this is only §5.4 snapshot rollback mechanics.

## 10. Failure injection

In-memory/fake adapters must support deterministic failure injection so tests can verify:

- structural write failure;
- USDO registration failure before publish;
- vector upsert failure;
- snapshot creation/finalization failure if modeled.

A failure must leave states consistent with §5.4 recovery semantics.

## 11. Integration with KnowledgeCurator

Do not automatically commit inside every `curate()` call unless doing so preserves the current API and tests cleanly.

Preferred separation:

```python
report = await curator.curate(assertion_set)
commit_result = await commit_coordinator.commit(assertion_set, report, source_fingerprint=...)
```

or a thin explicit `curate_and_commit` convenience method that composes the two.

The deterministic curation step must remain independently testable.

## 12. Required tests

Keep all current **68** tests green and add at least these:

### A. Success
- valid curated document commits and publishes one version;
- returned result has non-empty commit/snapshot/version identifiers;
- snapshot manifest is deterministic.

### B. Pre-publish rollback
- structural failure leaves no published version;
- USDO failure before structural finalization leaves no published version.

### C. Vector compensation
- vector failure -> `pending_vector`;
- no new published KB version while pending;
- retry succeeds;
- retry creates exactly one version;
- structural assertions are not duplicated.

### D. Idempotency
- exact same `(ref_id,fingerprint)` after publish returns existing result;
- no duplicate assertion/vector/snapshot/version;
- same ref_id + changed fingerprint can create a new version.

### E. Eligibility
- return_upstream report cannot publish;
- rejected assertions are not active facts;
- pending_review does not become high/verified through commit;
- downgrade keeps downgraded confidence.

### F. Rollback
- publish V1 then V2;
- rollback current pointer to V1;
- V2 remains historically present;
- nonexistent target fails explicitly.

### G. Boundaries
- no SQLite/FAISS/DeepSeek/DSH imports in the Phase 2 core;
- no §6/§7 implementation added.

## 13. DeepSeek policy

DeepSeek API is still approved as a temporary future LLM backend.

**Phase 2 does not require DeepSeek. Do not add network calls or API credentials.**

## 14. Report

Create:

`results/phase-02-executor-report.md`

Include:
- files changed;
- state machine implemented;
- idempotency behavior;
- failure/recovery behavior;
- snapshot/version/rollback behavior;
- complete test command and counts;
- CONTRACT_GAPS changes;
- whether public contracts changed (must be NO);
- implementation commit SHA.

Update `status.json`:
- phase = 2
- actor = executor
- state = executor_complete
- latest_commit = actual implementation SHA
- result_expected = results/phase-02-executor-report.md

Stop after Phase 2. Do not begin §6.
