# Phase 3.2.1 Planner Review — Preset Runtime PASS, 0.2 Model Turn Blocked

**Implementation:** `f29f20e8d5e8452e851782d459056f17b677cdf5`  
**origin/main bookkeeping tip:** `0c3dd29155fde3074e5d2968b4e8d788aaa38eb8`  
**integration/dsh tests:** 60 passed / 0 failed  
**knowledge_curator tests:** 127 passed / 0 failed  
**Verdict:** **PARTIAL PASS — DSH Agent packaging/mount accepted; live 0.2 model transport unresolved**

## Accepted

Phase 3.2.1 successfully proves the parts that Phase 3.2 had not yet proven:

- wildcard DSH dependencies were removed from the config-only product bundle;
- bundle installation uses the real profile package path: `PROFILE_PACKAGE_INSTALL`;
- pinned DSH source remains `4878cdabd87d4041bdaff61d04c966883b9fd07a` / `0.2.0-rc.1`;
- live `ctx.agentPresets.list()` contains `knowledge-curator` without a `broken` diagnostic;
- official unpublished-Agent setup contract is used:
  `ctx.agentPresets.mount(agentCtx, 'knowledge-curator')`;
- `ctx.agentPresets.composedPreset(handle.agent.ctx)` resolves `knowledge-curator`;
- assembled model-visible context contains the knowledge_curator persona;
- the mounted Agent's scoped tool schemas include
  `mcp__knowledge_curator__curate_assertion_set`;
- DSH source checkout remains clean;
- no global registry/root Agent factory ownership moved into the product bundle;
- no §6/§7 implementation was started.

These facts mean the **DSH preset/package/mount layer is now accepted**.

## Blocking item P3.2.2-01 — source-built 0.2 model turn returns EMPTY_RESPONSE

The actual 0.2 mounted Agent never reaches a tool call.

Observed Session evidence:
- request enters `deepseek-official`;
- turn/step start normally;
- five retry cycles occur;
- attempts finish without assistant content;
- no matching `tool/call`;
- no matching `tool/result`.

The adapter reports `EMPTY_RESPONSE`.

Official DSH 0.2 documentation defines this condition as a terminal provider `stop` with no content blocks, which is retryable by the default policy.

The 0.1.5rc1 DeepSeekHarness+MCP reference path still produces one tool call/result and A==B==C, but this is **reference evidence only** and does not satisfy the source-pinned 0.2 Agent acceptance.

## Why model guessing is not an acceptable fix

Pinned upstream itself contains real-API tests for `deepseek-v4-flash`, including a tool-call round trip. Therefore the next action is not to randomly change model names or prompts.

The failure must be isolated against the upstream 0.2 adapter first.

## Integration-harness portability issues to fix

The committed Phase 3.2.1 test harness contains executor-local defaults such as:
- `C:/Users/.../AI4S-ED`;
- `C:/dsh-src`.

Those are acceptable as one execution's report facts but not as committed integration-code defaults.

The runner also uses:
`AI4S_KC_PYTHON ?? process.execPath`.

Inside the Node/vitest runner, `process.execPath` is the Node executable, not Python. This fallback is wrong even though the actual test environment supplied a valid Python path.

Phase 3.2.2 must make the harness portable and fail clearly when required paths/interpreters are not provided.

## Next

Proceed to Phase 3.2.2 — layered DSH 0.2 live transport isolation.

Do not modify knowledge_curator core, the accepted MCP codec/tool, or product preset semantics merely to mask an upstream/provider failure.
