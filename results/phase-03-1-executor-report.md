# Phase 3.1 Executor Report — Python MCP Adapter + Live DSH MCP Bridge

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-28  
**Phase:** 3.1  
**Executable DSH baseline:** `deepseek-harness-sdk==0.1.5rc1` / `runtime-bin==0.1.5rc1`  
**Scope:** 仅 Python MCP adapter + live DSH MCP bridge。未实现 Agent Preset / §6 / §7。

---

## 1. MCP SDK version

```text
mcp == 2.2.0
（v2 API: from mcp.server import MCPServer）
```

未手写 JSON-RPC；使用官方 `MCPServer.run_stdio_async` / `ClientSession`+`stdio_client`。

## 2. MCP tools

| Tool | 角色 |
|---|---|
| `curate_assertion_set` | 唯一业务工具：AssertionSet JSON → CurationReport |
| `knowledge_curator_health` | integration diagnostic only |

**未暴露** `commit_to_production_kb`（§5.4 保持内部）。

DSH 公开工具名：`mcp__knowledge_curator__curate_assertion_set`

## 3. Codec design

`knowledge_curator/mcp_server/codec.py`：
- JSON ↔ 现有 temporary compatibility dataclasses
- 拒绝 malformed / 非法 enum（confidence/action/value_type/claim_type）
- 不自动填补 completeness 应判缺失的字段（如 locator）
- 确定性序列化，无 Python repr / traceback 泄漏

## 4. Direct MCP contract tests

- in-process `list_tools` / `call_tool`
- subprocess stdio：`python -m knowledge_curator.mcp_server`
- MCP 结果 == 直接 `KnowledgeCurator.curate()` 结果
- malformed / invalid enum → 结构化错误
- keyless，无需 API key

结果：**PASS**

## 5. DSH MCP client resolve (0.1.5rc1)

`--dump-config --patch` 接受 `@deepseek-ai/dsh-mcp-client` 行。
Patch 格式为 **top-level YAML/JSON array of loader patch entries**（首试 dict 被拒，已修正）。

`build_patch()` 在运行时注入 `sys.executable` 与 workspace，**未**把机器绝对 Python 路径写入仓库模板。

结果：**PASS**（plugin name resolve + overlay format）

## 6. Live tool discovery / call evidence

```text
DSH started:           yes
MCP server spawned:    yes (stdio python -m knowledge_curator.mcp_server)
tool discovered:       yes
tool called:           yes (tool_call_count >= 1)
expected tool name:    mcp__knowledge_curator__curate_assertion_set
tool result received:  yes
finish_reason:         completed
secret leak:           none
```

## 7. Deterministic expected vs observed

| 字段 | Expected (core) | Observed (MCP→model) |
|---|---|---|
| status | successful | successful |
| action | accept | accept |
| confidence | medium | medium |

最终模型回答：`status=successful / action=accept / confidence=medium` — 与 core 一致。

## 8. Test counts

```text
Phase 3.1 keyless (integration/dsh/tests):  35 passed / 0 failed
  - test_mcp_codec.py            8
  - test_mcp_server_contract.py  7
  - test_dsh_mcp_patch.py        5
  - test_dsh_config.py           7
  - test_dsh_smoke_contract.py   8
knowledge_curator tests:                  127 passed / 0 failed
Phase 3.0 keyless DSH:                    15 passed / 0 failed
```

Live test 单独执行，普通 pytest 不需要 `DEEPSEEK_API_KEY`。

## 9. Live smoke status

**LIVE_MCP_BRIDGE_PASS**

Artifact: `results/phase-03-1-dsh-mcp-smoke.json`

## 10. Version skew

```text
executable:  0.1.5rc1 (sdk + runtime-bin)
reviewed:    0.2.0-rc.1 / 4878cdabd87d4041bdaff61d04c966883b9fd07a
mcp python:  2.2.0
CG-015:      保持 open
```

未混装 0.2.0 包；Agent Preset 未触碰。

## 11. CONTRACT_GAPS

**无新增。** CG-001/CG-014/CG-015 保持不变。

## 12. Public contracts changed?

**NO**

## 13. Implementation commit SHA

```
implementation commit: <pending>
```
