# Phase 5.3-R1 Planner Review — MOSTLY PASS / Final Material-Lock Closure Required

Implementation CODE SHA: 3a1aa02db07837269ebe0163687a37008ec9de7c
origin/main bookkeeping tip: 12593e9709e78aa0d707ac5b280cb5ccc7e9647b

Verdict: MOSTLY PASS. Real async integration is now proven, but two final publication-material gaps remain.

## Accepted

- RevisionPublicationCoordinator.publish is async and awaits the real frozen DocumentCommitCoordinator;
- primary P2J E2E uses the real DocumentCommitCoordinator and real LifecycleRevisionCoordinator;
- V_target is created by the real document commit;
- V_final is created by lifecycle revision;
- new SourceVersion binds to V_final, not V_target;
- package/request identity and mandatory curation gates exist;
- approval scope binds real CommitRequest source/metadata/report material;
- target and final version/snapshot validation is present;
- final snapshot content-preservation validation is present;
- post-bind recovery logic exists at the publication entry;
- full replay is idempotent in the real E2E;
- reported baselines remain green.

## BLOCKER R2-01 — existing target commit guard does not lock decision material

_existing_commit_guard currently compares:
- assertion IDs;
- canonical assertion scientific material.

It does NOT compare existing AdmittedAssertion:
- action;
- admitted confidence;
- visibility.

Frozen DocumentCommitCoordinator returns IDEMPOTENT_HIT for the same (ref_id, fingerprint) without re-evaluating request material.

Therefore:
1. target commit already published with J-A1 action=ACCEPT / visibility=ACTIVE;
2. a new Phase 5.3 request for the same ref/fingerprint uses DOWNGRADE;
3. approval scope correctly changes and may be newly approved;
4. existing guard still passes because assertion scientific material/ID is unchanged;
5. DocumentCommitCoordinator returns the old commit as idempotent;
6. lifecycle continues while request/audit says DOWNGRADE but stored target commit is still ACCEPT/ACTIVE.

This violates exact publication material semantics.

Required:
- derive expected admitted decision material from target_commit_request.report;
- compare existing AdmittedAssertion.action exactly;
- compare existing AdmittedAssertion.confidence exactly;
- compare expected visibility exactly:
  ACCEPT -> ACTIVE
  DOWNGRADE -> DOWNGRADED;
- any mismatch => CONFLICT before lifecycle.

Also compare commit record metadata_hash to the exact expected metadata hash using the frozen commit hashing semantics or an equivalent canonical helper.

## BLOCKER R2-02 — canonical condition values erase type information

canonical_assertion_material currently serializes conditions as:

str(c.value)

This is not material-exact.

Examples such as:
- integer 1 vs string "1";
- list [1,2] vs string "[1, 2]";
- dict-like structured values with string representation collisions/order artifacts

can be treated as the same package/request material.

Required:
- preserve the actual JSON-compatible value structure in canonical material;
- recursively canonicalize dict/list/tuple structures without converting values to str;
- retain primitive type information naturally through canonical JSON;
- sort dict keys deterministically;
- for non-JSON exotic values, use an explicit typed fallback structure rather than a plain str.

Use the SAME canonical scientific-value helper for:
- assertion package/request equality;
- approval scope hashing;
- existing committed assertion material comparison.

## BLOCKER R2-03 — existing commit metadata material is not guarded

Approval scope binds current request metadata, but an existing published commit with the same ref/fingerprint may contain a different metadata_hash.

Because DocumentCommitCoordinator returns IDEMPOTENT_HIT, changing metadata in a retry does not republish it.

Required:
- deterministically compute expected metadata hash from CommitRequest.assertion_set.metadata using the same fields as frozen DocumentCommitCoordinator:
  title, authors, year, source, doi, stable_id;
- if existing commit has a non-empty metadata_hash, require equality;
- for PUBLISHED existing records with manifest, require manifest.metadata_hash equality too;
- if metadata differs => CONFLICT.

This prevents request/audit scope from claiming metadata that is not actually stored in the idempotent target commit.

## BLOCKER R2-04 — target published record/result agreement should be checked when available

After a real target commit returns PUBLISHED/IDEMPOTENT_HIT, the publication coordinator already validates VersionStore/snapshot identity.

Also validate the actual DocumentCommitStore record when available:
- record.phase is PUBLISHED for a published/idempotent terminal target;
- record.version_id == result.version_id;
- record.snapshot_id == result.snapshot_id;
- record.manifest content_hash/ref/fingerprint agree with the resolved snapshot.

If the store cannot be read, fail closed in Phase 5.3 publication.

## Minor semantic cleanup

On a first successful publication, the final return currently marks idempotent=True unconditionally.

Prefer:
- first completed saga: idempotent=False;
- replay/recovery exact completion: idempotent=True/resumed as appropriate.

This is not a storage-safety blocker but should be corrected in R2 while touching the result path.

## Decision

Execute one final Phase 5.3-R2 material-lock closure.

No new architecture.
No Phase 5.4.
After R2 passes, Planner performs immediate ACCEPTED / FROZEN / DELIVERABLE finalization.
