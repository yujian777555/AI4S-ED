# DSH Runtime Smoke (Phase 3.0)

验证 **官方 DeepSeek Harness Python SDK** 能否启动真实 DSH Runtime，并通过
`provider/model` 路由调用真实 DeepSeek API。

## 基准

- 仓库: https://github.com/deepseek-ai/deepseek-harness
- 审阅 release: `0.2.0-rc.1`
- 审阅 commit: `4878cdabd87d4041bdaff61d04c966883b9fd07a`
- 实际 PyPI `deepseek-harness-sdk` 见 smoke JSON（可能与审阅版本不一致）

## 用法

```bash
# keyless
pytest integration/dsh/tests

# live（需要 DEEPSEEK_API_KEY）
export DEEPSEEK_API_KEY=...
export DSH_HOME=/absolute/isolated/home
export DSH_MODEL=...
python -m integration.dsh.smoke
```

## 环境变量

| 变量 | 说明 |
|---|---|
| `DSH_HOME` | 必须显式隔离路径，不使用 `~/.dsh` |
| `DSH_MODEL` | 模型 id（可配置） |
| `DEEPSEEK_API_KEY` | 仅环境注入，禁止写入仓库 |
| `DEEPSEEK_BASE_URL` | 可选 |
| `DSH_PROFILE` | 默认 `sdk-minimal` |
| `DSH_MAX_TOKENS` | 默认 256 |

## 禁止

- 在 `knowledge_curator/core|schemas` 引入 DSH
- 把 API Key 写进代码/报告/日志
- 实现 MCP server / Agent preset / §6（后续 Phase）
