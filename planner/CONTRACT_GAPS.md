# Contract Gaps

本文件记录会影响其他团队/公共契约、但当前 01/03 尚未冻结的事项。

Executor 不得在这里的问题上自行改变全项目接口；可使用最小兼容层继续本轮，并写明临时处理。

| ID | 相关模块 | 缺口 | 当前临时处理 | 是否阻塞 Phase 1 | 需要确认方 |
|---|---|---|---|---|---|
| CG-001 | DSH runtime | 尚无正式 Agent/Tool 注册 API | core 与 runtime 解耦，仅保留 dsh adapter 说明 | 否 | 平台/08 |
| CG-002 | 02 / Schema Registry | 正式 AssertionSet / CurationReport Python Schema 尚未提供 | 按 03 字段建立 temporary compatibility model | 否 | 02/08 |
| CG-003 | 04 | Mechanism Validator 的真实调用形态尚未冻结 | 使用 Protocol + Fake | 否 | 04 |
| CG-004 | L2 | KnowledgeRepository 的正式读写 API 尚未冻结 | 使用 Protocol + InMemory adapter | 否 | 02/08 |
