# Phase 4.3.1 Planner Review — Core PASS, Mounted-DSH Live Harness NOT ACCEPTED

Implementation code SHA: 8f8fa2f2e5256319ed77e09996112aba6c9ba5ea
origin/main bookkeeping tip: 85cbb2fca3909adf22ebdaaffd2f72bbe53b8232
Verdict: CORE PASS / LIVE DSH VALIDATION INCOMPLETE.

## Accepted and frozen pending live validation only

The Phase 4.3.1 production/core fixes are accepted:
- guardable_as_anchor now matches actual EvidenceAnchor constructability;
- evidence_type missing/invalid is fail-closed;
- coverage counts only anchorable evidence;
- H2 checked/PARTIAL/METADATA_UNAVAILABLE semantics are truthful;
- metadata unavailable is not misreported as H2 hallucination;
- integration fixture mode is explicit and production default remains retrieval_unavailable;
- existing knowledge-curator preset is reused;
- mounted Agent schemas expose the new evidence tools;
- MCP UTF-8 mojibake is fixed;
- 311 knowledge_curator tests and 83 integration/dsh tests are reported green.

No production retrieval/guard/MCP business-code redesign is requested after this review.

## P4.3.2-01 — lane325 soft-passes a live failure

When credentials exist but retrieve_evidence produces zero tool/call events, lane325 currently:
- prints LANE325_LIVE_NO_TOOLCALL;
- returns from the test.

Therefore Vitest reports the test as passed even though the live requirement failed.

For a live run with available prerequisites, zero tool/call MUST fail the E2E test after diagnostic output.

Discovery-only may pass only when live prerequisites are genuinely unavailable before the turn.

## P4.3.2-02 — run_lane325 can produce false PASS for validate and direct-vs-DSH comparisons

run_lane325.py currently checks only a generic:
LANE325_LIVE_TOOL_OK

If present, it sets ALL of these to PASS:
- mounted_dsh_retrieve_evidence_live;
- mounted_dsh_validate_retrieved_claims_live;
- direct_vs_dsh_evidence_identity_match;
- direct_vs_dsh_policy_match.

But lane325 emits LANE325_LIVE_TOOL_OK immediately after retrieve_evidence succeeds.

Thus validate/policy/identity can be marked PASS without corresponding evidence.

Required: use separate explicit success markers backed by actual assertions.

## P4.3.2-03 — lane325 does not actually compare direct vs mounted-DSH results

Phase 4.3.1 required:
- direct EvidenceRetrievalService vs mounted DSH retrieve_evidence identity comparison;
- direct ClaimGuardService vs mounted DSH validate_retrieved_claims policy comparison.

Current lane325 checks the mounted tool result internally but does not compute the direct service reference result and compare:
- evidence chunk identities;
- Abstain;
- claim policy;
- unresolved anchors/H1.

Implement these comparisons inside the E2E lane and emit PASS markers only after assertions succeed.

## External live observation

The reported 0-tool-call failure is plausibly an external DeepSeek EMPTY_RESPONSE fluctuation because lane324 curate_assertion_set also showed zero tool/call in the same window.

However that does not justify a soft-passing live test.
The strict harness must distinguish:
- control baseline and evidence lane both fail with empty response -> external runtime incident;
- baseline passes while evidence lane fails -> evidence integration regression;
- evidence lane tool calls/results succeed -> live PASS.

## Next

Proceed to Phase 4.3.2 only.
This is a validation-harness closure, not a new product phase.

After a strict live evidence roundtrip is proven, freeze docs/03 §6 and proceed to §7.
