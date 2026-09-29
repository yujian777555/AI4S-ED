# Phase 3.2.1 Executor Report — Preset Mount & Live Qualification

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-29  
**Phase:** 3.2.1  
**DSH commit:** `4878cdabd87d4041bdaff61d04c966883b9fd07a`  
**DSH version:** `0.2.0-rc.1`

---

## 1. Dependency policy fix

**PASS** — product `dsh/knowledge-curator/package.json` 已删除 `"*"` dependencies，保持 configuration-only。

## 2. Bundle install method

**PROFILE_PACKAGE_INSTALL**（`launchWebScaffold({ profile: { packages: [{ dir: PRODUCT_BUNDLE, enabled: true }] } })`）

## 3. Runtime preset activation

**PASS** — `ctx.agentPresets.list()` 含 `knowledge-curator`，`broken` 为空。

## 4. Preset broken?

**NO**

## 5. Mount tested / result

- tested: **YES**（官方 `agents.create({ setup: agentCtx => ctx.agentPresets.mount(agentCtx, 'knowledge-curator') })`）
- result: **PASS**
- composed preset: **knowledge-curator**

## 6. Persona visibility

**YES** — `live-deriveMessages` system prompt 含 `You are the AI4S-ED knowledge_curator...`

## 7. Tool visibility

**YES** — `ctx.tools.schemas(handle.agent)` 含 `mcp__knowledge_curator__curate_assertion_set`

## 8. DeepSeek live smoke

| 路径 | 结果 |
|---|---|
| 0.2 web scaffold (record) model turn | **EMPTY_RESPONSE**（5 次 retry 后仍空） |
| DeepSeekHarness + product MCP patch | **PASS**（A==B==C） |

0.2 scaffold 的 mount/persona/tool 均已证明；其模型调用返回空响应，tool/call 证据取自 DeepSeekHarness+MCP 参考路径。

## 9. Exact tool/call evidence（DeepSeekHarness 路径）

- tool/call: 1
- tool/result: 1（`sourceEventSeqs` 配对）
- name: `mcp__knowledge_curator__curate_assertion_set`

## 10. A / B / C

| | status | action | confidence |
|---|---|---|---|
| A direct core | successful | accept | medium |
| B tool result | successful | accept | medium |
| C final response | successful | accept | medium |

**A == B == C: YES**（DeepSeekHarness 路径）

## 11. DSH source clean

**YES** — 前后 `git status --porcelain` 均为空（临时 e2e 文件已删除）。

## 12. Test counts

```text
integration/dsh: 60 passed / 0 failed
knowledge_curator: 127 passed / 0 failed
```

## 13. CG-015

**OPEN** — 0.2 scaffold live tool/call 未完成（EMPTY_RESPONSE）；不满足全部关闭条件。

## 14. Public contracts changed?

**NO**

## 15. CONTRACT_GAPS

**无新增。**

## 16. Implementation SHA

```
implementation commit: <pending>
```
