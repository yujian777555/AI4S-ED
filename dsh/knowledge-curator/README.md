# @ai4s-ed/knowledge-curator-dsh

AI4S-ED `knowledge_curator` 的 **DSH Agent Preset product bundle**（configuration-only）。

## 边界

本 bundle **只声明一个** Agent Preset：

- `id = knowledge-curator`
- 名称：AI4S-ED Knowledge Curator
- 职责：§5 证据完备性 / 冲突检测 / 质量置信评估 / 可信入库门禁

**禁止**在此 bundle 中放入：

- `@deepseek-ai/dsh-agent-preset-registry`（全局 registry 属于系统级）
- 其他 Agent preset
- §6 / §7 尚未实现的能力

全局 registry 仅出现在 `integration/dsh/` 的 **TEST / QUALIFICATION ONLY** fixture 中。

## Child plugins

| Plugin | 作用 |
|---|---|
| `@deepseek-ai/dsh-persona` | 短 persona：knowledge_curator 角色边界 |
| `@deepseek-ai/dsh-mcp-client` | stdio MCP → `python -m knowledge_curator.mcp_server` |

MCP public tool：

```text
mcp__knowledge_curator__curate_assertion_set
```

## 运行时配置（非密钥）

| 环境变量 | 说明 |
|---|---|
| `AI4S_KC_PYTHON` | Python 可执行文件；未设置时 fallback `python` |
| `AI4S_KC_WORKSPACE` | MCP 工作目录；未设置时 `process.cwd()` |

**不要**向 MCP subprocess 传递 `DEEPSEEK_API_KEY`（MCP server 不需要模型 Key）。
**不要**把用户机器绝对路径写进本仓库。

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
