# Phase 5.2-R1 Executor Report — Input/Material Integrity Hardening

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.2-R1  

---

## 1. Scope

仅修复 Phase 5.2 review 的 7 个 input/material integrity blocker。未启 Phase 5.3，未改 exact alignment / delta classification / semantic slot / §7 lifecycle / §7.1 lineage。

## 2. R1-01 deep-copy carry-forward

**PASS**

`carry_forward_unchanged` 现在 deep-copy：Subject / ObjectValue / Condition[]。Provenance 重建（locator=new unit locator，sentence 按值复制）。

回归：mutate new.subject.original_mention / new.object.value / new.conditions[0].value → old assertion 完全不变。替换 vacuous `or True` 为真实 semantic equality。

## 3. R1-02 manifest/inventory/batch identity validation

**PASS**

`RevisionPackageBuilder.build` 开头校验：

| 对象 | 字段 |
|---|---|
| prior manifest | source_version_id / ref_id / source_fingerprint |
| new manifest | source_version_id / ref_id / source_fingerprint |
| prior inventory | source_version_id / ref_id |
| delta batch | source_version_id / ref_id |

任一不一致 → fail closed。

## 4. R1-03 intent relation / prior KB binding

**PASS**

- `intent.relation == new.relation` 必须成立
- `prior.kb_version_id` + `prior.snapshot_id` 必须非空（lifecycle upgrade 基于已发布 prior）
- new 可未绑定（Phase 5.3 publication）

## 5. R1-04 prior inventory integrity

**PASS** — unique ids / ref match / unit mapping 存在 / 无 dangling map。unresolvable unit 允许触发 FULL_REEXTRACT（structural invalidity 仍 fail closed）。

## 6. R1-04/05 extraction completion coverage

**PASS**

`DeltaAssertionBatch.processed_unit_ids`（CG-020 internal）：

| mode | required processed scope |
|---|---|
| DELTA_SAFE | == plan.extraction_unit_ids |
| FULL_REEXTRACT | == all new manifest unit_ids |

processed unit 0 assertions = valid；unprocessed ≠ 0 assertions。

## 7. R1-05 FULL_REEXTRACT validation

**PASS** — batch structural 校验在**所有** mode 执行（unique ids / ref match / unit binding / no dangling / mapped unit ∈ processed）。FULL_REEXTRACT 无 carry-forward。

## 8. R1-06 material package identity

**PASS**

package_id 现在包含 scientific material：prior/new manifest identities + content hashes、processed_unit_ids、target assertion semantic_payload_hash + provenance、transitions。

回归：同 ID/action 但 value 2.0→3.0 → **不同 package_id**；相同 material → 同 package_id。

## 9. R1-07 complete draft replacement ids

**PASS**

`replacement_assertion_ids = sorted(unique(supersede_actions.values() + added_assertion_ids))`。旧 id 不出现。

## 10. Lifecycle publication performed

**NO**

## 11. 测试

```text
knowledge_curator: 461 passed / 0 skipped / 0 failed  (baseline 442 + 19)
integration/dsh:    90 passed / 0 failed
```

## 12. Public contracts changed?

**NO**

## 13. CONTRACT_GAPS

**无新增/修改**
