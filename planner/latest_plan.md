# Phase 5.0 Plan — §7 Lifecycle Core: Revision, Retraction, Soft Archive, Versioned Visibility

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Goal

Implement the curator-owned core of docs/03 §7:
- revision drafts;
- retraction/corrigendum lifecycle state;
- soft archive / supersede without physical deletion;
- publish a new immutable KB version for lifecycle changes;
- rollback-safe current visibility;
- retrieval/training eligibility decisions;
- append-only lifecycle event outbox.

This is NOT the Crossref/RetractionWatch crawler and NOT downstream consumer implementation.

## 1. Boundaries

Do NOT:
- build Crossref / RetractionWatch / publisher polling;
- create 04 training refresh jobs;
- create 05/07 consumers;
- choose Kafka/Redis/RabbitMQ/topic names;
- physically delete published structural/USDO/vector history;
- mutate historical snapshots;
- change frozen §6 ranking/guard semantics;
- start final QA generation.

External event transport remains CG-018.

## 2. Internal lifecycle models

Create INTERNAL temporary models, recommended module:
knowledge_curator/schemas/lifecycle.py

At minimum model:

### DocumentLifecycleStatus
- ACTIVE
- RETRACTED
- SUPERSEDED
- ARCHIVED (if needed as document-level state; avoid redundant states if semantics can remain simpler)

### AssertionLifecycleStatus
- ACTIVE
- ARCHIVED
- SUPERSEDED

Do not extend the project Confidence enum.

### LifecycleReason / event kind
At minimum represent:
- RETRACTION
- CORRIGENDUM
- MANUAL_CORRECTION
- CONFLICT_RESOLUTION
- CASE_FEEDBACK
- STRONGER_EVIDENCE
- PREPRINT_TO_JOURNAL
- ROLLBACK / RESTORE if needed for audit events.

Use explicit string enums; do not encode reasons in free-form status text only.

## 3. Lifecycle record must be append-only

Add records keyed by immutable event/revision identity, not mutable fields on historical Assertion objects.

Recommended:
DocumentLifecycleRecord:
- lifecycle_id;
- ref_id;
- source_version/fingerprint when known;
- status;
- reason;
- effective_version_id;
- prior_lifecycle_id;
- affected_assertion_ids;
- evidence refs / rationale summary;
- trace_id;
- provenance_id;
- created_at or deterministic sequence metadata as appropriate.

AssertionLifecycleRecord:
- assertion_id;
- ref_id;
- status;
- lifecycle_id / revision_id;
- superseded_by_assertion_id optional.

Do not rewrite historical Assertion payloads to simulate archive.

## 4. LifecycleStore Port

Create a minimal internal Port, e.g. LifecycleStore:
- append_document_record(record);
- append_assertion_records(records);
- latest_document_state(ref_id, at_version_id=None);
- latest_assertion_state(assertion_id, at_version_id=None);
- list_records_for_ref(ref_id);
- list_active_ref_ids(...) only if semantics are clear;
- idempotent lookup by deterministic lifecycle/revision key.

In-memory adapter required.

Append must be idempotent.
Conflicting reuse of the same event id with different content must fail.

## 5. RevisionDraft

Model curator's §7.3 draft before publication.

RevisionDraft should capture:
- revision_id;
- ref_id;
- trigger/reason;
- base_version_id;
- affected assertion ids;
- proposed archive/supersede actions;
- replacement/new assertions if supplied;
- evidence chain;
- risk classification;
- review requirement;
- trace_id/provenance_id.

Do NOT invent a global human-review UI.
Represent whether manual adjudication is required.

## 6. Deterministic risk gate

Implement only the §7.3 rule-level distinction supported by docs:
- low-risk may be rule-approved when high confidence + multi-source + no unresolved controversy;
- high-risk requires L0/manual adjudication.

Do not invent a numeric global risk score.

Recommended output:
- AUTO_RULE_REVIEW_ELIGIBLE;
- MANUAL_ADJUDICATION_REQUIRED.

Retraction should be treated as high-impact lifecycle action even when the source signal is trusted; its publication may be deterministic only if the triggering event has already been externally verified/authorized by caller context.
Do not make network trust decisions inside curator.

