# AI4S-ED Knowledge Curator — DeepSeek Harness 接入指南

本指南面向未参与 SI-4 开发的工程师，帮助你从最终交付 ZIP 完成 Knowledge Curator 与 DeepSeek Harness（DSH）的接入。

---

## 1. 准备交付文件

解压 `AI4S-ED-Knowledge-Curator-SI4-Delivery.zip` 后，确保以下目录存在：

```
knowledge-curator-si4/
├─ source/
│  ├─ knowledge_curator/        # Python 核心
│  ├─ system/                   # 系统集成层
│  └─ dsh/knowledge-curator/    # DSH Agent 包源码
├─ packages/
│  └─ knowledge-curator-dsh/    # DSH tgz 安装包
├─ docs/
├─ evidence/
└─ tests/
```

关键文件：
- `packages/knowledge-curator-dsh/ai4s-ed-knowledge-curator-dsh-0.2.0.tgz` — DSH 可安装包
- `source/knowledge_curator/` + `source/system/` — Python 运行时

---

## 2. 准备 Python 环境

设置 PYTHONPATH 指向交付源码根目录：

**Linux/macOS：**
```bash
export PYTHONPATH="<KC_DELIVERY_ROOT>/source"
python -c "import knowledge_curator"
python -c "import system.mcp_stdio"
```

**Windows PowerShell：**
```powershell
$env:PYTHONPATH="<KC_DELIVERY_ROOT>\source"
python -c "import knowledge_curator"
python -c "import system.mcp_stdio"
```

---

## 3. 必需环境变量

### AI4S_KC_PYTHON

DSH MCP client 启动 Python backend 时使用的 Python 可执行文件。

```bash
# Linux
export AI4S_KC_PYTHON=/path/to/python
# Windows
$env:AI4S_KC_PYTHON="C:\path\to\python.exe"
```

### AI4S_KC_WORKSPACE

`python -m system.mcp_stdio` 运行时的 Python workspace 根目录。必须保证 `knowledge_curator` 和 `system` 可以 import。

```bash
# Linux
export AI4S_KC_WORKSPACE="<KC_DELIVERY_ROOT>/source"
# Windows
$env:AI4S_KC_WORKSPACE="<KC_DELIVERY_ROOT>\source"
```

### AI4S_SYSTEM_ADAPTER_FACTORY

部署环境的 provider bundle factory，格式：`package.module:factory_function`

```bash
# Linux
export AI4S_SYSTEM_ADAPTER_FACTORY=my_provider:create_provider_bundle
# Windows
$env:AI4S_SYSTEM_ADAPTER_FACTORY="my_provider:create_provider_bundle"
```

**重要：** 交付包中的 `integration` fixtures 仅用于测试/qualification，生产环境必须替换为真实 provider factory。

---

## 4. Provider Factory 是什么

Knowledge Curator 是 runtime-independent 的 domain/application 实现，不硬编码数据库、向量库等。

DSH 启动 MCP backend 后：
```
python -m system.mcp_stdio
  → system.provider_loader (读取 AI4S_SYSTEM_ADAPTER_FACTORY)
    → system.composition (装配依赖)
      → Knowledge Curator runtimes
```

如果未配置 production provider，DSH preset 可以加载，但真实 commit/revision/retrieval 无法完成生产操作。

**Production provider 需要实现的依赖（根据真实 composition contract）：**

| 分组 | 依赖 |
|---|---|
| `curator` | `repository`, `ontology`, `mechanism_validator` |
| `commit` | `commit_store`, `structural_store`, `vector_index`, `usdo_store`, `version_store` |
| `revision` | `source_registry`, `lifecycle_store`, `event_outbox`, `publication_store` |
| `evidence`（可选） | `retrieval`, `mechanism_validator` |

Factory 返回一个 dict，包含上述分组。每个依赖必须满足对应 frozen Port 协议。

---

## 5. 安装 DSH Agent Package

