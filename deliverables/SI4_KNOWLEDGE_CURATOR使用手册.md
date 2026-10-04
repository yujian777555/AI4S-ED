# AI4S-ED Knowledge Curator 使用与部署手册

## 1. 模块说明

Knowledge Curator 是 AI4S-ED 文献自动调研与知识入库流水线中的科学知识策展 Agent，负责：

- **§5 Evidence Curation**：完整性检查、冲突检测、质量评分、策审决策
- **§5.4 Atomic Commit**：策审结果原子提交入库，生成不可变 KB 版本
- **§6 Anti-hallucination Retrieval QA**：证据优先的反幻觉检索问答
- **§7 Lifecycle / Revision / Publication**：知识生命周期更新与版本治理

## 2. 当前交付版本

| 项目 | 值 |
|---|---|
| 交付阶段 | SI-4 |
| 状态 | ACCEPTED / FROZEN / DELIVERABLE |
| Final CODE SHA | `322e53e3ac8319082188049e5e61e0ee13666540` |
| Pinned DeepSeek Harness | 0.2.0-rc.1 |
| Pinned DSH SHA | `4878cdabd87d4041bdaff61d04c966883b9fd07a` |

## 3. 交付目录结构

```
knowledge-curator-si4/
├─ README_DELIVERY.md          # 英文交付说明
├─ VERSION.txt                  # 版本信息
├─ MANIFEST.md                  # 文件清单
├─ SHA256SUMS.txt               # 校验和
├─ LICENSE_NOTICE.md            # 许可证说明
├─ source/                      # 完整源码
│  ├─ knowledge_curator/        # Knowledge Curator 核心
│  ├─ system/                   # 系统集成层
│  ├─ dsh/knowledge-curator/    # DSH Agent 包源码
│  └─ project-config/           # 项目配置
├─ tests/                       # 测试代码
│  ├─ knowledge_curator/        # 核心单元测试（522 个）
│  ├─ integration-system/       # 系统集成测试（190 个）
│  └─ integration-dsh/          # DSH 集成测试（109 个）
├─ docs/                        # 文档
│  ├─ architecture/             # 架构设计文档
│  ├─ usage/                    # 使用手册
│  └─ acceptance/               # 验收文件
├─ evidence/                    # 证据
│  └─ qualification/            # Qualification 证据
└─ packages/                    # 可安装包
   └─ knowledge-curator-dsh/    # DSH tgz 安装包
```

## 4. 核心源码位置

| 内容 | 路径 |
|---|---|
| Knowledge Curator 核心 | `source/knowledge_curator/` |
| 系统集成 | `source/system/` |
| DSH Agent 包源码 | `source/dsh/knowledge-curator/` |
| 可安装 DSH tgz | `packages/knowledge-curator-dsh/ai4s-ed-knowledge-curator-dsh-0.2.0.tgz` |

## 5. Public MCP Tools（恰好四个）

| 工具 | 作用 |
|---|---|
| `curate_assertion_set` | 对 AssertionSet 执行策审（完整性/冲突/质量/决策） |
| `knowledge_curator_health` | 健康检查，返回 adapter 身份和 retrieval 可用性 |
| `retrieve_evidence` | 检索证据包（EvidenceBundle），含 coverage 和 abstain 状态 |
| `validate_retrieved_claims` | 对 claim 进行证据验证，返回 policy/abstain/hallucination 检查结果 |

## 6. DSH Native Tools（preset-scoped，非 MCP）

| 工具 | 作用 |
|---|---|
| `knowledge_curator_commit` | §5 策审入库：curate → CurationCommitWorkflow → KB 版本 |
| `knowledge_curator_revision` | §7 修订发布：RevisionPackage → RevisionPublicationWorkflow → 新 KB 版本 |

这两个是 preset-scoped DSH native tools，**不是** public MCP tools。

## 7. 环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.11+ | Knowledge Curator 运行时 |
| Node.js | 22.19+ 或 24+ | DSH 运行时 |
| pnpm | 11.7.0 | 包管理 |
| DeepSeek Harness | 0.2.0-rc.1 | DSH Agent 框架（pinned） |

## 8. 必需环境变量

| 变量 | 用途 |
|---|---|
| `AI4S_KC_PYTHON` | 指定 DSH/MCP 启动 Knowledge Curator 时使用的 Python 可执行文件 |
| `AI4S_KC_WORKSPACE` | AI4S-ED / Knowledge Curator Python workspace 根目录 |
| `AI4S_SYSTEM_ADAPTER_FACTORY` | 部署环境的 provider bundle factory，格式：`package.module:factory_function` |

## 9. Python 源码使用方式

设置 PYTHONPATH 后即可导入：

**Linux/macOS：**
```bash
export PYTHONPATH=<KC_DELIVERY_ROOT>/source
python -c "import knowledge_curator"
python -c "import system.curator_agent_bridge_stdio"
```

