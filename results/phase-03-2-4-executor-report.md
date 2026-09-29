# Phase 3.2.4 Executor Report — Exact Loop Request Replay & MCP Round-Trip

**Executor:** MiMo  
**Date:** 2026-09-29  
**DSH commit:** `4878cdabd87d4041bdaff61d04c966883b9fd07a` / `0.2.0-rc.1`

---

## 1. Exact captured request

通过 `ctx.on('llm/stream', ..., { prepend: true })` + `isAgentLoopRequest`（从 `@deepseek-ai/dsh-llm` 导出）捕获真实 AgentLoop request。`markAgentLoopRequest` / `SessionId` / `toolHistory` 均使用真实 API。

## 2. Key discovery

**minimal Agent 本轮稳定 PASS**（0 retries, `assistant/message` 正常）。先前 EMPTY_RESPONSE 为瞬态/接口波动，非确定性 AgentLoop 缺陷。

## 3. Probes (real APIs)

| Probe | 结果 |
|---|---|
| P2 real SessionId | PASS |
| P4 Session.toolHistory present | true |
| P4 markAgentLoopRequest | true (isAgentLoopRequest verified) |
| P4 marked stream | PASS |

## 4. knowledge-curator strict MCP round-trip

| 项 | 值 |
|---|---|
| composed_preset | knowledge-curator |
| tool_visible | true |
| tool/call count | **1** |
| tool/result count | **1**（linked） |
| A direct core | successful / accept / medium |
| B tool result | successful / accept / medium |
| C final response | successful / accept / medium |
| **A == B == C** | **YES** |

## 5. blocking_subsystem

**null** — source-pinned 0.2 mounted knowledge-curator Agent 完成严格 MCP round-trip。

## 6. DSH source clean

**YES**

## 7. Test counts

```text
pytest integration/dsh/tests --collect-only -q  →  65 collected
pytest integration/dsh/tests -q                →  65 passed / 0 failed
pytest knowledge_curator/tests -q              →  127 passed / 0 failed
```

## 8. CG-015

**CLOSED** — 满足全部条件：0.2 source build、profile/bundle、preset activation、mount、persona、MCP tool、真实 DeepSeek turn、exact tool/call、tool/result、A==B==C、DSH clean。

## 9. Public contracts changed?

**NO**

## 10. CONTRACT_GAPS

**无新增**

## 11. Implementation SHA

```
implementation commit: <pending>
```
