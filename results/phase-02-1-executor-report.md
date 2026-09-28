# Phase 2.1 Executor Report — §5.4 Persistence / Recovery / Rollback Correctness

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-28  
**Module:** knowledge_curator  
**Phase:** 2.1  
**Base implementation:** `dee9ba4a881096349a65eecb40df2544164dfd29`  
**Scope:** 仅关闭 §5.4 persistence/recovery correctness（P2.1-01~05 + H2.1-01/02）。§5.1–§5.3 冻结。未做 §6/§7，未接 DeepSeek/DSH。

---

## 1. 本轮完成内容

| ID | 问题 | 修复 |
|---|---|---|
| P2.1-01 | lifecycle record 代替 structural 持久化 | 新增 `StructuralKnowledgeStore` Port + InMemory adapter；admitted assertions/metadata 显式 stage→commit |
| P2.1-02 | USDO register 立即可见 | USDO 改为 stage/commit/abort；`list_for_ref` 只返回 committed |
| P2.1-03 | publish 不幂等、ack 失败窗口 | `publish_version` 按 snapshot 幂等；publish 副作用后异常可恢复 version；ack 失败可 resume |
| P2.1-04 | vector id 非 version-safe | `vec-{ref_id}-{fp12}-{assertion_id}-{hash12}`；新 fingerprint 不覆盖旧向量 |
| P2.1-05 | CommitRequest 未绑定校验 | `validate_commit_request` fail-closed：ref_id 一致、fingerprint 非空、决策一一对应、无重复/外来 id |
| H2.1-01 | SUPERSEDE 被当 ACTIVE | `AssertionVisibility.SUPERSEDED`，永不 active |
| H2.1-02 | assertion hash 缺稳定字段 | 覆盖 uncertainty、sentence、quality、subject 字段等 |

另：`FailureInjection` 支持 `fail_after`/`fail_on_nth`/`also_fail`；lifecycle store 为 copy-on-write。

## 2. 持久化模型

```text
DocumentCommitStore     — lifecycle / idempotency / audit（非 structural 证明）
StructuralKnowledgeStore— stage → commit/abort；staged 不可见
USDOStore               — stage → commit/abort；list_for_ref 仅 committed
VectorIndex             — immutable version-safe ids
VersionStore            — snapshot + idempotent publish + rollback pointer
```

## 3. stage → commit → abort 可见性

| 阶段 | structural committed 读 | USDO committed 读 |
|---|---|---|
| staged only | 空 | 空 |
| commit_stage 成功 | 可见 | 可见 |
| abort_stage / 预提交失败 | 空 | 空 |
| 生命周期 audit record | 可残留 FAILED | — |

## 4. Vector identity

```text
vec-{ref_id}-{fingerprint[:12]}-{assertion_id}-{assertion_hash[:12]}
```

- 同 exact retry 复用相同 id
- 同 ref_id 不同 fingerprint → 不同 id，旧 payload 保留
- V1 snapshot 在 V2 发布后仍可解析 V1 vectors

## 5. Version publish 幂等

- 一 snapshot 至多一个 published version
- 重复 `publish_version(snapshot_id)` 返回既有 version
- publish 前失败 → 可 resume
- publish 副作用成功但 ack 失败 → 结果携带 version_id，retry 不产生第二版本

## 6. 失败窗口

| 窗口 | 行为 |
|---|---|
| structural stage/commit 前失败 | abort staged；无 committed knowledge；无 version |
| vector 失败 | `pending_vector`；structural 已提交可恢复 |
| snapshot 失败 | 保持 VECTOR_COMMITTED 可 resume（不误标 vector 失败） |
| publish 前失败 | SNAPSHOT_CREATED 可 resume |
| publish 后 ack 失败 | 版本已存在；retry 幂等复用 |

## 7. 测试命令与结果

```bash
.venv\Scripts\python.exe -m pytest knowledge_curator/tests -q --tb=short
```

```text
109 passed in 0.97s — failed 0

test_atomic_commit.py       17
test_completeness.py        10
test_conflict.py             6
test_curator.py             13
test_phase11_regressions.py 13
test_phase12_regressions.py 19
test_phase21_persistence.py 26  (新增)
test_quality.py              7
```

既有 85 测试全绿；Phase 2.1 新增 24 项回归（含 binding/vector/publish/supersede/manifest/rollback）。

## 8. CONTRACT_GAPS

**无新增。** 按 Plan §11：CG-012/CG-013 保留；本轮为实现缺陷修复，不新开契约缺口。

## 9. TODO / placeholder

- StructuralKnowledgeStore / USDOStore / VectorIndex / VersionStore 仍为内部 Port（CG-004）
- 生产 L2 adapter 未接
- SUPERSEDE 仅 visibility 标记，完整真值判定仍待 CG-008

## 10. 外部依赖

- Python 3.12 标准库（hashlib/json/uuid/copy）
- pytest 9.1.1
- **无** SQLite / FAISS / DeepSeek / DSH / 网络

## 11. 是否修改公共契约

**NO**

## 12. 已知风险

1. Vector id 含 assertion_hash，内容微调会新 id（正确但会增加索引体积）。
2. SUPERSEDE 未做跨断言替换关系建模，仅本条 visibility。
3. `fail_on_nth` 类注入仍偏脆，建议生产侧用显式事务 id。

## 13. Git commit hash

```
implementation commit: <pending>
```
