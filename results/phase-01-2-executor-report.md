# Phase 1.2 Executor Report — confidence monotonicity & tolerance semantics

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-28  
**Module:** knowledge_curator  
**Phase:** 1.2  
**Base implementation:** `9611bb2e86720bad6c548c2ac30c4cb8c0e36361`  
**Scope:** 仅关闭 Planner 评审阻塞项 P1.2-01 / P1.2-02。未实现 §5.4/§6/§7，未接 DeepSeek，未改公共契约。

---

## 1. 本轮完成内容

| ID | 问题 | 修复 |
|---|---|---|
| P1.2-01 | “at most medium” 被实现成 “always medium”，会把 hypothesis 抬成 medium | `decision._at_most_medium` 单调上限：hypothesis→hypothesis，medium→medium，high/verified→medium；consistent 多源路径禁止 hypothesis 直跳 high |
| P1.2-02 | 双边扩张使 5% 容差接近 10% | `_intervals_compatible`：raw 重叠先 consistent；否则只扩张 existing/reference；相对容差按 reference 量级 |

### P1.2-01 行为矩阵

| incoming | 单源 primary | 单源 secondary | consistent primary | consistent secondary |
|---|---|---|---|---|
| hypothesis | hypothesis | hypothesis | hypothesis | hypothesis |
| medium | medium | medium | high | medium |
| high | medium | medium | high | medium |
| verified | medium | medium | high（非 verified） | medium |

### P1.2-02 判定顺序

1. raw interval overlap → consistent  
2. 否则仅扩张 reference：`pad = max(relative_tolerance * |ref|, absolute_tolerance)`  
3. new ∩ expanded(reference) 非空 → consistent，否则 numeric_conflict  

回归样例（默认 5%）：1.00/1.04 一致；1.00/1.09 冲突；0.0100/0.0104 一致；0.0100/0.0109 冲突。

## 2. 实际文件树（本轮变更）

```text
knowledge_curator/
├── core/
│   ├── decision.py          # P1.2-01 单调 confidence 上限
│   └── conflict.py          # P1.2-02 单侧容差
└── tests/
    └── test_phase12_regressions.py   # 新增回归
results/phase-01-2-executor-report.md
status.json
```

## 3. 新增/修改文件列表

### 修改
- `knowledge_curator/core/decision.py`
- `knowledge_curator/core/conflict.py`
- `status.json`

### 新增
- `knowledge_curator/tests/test_phase12_regressions.py`
- `results/phase-01-2-executor-report.md`
- `results/pytest-phase-01-2-output.txt`

### 未修改
- docs/01、docs/03、Boundary、公共 confidence 枚举、schemas 契约字段
- 未触碰 §5.4/§6/§7

## 4. 对应实现的 Plan 项

| Plan 项 | 实现 |
|---|---|
| §A Confidence monotonicity | `_at_most_medium` 单调上限；hypothesis 不提升；multi-source 仅 medium/high 可到 high |
| §B Exact tolerance | raw overlap → 仅扩张 reference → 相交判定 |
| §C Bookkeeping | 本轮不改 1.1 报告（文档性，不阻塞） |
| DeepSeek policy | 零网络调用 |

## 5. 未实现内容

- §5.4 原子入库 / KB-version
- §5.2 真值判定 supersede（CG-008）
- §6 / §7
- DeepSeek / DSH 集成
- source-family 全局独立性（CG-011 仍用 non-self ref_id 代理）

## 6. 测试命令

```bash
.venv\Scripts\python.exe -m pytest knowledge_curator/tests -v --tb=short
```

## 7. 完整测试结果

```text
platform win32 -- Python 3.12.13, pytest-9.1.1
collected 68 items

test_completeness.py       10 passed
test_conflict.py            6 passed
test_curator.py            13 passed
test_phase11_regressions.py 13 passed
test_phase12_regressions.py 19 passed (新增)
test_quality.py             7 passed

TOTAL: 68 passed in 0.48s — failed 0
```

### Phase 1.2 回归映射

| 用例 | 覆盖 | 结果 |
|---|---|---|
| primary single-source hypothesis stays hypothesis | P1.2-01 | PASSED |
| secondary single-source hypothesis stays hypothesis | P1.2-01 | PASSED |
| condition_difference + hypothesis stays hypothesis | P1.2-01 | PASSED |
| primary single-source medium stays medium | P1.2-01 | PASSED |
| primary single-source high/verified cap to medium | P1.2-01 | PASSED |
| secondary high caps to medium (monotone) | P1.2-01 | PASSED |
| consistent primary hypothesis not jump to high | P1.2-01 | PASSED |
| consistent primary medium can reach high | P1.2-01 | PASSED |
| consistent secondary hypothesis not promoted | P1.2-01 | PASSED |
| cap monotone across ladder | P1.2-01 | PASSED |
| existing 1.00 vs new 1.04 consistent | P1.2-02 | PASSED |
| existing 1.00 vs new 1.09 numeric_conflict | P1.2-02 | PASSED |
| existing 0.0100 vs new 0.0104 consistent | P1.2-02 | PASSED |
| existing 0.0100 vs new 0.0109 numeric_conflict | P1.2-02 | PASSED |
| raw overlapping uncertainty intervals consistent | P1.2-02 | PASSED |
| raw range overlap consistent | P1.2-02 | PASSED |
| new inside expanded reference consistent | P1.2-02 | PASSED |
| new just outside expanded reference conflict | P1.2-02 | PASSED |

## 8. CONTRACT_GAPS

**本轮无新增 CONTRACT_GAPS。** CG-001~CG-011 保持不变。

## 9. TODO / placeholder

同 Phase 1.1：commit/kb_version 预留；Ports 等待外部冻结；DeepSeek 仅未来 adapter。

## 10. 外部依赖

- Python 3.12 标准库
- pytest 9.1.1（本地 `.venv`）
- **无** DeepSeek / DSH / SQLite / FAISS / HTTP / 网络

## 11. 是否修改公共契约

**NO**

## 12. 已知风险

1. consistent 路径 incoming=verified 落为 high（多源成就级）而非 medium：符合“永不 auto-verified”，但若 Planner 要求 verified 一律压到 medium，可一行收紧。
2. 容差方向性以 existing 为 reference；若未来图中查询顺序相反，语义需在 L2 API 冻结时对齐（CG-004）。
3. non-self ref_id 独立性代理局限见 CG-011。

## 13. Git commit hash

```
implementation commit: <pending>
```
