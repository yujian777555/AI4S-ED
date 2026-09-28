# Phase 3.0 Planner Review — Official DSH Runtime / DeepSeek API

**Reviewed implementation:** `d17c77720cc9f83ca8221fc67f67ef24c12ae5f7`  
**Remote bookkeeping tip:** `8eb9baed748da04d08101039a291ca757de33756`  
**Keyless tests:** 15 passed / 0 failed  
**Frozen knowledge_curator tests:** 127 passed / 0 failed  
**Live DSH/DeepSeek smoke:** PASS  
**Same-session continuity:** PASS  
**Verdict:** **PASS WITH EXPLICIT VERSION-SKEW BOUNDARY**

## Accepted evidence

The live test used the official Python SDK/runtime path rather than a direct HTTP shortcut:

```text
DeepSeekHarness
  -> official bundled dsh runtime
  -> sdk-minimal profile
  -> provider=deepseek-official
  -> model=deepseek-chat
  -> real DeepSeek API
```

Two turns completed in the same session. Turn 2 recovered the sentinel from Turn 1, demonstrating the actual runtime/session/provider path.

Secrets were environment-injected and not committed.

The deterministic knowledge_curator core remains DSH-independent.

## Version mismatch ruling

The mismatch is **accepted for Phase 3.0** and does not require rerunning the smoke.

Observed executable baseline:
- `deepseek-harness-sdk==0.1.5rc1`
- `deepseek-harness-runtime-bin==0.1.5rc1`

Reviewed upstream architecture baseline:
- repository state `0.2.0-rc.1`
- commit `4878cdabd87d4041bdaff61d04c966883b9fd07a`

The published/executable smoke proves 0.1.5rc1 behavior only.

Planner compatibility check against official tag `dsh-v0.1.5-rc.1` confirms:
- Python SDK profile/provider/model/patch support exists;
- `@deepseek-ai/dsh-mcp-client` exists;
- stdio MCP transport/config exists;
- the CLI ships the MCP client for patch layers;
- the later `agent-preset` / `agent-preset-registry` package paths are not present in this tag.

Therefore:
- Phase 3.1 may safely target 0.1.5rc1 for the MCP bridge;
- Phase 3.2 may **not** assume Agent Preset support on 0.1.5rc1;
- a newer/source-pinned runtime compatibility gate is required before final Agent Preset packaging.

This is recorded as CG-015.

## Next phase

Proceed to **Phase 3.1 — Python knowledge_curator MCP adapter + live DSH MCP bridge**.

This phase proves:
1. a thin Python MCP server can expose the existing curator core;
2. official DSH 0.1.5rc1 can discover it through `@deepseek-ai/dsh-mcp-client`;
3. the real DeepSeek-backed DSH agent can call the curator tool and receive a deterministic CurationReport.

Do not implement Agent Preset yet.
