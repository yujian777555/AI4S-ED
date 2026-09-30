# Phase 5.3-R2 Executor Report — Final Publication Material Lock

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 5.3-R2  

---

## 1. Scope

最终 publication material-lock correction。未加新功能，未创建 Phase 5.4。

## 2. Typed canonical scientific material

**PASS**

`canonical_value()` 保留 primitive/nested 类型：

- None/bool/int/float/str → 原生 JSON 类型
- list → 递归 canonical
- tuple → `{"__type__":"tuple","items":[...]}`
- dict → 递归 canonical + 确定性 key 排序
- Enum / exotic → 显式 type + representation

回归：`Condition(value=1) != Condition(value="1")`；`[1,2] != "[1, 2]"`；dict insertion order → same。

## 3. Existing decision/action/confidence/visibility guard

**PASS**

`_existing_commit_guard(package, request)` 从 `request.report` 推导 expected decision material：

| action | expected visibility |
|---|---|
| ACCEPT | ACTIVE |
| DOWNGRADE | DOWNGRADED |

比较 existing `AdmittedAssertion.action / confidence / visibility`。ACCEPT vs DOWNGRADE → CONFLICT；confidence mismatch → CONFLICT；visibility mismatch → CONFLICT。

## 4. Existing metadata/manifest guard

**PASS** — expected metadata hash（title/authors/year/source/doi/stable_id）与 existing `metadata_hash` / `manifest.metadata_hash` 比较。manifest ref/fingerprint 也要一致。mismatch → CONFLICT。

## 5. Post-target commit-store agreement

**PASS** — commit 返回后读 DocumentCommitStore：record.phase/version_id/snapshot_id 与结果一致。store 不可读 → fail closed；store 无 record（fake commit）→ 跳过。

## 6. Approval scope typed-material lock

**PASS** — scope hash 使用修正后的 typed canonical。`Condition(value=1)` vs `"1"` → scope hash 变更；nested dict 变更 → 变更；dict insertion order → 不变。

## 7. Fresh-vs-replay result semantics

**PASS**

| 场景 | idempotent | resumed |
|---|---|---|
| 首次 happy path | false | false |
| exact replay | true | true |
| crash recovery | true | true |

## 8. Real P2J E2E

**PASS** — 保持真实 DocumentCommitCoordinator + LifecycleRevisionCoordinator E2E。

## 9. Post-bind recovery

**PASS** — bind 成功后 journal 崩溃 → retry → FINALIZED idempotent/resumed。

## 10. 测试

```text
knowledge_curator: 499 passed / 0 skipped / 0 failed  (baseline 489 + 10)
integration/dsh:    90 passed / 0 failed
```

## 11. Public contracts changed?

**NO**

## 12. CONTRACT_GAPS

**无新增/修改**
