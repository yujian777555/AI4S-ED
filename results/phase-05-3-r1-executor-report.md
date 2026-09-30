# Phase 5.3-R1 Executor Report — Real Integration & Final Recovery Closure

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.3-R1  

---

## 1. Scope

最终 integration hardening。未重新设计冻结组件。未创建 Phase 5.4。

## 2. Real async DocumentCommitCoordinator integration

**PASS** — `publish()` 改为 `async def`，真正 `await self._commit.commit(request)`。不使用 `asyncio.run` 嵌套。

## 3. Exact CommitRequest/package gate

**PASS** — `target_commit_request` 必填；`validate_commit_request` 先行；source/assertion_set/report ref_id 一致；assertion ID 集合与 canonical material 完全一致。

## 4. Approval scope binds source/metadata/report

**PASS** — `compute_publication_scope_hash(package, request)` 绑定 request.source / AssertionSet metadata / canonical assertions / report decisions / report status。metadata/decision/value 变更 → scope hash 变更。

## 5. Mandatory curation gate

**PASS** — 仅 ACCEPT/DOWNGRADE；PENDING_REVIEW/REJECT/RETURN_UPSTREAM/SUPERSEDE 阻止；`returned_upstream_count > 0` 阻止；report.status 不兼容时阻止。使用 `request.report` 唯一来源。

## 6. Exact existing-commit material guard

**PASS** — 比较 full assertion canonical material + action/confidence/visibility。同 ID 异 material → CONFLICT。store 读取失败 → fail closed。

## 7. Target version/snapshot validation

**PASS** — version exists/published、version.snapshot_id 一致、snapshot 存在、manifest ref/fingerprint 与 new source 一致。

## 8. Final snapshot content preservation

**PASS** — final snapshot 保留 target 的 ref_id / fingerprint / structural_stage_id / assertion_hashes / usdo_* / vector_ids / metadata_hash / decision_hashes。

## 9. Post-bind journal recovery

**PASS** — bind 成功后 journal FINALIZED 崩溃 → retry 识别 exact binding → FINALIZED idempotent。

## 10. Real P2J E2E

**PASS** — 真实 `DocumentCommitCoordinator` 产生 V_target；`LifecycleRevisionCoordinator` 产生 V_final；`V_final.prior == V_target`；new SourceVersion → V_final；prior 不变；ARXIV→SUPERSEDED/ineligible；JOURNAL→ACTIVE/eligible。

## 11. Real full replay idempotency

**PASS** — 相同 material replay → FINALIZED + idempotent。

## 12. 测试

```text
knowledge_curator: 489 passed / 0 skipped / 0 failed  (baseline 489)
integration/dsh:    90 passed / 0 failed
```

## 13. Public contracts changed?

**NO**

## 14. CONTRACT_GAPS

**无新增/修改**