**方式 A：tgz（推荐）**
```bash
pnpm add <KC_DELIVERY_ROOT>/packages/knowledge-curator-dsh/ai4s-ed-knowledge-curator-dsh-0.2.0.tgz
```

**方式 B：源码 pack**
```bash
cd <KC_DELIVERY_ROOT>/source/dsh/knowledge-curator
pnpm pack
pnpm add ./ai4s-ed-knowledge-curator-dsh-0.2.0.tgz
```

验证安装：
```bash
node -e "import('@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js').then(m=>console.log(m.name, typeof m.apply))"
# 预期输出: curator-bridge function
```

---

## 6. cordis.patch.yml

安装后位于：`node_modules/@ai4s-ed/knowledge-curator-dsh/cordis.patch.yml`

它声明 `knowledge-curator` preset，包含：
- `@deepseek-ai/dsh-persona` — Agent persona
- `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js` — native bridge tools
- `@deepseek-ai/dsh-mcp-client` — MCP stdio 连接

---

## 7. DSH Loader 验证（已 Qualification 验证）

**DSH 基线：** 0.2.0-rc.1（SHA `4878cdabd87d4041bdaff61d04c966883b9fd07a`）

```powershell
# Windows PowerShell
cd <DSH_ROOT>
node apps/cli/lib/bin.js --profile sdk-minimal --patch "<INSTALLED_KC_PACKAGE>\cordis.patch.yml" --dump-config
```

```bash
# Linux/macOS
cd <DSH_ROOT>
node apps/cli/lib/bin.js --profile sdk-minimal --patch "<INSTALLED_KC_PACKAGE>/cordis.patch.yml" --dump-config
```

**期望输出：**
- `preset-knowledge-curator` 已声明
- `id: knowledge-curator`
- 无 `broken` / `error` 诊断

**注意：** 这是 configuration / Loader validation，不是完整交互式 Agent session。

---

## 8. 在 DSH 中使用 knowledge-curator preset

DSH 0.2.0-rc.1 通过 Loader + AgentPresetRegistry API 加载 preset。以下是 qualification 验证通过的真实 API 模式：

```javascript
import { Context } from '@deepseek-ai/cordis'
import Loader from '@deepseek-ai/cordis-plugin-loader'
import Group from '@deepseek-ai/cordis-plugin-group'
import LlmRuntime from '@deepseek-ai/dsh-llm'
import SessionStore, { SessionId } from '@deepseek-ai/dsh-session'
import SessionProjectionRegistry from '@deepseek-ai/dsh-session-projection'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import AgentRegistry from '@deepseek-ai/dsh-agent'
import AgentLoop from '@deepseek-ai/dsh-agent-loop'
import AgentPresets from '@deepseek-ai/dsh-agent-preset-registry'

const ctx = new Context()
await ctx.plugin(Loader)
ctx.loader.builtins.group = Group
await ctx.plugin(LlmRuntime)
await ctx.plugin(SessionStore)
await ctx.plugin(SessionProjectionRegistry)
await ctx.plugin(SystemPrompt, { personaPrefix: '' })
await ctx.plugin(ToolRuntime)
await ctx.plugin(AgentRegistry)
await ctx.plugin(AgentLoop, { agents: [] })
await ctx.plugin(AgentPresets, { default: 'knowledge-curator' })

// 注册 preset（通过 installed cordis.patch.yml 或直接声明）
// ...

// 创建 Agent 并 mount preset
const handle = await ctx.agents.create({
  sessionId: SessionId('my-session'),
  setup: async (agentCtx) => {
    await ctx.agentPresets.mount(agentCtx, 'knowledge-curator')
  },
})
const agent = handle.agent

// 验证 native tools 可见
const scoped = ctx.tools.schemas(agent).map(r => r.name)
// 期望: ["knowledge_curator_commit", "knowledge_curator_revision"]

// 验证 global isolation
const global = ctx.tools.schemas().map(r => r.name)
// 期望: [] (native tools 不泄漏到 global)
```

