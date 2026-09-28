# Phase 2 Planner Review — §5.4 Atomic Ingest

**Reviewed implementation:** `dee9ba4a881096349a65eecb40df2544164dfd29`  
**Remote bookkeeping tip:** `cd8b93615de70e1eb856039962ac5300a2c43b21`  
**Executor-reported tests:** 85 passed / 0 failed  
**Planner mechanical test count:** 85  
**Verdict:** **MOSTLY PASSED — Phase 2.1 persistence/recovery closure required before §6**

## What is accepted

- The overall atomic-visibility state machine is appropriate.
- Exact-retry idempotency for the same `(ref_id, source_fingerprint)` is a safe interpretation; CG-012 correctly records the source wording ambiguity.
- CG-013 correctly records that cross SQLite/FAISS/filesystem ACID cannot be assumed.
- Vector failure after structural progress enters a recoverable state and does not publish a KB version.
- Snapshot manifests are deterministic with respect to the fields currently included.
- Version history and visible-pointer rollback scaffolding exist.
- Phase 1 §5.1–§5.3 semantics remain unchanged.
- No §6/§7/DeepSeek/DSH scope leakage occurred.

No rewrite is required.

## Blocking implementation issues

### P2.1-01 — admitted assertions are not actually persisted to a queryable structural knowledge store

The current coordinator stores admitted assertions inside `DocumentCommitRecord.admitted`, but does not write them into a structural knowledge/graph store used by the knowledge layer.

`count_structural_assertions()` currently counts the list inside the lifecycle record; it is not proof that the curated assertions were committed into the L2 structural knowledge surface.

03 §5.4 requires the document commit unit to include graph/assertion data + metadata + USDO registration.

**Required:** add an internal structural-write Port/Adapter (or a clean extension of an existing internal Port) that explicitly stages/commits the admitted assertion records and document metadata. Keep it runtime-independent and mark it as an internal temporary L2 boundary.

The lifecycle store must remain lifecycle/idempotency state, not silently stand in for the graph/assertion store.

### P2.1-02 — pre-structural rollback/visibility is not modeled strongly enough

`USDOStore.register()` immediately exposes records via `list_for_ref()`. There is no stage/commit/abort or compensation operation.

A failure after USDO registration but before the structural commit lifecycle update could leave a visible USDO record while the document commit is failed.

The in-memory failure injection currently checks before the register write, so the green test does not cover this failure window.

**Required:** model staged vs committed visibility (preferred) or explicit compensation for structural assertion/metadata/USDO writes. Before structural commit succeeds, downstream-visible reads must not expose the staged document.

Failed staging may leave an internal audit/lifecycle record, but not committed knowledge payloads.

### P2.1-03 — version publication is not idempotent across the publish/update failure window

`VersionStore.publish_version(snapshot_id)` creates a new version every call.

If real production `publish_version()` succeeds but the subsequent lifecycle-store update fails, a retry can publish a second KB version for the same snapshot/commit.

Also, `version.publish` exceptions are not currently converted into a recoverable commit result.

**Required:**
- make version publication idempotent by snapshot/commit idempotency identity;
- retrying the same snapshot must return the already-created version;
- publish failure should leave the record in a resumable state (for example `SNAPSHOT_CREATED`) rather than corrupting the lifecycle;
- add failure-injection coverage for the window after version publication but before lifecycle acknowledgement.

### P2.1-04 — vector identity is not version-safe, so rollback is not reproducible

Current vector id:

`vec-{ref_id}-{assertion.id}`

For the same ref_id with a new fingerprint/version and the same assertion id, a later upsert overwrites the prior vector payload.

The old snapshot still references the same vector id, but the vector now contains the newer version's payload/hash. A rollback that only switches the KB version pointer therefore cannot reproduce the old vector state.

**Required:** make vector identities immutable/version-aware, using fingerprint/content-hash/commit identity. A new document version must not overwrite vectors referenced by an older snapshot.

Tests must demonstrate:
- V1 and V2 with same ref_id/assertion id but changed content retain distinct vector ids/payloads;
- V1 snapshot still resolves to V1 vector payload after V2 publish;
- rollback to V1 does not depend on overwritten V2 vector state.

### P2.1-05 — CommitRequest is not strongly bound to the CurationReport it claims to persist

The coordinator does not verify that:

- `request.source.ref_id == request.assertion_set.ref_id == report.source_ref_id`;
- source fingerprint is non-empty;
- report decision ids match the AssertionSet ids exactly (one decision per assertion);
- no duplicate assertion/decision ids exist.

A mismatched report could therefore authorize/publish the wrong AssertionSet or produce a published version with an incomplete admission set.

**Required:** add deterministic pre-commit integrity validation before creating the commit record. Invalid binding must fail closed with no staged/published knowledge.

## Hardening required in the same narrow round

### H2.1-01 — do not treat SUPERSEDE as active

Current code falls through so `SUPERSEDE` is persisted as `ACTIVE`.

03 §5.2 says the losing assertion is retained historically and marked `superseded`, not kept as an active fact.

Until CG-008 truth-adjudication semantics are frozen, persist SUPERSEDE as an explicitly non-active/historical visibility or reject it from the active surface. Do not silently treat it as ACCEPT.

### H2.1-02 — snapshot assertion hash should cover the actual stable assertion record

The current assertion hash omits stable scientific fields such as uncertainty (and some provenance/quality content). A snapshot manifest intended for audit/reproduction should change when the committed assertion record changes.

Include the stable fields that materially define the assertion record while continuing to exclude ephemeral fields.

## Notes on CG-012 / CG-013

Both are legitimate contract gaps and should remain documented.

- **CG-012:** keep exact-retry idempotency for this implementation unless architecture owners explicitly choose version bump on identical fingerprint.
- **CG-013:** keep atomic visibility/compensation; do not claim cross-store ACID.

These gaps do not justify the blockers above; the blockers can be fixed inside the current internal Port/Adapter design.

## Exit criteria

Phase 2.1 passes only if:
- P2.1-01 through P2.1-05 are fixed;
- H2.1-01/H2.1-02 are covered;
- all existing 85 tests remain green;
- failure tests cover realistic post-side-effect windows;
- old snapshot data remains addressable after a newer version;
- no public cross-team contract is declared/frozen;
- no §6/§7 implementation is started.

After Phase 2.1 passes, §5 curation + ingest can be frozen and Planner can move to §6.
