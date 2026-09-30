# Phase 5.0-R1 Executor Report — Lifecycle Recovery & Retrieval Hardening

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.0-R1  

---

## 1. Scope

仅修复 Phase 5.0 review 的 5 个 blocker。未改 §6 ranking/guard，未启 Phase 5.1，未加 crawler / 外部事件总线 / 公共 MCP 变更。

## 2. R1-A crash-safe retry / resume

**PASS**

`apply_retraction` / `apply_revision` 现在区分：

| 状态 | 行为 |
|---|---|
| FINALIZED（已 bind + 事件齐全） | 幂等返回，不重复 publish/event |
| STAGED / PARTIAL | **resume**：确定性 manifest hash 复用 snapshot/version，补 bind，补齐 outbox 事件 |
| CONFLICT（同 id 不同 material） | fail closed |

失败矩阵（每种：首次失败 → retry → 唯一语义版本 + bind + outbox 完整且不重复 + 可见性正确）：

| 注入点 | 结果 |
|---|---|
| fail before `version.create_snapshot` | PASS |
| fail after `version.create_snapshot` | PASS |
| fail before `version.publish` | PASS |
| **fail after `version.publish`** | **PASS**（split-brain 被 retry 治愈） |
| fail after bind / before outbox complete | PASS（补事件，不重复版本） |

## 3. R1-B base-version validation

**PASS**

- 显式 `base_version_id` 必须存在且 published
- 新发布要求 base == current version
- 不存在 / stale 非 current → 拒绝
- rollback 后被 rollback 成 current 的版本可作为新 revision base
- **resume/replay 路径不强制 base==current**（否则 post-publish retry 无法恢复）

## 4. R1-C strict material idempotency

**PASS**

material equality 覆盖：

- DocumentLifecycleRecord：ref/status/reason/fingerprint/affected/evidence/rationale/revision/trace/provenance
- AssertionLifecycleRecord：assertion/ref/status/lifecycle/revision/superseded_by
- LifecycleEvent：type/ref/affected/old-new version/lifecycle/revision/trace/provenance/schema/payload

忽略仅 `created_seq` / `delivered`（transport/staging 簿记）。

冲突回归：同 event_id 改 payload、同 lifecycle_id 改 evidence、同 assertion identity 改 supersede target → 全部 fail closed。

## 5. R1-D retrieval pre-cutoff filtering

**PASS**

`_EligibilityFilteredPort` 现在 **expand 后再过滤**（请求 `top_k*10` 量级），不可在 backend top-k 截断后再丢弃，避免 under-fill。

回归：`top_k=1`，rank#1=已撤稿 REF-A，rank#2=active REF-B → 最终返回 **REF-B**（非空）。

## 6. R1-E historical retrieval E2E

**PASS**

`EvidenceRequest.at_version_id`（INTERNAL）贯通到 lifecycle eligibility。

真实 E2E（经 `EvidenceRetrievalService.retrieve()`，非直接 visibility helper）：

1. V1 active REF-A  
2. V2 retract REF-A  
3. current retrieval 不含 REF-A  
4. `at_version_id=V1` retrieval **返回 REF-A**

## 7. 测试

```text
knowledge_curator: 344 passed / 0 skipped / 0 failed  (baseline 329 + 15)
integration/dsh:    90 passed / 0 failed
```

## 8. Public contracts changed?

**NO** — `at_version_id` 为 INTERNAL request 字段；无 MCP/公共 schema 变更。

## 9. CONTRACT_GAPS

**无新增/修改**
