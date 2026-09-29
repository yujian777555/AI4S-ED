# Phase 3.2.2 Plan — Isolate DSH 0.2 EMPTY_RESPONSE and Close Live Agent Qualification

**Planner:** ChatGPT  
**Executor:** MiMo  
**State:** READY_FOR_EXECUTOR

## 0. Scope

This is a targeted runtime-diagnosis and integration-harness cleanup round.

Already accepted/frozen:
- §5.1–§5.4 knowledge_curator core;
- Python MCP server + strict event evidence;
- DSH 0.2 config-only product bundle;
- profile installation;
- runtime preset activation;
- preset mount;
- persona visibility;
- scoped MCP tool visibility.

Do **not** rewrite those layers unless a concrete regression is found.

The only product acceptance blocker is the source-built 0.2 real model turn returning `EMPTY_RESPONSE`.

## 1. Fixed upstream

Use exactly:
- repo: `https://github.com/deepseek-ai/deepseek-harness`
- commit: `4878cdabd87d4041bdaff61d04c966883b9fd07a`
- version: `0.2.0-rc.1`
- pnpm: `11.7.0`
- Node satisfying upstream engine range.

Do not follow master and do not edit upstream source.

Before and after every live lane:
```bash
git -C <DSH_SRC> rev-parse HEAD
git -C <DSH_SRC> status --porcelain
```

## 2. Read first

AI4S-ED:
- `planner/phase-03-2-1-review.md`
- `planner/latest_plan.md`
- `planner/CONTRACT_GAPS.md`
- existing Phase 3.2.1 runner/artifact.

Pinned DSH:
- `packages/llm/llm-deepseek/README.md`
- `packages/llm/llm-deepseek/tests/runtime.e2e.ts`
- `packages/llm/llm-deepseek/tests/adapter.e2e.ts`
- `apps/web/tests/scaffold.ts`.

Important upstream facts:
- official Messages root defaults to `https://api.deepseek.com/anthropic`;
- `deepseek-official` API-key route uses `DEEPSEEK_API_KEY`;
- upstream real-API tests explicitly exercise `deepseek-v4-flash`;
- `EMPTY_RESPONSE` means provider stop with no content blocks.

## 3. First fix the committed integration harness

Remove every executor-specific absolute default from committed integration code.

Forbidden committed defaults:
- `C:/Users/.../AI4S-ED`;
- `C:/dsh-src`;
- other user-home-specific paths.

Resolve AI4S root from the integration file location where possible.

Require `DSH_SRC` as an explicit absolute environment variable if it cannot be derived.

Require `AI4S_KC_PYTHON` explicitly for Node-driven live MCP tests, or discover a Python executable via a deterministic documented launcher step. Do **not** use Node `process.execPath` as Python.

Fail preflight with a clear message when required configuration is missing.

Also remove/reduce temporary duplicate phase321 runners or vitest stubs that are no longer needed. Keep one canonical keyless/live runner path.

## 4. Lane A — run official upstream 0.2 real-API adapter test unchanged

Before any AI4S Agent request, execute an **upstream-owned** real API test from the pinned checkout.

Preferred single-call target:

```text
packages/llm/llm-deepseek/tests/runtime.e2e.ts
"streams raw chunks in protocol order"
```

Use the pinned repo's own vitest config/command as required.

The test already uses:
- `deepseek-official`;
- `deepseek-v4-flash`;
- real `DEEPSEEK_API_KEY`;
- official 0.2 Messages transport.

Record:
- command;
- exact test name;
- PASS/FAIL;
- normalized failure code only;
- no API key/header/body secrets.

### Decision A

If Lane A fails with `EMPTY_RESPONSE` or another provider error:
- run **one** additional minimal upstream/direct adapter probe using catalog model `deepseek-flash` with `reasoningEffort=off`, `maxTokens=50`, prompt “Reply with exactly PONG.”
- do not modify AI4S business code;
- classify the blocker as 0.2 adapter/provider/account compatibility;
- keep CG-015 open;
- stop before burning calls on later lanes unless the alternate catalog probe passes.

If Lane A passes, continue.

## 5. Lane B — same Web scaffold, direct ctx.llm.stream, no Agent/preset

Boot the same source-built 0.2 Web scaffold in:
`DSH_SNAPSHOT=record`.

Install no knowledge-curator requirement for this lane.

Call the live adapter directly through:
`ctx.llm.stream(...)`.

Use:
- provider: `deepseek-official`;
- model: `deepseek-v4-flash`;
- reasoning effort: `off`;
- max tokens: 50;
- one user message: `Reply with exactly PONG.`;
- no tools.

Acceptance:
- at least one text block;
- terminal finish kind `stop`;
- text contains PONG.

Record a sanitized adapter summary only.

### Decision B

If A passes but B fails:
- the issue belongs to Web scaffold/composition configuration, not knowledge-curator;
- record provider list/model resolution and sanitized effective route facts;
- do not alter knowledge-curator preset;
- keep CG-015 open and stop before later lanes unless the root cause is corrected without upstream source edits.

If B passes, continue.

## 6. Lane C — baseline 0.2 Agent plain turn, non-knowledge-curator preset

Create a real Agent through the same scaffold and mount a shipped lightweight preset such as `minimal` using the official setup contract.

Explicit AgentOptions:
- provider `deepseek-official`;
- model `deepseek-v4-flash`;
- reasoningEffort `off`;
- maxTokens `50`.

