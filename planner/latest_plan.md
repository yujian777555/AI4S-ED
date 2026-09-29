# Phase 3.2.4 Plan — Capture and Replay the Exact DSH 0.2 AgentLoop Request

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Goal
Correct the invalid Phase 3.2.3 probes and isolate the real DSH 0.2 failure using the exact request object produced by AgentLoop.

Keep frozen:
- knowledge_curator §5 core
- MCP bridge/tool semantics
- DSH product bundle/preset/persona
- source pin 4878cdabd87d4041bdaff61d04c966883b9fd07a
- no §6/§7

## 1. Fix imports and typed Session construction
Import from the pinned runtime package:
- SessionId
- markAgentLoopRequest
- isAgentLoopRequest
- createUserMessage
using the actual exported package paths.

Create real sessions only as:
const session = ctx.sessions.create(SessionId('phase324-probe-...'))

Assert:
- ctx.sessions.get(session.id) === session
- sessionId is non-null and non-empty.

Never continue a session-aware probe if real Session creation failed.

## 2. Correct P2/P3
P2: ordinary ctx.llm.stream with sessionId=session.id.
P3: fresh ctx.llm.prepareCall(...), then prepared.stream(...) with sessionId=session.id.

Record whether the registered Session is visible through ctx.sessions.get(session.id) during dispatch.

## 3. Correct toolHistory probe
Use the actual object returned by:
session.toolHistory()

Do not substitute [].
Record only sanitized structural facts: presence, number of tools/history entries if exposed, never full tool payloads.

## 4. Correct loop marker probe
Use the actual exported function:
markAgentLoopRequest(request)

Assert before dispatch:
isAgentLoopRequest(request) === true

Also run an otherwise identical unmarked control.

## 5. Capture the exact real AgentLoop request
Before sending the minimal Agent PONG turn, register a test-only prepend listener:
ctx.on('llm/stream', (options, next) => { ...; return next() }, { prepend: true })

When isAgentLoopRequest(options) is true for the target Agent session:
- retain the exact options object in memory;
- record a sanitized fingerprint only.

Fingerprint fields:
- provider/model/reasoning/maxTokens
- sessionId present and equality to target Agent id
- Object.isFrozen(options)
- Object.isFrozen(options.messages)
- message role sequence
- content block type sequence per message
- message count
- tools count and tool-name hash only
- toolHistory present
- purpose present/absent
- own top-level keys sorted
- SHA-256 of a redacted structural projection, not full prompt text.

Do not log full messages, system prompt, tool schemas, request body or secrets.

## 6. Let the real minimal Agent fail normally
Run the known minimal Agent PONG once.
Require the listener actually captured exactly one first-attempt loop request before using its evidence.
Record retries and normalized failure.

## 7. Exact-object replay after failure
Before disposing the Agent or Session:
- create a fresh PreparedLlmCall using the captured request's provider/model/reasoning/maxTokens;
- call prepared.stream(capturedOptions) using the SAME captured object identity.

Because PreparedLlmCall is one-shot, use a fresh prepareCall.

Interpretation:
- exact replay FAIL => the captured request/session-aware downstream behavior itself is sufficient to reproduce failure.
- exact replay PASS => the envelope itself is valid; failure depends on AgentLoop temporal/lifecycle context or another first-dispatch side effect.

Record this as exact_captured_replay.

## 8. If exact captured replay FAILS: clone-and-bisect
Build detached variants from the captured object. Use fresh PreparedCall each time.
Do not mutate the frozen captured object.

Variants, one dimension at a time:
A. same content but remove loop marker by cloning only.
B. clone then reapply real markAgentLoopRequest.
C. remove sessionId.
D. keep sessionId, remove toolHistory.
E. keep sessionId/toolHistory, remove tools.
F. preserve tools but replace messages with one PONG user message.
G. preserve exact messages but remove system messages only.

After every clone:
- ensure call-config fields match fresh prepared.config;
- record marker true/false;
- record Session registration state.

Stop once a single field transition flips FAIL -> PASS, then reproduce once.

## 9. If exact captured replay PASSES: isolate AgentLoop temporal side effects
Do not keep altering request content.
Compare:
- first AgentLoop dispatch through the captured request
- immediate post-failure fresh prepared replay of the same object.

Check only DSH-owned runtime state:
- whether DeepSeek request extensions produced acceptance side effects before failure;
- Session events added before retry;
- request/header/context events;
- retry listener activity;
- signal aborted state;
- prepared adapter generation identity where observable.

Test one additional short-circuit listener that captures the real loop request and, instead of next(), dispatches an equivalent fresh prepared call outside the loop only if this can be done without recursion. If unsafe, do not force it.

## 10. Inventory toggle
Keep the prior inventory-off observation only as supporting evidence.
Do not spend more live calls on it unless exact capture shows plugin inventory-specific data is the flip dimension.

## 11. Tests
Run exact:
pytest integration/dsh/tests --collect-only -q
pytest integration/dsh/tests -q
pytest knowledge_curator/tests -q

Add keyless tests that fail if:
- a session-aware probe uses null/undefined sessionId;
- toolHistory is hard-coded as [];
- loop marker probe does not assert isAgentLoopRequest(request) true;
- exact-capture artifact lacks marker/session/freeze evidence.

## 12. Artifact
Create results/phase-03-2-4-exact-loop-request.json.

Required fields:
- upstream_commit
- c0/p1/p2/p3 corrected results
- real_session_registered
- real_tool_history_used
- real_loop_marker_used
- captured_loop_request_count
- captured_structural_fingerprint
- minimal_agent_result
- exact_captured_replay
- bisection_results
- first_fail_to_pass_dimension
- normalized_failure
- dsh_source_clean
- secret_leaked=false
- blocking_subsystem
- cg015

## 13. Final product round-trip
Only if this round finds a deployment-supported fix that does not change AI4S product ownership/contracts:
re-run minimal Agent PONG -> knowledge-curator plain PONG -> strict MCP tool round-trip.

For final MCP:
A = direct core
B = linked source-pinned 0.2 tool/result
C = final source-pinned 0.2 response
Require A==B==C.

## 14. CG-015
Close only after the real source-pinned 0.2 mounted knowledge-curator Agent completes the strict MCP round-trip.
Otherwise keep OPEN with the exact DSH blocking subsystem.

## 15. Report/status
Create results/phase-03-2-4-executor-report.md.
On completion set status.json:
phase=3.2.4
actor=executor
state=executor_complete
latest_commit=actual implementation SHA
result_expected=results/phase-03-2-4-executor-report.md

Push main and stop.