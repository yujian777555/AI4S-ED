# Phase 3.2.3 Plan — PreparedCall / Session-Aware Extension Binary Isolation

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## Goal
Find the exact DSH 0.2 subsystem responsible for the live Agent failure.
Already proven/frozen: §5 core, MCP bridge, DSH bundle/profile install, preset activation/mount, persona visibility and scoped MCP tool visibility.
Do not modify AI4S business logic.

## Fixed upstream
repo: https://github.com/deepseek-ai/deepseek-harness
commit: 4878cdabd87d4041bdaff61d04c966883b9fd07a
version: 0.2.0-rc.1
No upstream source edits.

## Read first
- planner/phase-03-2-2-review.md
- planner/latest_plan.md
- planner/CONTRACT_GAPS.md
- Phase 3.2.2 lane scripts/artifact
- DSH packages/core/agent-loop/src/agent.ts
- DSH packages/llm/llm/src/index.ts
- DSH packages/llm/llm/src/call-config.ts
- DSH packages/llm/llm-deepseek/src/adapter.ts
- DSH packages/session/session-log-deepseek/src/index.ts
- DSH packages/llm/plugin-package-inventory-deepseek/src/index.ts
- DSH apps/web/tests/scaffold.ts

## 1. Diagnostic hygiene
Remove request body previews from committed/live diagnostics.
Never log API keys, auth headers, raw provider bodies or full model-visible request bodies.
Allowed: URL path/origin, HTTP status, content type, model, maxTokens, reasoningEffort, message count/roles, tool count, sessionId present yes/no, loop marker present yes/no, normalized failure code/message.

## 2. Exact test counts
Run:
pytest integration/dsh/tests --collect-only -q
pytest integration/dsh/tests -q
pytest knowledge_curator/tests -q
Report collected count and passed/skipped/xfail exactly.

## 3. Control C0
Reconfirm once: direct ctx.llm.stream using deepseek-official / deepseek-v4-flash / reasoning off / maxTokens 50 / user PONG / no sessionId / no tools.
Expected PASS.

## 4. Probe P1 — PreparedCall without Agent/session
Call ctx.llm.prepareCall with the same provider/model/reasoning/maxTokens.
Then invoke prepared.stream with prepared.config plus the PONG user message and no sessionId, no toolHistory, no loop marker.
If P1 fails while C0 passes, blocking_subsystem = PreparedLlmCall / prepared adapter generation. Stop later product lanes and keep CG-015 open.

## 5. Probe P2 — ordinary direct stream with a real SessionId
Create a real temporary Session through the scaffold sessions service.
Call ordinary ctx.llm.stream with the same PONG request plus sessionId, no loop marker, no toolHistory.
This activates session-aware request-extension behavior without AgentLoop PreparedCall.
If P2 fails, go directly to extension toggles.

## 6. Probe P3 — PreparedCall + SessionId
Same as P1 but add the same real sessionId.
Interpretation:
- P1 PASS + P2 PASS + P3 FAIL => prepared-dispatch plus session-aware interaction.
- P2 FAIL + P3 FAIL => session-aware path independent of PreparedCall.

## 7. Probe P4 — add exact loop envelope dimensions one at a time
Only if P1-P3 do not identify the cause.
Use a fresh one-shot PreparedCall for every variant.
P4a: add toolHistory = session.toolHistory().
P4b: deep-freeze message/request shape to match AgentLoop, no loop marker.
P4c: add markAgentLoopRequest(request).
P4d: use the same first-turn system/user derivation shape as minimal Agent.
Record the first PASS -> FAIL transition.

## 8. Observe actual waterfall
Do not rely on monkey-patching ctx.llm.stream.
Register a test-only ctx.on('llm/stream', observer, { prepend: true }) and call next().
For the failing minimal Agent record only sanitized facts:
- isAgentLoopRequest true/false
- sessionId present
- provider/model
- tools count
- toolHistory present
- Object.isFrozen(request).

## 9. First targeted toggle — plugin-package-inventory-deepseek
Record from effective scaffold config that session-log-deepseek is disabled.
Run the same real minimal Agent PONG with only plugin-package-inventory-deepseek config.enabled=false via a test-only overlay.
If normal minimal Agent FAILS and inventory-disabled minimal Agent PASSES, restore inventory once and reproduce FAIL.
Then blocking_subsystem = @deepseek-ai/dsh-plugin-package-inventory-deepseek session-aware extension path.
Stop and do not patch upstream.

## 10. If inventory is not the cause
Toggle the next AgentLoop-only llm/stream listeners one at a time where the official scaffold supports it: agent-loop invariant, session checkpoint policy, session title observer, other effective listeners.
All toggles remain integration-only. Never bake them into the product bundle.

## 11. Scope
Do not modify knowledge_curator core, MCP codec/tool, product persona semantics, public docs/01 contracts, or begin §6/§7.
Do not vendor or patch DSH.

## 12. If a deployment-only optional workaround makes AgentLoop healthy
Only after exact subsystem identification, a test-only deployment overlay may be used to prove:
minimal Agent PONG -> knowledge-curator plain PONG -> final strict MCP round-trip.
Do not put the workaround into the product bundle without Planner approval.

Final strict round-trip requires source-pinned 0.2 evidence:
A = direct KnowledgeCurator core summary
B = actual linked 0.2 tool/result
C = final 0.2 model response
A == B == C.

## 13. Artifact
Create results/phase-03-2-3-dsh-preparedcall-isolation.json with:
C0/P1/P2/P3/P4 statuses, session-log enabled fact, inventory toggle result, actual llm/stream observer facts, blocking_subsystem, normalized failure, secret_leaked=false, DSH source clean.

## 14. CG-015
Close only if the source-pinned 0.2 mounted knowledge-curator Agent completes the strict MCP round-trip.
If an upstream subsystem is proven broken and only a diagnostic/deployment overlay works, keep CG-015 OPEN and report the exact subsystem.

## 15. Report
Create results/phase-03-2-3-executor-report.md.
Include exact pytest collection/result counts, C0/P1/P2/P3/P4, inventory toggle, middleware evidence, first PASS->FAIL dimension, blocking subsystem, source cleanliness, public contracts changed NO, implementation SHA.

## 16. status.json
On completion set phase=3.2.3, actor=executor, state=executor_complete, latest_commit=actual SHA, result_expected=results/phase-03-2-3-executor-report.md.
Stop. Do not start §6.