## 7. Retraction semantics

Implement a RetractionRevision builder/coordinator.

Given a verified retraction trigger for ref_id:
- new document state = RETRACTED;
- every assertion belonging to the affected committed document version becomes ARCHIVED in the new lifecycle view;
- no historical structural/USDO/vector object is physically deleted;
- current retrieval/training eligibility = false;
- historical version resolution remains possible.

A replay of the same verified retraction must be idempotent.

## 8. Corrigendum / generic revision semantics

For a corrigendum or manual correction:
- identify affected assertion ids explicitly;
- old assertions become SUPERSEDED or ARCHIVED according to the revision action;
- replacement assertions are new immutable assertion identities when content changes;
- unchanged assertions remain active;
- new version is published;
- old version remains resolvable.

Do not mutate the original assertion object's value in place.

## 9. Backward-compatible version manifest extension

Current SnapshotManifest has no lifecycle state.

Extend INTERNAL SnapshotManifest only as needed, e.g.:
- lifecycle_hashes: list[str] = [];
- lifecycle_record_ids: list[str] = [].

CRITICAL backward compatibility:
- old manifests with no lifecycle data must retain their previous deterministic stable_payload/content hash semantics;
- do NOT make recomputation of an old Phase 2 snapshot hash change merely because new empty fields exist.

Recommended:
include lifecycle fields in stable_payload only when non-empty, or equivalent versioned hashing behavior.

Add regression proving an old-style manifest hash remains unchanged.

## 10. Publish lifecycle revision as a NEW version

Implement a LifecycleRevisionCoordinator (name may vary) that composes:
- existing VersionStore;
- existing immutable snapshot/version behavior;
- LifecycleStore;
- existing structural/USDO/vector identities.

Do not physically rewrite underlying published objects.

For a lifecycle-only retraction revision, the new snapshot may reference the same immutable structural/USDO/vector ids plus new lifecycle records.

Required:
- base version exists/published;
- create deterministic new snapshot manifest;
- publish new VersionRecord whose prior_version_id points to the current/base version according to existing VersionStore semantics;
- lifecycle records reference the published version;
- retry after side-effect must be idempotent.

If the current VersionStore API is insufficient for safe atomic lifecycle publication, add the smallest internal Port extension and document why.

## 11. Failure atomicity

Use failure-injection tests analogous to Phase 2.

A lifecycle revision must never leave:
- current version pointer advanced without corresponding lifecycle records;
- lifecycle records claiming an unpublished version as active;
- half-applied assertion archive state visible to current consumers.

If full transaction across LifecycleStore + VersionStore is not possible with current Ports, use a staged lifecycle record / publish / finalize sequence and explicit recovery semantics.

Do not delete historical records as compensation after publication.

## 12. Rollback semantics

Existing VersionStore.rollback_to must remain non-destructive.

Required scenario:
V1 active document
-> V2 retraction archives it
-> current retrieval eligibility excludes ref
-> rollback_to(V1)
-> current lifecycle view treats ref/assertions as visible exactly as V1;
-> V2 remains historically resolvable and still records the retraction.

This requires lifecycle lookup to be version-scoped, not merely “latest record globally”.

Add explicit tests.

## 13. Current visibility / eligibility service

Add a small lifecycle visibility service/Port that answers for a given current or explicit version:
- document visible for retrieval?
- assertion visible for retrieval?
- eligible for training export?
- lifecycle status/reason.

Rules:
- RETRACTED document: no current retrieval/QA evidence; no training export;
- ARCHIVED assertion: no current retrieval/training;
- SUPERSEDED assertion: no current retrieval/training, but historical provenance remains;
- historical explicit version before the lifecycle event can still see the historical assertion.

Do not conflate “not currently eligible” with physical absence.

## 14. Compose visibility with §6 without changing ranking

Add lifecycle filtering as a composition layer BEFORE/AT query eligibility, not a new ranking algorithm.

Preferred approach:
- EvidenceRetrievalService optionally accepts a LifecycleVisibilityPort;
- derive/intersect allowed_ref_ids for the selected current version before calling frozen hybrid_retrieve;
- or use an exact eligibility wrapper that guarantees retracted refs cannot enter candidate results.

