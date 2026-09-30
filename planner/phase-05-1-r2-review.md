# Phase 5.1-R2 Planner Review — MOSTLY PASS, Final Exact-Replay Material Consistency Required

Implementation CODE SHA: 03238e7964337b30af559d1bd4e050c59ee1b0b4
origin/main bookkeeping tip: a69c4eacd0efbf09a27022f2e0ee9fddf134ec49

Verdict: MOSTLY PASS.

## Accepted

- contradictory explicit work/prior can no longer be silently swallowed by replay;
- relation-only requests enter explicit-lineage validation;
- explicit NONE vs omitted relation is distinguished;
- omitted relation defaults are deterministic;
- source-version append rejects unknown work, missing prior and cross-work prior before index mutation;
- R1 DOI/stable precedence and registry uniqueness remain intact;
- reported baselines remain green.

These areas are accepted and should not be redesigned.

## BLOCKER R3-01 — replay prior must match the existing record, not merely the work

_replay_lineage_conflict currently accepts any explicit_prior_version_id that exists in existing.work_id.

For an exact replay, this is too weak.

If the existing SourceVersionRecord has:
prior_source_version_id = P1

then a caller replaying the same ref_id+fingerprint with:
explicit_prior_version_id = P2

must be IDENTITY_CONFLICT even if P1 and P2 belong to the same work.

If existing.prior_source_version_id is None, supplying any prior is also contradictory.

The current test test_replay_compatible_lineage_still_replay uses the existing first version itself as the supplied prior, effectively claiming a source version is a revision of itself. That test must be replaced with a real two-version lineage fixture.

## BLOCKER R3-02 — explicit replay relation must match existing material

If candidate.explicit_relation is supplied (including VersionRelation.NONE), it must equal existing.relation for an exact replay.

Current code can accept REVISION_OF / CORRECTED_VERSION / EXPLICIT_SAME_WORK without comparing to existing.relation.

The PREPRINT_TO_JOURNAL replay logic is particularly incorrect:
it accepts existing.source_kind=PREPRINT + candidate.source_kind=JOURNAL for the SAME ref_id+fingerprint.

That is not replay; it is a material identity contradiction.

Correct replay example:
existing target version J1:
- source_kind=JOURNAL
- relation=PREPRINT_TO_JOURNAL
- prior_source_version_id=P1

Replay of J1 may explicitly repeat:
- relation=PREPRINT_TO_JOURNAL
- prior=P1
- source_kind=JOURNAL

and should remain EXACT_REPLAY.

## BLOCKER R3-03 — source_kind mismatch on exact replay is material conflict

SourceVersionRecord material equality already includes source_kind.

But _replay_material_conflict does not compare candidate.source_kind to existing.source_kind.

Same ref_id+fingerprint cannot silently change PREPRINT <-> JOURNAL / CONFERENCE / OTHER.

Mismatch => IDENTITY_CONFLICT.

## BLOCKER R3-04 — normalized title contradiction on exact replay is currently under-checked

Current code allows title change on exact replay when DOI/stable_id exist.

Phase 5.1's stated rule was:
same fingerprint under materially contradictory identity metadata -> fail closed.

For the same source fingerprint, if both existing and incoming normalized titles are present and differ, treat it as IDENTITY_CONFLICT.

Whitespace/case/NFKC-only differences remain equal because normalize_title already removes those harmless differences.
Do not require raw-title byte equality.

Missing incoming title may remain non-contradictory; only compare when both normalized values are present.

## Decision

Do not start Phase 5.2.

Execute one final narrow Phase 5.1-R3:
- exact replay prior equality;
- exact replay relation equality;
- source_kind equality;
- normalized-title material consistency;
- replace the invalid self-prior replay test with a real two-version replay fixture.

After R3 passes, freeze Phase 5.1.
