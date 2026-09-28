# Phase 1 Plan — knowledge_curator §5 Core

**Planner:** ChatGPT  
**Executor:** Kimi / Codex  
**Status:** READY_FOR_EXECUTOR

## 0. 开始前必须阅读

1. `docs/01-总体架构与数据流设计.md`
2. `docs/03-文献自动调研与知识入库流水线.md`
3. `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`
4. `status.json`

不要脱离这些文件自行重构项目。

## 1. 本轮唯一目标

建立与 DSH runtime 解耦的 `knowledge_curator` 代码包，并完成 **03 §5 策审与入库核心**：

`AssertionSet -> completeness -> conflict -> quality -> decision -> CurationReport`

本轮不要完整实现 §6/§7。

## 2. 推荐结构

```text
knowledge_curator/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── curator.py
│   ├── completeness.py
│   ├── conflict.py
│   ├── quality.py
│   └── decision.py
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
├── tests/
│   ├── test_completeness.py
│   ├── test_conflict.py
│   ├── test_quality.py
│   └── test_curator.py
└── README.md
```

可按仓库 Python package 习惯小幅调整，但不能改变职责边界。

## 3. Schema 原则

- `AssertionSet` 是上游公共输入，不得重新发明。
- 若仓库当前没有正式公共 Schema，可在 `schemas/assertions.py` 创建 **temporary compatibility model**，严格兼容 03 已给字段：
  - ref_id
  - subject
  - property
  - object(value/unit/value_type/uncertainty)
  - conditions[]
  - provenance(locator 等)
  - claim_type
  - source_claim_origin
  - confidence
  - quality
- 不得新增新的公共 confidence 等级。

## 4. §5.1 完备性检查

至少实现：

- metadata：title / authors / year / source + (DOI OR stable_id)
- assertion 非空，或显式声明无结构化数据
- 数值 assertion 的单位要求
- provenance locator 要求
- ChartObject 质量相关输入的兼容检查（若上游字段尚未冻结，放 compatibility/contract gap）
- ParsedDoc quality：
  - A/B -> formal curation
  - C -> manual review
  - D/E -> 不进入正式面

规则尽量 deterministic，不使用 LLM。

## 5. §5.2 冲突检测

至少支持：

```text
consistent
condition_difference
numeric_conflict
relation_conflict
mechanism_violation
none
```

规则：

- 同 subject + property 下查既有断言。
- **不同 conditions 优先判为 condition_difference，不得直接判 numeric_conflict。**
- 同条件数值区间重叠/容差内 -> consistent。
- 同条件区间不交叠 -> numeric_conflict。
- bool/enum 相反 -> relation_conflict。
- L3 机理违背通过 `MechanismValidator` Port 调用；不要实现 L3 本体。
- 容差等阈值集中配置，不允许 magic numbers 散落。

## 6. §5.3 质量评分

严格实现文档当前公式，不自行“优化需求”：

```text
Q(doc) =
w1*P_parse
+ w2*S_schema
+ w3*E_evidence
+ w4*N_novelty
+ w5*penalty
```

权重可配置，默认值按文档约 0.25/0.25/0.30/0.10/0.10。

如果认为公式存在问题，只记录在 CONTRACT_GAPS，不修改上位需求。

## 7. 策展动作

内部允许：

```text
accept
downgrade
pending_review
supersede
reject
return_upstream
```

这些是 action，不是 confidence。

`confidence` 仍只有：

```text
verified
high
medium
hypothesis
```

## 8. Ports

不要写死真实 SQLite / FAISS / HTTP / DSH。

至少定义：

### KnowledgeRepository
- find_assertions(...)
- 可选的最小 commit/lookup 接口，为 Phase 1 测试服务

### MechanismValidator
- check(claims)

### OntologyService
- 仅定义本模块需要的实体/条件规范化查询边界；不要实现完整 EDDO。

测试使用 InMemory/Fake 实现。

## 9. 主服务

提供 runtime-independent API，例如：

```python
class KnowledgeCurator:
    async def curate(self, assertion_set, context=None) -> CurationReport:
        ...
```

处理顺序必须是：

```text
completeness
-> conflict detection
-> quality evaluation
-> curation decision
-> CurationReport
```

Phase 1 不要求真实生产 KB 原子提交。

## 10. CurationReport

至少可表达：

- report_id
- source_ref_id
- status
- completeness result
- conflicts
- per-assertion decisions
- quality score
- accepted/downgraded/rejected/pending counts
- warnings
- trace/provenance（若当前兼容模型有）
- commit/snapshot 字段可预留但不要伪造真实版本

如果公共 CurationReport 尚未冻结，标明 implementation-level temporary model。

## 11. DSH

目前没有正式 DSH runtime 代码。

- 不实现虚假的 SDK。
- `dsh/README.md` 说明未来将 `KnowledgeCurator.curate()` 包装为 DSH Agent/Tool entrypoint。
- core 不得 import DSH。

## 12. 必测用例

- T01 正常 AssertionSet -> successful curation
- T02 无 DOI 但 stable_id 存在 -> metadata valid
- T03 DOI/stable_id 都不存在 -> return_upstream/incomplete
- T04 数值 assertion 缺单位 -> downgrade/manual handling
- T05 locator 缺失 -> hypothesis + warning
- T06 同条件数值区间重叠 -> consistent
- T07 数值不同但 conditions 不同 -> condition_difference，且不是 numeric_conflict
- T08 同条件数值区间完全不重叠 -> numeric_conflict + pending_review
- T09 fake MechanismValidator 返回 violation -> mechanism_violation
- T10 全部核心测试不依赖真实 DSH runtime

## 13. 工程要求

- Python 类型标注
- public API docstring
- deterministic rule 优先
- 配置集中化
- async 只在真正 I/O 边界需要时使用
- core 不写死 SQLite/FAISS/HTTP
- 不复制其他 Agent 的代码
- 测试可独立运行

## 14. CONTRACT_GAPS

凡涉及以下情况，追加到 `planner/CONTRACT_GAPS.md`：

- 01/03 未定义清楚
- 需要 02/04/07 或其他组确认
- 公共 Schema 未冻结
- 当前只能 temporary compatibility 处理

不要自行拍板跨模块公共契约。

## 15. Executor 完成后必须

1. 跑完全部测试；
2. 提交代码；
3. 写 `results/phase-01-executor-report.md`，包括：
   - 文件树
   - 实现内容
   - 未实现内容
   - 测试命令和结果
   - CONTRACT_GAPS
   - TODO/placeholder
   - 是否改过公共契约（应为 NO）
   - commit hash
4. 更新根目录 `status.json`：
   - actor = executor
   - phase = 1
   - state = executor_complete
   - latest_commit = 实际 SHA
5. **停止，不得进入 Phase 2。**

等待 Planner 复核。
