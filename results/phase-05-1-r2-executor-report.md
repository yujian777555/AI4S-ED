# Phase 5.1-R2 Executor Report — Lineage & Registry Integrity Closure

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.1-R2  

---

## 1. Scope

仅修复 R1 review 的 5 个 lineage/registry integrity blocker。未启 Phase 5.2，未改 normalization / DOI-stable precedence / title-only review gate / §7 lifecycle core。

## 2. R2-A replay explicit-lineage consistency

**PASS**

exact replay（同 ref+fingerprint）前先校验 explicit lineage：

| 提供字段 | 校验 | 违反 |
|---|---|---|
| `explicit_work_id` | 必须存在且 == existing.work_id | IDENTITY_CONFLICT |
| `explicit_prior_version_id` | 必须存在且 prior.work_id == existing.work_id | IDENTITY_CONFLICT |
| `explicit_relation` (non-NONE) | P2J 等 relation 材料兼容 | IDENTITY_CONFLICT |

兼容 lineage → 仍 EXACT_REPLAY；矛盾 → IDENTITY_CONFLICT，不 mutate registry。

## 3. R2-B relation-only validation

**PASS**

`explicit_relation != NONE` 即进入 explicit lineage 分类，即使无 work/prior：

| relation-only 请求 | 结果 |
|---|---|
| P2J / REVISION_OF / CORRECTED_VERSION 无 prior | IDENTITY_CONFLICT |
| EXPLICIT_SAME_WORK 无 work 且无 prior | IDENTITY_CONFLICT |

不再静默忽略 explicit_relation。

## 4. R2-B explicit NONE fail-closed

**PASS**

`VersionRelation.NONE` + work/prior → **IDENTITY_CONFLICT**（不生成 relation=NONE 的 SAME_WORK_NEW_VERSION）。

`explicit_relation=None`（omitted）才走默认。

## 5. Omitted-relation defaults

**PASS**

| 条件 | 默认 relation |
|---|---|
| omitted (None) + prior | REVISION_OF |
| omitted (None) + work only | EXPLICIT_SAME_WORK |

回归区分 `None` vs `VersionRelation.NONE`。

## 6. Registry work integrity

**PASS** — `append_source_version` 要求 `work_id` 已存在；不自动造 Work。orphan append → ValueError。

## 7. Registry prior integrity

**PASS**

- `prior_source_version_id` 非 null → prior 必须存在
- `prior.work_id == record.work_id`
- cross-work prior → reject

## 8. Append atomicity

**PASS** — work/prior referential check 在所有 index mutation 之前。失败 append 后 registry 完全不变。

## 9. 测试

```text
knowledge_curator: 406 passed / 0 skipped / 0 failed  (baseline 392 + 14)
integration/dsh:    90 passed / 0 failed
```

覆盖：replay 矛盾 work/prior、兼容 replay、relation-only P2J/REVISION/CORRECTED、explicit NONE+prior/work、omitted defaults、orphan/missing/cross-work prior append、失败原子性。

## 10. Public contracts changed?

**NO**

## 11. CONTRACT_GAPS

**无新增/修改**
