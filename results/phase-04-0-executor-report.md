# Phase 4.0 Executor Report — §6 Evidence Guard Foundation

**Executor:** MiMo  
**Date:** 2026-09-29  
**Phase:** 4.0  
**Scope:** §6 deterministic evidence/anchor/Abstain/H1-H3 foundation。无 FAISS/BM25/RRF/reranker/§7。

---

## 1. New schemas (`schemas/evidence.py`)

- `EvidenceType`: literature/graph/simulation/experiment（映射 文献/图谱/仿真/实验）
- `EvidenceAnchor`: evidence_type + ref_id + locator + confidence + quality + access_pointer
- `EvidenceRecord`: anchor + claim_id + summary + score + provenance
- `Claim`: claim_id + text + anchors + numeric fields + coverage_key
- `SurfacePolicy` / `ClaimPolicy`: confidence gate 输出

temporary compatibility model，非公共 Schema Registry。

## 2. New Ports (`ports/evidence_store.py`)

`EvidenceMetadataPort`：`ref_exists` / `get_ref_metadata` / `anchor_exists`

InMemory adapter：`adapters/in_memory_evidence.py`（仅测试）

## 3. Confidence gate

```
verified/high → FACTUAL_ALLOWED
medium        → CAVEATED_ONLY
hypothesis    → PENDING_HYPOTHESIS_ONLY
no anchors    → ABSTAIN
disjoint numeric ranges → CONFLICT_DISCLOSURE_REQUIRED
```

取最弱 anchor，不提升 confidence。

## 4. Abstain reasons

- LOW_RETRIEVAL_SUPPORT
- SUBQUESTION_NOT_COVERED
- CRITICAL_NUMERIC_ONLY_HYPOTHESIS_OR_PENDING
- UNSUPPORTED_INFERENCE_NO_MECHANISM
- PRIVATE_DATA_UNAUTHORIZED

返回结构化 `AbstainDecision`（abstain/reasons/missing_evidence/recommended_gap_kinds）。

## 5. H1 / H2 / H3

| 检测器 | 行为 |
|---|---|
| H1 | 无 anchor / 空 locator / ref 不可解析 |
| H2 | KB 本地存在性；不存在 → H2（不调 Crossref/web） |
| H3 | 复用 `MechanismValidator` Port；不可用 → `MECHANISM_UNAVAILABLE`（不假称 PASS） |

## 6. Coverage guard

required_keys - covered_keys → uncovered → Abstain/partial flag，不静默省略。

## 7. Numeric conflict disclosure

区间不交叠 → CONFLICT_DISCLOSURE_REQUIRED；重叠 → 不强制披露。

## 8. DSH live regression hardened

**YES** — `lane324_kc_roundtrip.e2e.ts`：
- `tool_call_count == 1` 严格断言
- `tool_result_count == 1` 严格断言
- `abc_match === true` 严格断言
- 删除 `inferred_from_tool_result_raw` / `tool_result_blob_matched` fallback
- 结构化 parse 失败 → FAIL，不从 A 复制 B

## 9. Test counts

```text
knowledge_curator: 151 passed / 0 failed  (127 既有 + 24 新 Phase 4.0)
integration/dsh:   70 passed / 0 failed
```

## 10. Public contracts changed?

**NO**

## 11. CONTRACT_GAPS

**无新增**

## 12. Implementation SHA

```
implementation commit: 2af6b019d4267c24f4b5813b43cb28587fba63b6
```