---

## 9. MCP Backend 启动

`cordis.patch.yml` 中的 `@deepseek-ai/dsh-mcp-client` 自动启动：
```
AI4S_KC_PYTHON -m system.mcp_stdio
cwd: AI4S_KC_WORKSPACE
```

正常情况下不需要手工启动。排查 Python/backend 问题时可手动运行：
```bash
python -m system.mcp_stdio
```

---

## 10. Public MCP Tools vs Native DSH Tools

### Public MCP Tools（恰好四个）

由 `system.mcp_stdio` 暴露给 `@deepseek-ai/dsh-mcp-client`：

| 工具 | 作用 |
|---|---|
| `curate_assertion_set` | §5 策审 |
| `knowledge_curator_health` | 健康检查 |
| `retrieve_evidence` | §6 证据检索 |
| `validate_retrieved_claims` | §6 claim 验证 |

### Native DSH Tools（preset-scoped）

由 `runtime/bridge-plugin.js` 通过 `defineTool(...)` 注册：

| 工具 | 作用 |
|---|---|
| `knowledge_curator_commit` | §5 策审入库 |
| `knowledge_curator_revision` | §7 修订发布 |

它们是 preset-scoped，只在 `knowledge-curator` Agent 作用域可见，不出现在 `ctx.tools.schemas()` global view 中。

**设计原因：** MCP tools 面向 curation/retrieval/validation capability，保持 public contract 稳定；Native tools 面向 application-level commit/revision orchestration，与 DSH preset scope 绑定。

---

## 11. §5 Native Commit 调用

`knowledge_curator_commit` 输入：
```json
{
  "source_ref_id": "ED-001",
  "source_fingerprint": "fp-001",
  "assertion_set": {
    "ref_id": "ED-001",
    "metadata": {"title": "...", "authors": ["..."], "year": 2024, "source": "..."},
    "assertions": [{
      "id": "AS-001",
      "ref_id": "ED-001",
      "subject": {"eddo_class": "...", "resolved_entity": "...", "original_mention": "..."},
      "property": "...",
      "object": {"value": 1.42, "unit": "kWh/m3", "value_type": "number"},
      "conditions": [...],
      "provenance": {"locator": "p.1", "sentence": "..."},
      "claim_type": "measurement",
      "source_claim_origin": "primary",
      "confidence": "medium",
      "quality": 0.85
    }]
  },
  "metadata": {},
  "trace": {}
}
```

**成功 canonical result：**
```json
{
  "status": "published",
  "commit_attempted": true,
  "blocked_reason": null
}
```

---

## 12. §7 Native Revision 调用

`knowledge_curator_revision` 输入包含 `package`（RevisionPackage）和 `target_commit_request`。

**无审批时 canonical result：**
```json
{
  "status": "approval_required",
  "error": null
}
```

这不是失败，代表 revision 已到达 approval gate，符合 §7 生命周期设计。

---

## 13. §6 QA 使用

Knowledge Curator 不允许无证据回答：

| 情况 | 行为 |
|---|---|
| 无证据 | ABSTAIN |
| 无效引用 | ABSTAIN |
| 不支持的 claim | ABSTAIN |
| 有支持证据 | grounded answer |

---

## 14. 典型用户流程

1. DSH 启动 `knowledge-curator` preset
2. MCP client 启动 Python `system.mcp_stdio`
3. 使用 `knowledge_curator_health` 检查 backend
4. 使用 `retrieve_evidence` 查询证据
5. 使用 `validate_retrieved_claims` 验证 claim
6. 使用 `curate_assertion_set` 做 §5 curation
7. 需要 application commit 时调用 `knowledge_curator_commit`
8. 有 revision 时调用 `knowledge_curator_revision`

---

## 15. 最小接入流程

