# Phase 5.0-R3 Executor Report — Final Lifecycle Retrieval Correctness

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.0-R3  

---

## 1. Scope

仅修复 R2 review 的 2 个 correctness bug。未改 §6 ranking/guard、R1/R2 已接受部分、CG-018、公共 MCP。未启 Phase 5.1。

## 2. R3-A all-candidate exhaustion detection

**PASS**

删除了错误的 `eligible_ids == prev_eligible_ids` 停止条件。改为跟踪 **全部 backend candidate identities**：

```
depth=50  → candidates #1..#50
depth=100 → candidates #1..#100  (即使 eligible=0，仍继续)
depth=200 → …
```

停止条件（仅此两种才是 exhaustion）：

| 条件 | 含义 |
|---|---|
| `returned_count < requested_depth` | backend 已耗尽 |
| 扩张后 **candidate identity set 不再增长** | backend 已耗尽 |

## 3. #101 eligible recovery

**PASS**

- ≥110 candidates
- #1–#100 全部 lifecycle-ineligible
- #101 eligible
- `top_k=1` → 返回 **GOOD-101**
- backend depth 请求确认 **> 100**

## 4. Capped backend termination

**PASS** — capped backend 重复同一批 identities → 判定 exhaustion，终止。

## 5. Resource guard fail-closed

**PASS**

`_MAX_STEPS` 仅作资源保护。若触达时 candidate 仍在增长且未达 target：

→ 抛出 `EligibilitySearchLimitError`（"eligibility search limit reached"）

**不**静默返回不完整结果，**不**伪装成 exhaustion。

## 6. R3-B allowed_ref assertion filtering

**PASS**

`allowed_ref_ids` 路径不再绕过 assertion lifecycle：

1. document 级 prefilter 有限 allowed_ref_ids  
2. **仍然 wrap `_EligibilityFilteredPort`** → 检查 `chunk.assertion_id`  
3. progressive fill 在 allowed universe 内继续

回归：`allowed_ref_ids=["REF-A"]`，A1 superseded / A2 active，backend rank #1=F1/A1，#2=F2/A2 → `top_k=1` 返回 **F2/A2**，不返回 A1，不空结果。

## 7. Historical allowed_ref retrieval

**PASS** — 同一 lifecycle history，`at_version_id=V1` + `allowed_ref_ids=["REF-A"]` → 可再次返回 A1。

## 8. Empty allowed_ref safety

**PASS** — `allowed_ref_ids=["REF-RETRACTED"]` 经 document prefilter 变空集 → **0 results**，不泄漏其他 ref。

## 9. 测试

```text
knowledge_curator: 358 passed / 0 skipped / 0 failed  (baseline 351 + 7)
integration/dsh:    90 passed / 0 failed
```

## 10. Public contracts changed?

**NO**

## 11. CONTRACT_GAPS

**无新增/修改**
