# Phase 3.1.1 Executor Report — Strict DSH Tool-Call Evidence Closure

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-28  
**Phase:** 3.1.1  
**Base:** `f79eea915673048cce1c98a7d4abf56501d4db6c`  
**Scope:** 仅证据硬化。未改 MCP 架构 / §5 / Agent Preset / §6 / §7。

---

## 1. Exact matching tool/call count

```text
tool_call_count = 1
```

判定规则（0.1.5rc1 真实事件）：

```python
event["type"] == "tool/call" and event["data"]["name"] == EXPECTED_TOOL
```

已删除字符串启发式（prompt/catalog 中的工具名不再计数）。

## 2. Exact matching tool/result count

```text
matching_tool_result_count = 1
```

配对规则：`tool/result` 的 `sourceEventSeqs` 必须包含 `tool/call` 的 `seq`；
`sourceEventSeqs` 存在但不匹配 → 拒绝。

## 3. Sanitized call evidence

```json
{
  "seq": 10,
  "callId": "call_00_KD6i3fzAJUA2LUE2rsG60162",
  "name": "mcp__knowledge_curator__curate_assertion_set",
  "turn": 1,
  "step": 1,
  "arguments_hash": "9e2ebada9c6e47eb",
  "arguments_fixture_ref_id": "ED-2025-0042"
}
```

Result：`seq=11`, `sourceEventSeqs=["10"]`, `isError=false`。

## 4. Three-layer summaries

| Layer | status | action | confidence |
|---|---|---|---|
| A direct core | successful | accept | medium |
| B tool/result | successful | accept | medium |
| C final response | successful | accept | medium |

**A == B == C: YES**

## 5. Secret semantics

```json
"credential_available": true,
"secret_leaked": false
```

（`secret_present` 字段已移除。未序列化 credential。）

## 6. Test counts

```text
integration keyless (incl. new evidence tests): 49 passed / 0 failed
  - test_mcp_evidence.py          15
  - test_mcp_codec.py              8
  - test_mcp_server_contract.py    7
  - test_dsh_mcp_patch.py          5
  - test_dsh_config.py             7
  - test_dsh_smoke_contract.py     8  (approx shared count)
knowledge_curator tests:          127 passed / 0 failed
```

新增证据测试覆盖：prompt 含名不算、catalog 不算、unrelated 不算、exact 算 1、
linked result 配对、unlinked 拒绝、direct≠tool 失败、tool≠final 失败、artifact 无 secret。

## 7. Live smoke result

**LIVE_STRICT_MCP_SMOKE_PASS**

- DSH 0.1.5rc1 + MCP 2.2.0 + isolated DSH_HOME
- finish_reason: `completed`
- artifact: `results/phase-03-1-dsh-mcp-smoke.json`

## 8. MCP malformed-input error semantics

官方 `mcp==2.2.0` 高层 API：tool 内 `raise ToolError(...)` → 线上 `CallToolResult(isError=true)`。

已采用 **TOOL_ERROR_ISERROR_TRUE**（malformed/invalid enum 抛 `ToolError`）。

## 9. CONTRACT_GAPS

**无新增。**

## 10. Public contracts changed?

**NO**

## 11. Implementation commit SHA

```
implementation commit: 47bd16cc467905810246bf8049008d5748f97ecf
```
