# Phase 4.3.2 Executor Report — Strict Live Validation Harness Closure

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 4.3.2  

---

## 1. Scope

本轮**只改 validation harness**，未修改：

- EvidenceRetrievalService / ClaimGuardService 业务语义
- Phase 4.1/4.2 retrieval
- MCP business contract
- Agent / preset 身份

## 2. 交付物

- `integration/dsh/lane325_kc_evidence_roundtrip.e2e.ts` — 严格 live E2E（禁止 soft-pass）
- `integration/dsh/direct_evidence_ref.py` — direct reference（retrieve + validate）
- `integration/dsh/run_lane325.py` — 独立 marker→status 映射 + baseline control
- `integration/dsh/vitest.phase432.config.ts` / `vitest.lane324.config.ts`
- `integration/dsh/tests/test_phase432_runner_classification.py` — 7 项 keyless 分类测试
- `results/phase-04-3-2-dsh-evidence-smoke.json`

## 3. strict live harness

**PASS**

- live prerequisite 存在时，`retrieve_evidence` 0 tool/call → **Vitest FAILED**（`throw new Error`），不再 return 成功
- 分离 marker，仅在对应断言通过后打印：
  - `LANE325_DISCOVERY_OK=1`
  - `LANE325_RETRIEVE_TOOLCALL_OK=1` / `LANE325_RETRIEVE_RESULT_OK=1` / `LANE325_RETRIEVE_IDENTITY_MATCH=1`
  - `LANE325_VALIDATE_TOOLCALL_OK=1` / `LANE325_VALIDATE_RESULT_OK=1` / `LANE325_VALIDATE_POLICY_MATCH=1`
  - `LANE325_LIVE_COMPLETE=1`
- tool/result 严格按 `sourceEventSeqs` / `callId` 绑定；structured parse 失败即 FAIL
- direct-vs-DSH 比较（`direct_evidence_ref.py`）在 E2E 内真实执行，不是假设
- 最多 3 次 live attempt，每次记录 attempt 号 / event types / calls / results

## 4. baseline mounted DSH control

**EMPTY_RESPONSE**

| 项 | 值 |
|---|---|
| lane | `lane324_kc_roundtrip.e2e.ts` |
| composed preset | knowledge-curator |
| tool_visible | true |
| tool_call_count | **0** |
| tool_result_count | 0 |
| event tail | `assistant/attempt` → `turn/end`（无 assistant text / tool/call） |

## 5. mounted DSH Agent discovery

**PASS**

mounted Agent schema 含：

```
mcp__knowledge_curator__curate_assertion_set
mcp__knowledge_curator__knowledge_curator_health
mcp__knowledge_curator__retrieve_evidence
mcp__knowledge_curator__validate_retrieved_claims
```

## 6. live evidence / validate

| 项 | 状态 | 证据 |
|---|---|---|
| retrieve_evidence tool call | **NOT_RUN_ENV**（外部阻塞） | 3 attempts，calls=0 |
| retrieve_evidence linked result | **NOT_RUN_ENV** | 无 tool/call 可链 |
| direct-vs-DSH evidence identity | **NOT_RUN_ENV** | 无 DSH tool result 可比 |
| validate_retrieved_claims tool call | **NOT_RUN_ENV** | retrieve 未过，未进入 validate |
| validate_retrieved_claims linked result | **NOT_RUN_ENV** | 同上 |
| direct-vs-DSH policy | **NOT_RUN_ENV** | 同上 |

## 7. classification

**C_EXTERNAL_RUNTIME_UNAVAILABLE** → 最终报告 **LIVE_VALIDATION_BLOCKED_EXTERNAL**

- baseline（已通过的 curate_assertion_set）与 evidence lane 在同一时间窗口内均为 EMPTY_RESPONSE / 0 tool/call
- 属 DeepSeek/provider/runtime 外部波动，非 evidence 工具回归
- 按约定：不改 §6 core code 追波动；也不把 evidence live 记为 PASS

## 8. runner 独立映射

`run_lane325.py` 每个字段由**自己的 marker** 决定：

- 仅有 retrieve marker → validate **不会** PASS
- 缺 identity marker → identity **不会** PASS
- Vitest returncode=0 **不**等于 semantic live PASS
- 无 credential → discovery PASS / live NOT_RUN_ENV

## 9. secret hygiene

credential 从 `~/.dsh/.credentials.yaml` 注入 env，输出全程 redact；`secret_leaked=false`。

## 10. 测试

```text
knowledge_curator: 311 passed / 0 skipped / 0 failed
integration/dsh:    90 passed / 0 failed   (baseline 83 + 7 classification)
```

新增 keyless 覆盖：

- retrieve marker 不能推出 validate PASS
- 缺 identity marker → identity 不 PASS
- prerequisite 存在但 0 toolcall → failed attempt
- 无 credential → NOT_RUN_ENV
- baseline+evidence 同时 EMPTY_RESPONSE → external runtime unavailable

## 11. Public contracts changed?

**NO**

## 12. CONTRACT_GAPS

**无新增**

## 13. 给 Planner

核心 §6 保持冻结。live acceptance 被外部 runtime 阻塞。是否带“外部验证阻塞”封板由 Planner 决定。
