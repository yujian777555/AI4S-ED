# Phase 3.0 Executor Report — Official DSH Runtime + DeepSeek API Smoke

**Executor:** MiMo Coding Agent  
**Date:** 2026-09-28  
**Phase:** 3.0  
**Scope:** 仅验证官方 DeepSeek Harness runtime + DeepSeek API 路由。未实现 MCP/bundle/preset/§6/§7。

---

## 1. SDK 安装结果

| 项 | 值 |
|---|---|
| 安装包 | `deepseek-harness-sdk` |
| 实际安装版本 | **0.1.5rc1** |
| 配套 runtime | `deepseek-harness-runtime-bin==0.1.5rc1` (win_amd64) |
| 审阅基准 | release `0.2.0-rc.1` / commit `4878cdabd87d4041bdaff61d04c966883b9fd07a` |
| **版本一致性** | **MISMATCH**（PyPI 最高仅 0.1.5rc1，无 0.2.0-rc.1） |
| 安装方式 | pip 网络 SSL 失败 → curl 下载 wheel 后 `pip install --no-index` |
| SDK import | OK |

> **版本 mismatch 已显式记录，等待 Planner 裁定。** Live smoke 在 0.1.5rc1 上执行，不宣称与 0.2.0-rc.1 行为等价。

## 2. SDK / Runtime version evidence

```text
deepseek-harness-sdk:        0.1.5rc1
deepseek-harness-runtime-bin: 0.1.5rc1
Python:                      3.12.13
OS:                          Windows-11-10.0.26200-SP0
reviewed upstream release:   0.2.0-rc.1
reviewed upstream commit:    4878cdabd87d4041bdaff61d04c966883b9fd07a
```

## 3. DSH_HOME / profile / provider / model

```text
DSH_HOME:   isolated temp (DSH_HOME_ALLOW_TEMP=1), not ~/.dsh
workspace:  isolated temp
profile:    sdk-minimal
provider:   deepseek-official
model:      deepseek-chat   (env DSH_MODEL, configurable)
```

## 4. Keyless tests

```bash
.venv-dsh\Scripts\python.exe -m pytest integration/dsh/tests -v
```

```text
15 passed / 0 failed
```

覆盖：SDK import、配置拒绝空/相对路径、DSH_HOME 隔离、provider/model 传递、
session id、secret masking、错误路径、cleanup 前置校验、core 无 DSH import。

## 5. Existing knowledge_curator tests

```bash
.venv\Scripts\python.exe -m pytest knowledge_curator/tests -q
```

```text
127 passed / 0 failed
```

## 6. Live API attempted

**YES** — 使用官方 `from deepseek_harness import DeepSeekHarness`，经 `DeepSeekHarnessConfig`
的 provider/model 路由调用真实 DeepSeek API。

命令（密钥仅环境变量，未写入任何文件）：

```bash
DEEPSEEK_API_KEY=*** DSH_HOME_ALLOW_TEMP=1 DSH_MODEL=deepseek-chat \
  python -m integration.dsh.smoke
```

结果：**LIVE_SMOKE_PASS**

## 7. Turn 1 / Turn 2 same-session continuity

| 轮次 | 结果 |
|---|---|
| Turn 1（存储 sentinel） | completed，final_response 非空 |
| Turn 2（同 session_id 回忆） | completed，返回 sentinel `AI4S_ED_DSH_SMOKE_2026` |
| session_continuity_passed | **true** |
| finish_reasons | `["completed", "completed"]` |

证明链：API 连接 + DSH AgentLoop + session persistence + provider/model 路由。

## 8. Secret leak check

- 报告/smoke JSON **无** API key
- `secret_present: true` 仅表示环境变量存在，不含值
- 代码/README/测试输出无 Authorization header
- `mask_secret()` 永不回显原值

## 9. Smoke artifact

`results/phase-03-0-dsh-smoke.json`（无 secret）

## 10. CONTRACT_GAPS

**无新增。** CG-001/CG-014 等保持不变。

**需 Planner 关注的版本事实（非新 GAP，属执行记录）：**
PyPI `deepseek-harness-sdk` 最新为 `0.1.5rc1`，与审阅基准 `0.2.0-rc.1` 不一致。

## 11. Public project contract changed?

**NO**

## 12. Implementation commit SHA

```
implementation commit: d17c77720cc9f83ca8221fc67f67ef24c12ae5f7
```

`status.json.latest_commit` 已记录该实现提交。

## 13. 未做事项（按计划禁止）

- knowledge_curator MCP server / FastMCP
- `@deepseek-ai/dsh-mcp-client` bundle
- Agent preset / DSH bundle
- §6 / §7
- 任何 requests/httpx/OpenAI 绕过 DSH 的直连调用
