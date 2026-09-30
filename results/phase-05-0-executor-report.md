# Phase 5.0 Executor Report — §7 Lifecycle Core

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.0  

---

## 1. Scope

实现 docs/03 §7 lifecycle core。**未**实现 Crossref/RetractionWatch crawler、publisher polling、Kafka/Redis、04/05/07 consumer、arXiv→journal fuzzy matching、final QA generator。

§6 core 已冻结，本轮未改动 ranking/guard 语义。

## 2. 交付物

- `knowledge_curator/schemas/lifecycle.py` — DocumentLifecycleStatus / AssertionLifecycleStatus / LifecycleReason / RevisionDraft / LifecycleEvent
- `knowledge_curator/ports/lifecycle_store.py` — LifecycleStore / LifecycleVisibilityPort / EventOutbox
- `knowledge_curator/adapters/in_memory_lifecycle.py` — in-memory adapters（append-only + 版本可见性）
- `knowledge_curator/core/lifecycle.py` — RevisionDraft builder、risk gate、Retraction/Corrigendum coordinator、版本发布、outbox 事件
- `knowledge_curator/core/lifecycle_visibility.py` — VersionStore 祖先链可见性
- `knowledge_curator/schemas/commit.py` — SnapshotManifest 增加 lifecycle 字段（**向后兼容**）
- `knowledge_curator/retrieval/evidence_service.py` — 可选 LifecycleVisibility 组合层（预过滤 allowed_ref_ids / 包装 port）
- `knowledge_curator/tests/test_phase50_lifecycle.py` — 18 项
- `results/phase-05-0-lifecycle-smoke.json`

## 3. 关键场景（计划 §12）

| 步骤 | 结果 |
|---|---|
| V1 active | PASS |
| V2 retraction → doc=RETRACTED，断言 ARCHIVED | PASS |
| current retrieval 不可见 REF | PASS |
| rollback_to(V1) → 恢复可见 | PASS |
| V2 历史仍可解析且仍记录 retraction | PASS |
| structural/USDO/vector **无物理删除** | PASS |

## 4. 分项

| 项 | 状态 | 说明 |
|---|---|---|
| lifecycle models/store | **PASS** | append-only；同 id 重放幂等；冲突 id 拒绝 |
| revision draft/risk gate | **PASS** | AUTO_RULE_REVIEW_ELIGIBLE / MANUAL_ADJUDICATION_REQUIRED；无全局数值风险分 |
| retraction soft archive | **PASS** | 新 KB 版本 + RETRACTED + ARCHIVED，不 delete |
| corrigendum/supersede | **PASS** | 只影响指定断言；替换为新 assertion id；未受影响断言保持 active |
| version publication | **PASS** | 新 snapshot manifest 引用同一 immutable id；prior_version_id 指向 base |
| rollback visibility | **PASS** | 版本范围生命周期查找（ancestor-or-self） |
| historical preservation | **PASS** | V1 snapshot/版本完整保留 |
| retrieval eligibility integration | **PASS** | 预过滤 allowed_ref_ids / port 包装，不在 top-k 后丢弃 |
| training eligibility | **PASS** | retracted/archived/superseded → eligible_for_training=false |
| event outbox | **PASS** | CG-018 仅内部；确定性 event_id；invalidate 载荷 |
| backward manifest hash compatibility | **PASS** | 空 lifecycle 字段不改变旧 stable_payload 哈希 |
| failure atomicity | **PASS** | publish 前失败：staged 记录未绑定，current 仍为 V1 |

## 5. CG-018

仅实现内部 `LifecycleEvent` + `EventOutbox` Port（append / list_pending / mark_delivered）。**不**选择 Kafka/Redis/HTTP/主题名。

## 6. 测试

```text
knowledge_curator: 329 passed / 0 skipped / 0 failed  (baseline 311 + 18)
integration/dsh:    90 passed / 0 failed
```

## 7. 边界

- 未开始 Phase 5.1 / 自动 Crossref 轮询 / 外部事件传输
- 未修改 §6 冻结语义
- 无 public contract 变更

## 8. Public contracts changed?

**NO** — lifecycle models 为 INTERNAL temporary model。

## 9. CONTRACT_GAPS

**无新增**（CG-018 维持 open，本轮仅内部 Port）
