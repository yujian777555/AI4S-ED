# Phase 3.2.3 Planner Review — Probe Implementation Defects Require Re-run

Implementation: f54394a4b7a864a61fb18ce077aacabcb4ade920
origin/main bookkeeping tip: 4651763d6262203c68d5241a5764b8921409e15e
Verdict: PARTIAL PASS — hygiene/test-count/inventory observations accepted; claimed dimension-by-dimension isolation is NOT accepted.

## Accepted
- bodyPreview logging was removed.
- integration/dsh now reports 65 collected / 65 passed / 0 failed.
- knowledge_curator remains 127 passed / 0 failed.
- DSH source remained clean.
- official/raw adapter and direct Web scaffold model paths remain known-good from prior phases.
- real minimal Agent still fails before any knowledge_curator tool call.
- inventory-off still reportedly fails; this continues to make package inventory a weaker suspect.

## Blocking review findings

### R3.2.3-01 — P2/P3 did not prove a real SessionId-backed session
lane323_probes.e2e.ts calls web.ctx.session?.create?.() or web.ctx.sessions?.create?.() without the required branded SessionId argument.
Pinned DSH public usage is ctx.sessions.create(SessionId('...')).
If creation fails, the code leaves sessionId as null and still executes P2/P3.
A null/stringified-null request is not equivalent to a live Agent Session and does not exercise session-aware extensions against a registered real session.

### R3.2.3-02 — P4a did not exercise Session.toolHistory()
lane323_p4_envelope.e2e.ts assigns toolHistory = [] rather than reading a real Session.toolHistory().
Therefore P4a PASS does not eliminate the actual AgentLoop toolHistory dimension.

### R3.2.3-03 — P4c did not mark the request
The code tests typeof llm.markAgentLoopRequest === 'function'.
In pinned DSH, markAgentLoopRequest is exported from @deepseek-ai/dsh-llm; it is not a method on the LlmRuntime instance.
Therefore P4c can report PASS while results.P4c_marked is false. That does not eliminate the loop-marker dimension.

### R3.2.3-04 — planned exact Agent first-turn shape P4d is absent
The Phase 3.2.3 plan required a final exact first-turn system/user derivation-shape probe.
No P4d implementation exists.

## Consequence
The report statement that PreparedCall/sessionId/toolHistory/freeze/loop-marker were all independently proven PASS is too strong.
The only safe conclusion remains:
DSH 0.2 raw provider/direct LLM works, but a real AgentLoop request path fails.
knowledge_curator remains excluded as the immediate cause because minimal/bare Agents fail before its tool call.

## Stronger next method
Do not reconstruct the loop envelope by hand first.
Capture the exact real loop-built GenerateOptions object at a test-only llm/stream waterfall listener before downstream dispatch.
Record only sanitized structure/hash facts, retain the exact object in memory, and after the failing Agent settles replay that same envelope through a fresh PreparedLlmCall while the Agent/Session is still registered.

This produces a decisive split:
- exact captured envelope replay FAIL => request/envelope or session-aware downstream behavior;
- exact captured envelope replay PASS => AgentLoop timing/lifecycle/waterfall context rather than envelope content.

Then bisect clones of the captured request by removing one field at a time, reapplying the real exported markAgentLoopRequest when required.

## Next
Proceed to Phase 3.2.4 — exact loop-request capture and replay.
Do not begin §6/§7 and do not change knowledge_curator core/MCP/product preset.