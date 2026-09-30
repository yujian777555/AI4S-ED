# Phase 5.2-R3 Executor Report — P2J Lifecycle Subject Direction

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.2-R3  

---

## 1. Scope

仅修复 P2J lifecycle subject direction。未改 content delta / FULL_REEXTRACT / deep-copy / package material / source lineage / risk gate。未启 Phase 5.3。

## 2. P2J lifecycle subject = prior ref

**PASS**

`package_to_revision_draft` 的 `ref_id` 从 `package.new_ref_id` 改为 `package.prior_ref_id`。

| 场景 | draft.ref_id | 结果 |
|---|---|---|
| P2J: prior=ARXIV-1, new=JOURNAL-1 | **ARXIV-1** | ARXIV-1→SUPERSEDED，JOURNAL-1 保持 active |
| same-ref revision: REF-1→REF-1 | REF-1 | 不受影响 |

统一规则：所有 upgrade relation 的 lifecycle subject = `prior_ref_id`（transition actions 操作的都是 prior assertions）。

## 3. New journal identities preserved

**PASS**

- `supersede_actions` 仍为 old→new（prior assertion → journal assertion）
- `replacement_assertion_ids` 仍为 **new journal assertion ids**（如 J-A3），不含 prior ids
- `evidence_refs` 保持 `[prior_source_version_id, new_source_version_id]`
- `package_id` 不变（draft helper 不改 package identity）

## 4. Same-ref compatibility

**PASS** — prior_ref_id == new_ref_id 时 draft.ref_id 行为不变。

## 5. Risk gate bypassed

**NO** — 未注入 high_confidence / multi_source / no_controversy，未设置 manual_adjudication_required=false。CG-021 记录 manual approval contract gap，留待 Phase 5.3。

## 6. Lifecycle publication performed

**NO**

## 7. 测试

```text
knowledge_curator: 475 passed / 0 skipped / 0 failed  (baseline 470 + 5)
integration/dsh:    90 passed / 0 failed
```

新增：P2J draft targets prior_ref_id / new journal replacement IDs preserved / same-ref compatibility / package_id unchanged / no lifecycle publication。

## 8. Public contracts changed?

**NO**

## 9. CONTRACT_GAPS

**无新增/修改**（CG-021 由 Planner 记录，维持 open）
