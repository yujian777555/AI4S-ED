# Phase 5.3 Executor Report — Recoverable Revision Publication Orchestration

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.3  

---

## 1. Scope

实现 publication orchestration layer。未重新设计 Phase 2/5.0/5.1/5.2 冻结组件、retrieval、DSH/MCP public tools。无 fake ACID，使用 recoverable saga。

## 2. 交付物

- `knowledge_curator/schemas/revision_publication.py` — RevisionApproval / PublicationPhase / PublicationRecord / PublicationResult
- `knowledge_curator/ports/revision_publication_store.py` — journal Port
- `knowledge_curator/adapters/in_memory_revision_publication.py` — append-only in-memory journal（单调 phase）
- `knowledge_curator/core/revision_publication.py` — RevisionPublicationCoordinator + scope hash
- `knowledge_curator/tests/test_phase53_publication.py` — 14 项

## 3. Approval-before-side-effects

**PASS**

approval missing / rejected / wrong package / wrong scope_hash / package.requires_manual_review → **0 target commit, 0 lifecycle, 0 source binding**。

## 4. Exact target material gate

**PASS** — request identity 校验 + existing commit material guard（same key 不同 admitted material → CONFLICT）。

## 5. Curation gate

**PASS** — 仅 ACCEPT / DOWNGRADE 可发布；PENDING_REVIEW / REJECT / RETURN_UPSTREAM / SUPERSEDE 阻止。每 target assertion 恰好一个 decision。

## 6. Target commit recovery

**PASS** — PUBLISHED / IDEMPOTENT_HIT 继续；PENDING_VECTOR / PENDING_FINALIZE → TARGET_PENDING 停止；FAILED → 停止。

## 7. Lifecycle recovery

**PASS** — lifecycle 失败后 new SourceVersion 保持 unbound，journal 停在 TARGET_PUBLISHED，retry 恢复。stale base → CONFLICT fail closed。

## 8. Final source-version binding

**PASS** — `new SourceVersion → V_final → S_final`（**不**绑 V_target）。`V_final.prior_version_id == V_target`。prior binding 不变。

## 9. Bind-after-lifecycle recovery

**PASS** — bind 失败后 retry 完成；lifecycle finalized 但 bind 未完成时 retry 幂等恢复。

## 10. Stale-base fail-closed

**PASS** — target 发布后插入无关版本 → CONFLICT，不 silent rebase，不 bind。

## 11. P2J visibility E2E

**PASS** — prior preprint ref → SUPERSEDED / retrieval=false / training=false；new journal ref → ACTIVE / retrieval=true；historical V1 仍可解析。

## 12. Idempotent full replay

**PASS** — 相同 material replay → FINALIZED + idempotent=true，无重复事件/版本。

## 13. 测试

```text
knowledge_curator: 489 passed / 0 skipped / 0 failed  (baseline 475 + 14)
integration/dsh:    90 passed / 0 failed
```

## 14. Public contracts changed?

**NO** — CG-021 approval 为 INTERNAL auditable contract。

## 15. CONTRACT_GAPS

**无新增/修改**
