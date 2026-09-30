# Phase 5.2-R2 Executor Report — FULL_REEXTRACT & Material Identity Closure

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.2-R2  

---

## 1. Scope

仅修复 Phase 5.2-R1 review 的 5 个 blocker。未启 Phase 5.3，未改 exact alignment / DELTA_SAFE / processed coverage / semantic slot / §7 lifecycle / §7.1 lineage。

## 2. R2-01 FULL_REEXTRACT transition semantics

**PASS**

`compute_transitions` 新增 FULL_REEXTRACT 分支：

- 全部 prior assertions → **ARCHIVE**（reason: `full_reextract_prior_archived`）
- 全部 new assertions → **ADDED**（reason: `full_reextract_new_added`）
- **无自动 SUPERSEDE**（即使 semantic slot 看似匹配）

segmentation_reset=True 回归：archive={A1,A2}，added={A1N,A3}，supersede={}，carried=[]。

## 3. R2-02 recursive scientific deep-copy

**PASS**

`_deep_copy_object` / `_deep_copy_condition` 使用 `copy.deepcopy` 复制 `ObjectValue.value` / `Condition.value`（可为 list/dict）。

回归：`old.object.value=[1.0,2.0]`、`old.conditions[0].value={"range":[1,2]}`，carry 后深层 mutate → old 完全不变。mutation 前 `semantic_payload_hash(new) == semantic_payload_hash(old)`。

## 4. R2-03 strict prior inventory

**PASS**

`RevisionPackageBuilder.build` 使用 **strict** `validate_prior_inventory`（不允许 unresolvable units）。malformed inventory（GHOST unit）→ fail closed，不走 FULL_REEXTRACT 掩盖。FULL_REEXTRACT 仅来自 `segmentation_reset=True` 等显式安全条件。

## 5. R2-04 side-labelled package material identity

**PASS**

package_id 现在分别包含：

- `prior_units`：unit_id / locator / kind / content_hash / prior_unit_id
- `new_units`：同上
- delta alignment：unchanged/modified pairs、added/removed unit ids、extraction_unit_ids
- target assertion：id / ref / semantic_payload_hash / provenance locator+sentence / **bound new unit_id**

回归：同 unit_id 交换 prior/new hash → 不同 package_id；同 assertion 绑定 U1 vs U2 → 不同 package_id。

## 6. R2-05 trace/provenance package identity

**PASS** — `trace_id` / `provenance_id` 纳入 package material。同 material 不同 trace → 不同 package_id；完全相同 → 同 package_id。

## 7. RevisionDraft FULL_REEXTRACT actions

**PASS** — archive_actions={A1,A2}，replacement_assertion_ids={A1N,A3}。

## 8. Lifecycle publication performed

**NO**

## 9. 测试

```text
knowledge_curator: 470 passed / 0 skipped / 0 failed  (baseline 461 + 9)
integration/dsh:    90 passed / 0 failed
```

## 10. Public contracts changed?

**NO**

## 11. CONTRACT_GAPS

**无新增/修改**
