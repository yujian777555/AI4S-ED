# @ai4s-ed/knowledge-curator-dsh

AI4S-ED `knowledge_curator` 的 **DSH Agent Preset product bundle**（configuration-only）。

## 边界

本 bundle **只声明一个** Agent Preset：

- `id = knowledge-curator`
- 名称：AI4S-ED Knowledge Curator
- 职责：证据完整性 / 冲突检测 / 质量置信评估 / 可信入库门禁

**禁止**在此 bundle 中放入：

- `@deepseek-ai/dsh-agent-preset-registry`（全局 registry 属于系统级）
- 其他 Agent preset
- §6 / §7 尚未实现的能力

全局 registry 仅出现在 `integration/dsh/` 的 **TEST / QUALIFICATION ONLY** fixture 中。

## Child plugins

| Plugin | 作用 |
|---|---|
| `@deepseek-ai/dsh-persona` | 知识 persona：knowledge_curator 角色边界 |
| `@deepseek-ai/dsh-mcp-client` | stdio MCP → `python -m system.mcp_stdio` |

## MCP 启动入口

```text
python -m system.mcp_stdio
```

## 运行时配置（非密钥）

| 环境变量 | 说明 |
|---|---|
| `AI4S_KC_PYTHON` | Python 可执行文件；未设置时 fallback `python` |
| `AI4S_KC_WORKSPACE` | MCP 工作目录；未设置时 `process.cwd()` |
| `AI4S_SYSTEM_ADAPTER_FACTORY` | **必需。** 生产依赖工厂标识，格式 `package.module:factory_function` |

### AI4S_SYSTEM_ADAPTER_FACTORY

这是一个 **部署方拥有的标识符**，不是密钥。

- 缺失或无效 → MCP 启动 **fail-closed**（进程失败，不回退 InMemory/Fake）
- adapter 需要的密钥/凭证由部署方自行配置，**不得提交到仓库**
- 生产环境 **不会** 自动启用 `KC_EVIDENCE_INTEGRATION_FIXTURE`

示例（集成测试专用，非生产推荐）：

```text
AI4S_SYSTEM_ADAPTER_FACTORY=integration.system.fixtures.dsh_provider:create_provider_bundle
```

## MCP public tools

```text
mcp__knowledge_curator__curate_assertion_set
mcp__knowledge_curator__knowledge_curator_health
mcp__knowledge_curator__retrieve_evidence
mcp__knowledge_curator__validate_retrieved_claims
```

## 目标 DSH 版本

```text
deepseek-harness 0.2.0-rc.1
commit 4878cdabd87d4041bdaff61d04c966883b9fd07a
```

Preset mount 须在 Agent 创建的 `setup` 阶段由调用方执行（本 bundle 不接管 Agent factory）：

```ts
ctx.agents.create({
  setup: async (agentCtx) => {
    await ctx.agentPresets.mount(agentCtx, "knowledge-curator")
  }
})
```
