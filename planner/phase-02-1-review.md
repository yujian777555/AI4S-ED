# Phase 2.1 Planner Review — Persistence/Recovery Closure

**Reviewed implementation:** `3d6e49e51995eec8bff6dd9e6a467ebd61166903`  
**Remote bookkeeping tip:** `1b4aab63571b4ddcce0fe7e7f3806788d0162458`  
**Executor-reported tests:** 109 passed / 0 failed  
**Planner mechanical test count:** 109  
**Verdict:** **MOSTLY PASSED — Phase 2.2 final §5.4 closure required**

## Confirmed fixes

The Phase 2.1 blockers were substantially fixed:

- lifecycle state is separated from structural knowledge persistence;
- structural and USDO stores now have staged vs committed concepts;
- vector identities are version-safe and V1/V2 no longer overwrite one another;
- version publication is idempotent per snapshot;
- request/report/assertion binding is validated fail-closed;
- lifecycle store uses copy-on-write semantics;
- SUPERSEDE is not exposed as ACTIVE;
- stable assertion hashing now includes uncertainty/provenance/quality fields;
- publish-after-side-effect/lifecycle-ack failure is covered;
- V1 vector dependencies remain addressable after V2.

The 109 total is correct. The executor report has a documentation typo: `test_phase21_persistence.py` contains **24** tests, not 26. 85 + 24 = 109.

## Remaining blocking issues

### P2.2-01 — structural + USDO finalization is still not atomic/reversible as a pair

The coordinator currently executes:

```text
structural.commit_stage(commit_id)
usdo.commit_stage(commit_id)
```

sequentially.

If the structural commit side effect succeeds and the USDO commit then fails, the exception handler calls `abort_stage()`, but `abort_stage()` only removes staged data. It does not remove already-committed structural data.

Likewise, a fail-after-side-effect on either store can leave committed-visible payloads while the lifecycle record is marked FAILED.

This violates the intended document-level atomic visibility.

**Required:** pre-publish committed side effects must be compensatable/reversible, or both stores must share one visibility gate. A failed document must not leave structural or USDO data exposed as committed knowledge.

This does not require pretending cross-store ACID. Explicit compensation/visibility gating is acceptable and consistent with CG-013.

### P2.2-02 — snapshot creation is not idempotent across post-side-effect failures

`create_snapshot()` always creates a new snapshot id.

If snapshot creation succeeds internally and then raises (fail-after-side-effect), the lifecycle record still has no snapshot id. Retry creates a second snapshot, leaving an orphan first snapshot.

**Required:** snapshot creation must be idempotent for the same deterministic manifest/content hash, or recoverable by manifest identity. Retry must reuse the existing snapshot.

### P2.2-03 — a transient pre-structural failure permanently blocks the exact same idempotency key

A failed lifecycle record remains stored under `(ref_id, fingerprint)`. On exact retry, `_resume_existing()` treats FAILED as not resumable.

A temporary stage/commit failure therefore requires a changed fingerprint even though the document content did not change.

**Required:** a FAILED pre-publish commit with no published version must be safely restartable for the exact same idempotency key, after staged/committed partial effects have been cleaned or verified absent.

### P2.2-04 — rollback changes only the version pointer; there is no version-scoped knowledge read view

The current `rollback_to(V1)` changes `VersionStore.current_version`, and old vectors remain addressable, but:

- structural store reads return all committed records for a ref;
- USDO reads return all committed records for a ref;
- the snapshot manifest does not expose a complete immutable dependency resolver to reconstruct the currently visible knowledge bundle.

Before §6 retrieval is built, §5.4 should provide a minimal **version-scoped storage read view**, not a QA/retrieval implementation.

**Required:** given a version (or current version), resolve exactly the structural record(s), USDO record(s), and vector payload ids referenced by that snapshot. After rollback V2 -> V1, resolving the current view must return V1 dependencies, while V2 remains historically resolvable by explicit version id.

## Hardening in the same round

### H2.2-01 — distinguish vector-pending from finalize/publish-pending

Snapshot/publish failures currently use `CommitStatus.PENDING_VECTOR` even when vectors are already committed.

That status will be misleading to future orchestration/watchdog logic.

Use an internal status such as `PENDING_FINALIZE` / `RECOVERABLE` for snapshot/version/lifecycle-ack recovery. Keep `PENDING_VECTOR` only for actual vector-write recovery.

This is an internal temporary commit status, not a project-wide confidence/schema change.

### H2.2-02 — committed stage cleanup

Successful `commit_stage()` should not leave stale staged copies indefinitely unless intentionally documented. Clean prepared state after successful finalization, while retaining committed/history state.

## Contract gaps

CG-012 and CG-013 remain valid. No new cross-team gap is required for the implementation issues above.

## Exit criteria

Phase 2.2 passes when:

- structural + USDO partial finalization cannot leave a failed document visible;
- fail-after-side-effect cases are tested;
- snapshot retry cannot create duplicate/orphan snapshots for identical manifest content;
- exact same fingerprint can retry after a transient FAILED pre-publish attempt;
- current-version resolution after V1 -> V2 -> rollback V1 returns V1 structural/USDO/vector dependencies;
- historical V2 remains explicitly resolvable;
- vector and finalize pending states are semantically distinct;
- all existing 109 tests remain green;
- no §6/§7 implementation is started.

After this round, Planner will freeze §5.1–§5.4.