Prompt:
`Reply with exactly PONG.`

Acceptance:
- Agent turn completes;
- assistant text contains PONG;
- no EMPTY_RESPONSE.

This isolates AgentLoop/request assembly from the knowledge-curator preset.

## 7. Lane D — knowledge-curator mounted Agent, plain text only

Mount `knowledge-curator` exactly as already accepted.

Do **not** require a tool call yet.

Use:
- reasoningEffort `off`;
- maxTokens `50`;
- prompt `Reply with exactly PONG.`

Acceptance:
- composed preset remains `knowledge-curator`;
- persona remains visible;
- curator MCP tool remains visible;
- model returns PONG.

### Decision D

If C passes but D fails:
- inspect the difference introduced by the product preset (persona/tool schema/MCP child);
- do not touch core curation logic;
- record exact Session failure evidence.

If D passes, continue.

## 8. Lane E — final mounted knowledge-curator tool round-trip

Now run the actual acceptance case.

Use the previously validated deterministic AssertionSet fixture.

Create a fresh mounted knowledge-curator Agent with:
- provider `deepseek-official`;
- model `deepseek-v4-flash`;
- explicit bounded maxTokens (recommend 2,000);
- reasoning effort matching the upstream real tool-call test, preferably `max` unless the resolved model reports a different supported set.

Require model to call:
`mcp__knowledge_curator__curate_assertion_set`.

Final response format:
```text
status=...
action=...
confidence=...
```

## 9. Strict Lane E evidence

Only Session structural events count.

Require:
- exact `tool/call` with expected public tool name;
- exactly linked `tool/result` using 0.2 callId/event linkage;
- tool result not error;
- final assistant response after tool result.

Compute:
A = direct Python KnowledgeCurator summary  
B = actual linked 0.2 tool/result summary  
C = final 0.2 model response summary

Require:
`A == B == C`.

Do not import the 0.1.5 reference result as B or C.

## 10. Diagnostics for EMPTY_RESPONSE

For every Agent lane, persist sanitized failure evidence:
- selected provider/model;
- resolved model id/capabilities;
- request/header config from Session events;
- turn/end reason;
- assistant/attempt failure code/message;
- retry count;
- whether any assistant content blocks were logged.

Do not persist:
- API key;
- Authorization/x-api-key;
- full credentials;
- full provider raw response.

If needed, a fetch wrapper may record only:
- URL origin/path;
- HTTP status;
- response content-type;
- sanitized request fields such as model/max_tokens/thinking/tools count.

Never store headers or full request bodies.

## 11. Do not randomly switch architecture models

`deepseek-v4-flash` remains the primary qualification model because pinned upstream real-API tests use it.

Only use `deepseek-flash` as the single diagnostic fallback described in Lane A if the upstream primary test itself fails.

Do not test a list of models until one happens to work.

## 12. Result matrix

Create:
`results/phase-03-2-2-dsh-live-isolation.json`

Required:

```json
{
  "upstream_commit": "...",
  "dsh_version": "0.2.0-rc.1",
  "lane_a_upstream_adapter": {"passed": true, "model": "deepseek-v4-flash"},
  "lane_b_scaffold_direct_llm": {"passed": true},
  "lane_c_baseline_agent": {"passed": true, "preset": "minimal"},
  "lane_d_kc_plain_agent": {"passed": true},
  "lane_e_kc_tool_roundtrip": {"passed": true},
  "tool_call_count": 1,
  "tool_result_count": 1,
  "direct_core_summary": {},
  "tool_result_summary": {},
  "final_response_summary": {},
  "summaries_match": true,
  "credential_available": true,
  "secret_leaked": false,
  "dsh_source_clean_before": true,
  "dsh_source_clean_after": true,
  "blocking_layer": null,
  "errors": [],
  "warnings": []
}
```

When a lane fails, later unrun lanes must be `not_run`, not falsely marked failed/pass.

## 13. Tests

Keep all current:
- integration/dsh: at least 60 passed;
- knowledge_curator: 127 passed.

Add keyless tests for:
- no committed executor-specific absolute paths in integration runners;
- Node `process.execPath` is never used as Python fallback;
- lane-result state machine: pass/fail/not_run;
- strict 0.2 event parsing;
- secret redaction;
- CG-015 closeability requires Lane E + A==B==C.

Live lanes are separate from ordinary pytest.

## 14. CG-015

Close CG-015 **only** if Lane A through E all pass and A==B==C on Lane E.

If Lane A/B/C fails:
- keep CG-015 open;
- state the exact blocking layer;
- do not compensate by citing the 0.1.5 reference path.

If A-D pass and E fails:
- the remaining blocker is specifically knowledge-curator tool round-trip on DSH 0.2.

## 15. Report

Create:
`results/phase-03-2-2-executor-report.md`

Include:
- harness portability cleanup;
- each lane command and PASS/FAIL/NOT_RUN;
- first failing layer;
- exact normalized failure;
- model/provider/config;
- Lane E strict event evidence if reached;
- A/B/C if reached;
- test counts;
- source cleanliness;
- CG-015 decision;
- public contracts changed? NO;
- implementation SHA.

## 16. status.json

On completion:
- phase = "3.2.2"
- actor = "executor"
- state = "executor_complete"
- latest_commit = actual implementation SHA
- result_expected = "results/phase-03-2-2-executor-report.md"

Stop after Phase 3.2.2.

Do not start §6.
