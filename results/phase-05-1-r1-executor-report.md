# Phase 5.1-R1 Executor Report — Identity Precedence & Registry Hardening

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.1-R1  

---

## 1. Scope

仅修复 Phase 5.1 review 的 5 个 identity correctness blocker。未启 Phase 5.2，未改 §7 lifecycle core / normalization 规则 / title-only review gate。

## 2. R1-01 DOI/stable precedence conflict

**PASS**

cross-identifier 检查移到所有 positive return **之前**：

1. `len(doi_works) > 1` → IDENTITY_CONFLICT  
2. `len(stable_works) > 1` → IDENTITY_CONFLICT  
3. DOI→Work A + stable→Work B → **IDENTITY_CONFLICT**（含双方 work ids）

回归：DOI X→Work A，stable Y→Work B，candidate 同时带 X+Y → 冲突，**不**因 DOI precedence 返回 Work A。

## 3. R1-02 stable multi-work invariant

**PASS** — registry `append_source_version` 拒绝同 stable_id 跨 work 映射；classification 层 `len(stable_works)>1` → IDENTITY_CONFLICT。

## 4. R1-03 prior-only explicit lineage

**PASS**

进入 explicit lineage 条件改为：

```python
explicit_work_id is not None OR explicit_prior_version_id is not None
```

- valid prior + 无 work_id → 继承 `prior.work_id` → SAME_WORK_NEW_VERSION  
- invalid prior → IDENTITY_CONFLICT  
- prior-only 继承 work 与 DOI/stable 映射矛盾 → IDENTITY_CONFLICT

## 5. R1-04 PREPRINT_TO_JOURNAL compatibility

**PASS**

强制校验：

| 条件 | 违反则 |
|---|---|
| `explicit_prior_version_id` 存在 | IDENTITY_CONFLICT |
| prior 存在 | IDENTITY_CONFLICT |
| prior.work_id == resolved work | IDENTITY_CONFLICT |
| prior.source_kind == PREPRINT | IDENTITY_CONFLICT |
| candidate.source_kind == JOURNAL | IDENTITY_CONFLICT |

合法路径仍生成 `VersionUpgradeIntent`；不合法**不**生成假 intent。

## 6. R1-05 registry uniqueness

**PASS**

| 不变量 | 行为 |
|---|---|
| 同 (ref_id, fingerprint) 异 material | reject |
| 同 DOI 跨 work | reject |
| 同 DOI 同 work 多版本 | 允许 |
| 同 stable_id 跨 work | reject |

## 7. Append atomicity

**PASS** — 所有 conflict check 在 `_versions` / `_version_order` / `_by_ref_fp` / `_by_doi` / `_by_stable` / `_by_title` 修改**之前**完成。失败 append 后 registry 不变（回归证明）。

## 8. WorkRecord hardening

**PASS** — 同 work_id 同 material 幂等；异 material fail closed。

## 9. 测试

```text
knowledge_curator: 392 passed / 0 skipped / 0 failed  (baseline 379 + 13)
integration/dsh:    90 passed / 0 failed
```

## 10. Public contracts changed?

**NO**

## 11. CONTRACT_GAPS

**无新增/修改**
