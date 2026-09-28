# AI4S-ED

AI4S-ED 多智能体科研平台项目仓库。

## 当前协作方式

- **Planner：ChatGPT** — 读取上位设计、冻结模块边界、生成每轮执行计划、复核 Executor 的代码与测试。
- **Executor：Kimi / Codex** — 严格按 `planner/latest_plan.md` 编码、测试、提交，不自行改变总体架构和公共契约。
- **GitHub** — 作为 Planner / Executor 的状态交接面。

## 当前负责模块

`knowledge_curator`（知识策展 Agent），工作范围来自：

- `03 §5` 策审与入库；
- `03 §6` 中本模块需要提供的反幻觉检索/证据能力；
- `03 §7` 更新与增量治理。

## Executor 每轮启动顺序

1. 阅读 `docs/01-总体架构与数据流设计.md`；
2. 阅读 `docs/03-文献自动调研与知识入库流水线.md`；
3. 阅读 `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`；
4. 阅读 `status.json`；
5. 执行 `planner/latest_plan.md`；
6. 编码、测试、提交后更新 `status.json` 并写执行报告。

**01 是全项目锚文档。不得为了本模块方便自行修改公共契约或侵入其他 Agent 的职责。**
