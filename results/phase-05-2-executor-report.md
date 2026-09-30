# Phase 5.2 Executor Report — Content Delta & RevisionPackage

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.2  

---

## 1. Scope

实现 structured content delta + assertion transition + RevisionPackage。**未**实现 PDF/XML 解析、OCR、爬虫、embedding/edit-distance/LLM 对齐、lifecycle publication、Phase 5.3。

§7 lifecycle core 与 §7.1 source identity 已冻结，本轮未改。

## 2. 交付物

- `knowledge_curator/schemas/version_delta.py` — ContentUnit / VersionContentManifest / ContentDeltaPlan / DeltaMode / DeltaExtractionRequest / VersionAssertionInventory / DeltaAssertionBatch / AssertionTransition / RevisionPackage
- `knowledge_curator/core/version_delta.py` — alignment / classification / carry-forward / transition diff / RevisionPackageBuilder / package_to_revision_draft
- `knowledge_curator/tests/test_phase52_version_delta.py` — 21 项

## 3. Exact content-unit alignment

**PASS**

优先级：`explicit prior_unit_id` > `same unit_id` > unaligned。  
禁止 embedding/edit-distance/LLM。  
duplicate alignment / invalid prior_unit_id → fail closed。

## 4. Delta classification

**PASS**

| 类别 | 规则 |
|---|---|
| UNCHANGED | aligned + same content_hash |
| MODIFIED | aligned + different content_hash |
| ADDED | new unit 无 prior alignment |
| REMOVED | prior unit 未被任何 new unit 对齐 |

## 5. Safe full-reextract fallback

**PASS**

`DeltaMode`: DELTA_SAFE / FULL_REEXTRACT_REQUIRED / REVIEW_REQUIRED。

FULL_REEXTRACT 触发：prior assertion 引用不可解析 unit、segmentation reset。此时 extraction scope = **all new units**，不假装 delta-safe。

## 6. Delta extraction request

**PASS** — 只生成请求对象（work_id / versions / extraction_unit_ids / locators / reason / trace），不调用 extractor。DELTA_SAFE 时 reason=`changed_or_added_units_only`。

## 7. Unchanged assertion carry-forward

**PASS**

- 克隆 prior assertion → new assertion（不 mutate old）
- deterministic new id = hash(prior_id + new_source_version_id + new_unit_id)
- new ref_id = new source ref
- provenance.locator = **new unit locator**；sentence 保留
- subject/property/object/conditions/claim_type/origin/confidence/quality 保持
- 记录 `old_assertion_id → carried_assertion_id`

## 8. Assertion transition diff

**PASS**

semantic slot key（不含 value/locator/id/ref）：subject.eddo_class + resolved_entity + property + normalized conditions + claim_type + value_type。

| 场景 | 动作 |
|---|---|
| unchanged carried | supersede old→new |
| removed unit | archive |
| modified unique slot match | supersede old→new |
| modified old slot 无 match | archive |
| modified new slot 无 match | added |
| added unit | added |

## 9. Ambiguity review gate

**PASS** — duplicate semantic slot → REVIEW_REQUIRED，不自动猜。

## 10. RevisionPackage determinism

**PASS** — 相同 intent + manifests + inventories + batch → 相同 `package_id`（canonical hash，无 random UUID）。

## 11. Lifecycle draft generation

**PASS** — `package_to_revision_draft` 填充 trigger / affected / supersede / archive / replacement / evidence / rationale / trace。`base_version_id=None`（publication-time bind）。**不**调用 `apply_revision()`。

## 12. Lifecycle publication performed

**NO**

## 13. 测试

```text
knowledge_curator: 442 passed / 0 skipped / 0 failed  (baseline 421 + 21)
integration/dsh:    90 passed / 0 failed
```

## 14. Public contracts changed?

**NO** — CG-020 INTERNAL compatibility boundary。

## 15. CONTRACT_GAPS

**无新增/修改**（CG-019/CG-020 维持 open）
