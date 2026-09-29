# Phase 3.2 Executor Report — DSH Agent Preset Package Qualification

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-29  
**Phase:** 3.2  
**Scope:** 源码构建 + product bundle + real Loader 验证。无 live Agent turn。

---

## 1. DSH source commit / version

```text
repo:    https://github.com/deepseek-ai/deepseek-harness
commit:  4878cdabd87d4041bdaff61d04c966883b9fd07a
version: 0.2.0-rc.1
checkout: C:\dsh-src（仓库外，未 vendor）
```

## 2. Node / pnpm

```text
Node:  v24.9.0   (satisfies ^22.19 || >=24)
pnpm:  11.7.0
```

## 3. Source build

| 步骤 | 结果 |
|---|---|
| `pnpm install` | PASS（避开中文路径下的 Windows EPERM） |
| `pnpm run build` | PASS |
| `pnpm dsh --version` | `0.2.0-rc.1` |

**source build: PASS**

## 4. Bundle structure

```text
dsh/knowledge-curator/
├── package.json          # @ai4s-ed/knowledge-curator-dsh, dsh.bundle.patch
├── cordis.patch.yml      # configuration-only
└── README.md
```

## 5. Preset structure

- 恰好一个 `@deepseek-ai/dsh-agent-preset`
- `config.id = knowledge-curator`
- name: AI4S-ED Knowledge Curator
- description: §5 evidence completeness / conflict / quality gate

## 6. Persona

`@deepseek-ai/dsh-persona`：短 persona，明确不担任 lit_researcher / orchestrator / proposer / critic / mechanism validator / evaluation scheduler，不编造科学事实，用 MCP tool 做确定性策展。无 §6/§7 能力声明。

## 7. MCP child

```yaml
serverName: knowledge_curator
transport: stdio
command: !!js process.env.AI4S_KC_PYTHON || 'python'
args: ['-m', 'knowledge_curator.mcp_server']
cwd: !!js process.env.AI4S_KC_WORKSPACE || process.cwd()
failOnStartupError: true
toolCallTimeoutMs: 60000
```

无硬编码用户路径；无 DEEPSEEK_API_KEY 传入 MCP。

## 8. Registry ownership

**product bundle 不含** `@deepseek-ai/dsh-agent-preset-registry`。

独立 qualification fixture：`integration/dsh/fixtures/knowledge-curator-qualification.patch.yml`（TEST ONLY）。

## 9. Real Loader result

```text
loader_config_passed: true
preset_declared:      true
preset_broken:        false
```

使用 source-built 0.2 `pnpm dsh --dump-config --patch <bundle|qualif>` 真实 Loader 解析。

## 10. Preset activation

qualification fixture 中 registry default=knowledge-curator，persona/mcp-client 行均出现在 composed config。

## 11. Mount tested?

**preset_mount_tested: false**（按计划留待下一轮 preset-aware live Agent smoke；不伪造 mount 通过）。

## 12. Test counts

```text
integration/dsh: 60 passed / 0 failed
  - 既有 49 + bundle contract 11
knowledge_curator: 127 passed / 0 failed
```

## 13. CG-015 status

**OPEN** — source build + preset resolve 已满足；仍待真实 preset-aware Agent turn 才可关闭。

## 14. CONTRACT_GAPS

**无新增。**

## 15. Public contracts changed?

**NO**

## 16. Implementation commit SHA

```
implementation commit: <pending>
```

## 17. Qualification artifact

`results/phase-03-2-dsh-package-qualification.json`
