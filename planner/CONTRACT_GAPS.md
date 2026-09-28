# Contract Gaps

本文件记录会影响其他团队/公共契约、但当前 01/03 尚未冻结的事项。

Executor 不得在这里的问题上自行改变全项目接口；可使用最小兼容层继续本轮，并写明临时处理。

| ID | 相关模块 | 缺口 | 当前临时处理 | 是否阻塞 Phase 1 | 需要确认方 |
|---|---|---|---|---|---|
| CG-001 | DSH runtime | 尚无正式 Agent/Tool 注册 API | core 与 runtime 解耦，仅保留 dsh adapter 说明 | 否 | 平台/08 |
| CG-002 | 02 / Schema Registry | 正式 AssertionSet / CurationReport Python Schema 尚未提供 | 按 03 字段建立 temporary compatibility model | 否 | 02/08 |
| CG-003 | 04 | Mechanism Validator 的真实调用形态尚未冻结 | 使用 Protocol + Fake | 否 | 04 |
| CG-004 | L2 | KnowledgeRepository 的正式读写 API 尚未冻结 | 使用 Protocol + InMemory adapter | 否 | 02/08 |
| CG-005 | 03 §5.3 | Q(doc) 公式中 `+ w5*penalty` 语义未写明：penalty 是“扣分后保留的正分项”还是“应从总分减去的惩罚”。 | Phase 1 按公式字面实现：penalty 从 1.0 起按冲突挂起/机理复核/图表 low 扣减，再以 +w5·penalty 加权。 | 否 | Planner |
| CG-006 | 03 §5.3 | `E_evidence = 出处定位完备率 + 一手来源占比` 未说明两比率是相加后归一还是取平均。 | Phase 1 取两者算术平均，保证 E_evidence ∈ [0,1]。 | 否 | Planner |
| CG-007 | 02 / EDDO | conditions 单位换算链与工况兼容性判定细则（跨单位可否换算后比对）未冻结。 | SimpleOntologyService 对不同 unit 一律判不兼容；不做盲换（符合 03 §4.3“无上下文禁止盲换”）。 | 否 | 02/04 |
| CG-008 | 03 §5.2 真值判定 | 数值冲突后的“证据强度排序 + 胜者升权/败者 supersede”细则（一手实验/综述/转引权重、期刊可信度、时效）未量化。 | Phase 1 对 numeric/relation conflict 一律 `pending_review`，不自动 supersede；完整真值判定留给 Planner 确认后的后续阶段。 | 否 | Planner |
| CG-009 | 03 §3.5 / §5.1 | ChartObject 上游字段（caption/axes/units/not_digitizable）正式 schema 未冻结。 | temporary `ChartObjectInfo` 最小兼容字段；不完整或 quality_low 时不参与 verified。 | 否 | 02/08 |
