# Phase 3.2.2 Executor Report — DSH 0.2 Live Transport Isolation

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-29  
**Phase:** 3.2.2  
**DSH commit:** `4878cdabd87d4041bdaff61d04c966883b9fd07a`  
**DSH version:** `0.2.0-rc.1`

---

## 1. Harness portability cleanup

**PASS**

- 移除 `C:/Users/...`、`C:/dsh-src` 等 committed 默认路径；从脚本位置推导或要求 `DSH_SRC` env
- 删除 `AI4S_KC_PYTHON ?? process.execPath`；缺失时 fail-fast（Node ≠ Python）

## 2. Lane results

| Lane | 内容 | 结果 |
|---|---|---|
| A upstream adapter | 官方 `runtime.e2e.ts` streams raw chunks + tool-call round trip | **PASS** |
| A diagnostic fallback | deepseek-flash PONG probe | **NOT_RUN**（A 已 PASS） |
| B scaffold direct llm | `ctx.llm.stream` async iterable → PONG | **PASS** |
| C baseline Agent | minimal preset Agent followup → PONG | **FAILED** |
| D kc plain Agent | knowledge-curator 无工具 PONG | **NOT_RUN**（C 失败） |
| E kc MCP round-trip | tool/call + A==B==C | **NOT_RUN**（C 失败） |

## 3. blocking_layer

**AgentLoop / request assembly**

### 诊断证据

| 探针 | 结果 |
|---|---|
| 官方 adapter raw stream | PASS |
| 官方 adapter tool-call | PASS |
| scaffold `ctx.llm.stream`（无/大 system/tools=0） | PASS（PONG） |
| agent-scope `llm.stream` 直接调用 | PASS（PONG） |
| minimal-preset Agent `followup` | FAIL：`DeepSeek Messages transport failed` / `TRANSPORT` ×5 retry |
| bare preset（0 tools）Agent | FAIL：同样 TRANSPORT — 与 tool schema 无关 |
| `globalThis.fetch` spy | 空（Agent 未走全局 fetch） |
| `ctx.llm.stream` spy | 空（AgentLoop 未调用该 API） |

结论：模型/adapter/llm 层正常；**AgentLoop 自身的 request 路径**产生 TRANSPORT 失败。与 knowledge_curator 无关。

## 4. exact tool/call & result

```text
tool/call count: 0
tool/result count: 0
```

## 5. A / B / C

NOT_RUN（Lane E 未执行）

## 6. DSH source clean

**YES** — 前后 `git status --porcelain` 为空。

## 7. Test counts

```text
integration/dsh: 64 passed / 0 failed  （60 既有 + 4 新 keyless）
knowledge_curator: 127 passed / 0 failed
```

## 8. CG-015

**OPEN** — blocking_layer = AgentLoop / request assembly

## 9. Public contracts changed?

**NO**

## 10. CONTRACT_GAPS

**无新增**（blocker 属于 DSH 0.2 AgentLoop 运行时行为，非跨团队契约缺口；已在 isolation JSON 记录）

## 11. Implementation SHA

```
implementation commit: b14a11795adf8d9e131043707840b8b738ebb8fd
```
