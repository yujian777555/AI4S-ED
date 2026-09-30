# Phase 5.1 Planner Review — MOSTLY PASS, Identity Precedence Hardening Required

Implementation CODE SHA: 773c84dc5fa657a3f70182027382371db8b2f9e5
origin/main bookkeeping tip: 28824aa003a0cd3401fb856d5af97e835da9390c

Verdict: MOSTLY PASS / Phase 5.1 not frozen yet.

## Accepted

- normalization is deterministic and intentionally non-fuzzy;
- exact ref+fingerprint replay exists;
- title-only matches are review-gated;
- no automatic preprint/journal fuzzy merge is implemented;
- append-only source-version lineage exists;
- published-bind semantics reject non-final commit states;
- explicit preprint->journal intent is represented without prematurely changing lifecycle state;
- Phase 5.0 lifecycle core remains untouched;
- reported baselines remain green.

## BLOCKER R1-01 — DOI/stable_id disagreement check is unreachable

prepare() currently returns SAME_WORK_NEW_VERSION on exact DOI before reaching the DOI/stable disagreement branch.

Counterexample:
- normalized DOI -> Work A;
- normalized stable_id -> Work B.

Current behavior can return Work A from the DOI branch.
Required behavior is IDENTITY_CONFLICT.

Move cross-identifier invariant/conflict checks before any positive DOI/stable return.

## BLOCKER R1-02 — stable_id multi-work registry corruption is not fail-closed

DOI mapped to multiple works is detected, but stable_id mapped to multiple works is not.

An exact stable_id is also an identity key in Phase 5.1. If it resolves to >1 work:
- return IDENTITY_CONFLICT;
- report all conflicting work ids;
- do not fall through to title/no-match.

## BLOCKER R1-03 — explicit_prior_version_id alone is ignored

_classify_explicit_lineage() can inherit work_id from a prior source version, but prepare() only calls it when explicit_work_id is non-null.

Therefore:
- explicit_prior_version_id=<valid prior>;
- explicit_work_id=None;

currently bypasses explicit-lineage handling.

Required:
enter explicit-lineage handling when either explicit_work_id OR explicit_prior_version_id is present.

A valid prior may provide the work family.
A missing prior must fail closed.

## BLOCKER R1-04 — PREPRINT_TO_JOURNAL relation compatibility is not enforced

Current code allows PREPRINT_TO_JOURNAL with an explicit work but no prior, and does not verify source kinds.

For Phase 5.1 explicit preprint->journal lineage must require:
- explicit_prior_version_id exists;
- prior belongs to resolved work;
- prior.source_kind == PREPRINT;
- candidate.source_kind == JOURNAL;
- explicit relation == PREPRINT_TO_JOURNAL.

Otherwise return IDENTITY_CONFLICT (or REVIEW_REQUIRED only if a caller intentionally omitted lineage and supplied no contradictory exact identifiers).

Do not infer this relation from title similarity.

## BLOCKER R1-05 — registry exact-identity uniqueness should fail closed

lookup_by_ref_fingerprint is singular, so the registry must not silently allow two source-version records with the same (ref_id, fingerprint) to map to different work/version identities.

Likewise, exact DOI/stable_id should not be silently mapped across multiple works through direct adapter writes.

Required registry invariants:
- same (ref_id, fingerprint) + different source_version/work material -> reject;
- same normalized DOI may appear in multiple versions of ONE work, but not across different work_ids;
- same stable_id may appear in multiple versions of ONE work, but not across different work_ids.

This keeps later classification deterministic instead of relying on a corrupted index.

## Decision

Do not start Phase 5.2.

Execute one narrow Phase 5.1-R1 hardening pass covering only:
1. cross-identifier precedence;
2. stable-id invariant conflicts;
3. prior-only explicit lineage;
4. PREPRINT_TO_JOURNAL compatibility;
5. registry uniqueness guards.

After R1 passes, Phase 5.1 can be frozen and Phase 5.2 may begin.