**Windows PowerShell：**
```powershell
$env:PYTHONPATH="<KC_DELIVERY_ROOT>\source"
python -c "import knowledge_curator"
python -c "import system.curator_agent_bridge_stdio"
```

## 10. MCP Server 启动

```bash
export AI4S_KC_PYTHON=<python-executable>
export AI4S_KC_WORKSPACE=<AI4S_ED_ROOT>
export AI4S_SYSTEM_ADAPTER_FACTORY=<provider-factory>
python -m system.mcp_stdio
```

## 11. DSH 安装方式 A：tgz（推荐）

```bash
pnpm add ./packages/knowledge-curator-dsh/ai4s-ed-knowledge-curator-dsh-0.2.0.tgz
```

安装后 package 名：`@ai4s-ed/knowledge-curator-dsh`

## 12. DSH 安装方式 B：源码 pack

```bash
cd source/dsh/knowledge-curator
pnpm pack
pnpm add ./ai4s-ed-knowledge-curator-dsh-0.2.0.tgz
```

## 13. DSH Preset

package 中的 `cordis.patch.yml` 声明 `knowledge-curator` preset，包含：
- `@deepseek-ai/dsh-persona` — Agent persona
- `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js` — native bridge tools
- `@deepseek-ai/dsh-mcp-client` — MCP stdio 连接

## 14. DSH 实际运行链

```
DSH Runtime
  ↓
knowledge-curator preset (cordis.patch.yml)
  ↓
bridge-plugin.js
  ↓
knowledge_curator_commit / knowledge_curator_revision
  ↓
Python stdio bridge (system.curator_agent_bridge_stdio)
  ↓
CuratorAgentBridge
  ↓
CurationCommitWorkflow / RevisionPublicationWorkflow
  ↓
Frozen Coordinators → Stores
```

## 15. §5 使用说明

`knowledge_curator_commit` 负责：curation → validation → commit workflow → KB publication。

成功 canonical result：
```json
{
  "status": "published",
  "commit_attempted": true,
  "blocked_reason": null
}
```

## 16. §7 使用说明

`knowledge_curator_revision` 负责：RevisionPackage → revision workflow → approval gate → publication。

无审批时 canonical result：
```json
{
  "status": "approval_required",
  "error": null
}
```

## 17. §6 QA 使用说明

Knowledge Curator 不允许无证据回答：

| 情况 | 行为 |
|---|---|
| 无证据 | ABSTAIN |
| 无效引用 | ABSTAIN |
| 不支持的 claim | ABSTAIN |
| 有支持证据 | grounded answer |

## 18. Provider 接入说明

**重要：** Knowledge Curator 是 runtime-independent 的 domain/application 实现。

生产部署需要实现 `AI4S_SYSTEM_ADAPTER_FACTORY` 指向的 provider factory，对接实际的：
- database
- vector store
- version store
- document store
- source registry

交付包中的 integration fixtures / in-memory adapters **仅用于测试/qualification**，不是生产数据库。

## 19. 测试

```bash
pytest knowledge_curator/tests        # 522 passed
pytest integration/system/tests       # 190 passed
pytest integration/dsh/tests          # 109 passed
```

以上为 accepted executor-reported regression baseline。

## 20. Native DSH Qualification

已真实验证：
- `ctx.tools.schemas(agent)` = `["knowledge_curator_commit", "knowledge_curator_revision"]`
- `ctx.tools.schemas()` = `[]`（global isolation）
- §5 → `PUBLISHED`
- §7 → `APPROVAL_REQUIRED`

## 21. Package Qualification

已真实验证：
`pnpm pack` → clean install → package subpath import → installed `cordis.patch.yml` → pinned DSH Loader → `knowledge-curator` declared → preset not broken

## 22. 验收文件

- 最终验收：`docs/acceptance/SI4_FINAL_ACCEPTANCE.md`
- Qualification 证据：`evidence/qualification/`

## 23. 常见问题排查

| 问题 | 排查 |
|---|---|
| ModuleNotFoundError | 检查 PYTHONPATH、AI4S_KC_WORKSPACE |
| Provider factory 加载失败 | 检查 AI4S_SYSTEM_ADAPTER_FACTORY 格式是否为 `package.module:function` |
| DSH 找不到 preset | 检查 cordis.patch.yml、installed package、pinned DSH 版本 |
| DSH 找不到 bridge plugin | 检查 `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js` 是否可解析 |
| MCP 启动失败 | 检查 AI4S_KC_PYTHON、AI4S_KC_WORKSPACE、Python 环境 |

## 24. 冻结边界

**This delivery is frozen.** 除非 confirmed bug 或 new explicitly approved contract，否则不修改核心代码。

## 25. Scope

本包是 Knowledge Curator / SI-4 的完整交付包，**不是**整个 AI4S-ED 项目所有模块的完整代码包。
