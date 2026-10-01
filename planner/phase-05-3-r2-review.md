# Phase 5.3-R2 Planner Review — MOSTLY PASS / Final Commit-Store Integrity Closure Required

Implementation CODE SHA: 4881288d3259582e559c8c301121e066b6a25f40
origin/main bookkeeping tip: b63bb903dbfe42647bb7040b25acf48ea077c4a2

Verdict: MOSTLY PASS.

## Verified

- typed canonical scientific values preserve primitive/list/tuple/dict material;
- condition int vs string and list vs string no longer collide;
- approval scope uses the typed canonical assertion material;
- existing commit guard now locks action/confidence/visibility;
- existing metadata_hash and basic manifest ref/fingerprint/metadata are checked;
- fresh publication returns non-idempotent semantics and replay is idempotent/resumed;
- real async P2J E2E remains green;
- post-bind journal recovery remains green;
- reported baselines: 499 knowledge_curator + 90 integration/dsh, zero failures.

## BLOCKER R3-01 — post-target missing commit-store record still fails open

After DocumentCommitCoordinator returns PUBLISHED/IDEMPOTENT_HIT, _run_target_commit reads DocumentCommitStore.

Current behavior:
- store read exception => fail closed;
- store record exists => phase/version/snapshot checked;
- store record is None => silently continue.

This violates the Phase 5.3-R2 requirement that a terminal target publication must be backed by the authoritative DocumentCommitStore record.

Required:
- document_commit_store is mandatory for Phase 5.3 publication;
- after PUBLISHED/IDEMPOTENT_HIT, find_by_key must return a record;
- missing record => FAILED/CONFLICT before lifecycle;
- do not advance journal to TARGET_PUBLISHED.

## BLOCKER R3-02 — published manifest material hashes are not cross-checked

_existing_commit_guard currently checks:
- admitted assertion scientific material;
- action/confidence/visibility;
- metadata_hash;
- manifest ref/fingerprint/metadata_hash.

But it does not verify that existing.manifest:
- assertion_hashes correspond to existing admitted assertions under the frozen DocumentCommitCoordinator._hash_assertion contract;
- decision_hashes correspond to admitted action/confidence/visibility under the frozen manifest contract.

Therefore a same-key published commit can have admitted material that looks correct while its immutable published snapshot manifest references different assertion/decision hashes.

Required:
- mirror the frozen Phase 2 assertion hash payload exactly;
- mirror the frozen decision hash payload exactly;
- compare sorted expected hashes with existing.manifest.assertion_hashes / decision_hashes;
- mismatch => CONFLICT.

Do not change the frozen Phase 2 hash contract.

## BLOCKER R3-03 — post-target record/manifest/snapshot agreement is incomplete

After target commit success, require the store record to agree with the returned and resolved publication material:

- record exists;
- record.phase == PUBLISHED;
- record.version_id == result.version_id;
- record.snapshot_id == result.snapshot_id;
- record.manifest exists;
- record.manifest.content_hash == resolved snapshot.manifest.content_hash;
- record.manifest.ref_id/source_fingerprint/metadata_hash match resolved snapshot;
- record.manifest.assertion_hashes and decision_hashes match admitted material;
- re-run or share the same exact committed-material validator used by the existing-commit guard.

Any disagreement => fail closed before lifecycle.

## BLOCKER R3-04 — no regression currently covers missing store record or hash tampering

Current R2 tests cover unreadable store, but not:
- successful target result + missing store record;
- manifest assertion_hash tamper;
- manifest decision_hash tamper;
- manifest content_hash mismatch after target commit.

These must be explicit tests.

## Decision

Execute one final narrow Phase 5.3-R3 integrity closure.

No new architecture.
No new feature.
No Phase 5.4.

After R3 passes, Planner immediately writes final ACCEPTED / FROZEN / DELIVERABLE record.
