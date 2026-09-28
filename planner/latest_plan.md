# Phase 3.1.1 Plan — Strict DSH Tool-Call Evidence Closure

**Planner:** ChatGPT  
**Executor:** MiMo  
**State:** READY_FOR_EXECUTOR  
**Base implementation:** `f79eea915673048cce1c98a7d4abf56501d4db6c`

## 0. Scope

This is a **small evidence-hardening round only**.

Do not redesign:
- knowledge_curator MCP server;
- §5 core;
- DSH patch architecture;
- model/provider setup.

Do not begin Agent Preset, §6, or §7.

Read:
1. `planner/phase-03-1-review.md`
2. `planner/latest_plan.md`
3. `planner/CONTRACT_GAPS.md`
4. current `integration/dsh/mcp_smoke.py`
5. official DSH 0.1.5rc1 event/session sources.

## 1. Replace heuristic call detection

Delete/retire the heuristic that treats arbitrary string occurrences of:
- `EXPECTED_TOOL`;
- `tool/call`;
- `tools/call`

as evidence of a real call.

Parse `RunResult.events` structurally.

A matching call is only:

```python
event["type"] == "tool/call"
and event["data"]["name"] == EXPECTED_TOOL
```

Support the concrete 0.1.5rc1 SDK event representation only as actually observed; do not build a vague recursive string scanner.

Persist a sanitized call evidence record containing:
- event seq;
- callId if present;
- name;
- turn;
- step;
- arguments hash or bounded non-secret fixture summary.

Do not persist unnecessary raw prompts.

## 2. Pair exact tool/result

For every matching call event:
- obtain the call event `seq`;
- find `event.type == "tool/result"`;
- require its `sourceEventSeqs` to contain that call seq;
- require exactly one corresponding successful result for the chosen acceptance call, unless DSH legitimately emits a documented multiplicity.

Extract the MCP returned payload from the paired result.

Prove the result is from:
`mcp__knowledge_curator__curate_assertion_set`

not from the model's final answer.

## 3. Compare direct core -> MCP result -> final model answer

For the same fixture, record three summaries:

### A. direct_core
- status
- first action
- first confidence

### B. actual_tool_result
Extracted from paired DSH `tool/result`.

### C. final_response
Parsed from final three-line answer.

Acceptance:
`A == B == C`

The live test fails if:
- no exact matching call event exists;
- no linked result exists;
- tool result cannot be parsed;
- tool result differs from deterministic core;
- final response differs from tool result.

## 4. Exact counts

`tool_call_count` must count only exact matching `tool/call` events.

Also record:
- `matching_tool_result_count`.

Do not infer count by occurrences in text.

For the current prompt, preferably expect exactly one call. If model/runtime may legitimately retry, allow >1 only if every counted item is a real exact call event and the accepted result is clearly identified.

## 5. Artifact semantics

Update `results/phase-03-1-dsh-mcp-smoke.json`.

Replace ambiguous:
- `secret_present`

with explicit fields:
- `credential_available`
- `secret_leaked`

For the live environment expected:
- credential_available = true
- secret_leaked = false

A keyless run may use:
- credential_available = false
- secret_leaked = false.

Never serialize the credential.

Add sanitized:
- matching_call_events
- matching_result_events
- direct_core_summary
- tool_result_summary
- final_response_summary
- summaries_match

Do not dump full session history.

## 6. Tests

Keep:
- 35 existing integration tests green;
- 127 knowledge_curator tests green.

Add keyless tests proving:
- prompt text containing EXPECTED_TOOL alone does **not** count as a call;
- tool catalog entry alone does **not** count as a call;
- unrelated `tool/call` does not count;
- exact `tool/call` does count;
- exact linked `tool/result` is paired by `sourceEventSeqs`;
- unlinked result is rejected;
- direct/tool/final mismatch fails acceptance;
- artifact contains no secret value and reports `secret_leaked=false`.

Use fixture event dicts matching official DSH 0.1.5rc1 event shape.

## 7. Optional MCP error semantics check

Inspect official `mcp==2.2.0` supported server error mechanism.

If there is a documented high-level method to return a sanitized tool error with MCP `isError=true`, update malformed payload handling and test it.

If doing so requires private APIs or custom framing, do **not** change current behavior. Record:
`STRUCTURED_OK_FALSE_RETAINED`.

This optional item must not expand the round.

## 8. Live smoke rerun

Rerun the real bridge with:
- DSH SDK/runtime 0.1.5rc1;
- MCP 2.2.0;
- isolated DSH_HOME;
- provider deepseek-official;
- configurable model.

Live PASS requires exact structural evidence from DSH events.

## 9. Report

Create:
`results/phase-03-1-1-executor-report.md`

Include:
- exact matching call count;
- matching result count;
- sanitized call seq/callId/name;
- direct core summary;
- actual tool-result summary;
- final response summary;
- equality result;
- secret semantics;
- keyless test counts;
- knowledge_curator test counts;
- live smoke status;
- MCP malformed-input error-semantics decision;
- public contract changed? NO;
- CONTRACT_GAPS changes;
- implementation commit SHA.

## 10. status.json

Set:
- phase = "3.1.1"
- actor = "executor"
- state = "executor_complete"
- latest_commit = actual implementation SHA
- result_expected = "results/phase-03-1-1-executor-report.md"

Stop.

Do not begin Phase 3.2.
