# Phase 5.3 Planner Review — MOSTLY PASS / Real Integration Closure Required

Implementation CODE SHA: 0474ce9066fbce1ea3d7624ba91e50829bb7c523
origin/main bookkeeping tip: 4b86717612768a5d22fdd0738aa8137b7128cd39

Verdict: MOSTLY PASS. Do not freeze the module yet.

## What is accepted

The orchestration architecture is directionally correct:

- explicit publication journal;
- monotonic PREPARED -> TARGET_PUBLISHED -> LIFECYCLE_PUBLISHED -> FINALIZED phases;
- approval modeled explicitly rather than faking low-risk scientific metadata;
- target/lifecycle/final-bind saga ordering;
- stale-base fail-closed intent;
- final SourceVersion intended to bind to V_final, not V_target;
- P2J lifecycle visibility semantics compose correctly in the fake happy path;
- frozen Phase 2/5.0/5.1/5.2 files were not redesigned.

However the implementation has not yet proven the actual repository interfaces end-to-end.

## BLOCKER R1-01 — real DocumentCommitCoordinator is async, publication coordinator is sync

Frozen Phase 2 interface is:

async def DocumentCommitCoordinator.commit(...)

Current RevisionPublicationCoordinator.publish() and _run_target_commit() call:

result = self._commit.commit(request)

without await.

The Phase 5.3 tests use a synchronous FakeCommitCoordinator, so this mismatch is hidden.

With the real coordinator, result is a coroutine object and publication cannot proceed correctly.

Required:
- make RevisionPublicationCoordinator.publish async;
- await the real commit coordinator;
- tests use pytest.mark.asyncio / equivalent;
- the primary E2E must use the real frozen DocumentCommitCoordinator.

Do not wrap async with nested event loops.

## BLOCKER R1-02 — target CommitRequest is optional and never validated

The plan required exact target CommitRequest identity/material validation.

Current code has no _validate_target_request helper. target_commit_request can be None and fake tests still pass.

Required before any side effect:
- target_commit_request must be a real CommitRequest;
- run frozen validate_commit_request(request);
- source.ref_id == package.new_ref_id;
- source.source_fingerprint == new.source_fingerprint;
- assertion_set.ref_id == package.new_ref_id;
- report.source_ref_id == package.new_ref_id;
- assertion_set assertions exactly equal package.target_assertions by canonical publication material;
- no missing/extra assertions.

None/malformed request => FAILED/CONFLICT before journal/commit side effects.

## BLOCKER R1-03 — approval scope hash does not actually bind CommitRequest material

compute_publication_scope_hash currently ignores target_commit_request contents.

It hashes package.target_assertions and optional separately supplied curation_decisions, but does not bind:
- request.source ref/fingerprint;
- AssertionSet metadata;
- request.report decisions;
- CommitRequest metadata/trace material that is intentionally publication-significant.

Therefore an approval can remain valid while the actual CommitRequest metadata/decisions change.

Required:
scope hash must be derived from the actual validated CommitRequest and include:
- package_id/new source identity;
- request source ref/fingerprint;
- full AssertionSet metadata;
- canonical exact assertion publication material;
- report decision material assertion_id/action/confidence;
- report publishability-relevant fields such as status/returned_upstream_count.

Do not accept a second independent curation_decisions parameter as the source of truth.

Use canonical JSON structures, not str(list/dict) shortcuts for nested scientific values.

## BLOCKER R1-04 — curation gate is bypassable

Current code only validates curation if curation_report is separately provided.

Calling publish(..., curation_report=None) bypasses the gate.

Also the report may differ from target_commit_request.report.

Required:
- target_commit_request.report is the single authoritative report;
- curation report is mandatory through CommitRequest;
- remove or deprecate the split curation_report/curation_decisions input path;
- every target assertion has exactly one decision;
- only exact CurationAction.ACCEPT / DOWNGRADE allowed;
- PENDING_REVIEW/REJECT/RETURN_UPSTREAM/SUPERSEDE block before side effects;
- returned_upstream_count > 0 blocks;
- report.status incompatible with ACCEPT/DOWNGRADE-only publication blocks.

