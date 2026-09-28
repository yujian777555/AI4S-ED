# Phase 2.2 Executor Report — Final §5.4 Atomic Visibility & Versioned Read Closure

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-28  
**Module:** knowledge_curator  
**Phase:** 2.2  
**Base implementation:** `3d6e49e51995eec8bff6dd9e6a467ebd61166903`  
**Scope:** 仅 §5.4 最终收口。未实现 §6/§7/DSH/MCP/DeepSeek。

---

## 1. Atomic visibility implementation

Document pair finalize 采用 **explicit compensation**（CG-013 兼容）：

```text
stage structural
stage USDO
finalize structural
finalize USDO
  → 仅当两阶段均成功才标记 STRUCTURAL_COMMITTED
任一失败（含 fail-after-side-effect）：
  compensate_committed(structural/USDO)
  abort_stage(剩余 staged)
  → committed 可见读必须为空
```

## 2. Compensation mechanism

| 操作 | 行为 |
|---|---|
| `StructuralKnowledgeStore.compensate_committed` | 移除未发布文档的 committed 可见性 |
| `USDOStore.compensate_committed` | 同上 |
| `abort_stage` | 清理未提交 staged |
| 适用范围 | 仅 pre-publish 失败文档；不改写已发布历史 |

## 3. structural + USDO visibility behavior

| 场景 | structural 可见 | USDO 可见 | snapshot/version |
|---|---|---|---|
| structural 成功 + USDO fail-before | 无 | 无 | 无 |
| structural 成功 + USDO fail-after | 无（已补偿） | 无（已补偿） | 无 |
| structural fail-after | 无（已补偿） | 无 | 无 |
| lifecycle ack 失败 | 无（已补偿） | 无 | 无 |
| 成功 | 1 条 | 1 条 | 1 version |

## 4. Snapshot idempotency

- `create_snapshot` 以 manifest `content_hash` 为幂等键
- fail-after-side-effect 后 retry 复用同一 snapshot（`get_snapshot_by_hash`）
- 相同 deterministic manifest ⇒ 相同 snapshot_id，无 orphan

## 5. FAILED exact retry

`(ref_id, fingerprint)` 在 **无 published version** 且 partial effects 已补偿时可安全重启：

- `FAILED` / `PREPARING` / `STRUCTURAL_STAGED` 均可 restart
- 复用 lifecycle record；不重复 structural/USDO/vector/version
- binding 校验在每次 retry 前重新执行

## 6. Version-scoped read view

`VersionedKnowledgeView.resolve(version_id | None)`：

```text
ResolvedKnowledgeBundle:
  version_id, snapshot_id, manifest
  structural record (by manifest.structural_stage_id)
  USDO records   (by manifest.usdo_record_ids)
  vector payloads (by manifest.vector_ids)
```

`resolve_current()` 解析当前 visible version 的依赖。

## 7. V1 / V2 / rollback proof

```text
V1 publish (ref=ED-S, AS-1 value=1.0, fp-v1)
V2 publish (ref=ED-S, AS-1 value=2.0, fp-v2)
current = V2
rollback_to(V1)
current = V1
```

验收结果：
- `resolve_current()` → V1 structural（stage_id=r1, value=1.0, fp-v1）
- → V1 USDO（fp-v1）
- → V1 vector（fp-v1）
- **不包含** V2 身份
- `resolve(V2)` 仍返回 V2 historical 结构/向量（value=2.0）

## 8. Recovery status semantics

| Status | 仅用于 |
|---|---|
| `PENDING_VECTOR` | vector upsert / vector replay |
| `PENDING_FINALIZE` | snapshot create / version publish / post-publish lifecycle ack |

Phase 字段仍精确反映 `VECTOR_PENDING` / `VECTOR_COMMITTED` / `SNAPSHOT_CREATED`。

## 9. Tests per file

| 文件 | 数量 |
|---|---|
| test_atomic_commit.py | 17 |
| test_completeness.py | 10 |
| test_conflict.py | 6 |
| test_curator.py | 13 |
| test_phase11_regressions.py | 13 |
| test_phase12_regressions.py | 19 |
| test_phase21_persistence.py | 24 |
| test_phase22_atomic_view.py | 18 |
| test_quality.py | 7 |

## 10. Total tests

```text
127 passed / 0 failed
```

（109 既有全绿 + 18 新增；并将 snapshot/publish 恢复期望从 PENDING_VECTOR 修正为 PENDING_FINALIZE）

## 11. CONTRACT_GAPS

**无新增。** CG-001/CG-012/CG-013/CG-014 保持不变。未删除或关闭 CG-014。

## 12. Public contracts changed?

**NO**

- 未改 docs/01、03、Boundary
- confidence 枚举未变
- 未实现 §6/§7/DSH/MCP/DeepSeek
- SnapshotManifest 扩展字段为 internal temporary（structural_stage_id / usdo_record_ids）

## 13. Implementation commit SHA

```
implementation commit: <pending>
```

---

### DSH / DeepSeek / MCP

**未提前实现。** 仅阅读 `planner/DSH_INTEGRATION_NOTES.md` 以遵守“禁止虚假 DSH decorator”约束；Python core 保持 runtime-independent。
