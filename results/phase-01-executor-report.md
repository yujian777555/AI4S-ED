# Phase 1 Executor Report — knowledge_curator §5 Core

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-28  
**Module:** knowledge_curator  
**Phase:** 1  
**Scope:** 03 §5 策审与入库核心（completeness → conflict → quality → decision → CurationReport）

---

## 1. 本轮完成内容

- 建立与 DSH runtime 解耦的 `knowledge_curator` Python 包。
- 实现 03 §5.1 完备性检查（deterministic rules）。
- 实现 03 §5.2 冲突检测（consistent / condition_difference / numeric_conflict / relation_conflict / mechanism_violation）。
- 实现 03 §5.3 质量评分公式 `Q(doc)=w1·P_parse+w2·S_schema+w3·E_evidence+w4·N_novelty+w5·penalty`。
- 实现策展决策（accept / downgrade / pending_review / reject / return_upstream）与 `CurationReport`。
- 定义 Ports：`KnowledgeRepository` / `MechanismValidator` / `OntologyService`。
- 提供 InMemory/Fake/Simple adapters 供独立测试。
- `dsh/README.md` 说明未来 thin adapter；core 不 import DSH。
- 单元与端到端测试 T01–T10 全部通过（36 tests）。
- 更新 `planner/CONTRACT_GAPS.md`（新增 CG-005 ~ CG-009）。

## 2. 实际文件树

```text
knowledge_curator/
├── __init__.py
├── config.py
├── README.md
├── core/
│   ├── __init__.py
│   ├── completeness.py
│   ├── conflict.py
│   ├── curator.py
│   ├── decision.py
│   └── quality.py
├── schemas/
│   ├── __init__.py
│   ├── assertions.py
│   └── curation.py
├── ports/
│   ├── __init__.py
│   ├── knowledge_repository.py
│   ├── mechanism_validator.py
│   └── ontology_service.py
├── adapters/
│   ├── __init__.py
│   └── in_memory_repository.py
├── dsh/
│   ├── __init__.py
│   └── README.md
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_completeness.py
    ├── test_conflict.py
    ├── test_curator.py
    └── test_quality.py
pytest.ini
results/
├── phase-01-executor-report.md
└── pytest-output.txt
```

## 3. 新增/修改文件列表

### 新增

- `knowledge_curator/` 全部源码与测试（见上文件树）
- `pytest.ini`
- `results/phase-01-executor-report.md`
- `results/pytest-output.txt`

### 修改

- `planner/CONTRACT_GAPS.md` — 追加 CG-005 ~ CG-009
- `status.json` — actor/state/latest_commit 更新

### 未修改

- `docs/01-总体架构与数据流设计.md`
- `docs/03-文献自动调研与知识入库流水线.md`
- `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`
- `planner/latest_plan.md`
- 任何公共 confidence 枚举（仍为 verified/high/medium/hypothesis）

## 4. 对应实现了 03 §5 哪些要求

| 要求 | 实现位置 | 说明 |
|---|---|---|
| §5.1 元数据完备（title/authors/year/source + DOI 或 stable_id） | `core/completeness.py` | 缺 DOI+stable_id → return_upstream |
| §5.1 断言非空 / 显式无结构化数据 | `core/completeness.py` | no_assertions / explicit_no_data |
| §5.1 数值断言 100% 带单位 | `core/completeness.py` | missing_unit → downgrade/hypothesis |
| §5.1 出处定位 locator | `core/completeness.py` | 缺 locator → hypothesis + warning |
| §5.1 ChartObject 质量 | `core/completeness.py` | chart_quality_low，不参与 verified |
| §5.1 ParsedDoc A/B/C/D/E 分级 | `core/completeness.py` | A/B 正式面，C 人工，D/E 不进 |
| §5.2 同 subject+property 查询既有断言 | `core/conflict.py` + KnowledgeRepository port | |
| §5.2 工况差异 ≠ 冲突 | `core/conflict.py` | 优先 `condition_difference` |
| §5.2 同工况区间重叠 → consistent | `core/conflict.py` | 容差可配置 |
| §5.2 同工况区间不交叠 → numeric_conflict | `core/conflict.py` | → pending_review |
| §5.2 布尔/枚举相反 → relation_conflict | `core/conflict.py` | |
| §5.2 机理违背 → MechanismValidator port | `ports/mechanism_validator.py` | 不实现 L3 本体 |
| §5.3 Q(doc) 公式与默认权重 | `core/quality.py` + `config.py` | 0.25/0.25/0.30/0.10/0.10 |
| §5.3 B 级 P_parse 扣 20% | `core/quality.py` | p_parse_b = 0.8 |
| §5.3 penalty（冲突挂起/机理/图表 low 扣分） | `core/quality.py` | |
| 策展动作枚举 | `schemas/curation.py` | accept/downgrade/pending_review/supersede/reject/return_upstream |
| confidence 统一枚举 | `schemas/assertions.py` | verified/high/medium/hypothesis |
| CurationReport | `schemas/curation.py` | 含 counts/warnings/trace；commit 字段预留为 None |
| runtime-independent API | `core/curator.py` | `async def curate(...)` |

