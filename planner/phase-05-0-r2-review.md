# Phase 5.0-R2 Planner Review — MOSTLY PASS, Two Final Eligibility Correctness Bugs

Implementation CODE SHA: 175cc643dacc5e887baab746c9a212bb7b37e579
origin/main bookkeeping tip: f1a02dfd91fe8f010e4645a580b2623bf1cf8821

Verdict: MOSTLY PASS. Phase 5.0 is not frozen yet.

## Accepted

- same LifecycleStore / same visibility historical retrieval E2E is now real;
- assertion-level filtering using chunk.assertion_id is implemented;
- corrigendum current/historical behavior is substantially correct;
- training eligibility follows assertion lifecycle state;
- deep-rank recovery past rank 50 works for the tested #56 case;
- crash recovery / idempotency / base validation from R1 remain accepted.

## BLOCKER R3-01 — exhaustion checks eligible identities, not backend candidate growth

_EligibilityFilteredPort currently stops when:

eligible_ids == prev_eligible_ids

after an expanded call.

This is not proof of backend exhaustion.

Counterexample:
- depth 50: candidates #1..#50 all lifecycle-ineligible -> eligible_ids = empty;
- depth 100: candidates #1..#100 all lifecycle-ineligible -> eligible_ids = empty;
- rank #101 is eligible.

Current code stops at depth 100 because the eligible set did not grow, and never reaches #101.

The agreed R2 rule was:
stop when backend candidate identities stop growing, not when eligible identities stop growing.

Required:
- track all returned candidate identities between expanded calls;
- continue when the backend result set grows, even if all newly seen candidates are ineligible;
- stop when returned_count < requested_depth OR candidate identity set stops growing;
- no arbitrary semantic assumption that 12 doublings proves exhaustion.

A safety cap may exist only as an explicit diagnostic/resource guard, not be reported as backend exhaustion. If hit before exhaustion, fail/diagnose rather than silently return an incomplete result.

Mandatory regression:
- top_k=1;
- candidates #1..#100 ineligible;
- #101 eligible;
- final result returns #101.

Also test:
- capped backend repeats same full candidate identities -> terminates.

## BLOCKER R3-02 — explicit allowed_ref_ids bypasses assertion lifecycle filtering

EvidenceRetrievalService currently has two branches:

- allowed_ref_ids is None -> wrap vector/keyword with _EligibilityFilteredPort;
- allowed_ref_ids is provided -> only pre-filter ref ids through document-level eligible_ref_ids, then use raw vector/keyword ports.

Therefore, for an active document REF-A:
- A1 superseded;
- A2 active;
- request allowed_ref_ids=[REF-A];

the raw backend can still return A1's superseded chunk because assertion_eligibility is never applied.

Required:
- retain exact document-level prefilter of the finite allowed_ref_ids set;
- ALSO preserve assertion-level candidate eligibility filtering for fine chunks;
- avoid reintroducing post-top-k under-fill.

A simple correct composition is:
1. prefilter allowed refs by document lifecycle;
2. still wrap the backend with the lifecycle eligibility wrapper so assertion_id is checked and progressive fill works within the allowed refs.

Mandatory regression:
- active REF-A with A1 superseded, A2 active;
- allowed_ref_ids=[REF-A];
- top result is A1, next is A2;
- final current retrieval returns A2 and never A1;
- historical V1 retrieval with same allowed_ref_ids may return A1.

## Decision

Do not start Phase 5.1.

Execute one final narrow Phase 5.0-R3 for these two correctness bugs only.
After R3 passes, Phase 5.0 lifecycle core can be frozen.
