# Phase 1.1 Executor Report — confidence & conflict correctness fixes

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-28  
**Module:** knowledge_curator  
**Phase:** 1.1  
**Base implementation:** `5cfafc39637138c836a6c4590f9b05c6aa4b4275`  
**Scope:** 仅修复 Planner 评审阻塞项 P1-01 ~ P1-04，并补回归测试。未实现 §6/§7，未引入 DeepSeek/网络依赖。

---

## 1. 本轮完成内容

| ID | 问题 | 修复 |
|---|---|---|
| P1-01 | single-source confidence 可错误保留 HIGH / auto-verified | `decision.py` 新增 `_cap_single_source`：单源 primary/secondary 一律 ≤ medium；verified 不自动授予 |
| P1-02 | secondary + consistent 被抬升 HIGH | consistent 分支：secondary → medium（需一手回溯）；primary + 非自 ref_id consistent → high |
| P1-03 | relation/enum 比较忽略 condition_difference | `conflict.compare_pair` 先做 condition 兼容判定，再做 enum/numeric 分类 |
| P1-04 | 相对容差对 <1 值有隐式 1.0 底垫 | `_intervals_compatible` 用真实量级；仅 `absolute_tolerance` 作近零下限 |
| D | chart 校验变异输入 | `_check_charts` 非变异；`quality._penalty` 直接检查字段完整性 |

并按 plan §A–§D 补齐回归测试；同步修正既有 `test_verified_is_not_auto_granted` 期望。

## 2. 实际文件树（本轮变更）

```text
knowledge_curator/
├── core/
│   ├── completeness.py     # 非变异 chart 校验
│   ├── conflict.py         # P1-03 / P1-04
│   ├── decision.py         # P1-01 / P1-02 confidence gate
│   └── quality.py          # chart penalty 不依赖变异字段
└── tests/
    ├── test_curator.py           # 更新 verified 用例
    └── test_phase11_regressions.py   # 新增 P1-01~P1-04 回归
planner/CONTRACT_GAPS.md    # 追加 CG-011
results/phase-01-1-executor-report.md
status.json
```

## 3. 新增/修改文件列表

### 修改

- `knowledge_curator/core/decision.py`
- `knowledge_curator/core/conflict.py`
- `knowledge_curator/core/completeness.py`
- `knowledge_curator/core/quality.py`
- `knowledge_curator/tests/test_curator.py`
- `planner/CONTRACT_GAPS.md`
- `status.json`

### 新增

- `knowledge_curator/tests/test_phase11_regressions.py`
- `results/phase-01-1-executor-report.md`

### 未修改

- `docs/01-总体架构与数据流设计.md`
- `docs/03-文献自动调研与知识入库流水线.md`
- `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`
- 公共 confidence 枚举（仍为 verified/high/medium/hypothesis）
- schemas 公共契约字段（仍为 temporary compatibility model）

## 4. 对应实现的 Plan 项

| Plan 项 | 实现 |
|---|---|
| §A Confidence gate | `_cap_single_source` + consistent 分支 origin 门禁 |
| §B Conditions before relation | `compare_pair` 条件兼容前置 |
| §C Relative tolerance | 去掉 1.0 底垫，量级自适应 |
| §D Validation side effects | chart 校验纯函数化 |
| DeepSeek policy | 本轮零网络调用；core 仍 runtime-independent |

## 5. 未实现内容

- 03 §5.4 原子入库 / KB-version
- 03 §5.2 真值判定 supersede（CG-008）
- 03 §6 / §7
- 真实 DeepSeek API / DSH Runtime 集成
- source-family 全局独立性 schema（CG-011，按 plan 用 non-self ref_id 代理）

## 6. 测试命令

```bash
.venv\Scripts\python.exe -m pytest knowledge_curator/tests -v --tb=short
```

## 7. 完整测试结果

```text
platform win32 -- Python 3.12.13, pytest-9.1.1
collected 49 items

test_completeness.py      10 passed
test_conflict.py           6 passed
test_curator.py           11 passed   (含更新后的 verified 用例)
test_phase11_regressions.py 13 passed (新增)
test_quality.py            7 passed

TOTAL: 49 passed in 0.43s — failed 0
```

### Phase 1.1 回归映射

| 用例 | 覆盖 | 结果 |
|---|---|---|
| single primary upstream high -> medium | P1-01 | PASSED |
| single primary upstream verified -> not verified/high | P1-01 | PASSED |
| single secondary clean -> medium | P1-01 | PASSED |
| secondary + consistent existing -> not high | P1-02 | PASSED |
| primary + compatible independent existing -> high | P1-02 | PASSED |
| ENUM opposite under different conditions -> condition_difference | P1-03 | PASSED |
| ENUM opposite under same conditions -> relation_conflict | P1-03 | PASSED |
| ENUM agree same conditions -> consistent | P1-03 | PASSED |
| sub-unit close values -> consistent | P1-04 | PASSED |
| sub-unit materially different -> numeric_conflict | P1-04 | PASSED |
| sub-unit conflict surfaces in curator | P1-04 | PASSED |
| chart validation does not mutate input | D | PASSED |
| incomplete chart penalizes quality without mutation | D | PASSED |

## 8. CONTRACT_GAPS

新增：

| ID | 缺口 | 临时处理 |
|---|---|---|
| CG-011 | source-family / 来源独立性 schema 未冻结 | 用 non-self `ref_id` 作独立性代理；不发明全局 schema |

既有 CG-001~CG-010 保持不变。本轮 **无其他新缺口**。

## 9. TODO / placeholder

- 同 Phase 1：commit_id/kb_version 预留 None；dsh/ 仅说明文档；Ports 等待 02/04/L2 冻结。
- source-family 独立性待 02/08 定义后可替换 non-self ref_id 代理。

## 10. 外部依赖

- Python 3.12 标准库
- pytest 9.1.1（本地 `.venv`）
- **无** DeepSeek API / DSH / SQLite / FAISS / HTTP / 网络调用

## 11. 是否修改公共契约

**NO**

- 未改 docs/01、docs/03、Boundary
- confidence 枚举未扩展
- schemas 仍为 temporary compatibility model
- 未增加 §6/§7 范围

## 12. 已知风险

1. non-self ref_id 独立性代理偏松：同一来源系列的不同 ref_id 可能被当作独立多源（CG-011）。
2. 单源一律 ≤ medium 可能使上游已人工核实的高质量单源也被压到 medium；verified 信号需后续契约（CG-008/信任信号）才能释放。
3. 亚单位数值在 `absolute_tolerance=1e-9` 下仅相对容差起作用；若领域需要不同量级 floor，需配置层扩展（非本轮范围）。

## 13. Git commit hash

```
implementation commit: 9611bb2e86720bad6c548c2ac30c4cb8c0e36361
```

`status.json.latest_commit` 已记录该实现提交。