The frozen DocumentCommitCoordinator is intentionally more permissive for generic commits; Phase 5.3 must remain stricter for replacement publication.

## BLOCKER R1-05 — existing target commit material guard compares IDs only and fails open

Current guard:
- compares admitted assertion IDs only;
- does not compare scientific material;
- does not compare admitted action/confidence/visibility;
- swallows commit-store exceptions and returns success.

Therefore same ref/fingerprint + same assertion IDs + changed values can continue to lifecycle.

Required:
for an existing commit record compare exact canonical admitted material:
- full assertion material;
- action;
- confidence;
- visibility;
- metadata_hash / manifest material where available.

Same IDs but changed value/unit/provenance/quality/decision => CONFLICT.

If commit-store inspection fails unexpectedly, fail closed; do not silently bypass the guard.

## BLOCKER R1-06 — lineage validation is incomplete

_validate_lineage must also require:
- prior.ref_id == package.prior_ref_id;
- new.ref_id == package.new_ref_id;
- new.relation == package.relation;
- new.work_id/prior/work relation exactly matches package;
- new source fingerprint agrees with validated CommitRequest source fingerprint.

Do not rely on work membership alone.

## BLOCKER R1-07 — bind-success / journal-finalize crash is not recoverable

Plan required:
bind_source_version succeeds
→ process/journal update fails
→ retry finalizes idempotently.

Current publish() checks new.kb_version_id at entry and only accepts it when journal.phase == FINALIZED.

If bind succeeded while journal is still LIFECYCLE_PUBLISHED, retry returns CONFLICT before _run_final_bind can recognize the exact binding.

Required:
if journal is LIFECYCLE_PUBLISHED and new binding exactly equals record.final_version_id/final_snapshot_id:
- treat bind as already completed;
- advance journal to FINALIZED;
- return idempotent/resumed success.

Different binding remains CONFLICT.

Add true after-side-effect failure injection on journal FINALIZED update.

## BLOCKER R1-08 — target version/snapshot validation is incomplete

After target commit success require:
- version exists/published;
- version.snapshot_id == commit_result.snapshot_id;
- snapshot exists;
- document commit record version/snapshot/manifest agrees with result;
- snapshot.ref_id/fingerprint agree with new target source.

Current code only checks that version exists/published.

## BLOCKER R1-09 — final lifecycle snapshot preservation is not verified

Before final bind require:
- final version exists/published;
- final snapshot exists;
- final version snapshot matches recovered final_snapshot_id;
- final_version.prior_version_id == V_target on fresh chain;
- final snapshot preserves target content identity:
  structural_stage_id,
  assertion_hashes,
  vector_ids,
  usdo_hashes/usdo_record_ids,
  metadata_hash,
  decision_hashes;
- lifecycle ids are added without replacing target scientific content.

Do not bind if lifecycle final snapshot is not a content-preserving derivative of V_target.

## BLOCKER R1-10 — tests are fake-heavy and do not prove real component integration

Current 14 tests use FakeCommitCoordinator and pre-create V_target manually.

They do not prove:
- real async DocumentCommitCoordinator;
- real CommitRequest/CurationReport;
- real document commit store admitted material;
- real snapshot/manifest chain;
- real pending-vector/finalize recovery with frozen commit coordinator.

Required primary E2E:
KnowledgeCurator.curate
→ real CommitRequest
→ real DocumentCommitCoordinator
→ RevisionPublicationCoordinator
→ real LifecycleRevisionCoordinator
→ SourceVersionRegistry bind.

Fakes may remain only for narrow injected error branches.

## Decision

Execute Phase 5.3-R1 as the final integration-hardening pass.

No Phase 5.4.
After R1, Planner performs final module acceptance/freeze.
