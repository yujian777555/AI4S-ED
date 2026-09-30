# Phase 5.1-R3 Executor Report — Exact Replay Material Consistency

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.1-R3  

---

## 1. Scope

仅修复 exact replay material consistency。R1/R2 identity precedence / relation state machine / registry integrity 保持冻结。未启 Phase 5.2。

## 2. R3-01 replay prior equality

**PASS**

| 场景 | 结果 |
|---|---|
| existing prior=P1, incoming prior=P1 | EXACT_REPLAY |
| existing prior=P1, incoming prior=P2（同 work） | **IDENTITY_CONFLICT** |
| existing prior=None, incoming prior=P1 | **IDENTITY_CONFLICT** |
| existing prior=P1, incoming prior omitted | EXACT_REPLAY |

不再只检查 prior 是否同 work，而是要求 **精确等于** `existing.prior_source_version_id`。root self-prior 自动拒绝。

## 3. R3-02 replay relation equality

**PASS**

`explicit_relation` 一旦提供（含 `VersionRelation.NONE`）必须 == `existing.relation`：

| existing | incoming | 结果 |
|---|---|---|
| REVISION_OF | REVISION_OF | replay |
| REVISION_OF | CORRECTED_VERSION | conflict |
| REVISION_OF | NONE | conflict |
| NONE | NONE | replay |
| (omitted) | — | 不构成冲突 |

不再对 P2J replay 做 source_kind 特判。

## 4. R3-03 source_kind consistency

**PASS** — 同 ref+fingerprint 的 `source_kind` 必须一致（PREPRINT↔JOURNAL 等均 conflict）。即使 DOI/stable 相同。

## 5. R3-04 normalized title consistency

**PASS**

- 两边 title 均存在且 normalize 后不同 → **IDENTITY_CONFLICT**
- `A Study` / `a study` / `Ａ Ｓｔｕｄｙ` / 多余空白 → normalize 后一致 → **EXACT_REPLAY**
- incoming title 缺失 → 不因缺失单独判 conflict

## 6. Valid P2J target replay

**PASS**

真两版本 fixture：

- P1: PREPRINT / work W / relation NONE  
- J1: JOURNAL / work W / prior=P1 / relation=PREPRINT_TO_JOURNAL / 不同 ref+fingerprint  

replay J1（同 ref+fingerprint + 兼容 explicit lineage）→ **EXACT_REPLAY**。

错误 prior / relation / source_kind → conflict。

## 7. Invalid self-prior regression

**PASS** — 旧的 self-prior「compatible replay」测试已重写为 root + omitted prior；新增 root + self prior → conflict 回归。

## 8. 测试

```text
knowledge_curator: 421 passed / 0 skipped / 0 failed  (baseline 406 + 15)
integration/dsh:    90 passed / 0 failed
```

## 9. Public contracts changed?

**NO**

## 10. CONTRACT_GAPS

**无新增/修改**
