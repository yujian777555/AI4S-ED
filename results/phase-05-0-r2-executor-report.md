# Phase 5.0-R2 Executor Report — Exhaustive Eligibility & Assertion-Level Filtering

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.0-R2  

---

## 1. Scope

仅关闭 R1 review 的 3 个 blocker。未改 §6 ranking/guard、R1 crash-recovery、CG-018、公共 MCP。未启 Phase 5.1。

## 2. R2-A progressive lifecycle filtering

**PASS**

替换固定 `max(top_k*10, 50)` 为渐进扩张：

```
depth = 50 → 100 → 200 → … (×2，最多 12 步安全上限)
```

停止条件：

| 条件 | 含义 |
|---|---|
| eligible ≥ target | 已拿到足够候选 |
| `returned < requested_depth` | backend exhaustion |
| 扩张后 eligible ids 不再增长 | backend exhaustion |

不重排，保留 backend rank / raw score；保留 query.text / level / allowed_ref_ids / subquestion_id。

## 3. Deep-rank recovery (>50)

**PASS**

- ≥60 candidates
- rank #1–#55 全部 ineligible（retracted REF-BAD）
- rank #56 eligible
- `top_k=1` → 最终返回 **GOOD-56**

并验证 depth 请求确实超过 50（非固定 10×）。

## 4. Backend exhaustion termination

**PASS**

- 全部 ineligible → 返回 `[]`，调用次数有界（≤12）
- capped backend 重复同一批 candidate → 终止，不无限扩张

## 5. R2-B same-history historical retrieval E2E

**PASS**

使用 **同一个** VersionStore + LifecycleStore + InMemoryLifecycleVisibility：

1. V1 active REF-A  
2. V2 retract REF-A（记录在同一 store）  
3. `retrieve(at_version_id=None)` → REF-A **absent**  
4. `retrieve(at_version_id=V1)` → REF-A **present**  
5. 断言 retraction record 在两次查询后仍在 store 中  

不再新建空 store。

## 6. R2-C assertion-level retrieval filtering

**PASS**

`_is_eligible` 现在两层检查：

1. `document_eligibility(chunk.ref_id, at_version_id)`  
2. 若 `chunk.assertion_id is not None` → `assertion_eligibility(...)`

coarse summary（assertion_id=None）只查 document。**不**从 chunk_id/payload 猜 assertion_id（有回归证明）。

## 7. Corrigendum current/historical

**PASS**

| 场景 | 结果 |
|---|---|
| V2 corrigendum：A1 SUPERSEDED，A2 不变，doc ACTIVE | — |
| current retrieval | F1/A1 不返回；F2/A2 返回 |
| `at_version_id=V1` | F1/A1 再次返回 |
| document coarse summary | 仍 eligible（doc 未撤稿） |

## 8. Assertion training eligibility

**PASS**

| 状态 | eligible_for_training |
|---|---|
| A1 superseded（current） | false |
| A2 unchanged（current） | true |
| A1 at V1 historical | true |

未实现 training exporter。

## 9. 测试

```text
knowledge_curator: 351 passed / 0 skipped / 0 failed  (baseline 344 + 7)
integration/dsh:    90 passed / 0 failed
```

## 10. Public contracts changed?

**NO**

## 11. CONTRACT_GAPS

**无新增/修改**
