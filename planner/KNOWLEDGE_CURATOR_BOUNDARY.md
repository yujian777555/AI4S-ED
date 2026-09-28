# Knowledge Curator Boundary

> 本文件是协作边界说明，不替代 01/03。若本文件与 01/03 冲突，以 01 为最高优先级、03 为本模块实现依据。

## 1. Agent 身份

- agent id: `knowledge_curator`
- layer: L4
- 上位职责：抽取规范化、冲突检测、质量评分、入库修订。
- 主输入/输出：`AssertionSet -> CurationReport + 原子提交快照`

## 2. 本模块负责

### 03 §5
- 完备性检查
- 冲突检测
- 质量评分
- 策展决策
- 原子入库所需的业务编排/接口适配
- 人工复核升级条件
- 版本/审计信息输出

### 03 §6
- 为既有知识消费方提供文档规定的证据检索、证据定位、confidence 门禁、引用校验、Abstain/反幻觉校验能力
- H1/H2/H3 的本模块检测结果输出
- 不接管最终面向用户的回答组织

### 03 §7
- 新版本/增量知识的策展侧处理
- 撤稿、勘误、修订
- soft archive / superseded / pending review
- 新 KB version 的策展侧提交
- 向其他模块发布失效/修订事件

## 3. 明确不负责

- `lit_researcher` 的文献/专利/标准检索
- PDF/XML/LaTeX 解析
- 原始 Assertion 抽取器
- orchestrator 任务分解与最终输出
- proposer / critic / RADE 业务逻辑
- L3 机理模型和约束校验器本体
- exp_designer / dry_lab_runner / wet_protocoler / validator
- 07 全局 Watchdog、全局指标口径、模型重训
- memory_arbiter
- 自行重新设计 EDDO / USDO / AssertionSet 公共契约

## 4. 开发纪律

1. 01/03 是上位约束，不能为了“更漂亮”而改架构。
2. 外部模块一律通过 Port/Adapter 交互；不要复制别人的实现。
3. 当前没有正式 DSH runtime API，因此核心业务必须 runtime-independent。
4. 不得编造 `@dsh.agent`、`Agent(...)` 等未定义 API。
5. 公共 Schema 未冻结时，只允许建立兼容模型，并明确标记为 temporary compatibility model。
6. 对影响其他组的缺口写入 `planner/CONTRACT_GAPS.md`，不要私自定案。
7. deterministic rule 优先；LLM 只处理规则难以覆盖的语义判断。
8. `confidence` 保持统一枚举：`verified/high/medium/hypothesis`。
9. 事实级知识不可物理删除；修订/撤稿遵循版本化、soft archive、可回滚纪律。

## 5. 第一阶段范围

Phase 1 只实现 03 §5 的核心业务、schemas、ports、测试和文档。

**禁止提前完整实现 §6 / §7。**
