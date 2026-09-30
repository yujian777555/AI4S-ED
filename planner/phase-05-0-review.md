# Phase 5.0 Planner Review — REVISE before §7 freeze

Implementation CODE SHA: `3449a410bf4103ee0aeb37c2f582f288518aef9e`  
Bookkeeping origin/main at review start: `76afb6396845b1e8b9527921b60d91832c2b4867`

Verdict: **REVISE / Phase 5.0 not frozen yet**

The implementation is substantial and most of the lifecycle model is aligned with docs/03 §7, but the current tests miss several failure/retrieval paths that are explicit Phase 5.0 acceptance requirements.

## Accepted parts

The following design pieces are directionally accepted and should not be rewritten without need:

- lifecycle enums / draft / risk-gate separation;
- retraction as RETRACTED + assertion ARCHIVED without physical deletion;
- corrigendum archive/supersede model;
- version-scoped lifecycle visibility ancestry model;
- backward-compatible SnapshotManifest lifecycle fields;
- retrieval/training eligibility abstraction;
- internal CG-018 outbox boundary only;
- no external event-bus selection;
- no public MCP mutation tool;
- no new CONTRACT_GAP required for the defects below.

Reported regression counts are noted:
- integration/dsh: 90 passed;
- knowledge_curator: 329 passed.

These are executor-local results; the review below is based on committed source/tests.

## BLOCKER 1 — staged lifecycle retry can become permanently stuck

`apply_retraction()` / `apply_revision()` return immediately whenever the deterministic lifecycle record already exists.

That is correct only for a fully finalized lifecycle revision.

It is not correct for a staged record whose `effective_version_id is None`.

Current failure path:

1. append staged lifecycle records;
2. create snapshot and/or publish version;
3. injected failure occurs before bind/finalize;
4. staged record remains;
5. retry sees existing lifecycle ID and returns `idempotent_hit=True`;
6. publication/binding/events are never completed.

The worst case is `fail_after("version.publish")`: VersionStore has already advanced current version, while lifecycle records remain unbound and therefore invisible. Retry then returns early and cannot heal the state.

This violates the frozen requirements:
- no current version pointer advanced without corresponding lifecycle visibility;
- retry after side effect must be idempotent and recoverable;
- failure before/after side effects must be tested.

### Required repair

Existing lifecycle ID must distinguish:

- finalized: bound to a published version and required events complete -> idempotent return;
- staged/unbound: resume deterministic snapshot/version/bind/outbox finalization;
- conflicting material content for the same revision/lifecycle ID -> fail closed.

Use deterministic manifest hash + existing VersionStore lookup APIs to resume rather than create duplicates.

Add failure-recovery tests for at least:
- failure before `version.create_snapshot`;
- failure after `version.create_snapshot`;
- failure before `version.publish`;
- failure after `version.publish`;
- failure after version bind but before all required outbox events are present.

Each case must prove a retry converges to exactly one published version, one bound lifecycle revision, complete idempotent events, and correct current visibility.

## BLOCKER 2 — lifecycle retrieval filtering can under-fill after backend top-k

When `EvidenceRequest.allowed_ref_ids is None`, `_EligibilityFilteredPort.search()` currently:

1. calls the inner backend search at the requested top-k;
2. drops lifecycle-ineligible candidates from the returned list.

This is precisely the failure mode forbidden by Phase 5.0: retrieving backend top-k first and then dropping retracted hits can hide eligible results immediately below the cutoff.

The existing test uses top_k=5 over only four chunks, so it cannot detect this.

### Required repair

Lifecycle eligibility must be applied before the effective retrieval cutoff, or the adapter must deterministically expand/re-query until it can return the requested number of eligible candidates (or prove backend exhaustion).

Add a regression such as:
- request top_k=1;
- backend rank #1 = retracted REF-A;
- backend rank #2 = eligible REF-B;
- final retrieval must contain REF-B, not an empty/under-filled result caused by dropping REF-A after top-k.

Do not change frozen RRF/reranker semantics.

## BLOCKER 3 — historical retrieval is not actually integrated

The current Phase 5.0 test constructs `svc_hist` but never retrieves through it. It only calls:

`vis.document_eligibility(..., at_version_id=v1)`

directly.

Also, `EvidenceRetrievalService` currently has no effective way to pass an explicit historical `at_version_id` into lifecycle filtering.

Therefore the required behavior:

> historical-version retrieval explicitly configured -> pre-retraction evidence can appear

is not yet proven end-to-end.

### Required repair

Add an INTERNAL version selection path for retrieval, either on the service configuration or request model.

Then add an actual retrieval regression:

- current/V2 retraction -> REF-A excluded;
- explicit historical V1 retrieval -> REF-A returned when ranking would select it.

Do not create a new public MCP contract for this.

## BLOCKER 4 — idempotency conflict checks are too weak

`InMemoryEventOutbox.append()` treats the same `event_id` as idempotent when only `event_type` and `ref_id` match.

So the same event ID with different:
- affected assertion IDs;
- old/new version IDs;
- lifecycle/revision IDs;
- trace/provenance IDs;
- payload

can be silently accepted.

Likewise, document/assertion lifecycle replay compatibility ignores material fields such as evidence/rationale/source fingerprint and other revision identity metadata.

This violates the requirement that same ID + different material content fails closed.

### Required repair

Define canonical material equality for:
- DocumentLifecycleRecord;
- AssertionLifecycleRecord;
- LifecycleEvent.

Ignore only explicitly non-material delivery/staging sequence fields where justified.

Add regressions proving same deterministic ID + altered payload/evidence/version metadata is rejected.

## BLOCKER 5 — explicit base version is not validated

`_find_base_manifest()` currently returns `None` when an explicit `base_version_id` does not exist. The coordinator can then build/publish a lifecycle-only snapshot instead of failing.

Phase 5.0 requires the base version to exist/published.

### Required repair

For an explicit base version:
- missing/unpublished -> fail closed before lifecycle publication;
- for Phase 5.0, prefer requiring the base version to equal the current version at publication time, unless the existing VersionStore is explicitly extended for safe branching semantics.

Add regression for nonexistent/stale base version.

## Non-blocking note — staged bind mutation

`bind_effective_version()` mutates the in-memory staged record's binding field. This is acceptable for Phase 5.0 only as a staging/finalization mechanism if status/reason/evidence content is immutable and the record is invisible until binding. Do not describe this as unrestricted mutation of historical lifecycle state.

## Decision

Do **not** begin Phase 5.1.

Execute one narrow **Phase 5.0-R1** repair covering only:
1. crash-safe resume/idempotent finalization;
2. retrieval pre-cutoff eligibility + real historical retrieval path;
3. strict material conflict detection;
4. explicit base-version validation;
5. regressions for all paths above.

Keep:
- §6 ranking/guard semantics frozen;
- no Crossref/RetractionWatch crawler;
- no external event transport;
- no public mutation MCP;
- CG-018 unchanged.
