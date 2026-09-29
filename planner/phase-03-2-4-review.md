# Phase 3.2.4 Planner Review — DSH Agent Layer Accepted

Implementation: 8cc7bd2cd4f9c8ed052cc892b6b79d3076cf064e
origin/main bookkeeping tip: 5426e690af2db76b5b4faaccb84d976517473ddf
Verdict: PASS — CG-015 CLOSED; DSH Agent integration accepted and frozen.

## Accepted live evidence
- pinned DSH source: 4878cdabd87d4041bdaff61d04c966883b9fd07a / 0.2.0-rc.1
- minimal Agent completed with zero retries in this acceptance run;
- knowledge-curator preset mounted successfully;
- composed preset = knowledge-curator;
- MCP tool is visible in the mounted Agent scope;
- exactly one structural tool/call for mcp__knowledge_curator__curate_assertion_set;
- exactly one linked tool/result;
- direct core summary = successful / accept / medium;
- actual tool-result summary = successful / accept / medium;
- final model response summary = successful / accept / medium;
- A == B == C;
- DSH source checkout clean;
- no public project contract change.

## Interpretation of prior EMPTY_RESPONSE
The previous source-pinned 0.2 EMPTY_RESPONSE failure did not reproduce in Phase 3.2.4 after the probes were corrected.
Because the same runtime/provider path now completes the strict MCP round-trip without a product-code workaround, Planner treats the earlier failures as transient runtime/provider instability, not a deterministic knowledge_curator or DSH AgentLoop defect.
No workaround is added to the product bundle.

## Test-count correction
The Phase 3.2.4 executor report still contains the older 65-test integration count.
Current main mechanically contains 70 test_* functions under integration/dsh/tests: the previous 65 plus 5 Phase 3.2.4 regression tests.
The user/executor rerun reports 70 collected / 70 passed / 0 failed.
This is report metadata lag, not a code blocker.

## Regression-quality hardening still required
The live acceptance artifact from this run is credible: B was structurally parsed and does not carry an inference/fallback source marker.
However lane324_kc_roundtrip.e2e.ts still has two weaknesses that must be hardened immediately in the next phase:
1. the test only asserts tool_call_count >= 1 at the end; it must also assert exactly one linked tool/result and abc_match == true;
2. when structured tool-result parsing fails, code may infer B from raw string presence and copy A values. That fallback must not participate in acceptance.

These are regression-test quality issues, not grounds to reopen CG-015 for the already observed successful run.

## Frozen baseline
- §5.1–§5.4 deterministic curator core
- Python MCP server on mcp 2.2.0
- public DSH tool mcp__knowledge_curator__curate_assertion_set
- config-only knowledge-curator DSH bundle/preset
- source-pinned DSH 0.2.0-rc.1 live Agent integration

## Next
Proceed to Phase 4.0: §6 deterministic evidence/anchor/Abstain/anti-hallucination foundation.
Do not implement full FAISS/BM25/reranker yet and do not take over final user-answer generation.