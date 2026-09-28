# Contract Gaps

本文件记录会影响其他团队/公共契约、但当前 01/03 尚未冻结的事项。

Executor 不得在这里的问题上自行改变全项目接口；可使用最小兼容层继续本轮，并写明临时处理。

| ID | 相关模块 | 缺口 | 当前临时处理 | 是否阻塞 Phase 1 | 需要确认方 |
|---|---|---|---|---|---|
| CG-001 | DSH runtime / model backend | 尚无正式 DSH Agent/Tool 注册 API；Planner 已确认开发阶段可临时使用 DeepSeek API 作为模型后端 | core 与 runtime 解耦；后续通过可替换 Reasoning/LLM Adapter 接 DeepSeek API，禁止把 API 调用写入 deterministic core，也不视为 DSH Runtime 已冻结 | 否 | 平台/08 |
| CG-002 | 02 / Schema Registry | 正式 AssertionSet / CurationReport Python Schema 尚未提供 | 按 03 字段建立 temporary compatibility model | 否 | 02/08 |
| CG-003 | 04 | Mechanism Validator 的真实调用形态尚未冻结 | 使用 Protocol + Fake | 否 | 04 |
| CG-004 | L2 | KnowledgeRepository 的正式读写 API 尚未冻结 | 使用 Protocol + InMemory adapter | 否 | 02/08 |
| CG-005 | 03 §5.3 | Q(doc) 公式中 `+ w5*penalty` 语义未写明：penalty 是“扣分后保留的正分项”还是“应从总分减去的惩罚”。 | Phase 1 按公式字面实现：penalty 从 1.0 起按冲突挂起/机理复核/图表 low 扣减，再以 +w5·penalty 加权。 | 否 | Planner |
| CG-006 | 03 §5.3 | `E_evidence = 出处定位完备率 + 一手来源占比` 未说明两比率是相加后归一还是取平均。 | Phase 1 取两者算术平均，保证 E_evidence ∈ [0,1]。 | 否 | Planner |
| CG-007 | 02 / EDDO | conditions 单位换算链与工况兼容性判定细则（跨单位可否换算后比对）未冻结。 | SimpleOntologyService 对不同 unit 一律判不兼容；不做盲换（符合 03 §4.3“无上下文禁止盲换”）。 | 否 | 02/04 |
| CG-008 | 03 §5.2 真值判定 | 数值冲突后的“证据强度排序 + 胜者升权/败者 supersede”细则（一手实验/综述/转引权重、期刊可信度、时效）未量化。 | Phase 1 对 numeric/relation conflict 一律 `pending_review`，不自动 supersede；完整真值判定留给 Planner 确认后的后续阶段。 | 否 | Planner |
| CG-009 | 03 §3.5 / §5.1 | ChartObject 上游字段（caption/axes/units/not_digitizable）正式 schema 未冻结。 | temporary `ChartObjectInfo` 最小兼容字段；不完整或 quality_low 时不参与 verified。 | 否 | 02/08 |

| CG-010 | DeepSeek API | 临时模型后端已获允许，但具体模型、鉴权配置、超时/重试/结构化输出契约尚未冻结 | 后续需要 LLM reasoning 时新增 Port/Adapter；API key 仅环境变量/secret 注入，不入仓库；Phase 1.1 不引入网络调用 | 否 | Planner/08 |
| CG-011 | 03 §5.3 多源一致性 / 来源独立性 | “多源一致”所需 source-family / 来源独立性 schema 未冻结（同一课题组多篇、同一数据库转引等是否算独立） | Phase 1.1 按 Planner 指示使用 non-self `ref_id` 作为独立性代理；同 ref_id 不自证，跨 ref_id 且数值 consistent + primary 才可升 high。局限已知，不发明全局 source-family schema | 否 | Planner/02/08 |
| CG-012 | 03 §5.4 幂等语义 | §5.4 写“重复提交仅做 merge/version bump”，与“同 fingerprint 不重复发布”存在歧义：完全相同 fingerprint 重提究竟只做 lookup，还是允许 bump 出新版本号 | Phase 2 按 Planner 指示采用安全 exact-retry 幂等：同 `(ref_id, source_fingerprint)` 已发布则返回既有结果，不重复 structural/vector/snapshot/version；仅同 ref_id + 不同 fingerprint 才允许新版本 | 否 | Planner/02/08 |
| CG-013 | 03 §5.4 跨存储事务 | 真正跨 SQLite/FAISS/文件的 ACID 不可行；文档未给出失败矩阵与补偿 SLA | Phase 2 实现 atomic visibility 状态机 + pending_vector 补偿重放；不假装跨存储 ACID。生产 L2 事务边界/隔离级别待冻结 | 否 | 02/08 |
