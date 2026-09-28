# Phase 3.1 Planner Review — MCP Bridge

**Reviewed implementation:** `f79eea915673048cce1c98a7d4abf56501d4db6c`  
**Remote bookkeeping tip:** `942a3ffb8f07bee0655b725c92e725f2910e4976`  
**Keyless DSH/MCP tests:** 35 passed / 0 failed  
**Frozen knowledge_curator tests:** 127 passed / 0 failed  
**Direct MCP contract:** PASS  
**Live DSH MCP bridge:** functionally PASS, evidence hardening required  
**Verdict:** **MOSTLY PASS — Phase 3.1.1 evidence closure only**

## Accepted

- official `mcp==2.2.0` is used;
- server entrypoint is real stdio MCP, not handwritten JSON-RPC;
- `curate_assertion_set` delegates to existing `KnowledgeCurator.curate()`;
- integration adapters are clearly marked fake/in-memory;
- no fake production commit tool is exposed;
- DSH 0.1.5rc1 resolves `@deepseek-ai/dsh-mcp-client`;
- runtime-generated patch avoids committing developer-specific Python paths;
- direct MCP list/call path is tested;
- model final response matches deterministic core for the live fixture;
- no §6/§7/Agent Preset scope creep;
- the two reported `String to replace not found` messages were transient editor/patch failures; final committed files are coherent and tests are green.

## Blocking evidence issue P3.1.1-01

Current live evidence detector is heuristic. It recursively scans event/notification strings for the public tool name and counts occurrences of:
- `tool/call` text;
- `tools/call` text;
- the public tool name.

Because the **prompt itself contains the tool name** and the discovered tool catalog also contains it, `tool_call_count=7` is not an authoritative count of actual dispatched tool calls.

Official DSH session behavior provides a precise event contract:
- real dispatch emits `event.type == "tool/call"`;
- exact tool name is `event.data.name`;
- result emits `event.type == "tool/result"`;
- result links to the call event through `sourceEventSeqs`.

Therefore Phase 3.1 must not claim strict call evidence from string scanning.

## Hardening P3.1.1-02 — prove the actual tool result, not only the final model paraphrase

Current expected-vs-observed comparison is primarily:
- expected summary from direct core;
- model final text contains expected action/confidence.

That is useful, but the acceptance chain should also extract the **actual `tool/result` event paired with the exact call** and compare its returned CurationReport summary to direct core.

Required proof:
```text
exact tool/call(name == expected MCP tool)
  -> exact call event seq
  -> tool/result(sourceEventSeqs contains call seq)
  -> parse MCP returned report
  -> status/action/confidence == direct core
```

## Hardening P3.1.1-03 — secret artifact semantics

The smoke artifact currently stores:

`"secret_present": true`

This means a credential existed in the executor environment, not that a secret leaked. The name is ambiguous and contradicts the intended evidence field `secret_present=false`.

Replace/split it into explicit semantics, for example:
- `credential_available: true`
- `secret_leaked: false`

The artifact must never store the credential value.

## Optional protocol hardening

Malformed input currently returns a normal successful MCP result carrying `{"ok": false, ...}`.

If the official MCP 2.2.0 high-level server provides a supported sanitized tool-error mechanism that results in MCP `isError=true`, prefer it for malformed input and test it. If not, keep the current structured `ok:false` contract and document the limitation; do not invent custom wire behavior.

## Exit criteria

Phase 3.1.1 passes when:
- exact `tool/call` events are parsed structurally, not by string search;
- exact call count is derived only from matching DSH events;
- at least one exact matching `tool/result` is paired to the call;
- the tool-result CurationReport summary matches direct core;
- final response still matches that tool result;
- secret artifact semantics are unambiguous;
- all 35 integration tests and 127 knowledge_curator tests remain green;
- live DSH MCP smoke passes again;
- no new business/runtime feature is added.

After this, the MCP bridge is accepted and Planner can move to the DSH Agent packaging compatibility gate.
