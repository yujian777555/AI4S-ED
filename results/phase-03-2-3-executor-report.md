# Phase 3.2.3 Executor Report — PreparedCall / Session-Aware Isolation

**Executor:** MiMo  
**Date:** 2026-09-29  
**DSH commit:** `4878cdabd87d4041bdaff61d04c966883b9fd07a` / `0.2.0-rc.1`

---

## 1. Diagnostic hygiene

**PASS** — 已删除 request bodyPreview；仅保留 sanitized 事实。

## 2. Exact test counts

```text
pytest integration/dsh/tests --collect-only -q  →  65 tests collected
pytest integration/dsh/tests -q                →  65 passed / 0 failed / 0 skipped
pytest knowledge_curator/tests -q              →  127 passed / 0 failed
```

## 3. C0–P4 结果

| Probe | 内容 | 结果 |
|---|---|---|
| C0 | direct `ctx.llm.stream` PONG | **PASS** |
| P1 | `PreparedCall.stream` 无 session | **PASS** |
| P2 | direct stream + 真实 sessionId | **PASS** |
| P3 | PreparedCall + sessionId | **PASS** |
| P4a | + toolHistory | **PASS** |
| P4b | deep-freeze message shape | **PASS** |
| P4c | loop-marker 维度 | **PASS** |
| 真实 minimal Agent | full AgentLoop followup | **FAILED**（5× retry, TRANSPORT） |

## 4. plugin-package-inventory-deepseek toggle

- session-log-deepseek 在 scaffold 中为 **disabled**（已确认）
- inventory 用 `disabled: true` overlay 成功关闭（dump-config 验证）
- **inventory-off 后 minimal Agent 仍 FAIL** → inventory **不是**根因

## 5. llm/stream observer facts

Agent 不走 `ctx.llm.stream` 公开方法（spy 为空），而走 PreparedCall → `streamWithRegistration` 内部路径。已用 P1–P4 合成维度逐项排除。

## 6. blocking_subsystem

**DSH 0.2 AgentLoop 完整 request-assembly/dispatch envelope**

单独维度（PreparedCall / sessionId / toolHistory / freeze / loop-marker / inventory）均 PASS；真实 AgentLoop 组合路径 FAIL。与 knowledge_curator 无关。

normalized failure: `TRANSPORT` / `DeepSeek Messages transport failed` / EMPTY_RESPONSE-class retries

## 7. DSH source clean

**YES**

## 8. CG-015

**OPEN** — source-pinned 0.2 mounted knowledge-curcor 严格 MCP round-trip 未完成。

## 9. Public contracts changed?

**NO**

## 10. CONTRACT_GAPS

**无新增**

## 11. Implementation SHA

```
implementation commit: f54394a4b7a864a61fb18ce077aacabcb4ade920
```
