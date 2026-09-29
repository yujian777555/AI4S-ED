# Phase 3.2.2 Planner Review — Isolation Accepted, Exact Upstream Seam Still Open

Implementation: b14a11795adf8d9e131043707840b8b738ebb8fd
origin/main bookkeeping tip: 2bb841de54a886b1536410609b4e8d818895a8c4
Verdict: PASS as an isolation milestone; NOT a final DSH live-agent acceptance.

## Proven
- Lane A pinned upstream DSH 0.2 real-API adapter path passes.
- Lane B same Web scaffold direct ctx.llm.stream path passes.
- Lane C shipped minimal Agent fails.
- Lane C2 empty bare preset with zero tools fails the same way.
- Lane D/E correctly remain NOT_RUN after Lane C failure.

This excludes DeepSeek credentials, raw adapter, basic Web provider route, knowledge_curator persona, MCP server, tool schema and preset mount as causes.

## Correction to Lane C interpretation
AgentLoop first calls llm.prepareCall() in prepareRequest(), then dispatches through PreparedLlmCall.stream(request).
PreparedLlmCall.stream still enters the llm/stream waterfall via streamWithRegistration, but it does not invoke the public ctx.llm.stream method object that the executor monkey-patched.
Therefore an empty method spy is expected. Accepted blocker wording is: DSH 0.2 AgentLoop / PreparedCall / loop-request envelope path.

## High-probability request-extension seam
The pinned Web scaffold explicitly disables session-log-deepseek. plugin-package-inventory-deepseek remains enabled.
When sessionId is present, plugin-package-inventory-deepseek additionally resolves the requesting Agent and its standing preset tree and performs package-manifest resolution during async request-extension preparation.
If that preparation throws an ordinary Error, DeepSeekAdapter.generate wraps it as TRANSPORT: DeepSeek Messages transport failed, matching Lane C.
This is a hypothesis, not yet a conclusion.

## Portability cleanup
Accepted: machine-local C:/Users defaults removed; C:/dsh-src defaults removed; Node process.execPath is no longer used as Python fallback.

## Test-count discrepancy
The executor report says integration/dsh: 64 passed / 0 failed (60 existing + 4 new).
The repository currently contains 65 mechanically countable test_* functions under integration/dsh/tests, including 5 in test_phase322_isolation.py.
Phase 3.2.3 must report pytest --collect-only collected count plus actual pass/skip/xfail counts.

## Logging hygiene
lane322_c_baseline_agent.e2e.ts logs a request bodyPreview. Remove model request-body preview logging. Keep only sanitized route/status/config facts.

## Next
Proceed to Phase 3.2.3: PreparedCall / session-aware extension binary isolation.
Do not touch knowledge_curator core, MCP semantics, product preset semantics, docs/01, §6 or §7.