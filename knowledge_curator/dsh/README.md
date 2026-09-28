# DSH Adapter (placeholder)

当前项目尚未确定 DeepSeek Harness Runtime 的正式 Python API。

**禁止编造** `@dsh.agent(...)` / `Agent(...)` 等未定义接口。

## 设计约定

```text
runtime-independent core
    +
thin DSH adapter later
```

- `knowledge_curator.core.KnowledgeCurator.curate()` 不依赖任何 DSH SDK。
- 未来 DSH 集成只做薄包装：把 `curate()` 注册为 Agent/Tool entrypoint，负责参数解析与日志上报。
- 本目录在 API 冻结前不放置任何伪造的 runtime 代码。

See planner/CONTRACT_GAPS.md (CG-001).