## 5. 未实现内容（按计划留待后续阶段）

- 03 §5.4 原子入库 / 三载体落库 / KB-version 快照（Phase 1 不要求真实生产提交）
- 03 §5.2 真值判定完整证据强度排序与 `supersede` 自动升权（CG-008）
- 03 §6 反幻觉检索问答
- 03 §7 更新与增量 / 撤稿勘误
- 真实 DSH Runtime 集成
- 真实 L2 SQLite / FAISS / L3 约束校验器
- 完整 Assertion 抽取 Agent / 文献搜索 / PDF 解析

## 6. 所有测试命令

```bash
# 使用本地 venv（MIMO_PYTHON 未预装 pytest，故建 .venv；未污染托管运行时）
.venv\Scripts\python.exe -m pytest knowledge_curator/tests -v --tb=short
```

## 7. 完整测试结果

```text
platform win32 -- Python 3.12.13, pytest-9.1.1
collected 36 items

test_completeness.py  10 passed  (含 T01–T05 完备性场景)
test_conflict.py       6 passed  (含 T06–T09 冲突场景)
test_curator.py       11 passed  (含 T01–T10 端到端 + 契约护栏)
test_quality.py        7 passed

TOTAL: 36 passed in 0.29s
```

关键用例映射：

| 用例 | 结果 |
|---|---|
| T01 正常 AssertionSet → successful curation | PASSED |
| T02 无 DOI 但 stable_id → metadata valid | PASSED |
| T03 DOI/stable_id 全缺 → return_upstream | PASSED |
| T04 数值缺 unit → downgrade/hypothesis | PASSED |
| T05 locator 缺失 → hypothesis + warning | PASSED |
| T06 同工况区间重叠 → consistent | PASSED |
| T07 不同工况 → condition_difference（非 numeric_conflict） | PASSED |
| T08 同工况区间不交叠 → numeric_conflict + pending_review | PASSED |
| T09 mechanism violation → mechanism_violation + reject | PASSED |
| T10 核心不依赖 DSH | PASSED |

## 8. CONTRACT_GAPS

既有：CG-001 ~ CG-004（见 `planner/CONTRACT_GAPS.md`）。

本轮新增：

| ID | 缺口 | 临时处理 |
|---|---|---|
| CG-005 | `+ w5*penalty` 语义歧义 | 按公式字面：penalty 从 1.0 扣减后加权 |
| CG-006 | E_evidence 两比率组合方式未写明 | 取算术平均，保持 ∈[0,1] |
| CG-007 | conditions 跨单位换算细则未冻结 | 不同 unit 判不兼容，不盲换 |
| CG-008 | 真值判定证据强度排序未量化 | 一律 pending_review，不自动 supersede |
| CG-009 | ChartObject 正式字段未冻结 | temporary ChartObjectInfo |

## 9. TODO / placeholder

- `CurationReport.commit_id` / `kb_version` / `snapshot_id` 预留为 `None`（不伪造版本）。
- `dsh/` 目录仅文档说明，无实现（禁止编造 API）。
- `OntologyService` / `KnowledgeRepository` / `MechanismValidator` 为 Protocol + Fake/InMemory，等待 02/04/L2 冻结后替换 adapter。
- §5.4 原子入库接口预留，未接真实存储。

## 10. 外部依赖

- 运行时：Python 3.12 标准库（dataclasses / enum / typing / asyncio / uuid）
- 测试：pytest 9.1.1（本地 `.venv`，未写入仓库依赖锁定）
- **无** DSH SDK、SQLite、FAISS、HTTP 客户端、第三方科学计算库

## 11. 是否修改公共契约

**NO**

- 未修改 docs/01、docs/03、Boundary、latest_plan
- 未新增/修改全局 confidence 枚举（verified/high/medium/hypothesis）
- schemas 标注为 **temporary compatibility model**（CG-002）
- 冲突类型与策展 action 严格按 plan §5/§7 枚举

## 12. 已知风险

1. 真值判定未完整实现（CG-008）：冲突断言全部挂起，长期可能堆积 pending_review 队列。
2. quality 公式两处歧义（CG-005/006）：若 Planner 重新解释，需要调整 `core/quality.py` 但测试基线可复用。
3. 条件兼容性对 unit 敏感（CG-007）：上游若给出等价但不同写法的 unit，会被误判 condition_difference。
4. 本地 git 与 github.com 直连受限：本轮通过 GitHub API 提交；若 API 配额受限，可能影响推送时序。

## 13. Git commit hash

```
commit (phase 1 implementation): 5cfafc39637138c836a6c4590f9b05c6aa4b4275
origin/main (after push): see remote tip
```
