# Phase 5.1 Executor Report — Incremental Source Identity & Version Registry

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.1  

---

## 1. Scope

实现 §7.1 incremental intake identity + SourceVersionFamily registry。**未**实现爬虫 / fuzzy 匹配 / changed-paragraph 抽取 / preprint assertion supersede / Phase 5.2。

§7 lifecycle core 已冻结，本轮未改其语义。

## 2. 交付物

- `knowledge_curator/schemas/source_versions.py` — SourceKind / IntakeDisposition / VersionRelation / SourceCandidate / WorkRecord / SourceVersionRecord / VersionUpgradeIntent / IntakeDecision
- `knowledge_curator/ports/source_version_registry.py` — SourceVersionRegistry Port
- `knowledge_curator/adapters/in_memory_source_versions.py` — append-only registry
- `knowledge_curator/core/source_identity.py` — normalize_doi/title/stable_id + IncrementalIntakeService
- `knowledge_curator/tests/test_phase51_source_identity.py` — 21 项

## 3. Normalization

**PASS**

| 函数 | 规则 |
|---|---|
| `normalize_doi` | trim / 去 `doi:` / 去 doi.org & dx.doi.org URL 前缀 / casefold。**不** fuzzy 修 DOI |
| `normalize_title` | NFKC / trim / 折叠空白 / casefold。**不**删标点，**不** edit distance |
| `normalize_stable_id` | 仅 trim |

回归：`Study of membranes` vs `Study of membranes!` 保持 distinct。

## 4. SourceVersionRegistry

**PASS**

- lookup by ref+fingerprint / DOI / stable_id / normalized title
- get_work / get_source_version / list_versions(work_id)
- append_work / append_source_version（append-only）
- bind_source_version（仅一次，冲突 rebind 拒绝）
- material idempotency：同 ID 同 material 幂等；同 ID 异 material fail closed

## 5. Classification

| 场景 | 结果 |
|---|---|
| exact ref+fingerprint replay | **EXACT_REPLAY** |
| replay 但 metadata 矛盾 | **IDENTITY_CONFLICT** |
| 同 DOI + 新 fingerprint | **SAME_WORK_NEW_VERSION** |
| 同 stable_id + 新 fingerprint | **SAME_WORK_NEW_VERSION** |
| 仅 title 命中 | **REVIEW_REQUIRED**（不 auto-merge） |
| 无命中 | **NEW_WORK** |
| DOI→Work A + explicit Work B | **IDENTITY_CONFLICT** |
| invalid explicit work/prior | **IDENTITY_CONFLICT** |

precedence：ref+fingerprint → explicit lineage → DOI → stable_id → title → none。

## 6. Exact replay

**PASS**

## 7. Same-work new version

**PASS** — 同 DOI/同 stable_id 新 fingerprint 进入同一 work，`list_versions` 保留两者。

## 8. Title-only review gate

**PASS** — 仅 title 命中 → REVIEW_REQUIRED，带 ambiguity_candidates，`proceed_to_commit=false`。

## 9. Identity conflict fail-closed

**PASS** — DOI vs explicit work、无效 explicit 谱系、replay 材料矛盾全部 IDENTITY_CONFLICT。

## 10. Published-bind idempotency

**PASS**

| commit_status | 可 bind？ |
|---|---|
| PUBLISHED / IDEMPOTENT_HIT | 是 |
| FAILED / NOT_PUBLISHABLE / PENDING_VECTOR / PENDING_FINALIZE | **拒绝** |

bind retry 幂等；冲突 rebind（改绑不同 KB version）拒绝。

## 11. Explicit preprint→journal lineage

**PASS**

caller 显式传 `explicit_work_id + explicit_prior_version_id + relation=PREPRINT_TO_JOURNAL` → SAME_WORK_NEW_VERSION；P1 不删除；`list_versions` 含 [P1, J1]。**不**自动 title 相似合并（回归：同标题异 DOI 无 explicit → REVIEW_REQUIRED）。

## 12. Upgrade intent generation

**PASS** — `VersionUpgradeIntent`：work_id / prior_source_version / new_source_version / relation / base_kb_version / `requires_delta_extraction=true` / `lifecycle_reason=preprint_to_journal`。Phase 5.2 输入，5.1 不执行 supersede/重抽。

## 13. 测试

```text
knowledge_curator: 379 passed / 0 skipped / 0 failed  (baseline 358 + 21)
integration/dsh:    90 passed / 0 failed
```

## 14. Public contracts changed?

**NO** — CG-019 保持 INTERNAL compatibility boundary。

## 15. CONTRACT_GAPS

**无新增/修改**（CG-019 维持 open）
