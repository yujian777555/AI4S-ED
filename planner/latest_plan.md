# Phase 5.3-R3 Plan — Final Commit-Store / Manifest Integrity Closure

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Close only the final authoritative commit-store integrity gaps from:
planner/phase-05-3-r2-review.md

Do not add features.
Do not create Phase 5.4.

## 1. Freeze all existing architecture

Do not redesign:
- async RevisionPublicationCoordinator API;
- approval/scope model;
- publication journal;
- DocumentCommitCoordinator;
- LifecycleRevisionCoordinator;
- SourceVersionRegistry;
- RevisionPackage;
- DSH/MCP.

## 2. Phase 5.3 requires DocumentCommitStore

For publication orchestration, document_commit_store must be configured.

Before any target publication side effect:
- if self._commit_store is None, return FAILED;
- do not treat missing store capability as optional.

This is an internal orchestration requirement, not a public contract change.

## 3. Mirror frozen assertion hash exactly

Add an internal helper that mirrors DocumentCommitCoordinator._hash_assertion without changing it.

Payload must match Phase 2 exactly:

- id;
- ref_id;
- subject_class;
- subject_entity;
- subject_mention;
- property;
- value;
- unit;
- value_type;
- uncertainty;
- conditions as ordered {c,v,u};
- locator;
- sentence;
- claim_type;
- origin;
- quality.

Use the same canonical JSON:
json.dumps(sort_keys=True, ensure_ascii=False, default=str)
then SHA256.

Do NOT substitute Phase 5.3 typed canonical material here. This helper exists to verify the frozen Phase 2 snapshot contract byte-for-byte.

## 4. Mirror frozen decision hash exactly

For each admitted assertion mirror:

{
  "assertion_id": item.assertion.id,
  "action": item.action.value,
  "confidence": item.confidence.value,
  "visibility": item.visibility.value
}

Same canonical JSON/SHA256 as frozen commit coordinator.

## 5. One shared committed-record validator

Refactor if useful:

_validate_committed_record_material(
    record,
    request,
    package,
    expected_version_id=None,
    expected_snapshot_id=None,
    resolved_snapshot=None,
)

It must validate:

### record identity
- ref_id == request.source.ref_id;
- source_fingerprint == request.source.source_fingerprint.

### admitted material
- exact assertion ID set;
- exact canonical scientific assertion material;
- action;
- confidence;
- visibility.

### metadata
- record.metadata_hash == exact expected metadata hash when record is publication-staged/published;
- missing metadata_hash on a PUBLISHED record => conflict/fail closed.

### manifest
For PUBLISHED record:
- manifest must exist;
- manifest.ref_id/fingerprint/metadata_hash exact;
- sorted manifest.assertion_hashes == sorted mirrored frozen assertion hashes from record.admitted;
- sorted manifest.decision_hashes == sorted mirrored frozen decision hashes from record.admitted.

If expected version/snapshot supplied:
- record.version_id == expected_version_id;
- record.snapshot_id == expected_snapshot_id.

If resolved_snapshot supplied:
- manifest.content_hash == resolved_snapshot.manifest.content_hash;
- manifest stable publication fields equal resolved snapshot manifest.

## 6. Pre-existing commit guard

_existing_commit_guard may allow a genuinely early resumable record that has not yet produced admitted/manifest material.

But:
- if phase == PUBLISHED, full committed-record validator is mandatory;
- a PUBLISHED record with empty admitted material while package target is non-empty => CONFLICT;
- PUBLISHED record without manifest => CONFLICT.

For partial pre-publish records, allow the frozen DocumentCommitCoordinator to resume only if no contradictory material is already present.

## 7. Post-target success must find authoritative store record

After await commit returns PUBLISHED or IDEMPOTENT_HIT:

- self._commit_store must be configured;
- find_by_key(new.ref_id, new.source_fingerprint) must succeed;
- returned record must NOT be None.

If None:
- set last_error = "post-commit store record missing" or equivalent;
- return FAILED;
- journal remains PREPARED;
- do not run lifecycle;
- do not bind SourceVersion.

## 8. Post-target terminal agreement

For the returned store record require:

- phase == PUBLISHED;
- version_id == commit result.version_id;
- snapshot_id == commit result.snapshot_id;
- manifest exists;
- full committed-record material validator passes;
- resolved VersionStore snapshot exists;
- record.manifest.content_hash == snapshot.manifest.content_hash;
- record.manifest stable payload equals snapshot.manifest stable payload for all frozen content fields.

Only then:
journal.phase = TARGET_PUBLISHED.

## 9. Manifest tamper regressions

Add tests where an otherwise valid published record has:

1. assertion_hashes tampered;
2. decision_hashes tampered;
3. metadata_hash tampered;
4. manifest.content_hash tampered;
5. manifest missing.

Each must block lifecycle.

## 10. Missing store regressions

Add tests:

1. document_commit_store=None -> publication fails before target side effect;
2. commit returns PUBLISHED but find_by_key returns None -> fail closed;
3. commit returns IDEMPOTENT_HIT but find_by_key returns None -> fail closed;
4. store read throws -> fail closed.

## 11. Preserve real E2E

Real P2J E2E using real DocumentCommitCoordinator + real store must still finalize:

- V_target real;
- V_final real;
- new SourceVersion -> V_final;
- prior superseded/currently ineligible;
- journal FINALIZED.

Exact replay still idempotent.
Post-bind recovery still works.

## 12. Baselines

Maintain:
- knowledge_curator >= 499 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

## 13. Deliverable

Create:
results/phase-05-3-r3-executor-report.md

Report exactly:

Phase 5.3-R3 implementation CODE SHA:

authoritative commit-store required:
PASS / FAILED

frozen assertion-hash mirror:
PASS / FAILED

frozen decision-hash mirror:
PASS / FAILED

published manifest material guard:
PASS / FAILED

post-target missing-record fail-closed:
PASS / FAILED

post-target manifest/snapshot agreement:
PASS / FAILED

real P2J E2E:
PASS / FAILED

full replay idempotency:
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
- phase = 5.3-R3
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-3-r3-executor-report.md

Push main and STOP.

Do not create Phase 5.4.
Planner performs immediate final freeze after review.
