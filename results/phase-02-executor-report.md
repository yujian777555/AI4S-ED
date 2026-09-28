# Phase 2 Executor Report — §5.4 Atomic Ingest & KB Version Snapshot

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-28  
**Module:** knowledge_curator  
**Phase:** 2  
**Accepted baseline:** `e88eabad1b42304d2a9ebade6308c9eb16c24573`  
**Scope:** 仅实现 03 §5.4 原子入库 / pending_vector / 幂等 / KB version / snapshot / rollback。§5.1–§5.3 冻结行为未改。未做 §6/§7，未接 DeepSeek/DSH。

---

## 1. 本轮完成内容

- `DocumentCommitCoordinator`：document 为事务边界的 commit 编排
- atomic visibility 状态机：`PREPARING → STRUCTURAL_STAGED → STRUCTURAL_COMMITTED → VECTOR_PENDING|VECTOR_COMMITTED → SNAPSHOT_CREATED → PUBLISHED`
- structural 成功 + vector 失败 → `pending_vector`，不发布 KB version
- replay/pending 恢复不重复 structural records，成功后只发布一个 version
- `(ref_id, source_fingerprint)` 幂等；同 fingerprint 重提返回既有结果
- 同 ref_id + 新 fingerprint 可形成新版本
- deterministic snapshot manifest（排除 report_id 等 ephemeral 字段）
- rollback 仅切换 visible pointer，历史版本保留；非法目标显式失败
- eligibility：return_upstream / all-rejected 不可发布；REJECT 不入 active 面；PENDING_REVIEW 不升 high/verified；DOWNGRADE 保持降级 confidence
- InMemory adapters + deterministic failure injection
- `KnowledgeCurator.curate_and_commit` 组合入口（curation 仍可独立测试）
- 新增 17 个 Phase 2 测试；既有 68 测试保持全绿

## 2. 文件树（本轮新增/修改）

```text
knowledge_curator/
├── core/
│   ├── commit.py                    # 新增 DocumentCommitCoordinator
│   ├── curator.py                   # 增加 curate_and_commit
│   └── __init__.py
├── schemas/
│   ├── commit.py                    # 新增临时 commit 模型
│   └── __init__.py
├── ports/
│   ├── document_commit_store.py     # 新增
│   ├── vector_index.py              # 新增
│   ├── usdo_store.py                # 新增
│   ├── version_store.py             # 新增
│   └── __init__.py
├── adapters/
│   ├── in_memory_commit.py          # 新增（含 FailureInjection）
│   └── __init__.py
└── tests/
    └── test_atomic_commit.py        # 新增 17 tests
planner/CONTRACT_GAPS.md             # CG-012 / CG-013
results/phase-02-executor-report.md
status.json
```

## 3. 状态机（atomic visibility）

```text
PREPARING
  -> STRUCTURAL_STAGED      (stage admitted assertions + USDO + vector identities)
  -> STRUCTURAL_COMMITTED   (USDO/structural registration as one document unit)
  -> VECTOR_PENDING         (vector upsert failed; recoverable; no version)
  -> VECTOR_COMMITTED
  -> SNAPSHOT_CREATED       (deterministic content-hash manifest)
  -> PUBLISHED              (exactly one KB version)
```

失败语义：
- structural 前失败 → `FAILED`，无 version/snapshot
- structural 后 vector 失败 → `VECTOR_PENDING`，structural 保留，可 replay
- replay 成功 → 清除 pending，发布恰好一个 version
- snapshot 创建失败 → 保持可恢复，不发布

## 4. 幂等

| 场景 | 行为 |
|---|---|
| 同 `(ref_id,fingerprint)` 已发布 | `IDEMPOTENT_HIT`，返回既有 version，不重复写 |
| 同 fingerprint 处于 `pending_vector` | replay vector/publish，不重复 structural |
| 同 ref_id + 不同 fingerprint | 新 commit，可发布新 KB version |

## 5. Snapshot / Version / Rollback

- manifest 含 source fingerprint、admitted assertion hashes、USDO hashes、vector ids、metadata hash、decision hashes
- `content_hash = sha256(canonical sorted payload)`，相同内容 ⇒ 相同 hash
- 每次成功 document commit 恰好一个 version
- `list_published_versions` / `current_version` 只暴露已发布
- `rollback_to` 切换 pointer；后续历史 version 仍在 `list_published_versions` / `get_version`
- 目标不存在或非 published → `ValueError`

## 6. Eligibility

| 决策 | 入库 visibility | 可发布 |
|---|---|---|
| ACCEPT | active | 是 |
| DOWNGRADE | downgraded（保持 hypothesis/medium） | 是（不提升） |
| PENDING_REVIEW | pending | 是（不进入 high/verified） |
| REJECT | 不入库 | — |
| RETURN_UPSTREAM | — | 否 |

## 7. 测试命令与结果

```bash
.venv\Scripts\python.exe -m pytest knowledge_curator/tests -v --tb=short
```

```text
collected 85 items

test_atomic_commit.py        17 passed  (新增)
test_completeness.py         10 passed
test_conflict.py              6 passed
test_curator.py              13 passed
test_phase11_regressions.py  13 passed
test_phase12_regressions.py  19 passed
test_quality.py               7 passed

TOTAL: 85 passed in 1.29s — failed 0
```

Phase 2 覆盖：success / pre-publish rollback / vector pending+retry / idempotency / eligibility / rollback / boundaries。

## 8. CONTRACT_GAPS

新增：
- **CG-012** 同 fingerprint “merge/version bump” 与 exact-retry 幂等歧义 → Phase 2 取安全 exact-retry，不重复发布
- **CG-013** 跨存储 ACID 不可行 → atomic visibility + pending_vector 补偿

CG-001~CG-011 保持不变。

## 9. TODO / placeholder

- DocumentCommitStore / VectorIndex / USDOStore / VersionStore 为内部 Port，非最终 L2 契约（CG-004）
- 生产 SQLite/FAISS/真实 USDO 存储 adapter 未接（本轮禁止写死）
- §7 撤稿/修订/soft-archive 流程未做（按计划禁止）

## 10. 外部依赖

- Python 3.12 标准库（hashlib/json/uuid）
- pytest 9.1.1（本地 `.venv`）
- **无** SQLite / FAISS / DeepSeek / DSH / HTTP / 网络

## 11. 是否修改公共契约

**NO**

- 未改 docs/01、docs/03、Boundary
- 未改 confidence 枚举
- 未改 §5.1–§5.3 决策语义
- commit schemas 标注 temporary compatibility model

## 12. 已知风险

1. exact-retry 幂等与 03 “merge/version bump” 字面可能不完全一致（CG-012），若 Planner 要求 bump，需小改 idempotent 分支。
2. SUPERSEDE 动作暂按 active 入库（Phase 2 不做真值判定/§7）；完整 supersede 语义依赖 CG-008。
3. VectorPayload 仅身份/内容哈希，无真实 embedding；接入 FAISS 时需扩展 upsert 载荷。

## 13. Git commit hash

```
implementation commit: <pending>
```