Do NOT:
- retrieve top-k first and then simply drop retracted hits if that could under-fill/miss eligible results;
- mutate FAISS/BM25 persisted history;
- change RRF/reranker scoring.

Tests must prove retracted ref never appears in current EvidenceBundle but can appear in historical-version retrieval when explicitly configured.

For Phase 5.0, deterministic/in-memory retrieval integration is sufficient; do not require rebuilding the real BGE indexes just to validate lifecycle semantics.

## 15. Event outbox (CG-018)

Create INTERNAL append-only lifecycle events/outbox.

Event examples:
- KB_DOCUMENT_RETRACTED;
- KB_ASSERTIONS_ARCHIVED;
- KB_REVISION_PUBLISHED;
- KB_VERSION_ROLLED_BACK;
- KB_CORRIGENDUM_PUBLISHED.

Each event:
- deterministic event_id;
- event type;
- ref_id;
- affected assertion ids;
- old/new version ids;
- trace_id;
- provenance_id;
- lifecycle/revision id;
- payload schema version;
- created sequence/time metadata.

EventSink/Outbox Port:
- append;
- list pending/all;
- mark delivered only if useful internally.

Do not implement external delivery transport in Phase 5.0.

## 16. Training/retrieval invalidation semantics

At minimum, emitted retraction/revision event payload must contain enough information for future consumers to invalidate:
- QA evidence cache;
- 04 training/constraint exports;
- 07 audit/metrics.

Do not call those systems directly.

## 17. Preprint -> journal

Phase 5.0 only lays the lifecycle/version foundation.

Do NOT yet implement fuzzy arXiv/journal identity matching.
If an upstream caller explicitly supplies that ref/version B supersedes version A, the internal revision model may represent PREPRINT_TO_JOURNAL.

Automated DOI/title/version matching belongs to a later §7 increment.

## 18. MCP boundary

Do not expose destructive/authoritative lifecycle publication as an unrestricted public MCP tool in this first phase.

If any MCP addition is made, limit it to read-only lifecycle status/preview unless Planner explicitly approves mutation semantics later.

Core lifecycle tests first.

## 19. Tests

Maintain:
- knowledge_curator >= 311 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add tests for at least:
- append-only lifecycle store;
- idempotent same-event replay;
- conflicting event-id payload rejected;
- retraction archives all affected assertions;
- no physical delete of structural/USDO/vector historical records;
- current visibility excludes retracted/archived;
- historical explicit version still resolves old data;
- V1 -> V2 retraction -> rollback V1 restores current visibility;
- corrigendum supersedes only affected assertions;
- unchanged assertions remain active;
- backward manifest hash compatibility;
- lifecycle new snapshot/version deterministic;
- failure before/after lifecycle/version side effects recovers safely;
- outbox deterministic/idempotent;
- retrieval composition excludes retracted refs without post-top-k under-retrieval;
- training eligibility excludes retracted/archived.

## 20. Deliverables

Create:
- results/phase-05-0-executor-report.md;
- lifecycle transition/snapshot smoke JSON if helpful.

Report:
- lifecycle models/store: PASS/FAILED;
- revision draft/risk gate: PASS/FAILED;
- retraction soft archive: PASS/FAILED;
- corrigendum/supersede: PASS/FAILED;
- version publication: PASS/FAILED;
- rollback visibility: PASS/FAILED;
- historical preservation: PASS/FAILED;
- retrieval eligibility integration: PASS/FAILED;
- training eligibility: PASS/FAILED;
- event outbox: PASS/FAILED;
- backward manifest hash compatibility: PASS/FAILED;
- failure atomicity: PASS/FAILED;
- exact test counts;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- new CONTRACT_GAPS.

## 21. Completion

Update status.json:
- phase = 5.0
- actor = executor
- state = executor_complete
- latest_commit = actual CODE implementation SHA
- result_expected = results/phase-05-0-executor-report.md

Push main and STOP.

Do not start automated Crossref/RetractionWatch polling, preprint identity matching, external event transport, or Phase 5.1 until Planner review.
