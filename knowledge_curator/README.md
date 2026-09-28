# knowledge_curator — Phase 1

`knowledge_curator` 是 AI4S-ED L4 策审 Agent 的 Phase 1 实现，覆盖 **03 §5 策审与入库核心**：

```text
AssertionSet
    ↓
Completeness Check   (03 §5.1)
    ↓
Conflict Detection   (03 §5.2)
    ↓
Quality Evaluation   (03 §5.3)
    ↓
Curation Decision
    ↓
CurationReport
```

## 边界

| 负责 | 不负责 |
|---|---|
| 完备性检查 | 文献检索 / PDF 解析 |
| 冲突检测（含 condition_difference） | 完整 Assertion 抽取 Agent |
| 质量评分 Q(doc) | L3 机理模型本体（Donnan/NP/CFD…） |
| 策展决策与 CurationReport | RADE / 实验 Agent / Watchdog / memory_arbiter |
| Ports + InMemory/Fake adapters | 真实 SQLite / FAISS / HTTP / DSH |

公共 Schema 未冻结前，`schemas/` 内模型为 **temporary compatibility model**（见 `planner/CONTRACT_GAPS.md`）。

## 快速使用

```python
from knowledge_curator import KnowledgeCurator, AssertionSet
from knowledge_curator.adapters import (
    InMemoryKnowledgeRepository,
    FakeMechanismValidator,
    SimpleOntologyService,
)

curator = KnowledgeCurator(
    repository=InMemoryKnowledgeRepository(),
    ontology=SimpleOntologyService(),
    mechanism_validator=FakeMechanismValidator(),
)
report = await curator.curate(assertion_set)
```

## 测试

```bash
python -m pytest knowledge_curator/tests -v
```

核心逻辑不依赖真实 DSH Runtime。

## 模块

```text
knowledge_curator/
├── config.py          # 权重/阈值/容差集中配置
├── core/              # completeness / conflict / quality / decision / curator
├── schemas/           # temporary compatibility models
├── ports/             # KnowledgeRepository / MechanismValidator / OntologyService
├── adapters/          # InMemory / Fake / Simple ontology
├── dsh/               # 未来 thin adapter 说明（无伪造 API）
└── tests/             # T01–T10
```