1. 解压 delivery ZIP
2. 设置 PYTHONPATH
3. 设置 AI4S_KC_PYTHON / AI4S_KC_WORKSPACE / AI4S_SYSTEM_ADAPTER_FACTORY
4. 安装 ai4s-ed-knowledge-curator-dsh-0.2.0.tgz
5. 找到 installed cordis.patch.yml
6. 让 DSH 加载该 patch
7. 确认 knowledge-curator preset declared
8. mount knowledge-curator Agent
9. 确认 native tools 可见
10. 确认四个 MCP tools
11. 运行 health / retrieval / curation smoke test

---

## 16. Windows PowerShell 完整示例

```powershell
$env:PYTHONPATH="D:\opt\knowledge-curator-si4\source"
$env:AI4S_KC_PYTHON="D:\venvs\kc\Scripts\python.exe"
$env:AI4S_KC_WORKSPACE="D:\opt\knowledge-curator-si4\source"
$env:AI4S_SYSTEM_ADAPTER_FACTORY="my_provider:create_provider_bundle"

pnpm add "D:\opt\knowledge-curator-si4\packages\knowledge-curator-dsh\ai4s-ed-knowledge-curator-dsh-0.2.0.tgz"

cd <DSH_ROOT>
node apps/cli/lib/bin.js --profile sdk-minimal --patch "<INSTALLED_KC>\cordis.patch.yml" --dump-config
```

---

## 17. Linux/macOS 示例

```bash
export PYTHONPATH=/opt/knowledge-curator-si4/source
export AI4S_KC_PYTHON=/opt/venvs/kc/bin/python
export AI4S_KC_WORKSPACE=/opt/knowledge-curator-si4/source
export AI4S_SYSTEM_ADAPTER_FACTORY=my_provider:create_provider_bundle

pnpm add /opt/knowledge-curator-si4/packages/knowledge-curator-dsh/ai4s-ed-knowledge-curator-dsh-0.2.0.tgz

cd <DSH_ROOT>
node apps/cli/lib/bin.js --profile sdk-minimal --patch "<INSTALLED_KC>/cordis.patch.yml" --dump-config
```

---

## 18. 接入验证 Checklist

- [ ] Python imports pass
- [ ] AI4S_KC_PYTHON configured
- [ ] AI4S_KC_WORKSPACE configured
- [ ] AI4S_SYSTEM_ADAPTER_FACTORY configured
- [ ] DSH package installed
- [ ] bridge plugin importable
- [ ] installed cordis.patch.yml located
- [ ] pinned DSH loads patch
- [ ] knowledge-curator preset declared
- [ ] preset is not broken
- [ ] Agent mounts successfully
- [ ] native commit tool visible
- [ ] native revision tool visible
- [ ] global native tools absent
- [ ] MCP has exactly four tools
- [ ] knowledge_curator_health works
- [ ] retrieval smoke works
- [ ] curation smoke works

---

## 19. 故障排查

| 问题 | 排查 |
|---|---|
| preset broken | 检查 package installed、cordis.patch.yml、DSH 版本、peer dependencies |
| Cannot find package | 检查 `@ai4s-ed/knowledge-curator-dsh` 是否安装在 DSH module resolution 环境 |
| bridge plugin not found | 验证 `node -e "import('@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js')..."` |
| MCP startup failed | 检查 AI4S_KC_PYTHON、AI4S_KC_WORKSPACE、PYTHONPATH |
| adapter factory import failed | 检查 AI4S_SYSTEM_ADAPTER_FACTORY 格式 `package.module:function` |
| native tool visible globally | 异常！`ctx.tools.schemas()` 应为 `[]` |
| revision returns conflict | 检查 RevisionPackage/target_commit_request 材料一致性；正常 qualification expected: `approval_required` |

---

## 20. 冻结边界

**This delivery is frozen.** 除非 confirmed bug 或 new explicitly approved contract，否则不修改核心代码。

## 21. Scope

本包是 Knowledge Curator / SI-4 完整交付包，不是整个 AI4S-ED 项目所有模块的完整代码包。
