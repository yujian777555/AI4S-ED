# Phase 4.0.1 Executor Report — H1 Locator Reality & H2 Local Metadata Validation

**Executor:** MiMo  
**Date:** 2026-09-29  
**Phase:** 4.0.1

---

## 1. H1 locator reality

`EvidenceMetadataPort.anchor_exists` 语义改为 `Optional[bool]`：
- `True` = 已验证存在
- `False` = 已验证不存在
- `None` = 当前 adapter 无法校验（NOT_CHECKED）

`detect_h1` 调用 `anchor_exists`：
- locator 非空 ≠ locator 存在
- `False` → H1（fabricated locator）
- `None` → NOT_CHECKED 记录（不假称 PASS）

InMemory adapter 支持 per-ref locator 注册（`add_ref(ref_id, locators={...})`）。

## 2. H2 local DOI/title metadata

新增 `CitationMetadata`（ref_id + cited_title? + cited_doi?）temporary compatibility model。

本地验证（不调 Crossref/web）：
- ref_id 不存在 → H2
- cited DOI + KB DOI normalize 后不同 → H2
- cited title + KB title normalize 后不同 → H2
- 无 citation metadata → 仅做存在性检查

DOI normalize: trim + casefold + 移除 `https://doi.org/` / `http://doi.org/`（不改写 path）  
Title normalize: casefold + collapse whitespace + trim

## 3. H1 + H2 可同时命中

不存在的 literature ref_id 同时产生 H1（anchor 不可解析）和 H2（编造文献），不去重。

## 4. Test counts

```text
knowledge_curator: 166 passed / 0 failed  (151 既有 + 15 新 Phase 4.0.1)
integration/dsh:   70 passed / 0 failed
```

新增覆盖：
- H1 valid registered locator / fabricated locator / validator unavailable / empty locator
- H2 DOI match / DOI mismatch / title match / title mismatch / missing citation metadata
- non-literature 不走 literature H2
- H1+H2 同时命中
- DOI/title normalize helpers

## 5. 未修改

confidence gate / Abstain / H3 / numeric conflict / coverage / DSH regression / §5 core / MCP semantics

## 6. Public contracts changed?

**NO**

## 7. CONTRACT_GAPS

**无新增**

## 8. Implementation SHA

```
implementation commit: <pending>
```
