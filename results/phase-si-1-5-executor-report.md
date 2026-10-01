# Phase SI-1.5 Executor Report — DSH Production Bootstrap Wiring

**Executor:** MiMo  
**Date:** 2026-10-01  
**Phase:** SI-1.5 / SI-1.5-R1  
**Module:** system_integration  

---

## Phase SI-1.5-R1 implementation CODE SHA

0f014f0

---

product preset uses system.mcp_stdio:
PASS

generated mcp_patch uses system.mcp_stdio:
PASS

mounted DSH lane supplies AI4S_SYSTEM_ADAPTER_FACTORY:
PASS

mounted DSH no longer relies on KC_EVIDENCE_INTEGRATION_FIXTURE for MCP composition:
PASS

README provider docs:
PASS

real stdio valid-provider startup:
PASS

exact four-tool discovery:
PASS

health provider identity:
PASS

curation round-trip:
PASS

missing-provider fail-closed:
PASS

actual mounted DSH live lane executed:
NOT_RUN_ENV（需 DeepSeek credential，本次未执行 live model round-trip；structural/bootstrap 验证已通过）

frozen trees changed?
NO

test results:
- knowledge_curator: 522 passed / 0 skipped / 0 failed
- integration/system: 58 passed / 0 skipped / 0 failed
- integration/dsh: 90 passed / 0 skipped / 0 failed

origin/main SHA:
（见 push 后）

deviations:
NONE

---

## R1 修改文件

- `dsh/knowledge-curator/README.md` — 重写，文档化 system.mcp_stdio + AI4S_SYSTEM_ADAPTER_FACTORY
- `integration/dsh/lane325_kc_evidence_roundtrip.e2e.ts` — 添加 AI4S_SYSTEM_ADAPTER_FACTORY，移除 KC_EVIDENCE_INTEGRATION_FIXTURE 对 MCP 的依赖
- `integration/dsh/mcp_patch.py` — args 改为 `system.mcp_stdio`
- `integration/dsh/tests/test_dsh_mcp_patch.py` — 更新入口断言
- `integration/system/tests/test_si15_r1_stdio_subprocess.py` — 新增真实 stdio subprocess 测试

## 未修改

- `knowledge_curator/**` 全部
- `system/composition.py` / `provider_loader.py` / `mcp_stdio.py`
- `planner/CONTRACT_GAPS.md`

---

## Phase SI-1.5-R2 implementation CODE SHA

0f014f0

direct reference integration_fixture=true asserted:
PASS

mounted/provider integration_fixture=false asserted:
PASS

integration provider fixture-corpus parity:
PASS

evidence chunk identity parity:
PASS

coverage/Abstain parity:
PASS

claim-guard policy parity:
PASS

integration provider uses forbidden InMemory/Fake adapters:
NO

run_lane325 supplies AI4S_SYSTEM_ADAPTER_FACTORY:
PASS

run_lane325 globally sets KC_EVIDENCE_INTEGRATION_FIXTURE:
NO

lane324 baseline receives provider contract:
PASS

mcp_smoke preserves caller-supplied provider:
PASS

mcp_smoke supplies integration provider when absent:
PASS

patch template documents system.mcp_stdio:
PASS

real stdio subprocess acceptance remains green:
PASS

actual mounted DSH live lane executed:
NOT_RUN_ENV

known deterministic mounted-live mismatch remains:
NO

knowledge_curator frozen tree changed:
NO

SI-1 frozen production composition changed:
NO

product preset changed during R2:
NO

CONTRACT_GAPS changed:
NO

orchestrator/workflow added:
NO

curation-to-commit wiring added:
NO

knowledge_curator tests:
522 passed / 0 skipped / 0 failed

integration/system tests:
78 passed / 0 skipped / 0 failed

integration/dsh tests:
90 passed / 0 skipped / 0 failed

origin/main SHA:
（见 push 后）

deviations:
NONE

---

## R2 修改文件

- integration/system/fixtures/dsh_provider.py — 重写证据适配器为测试本地类，对齐 fixture 语料
- integration/dsh/lane325_kc_evidence_roundtrip.e2e.ts — integration_fixture 边界断言（direct=true / DSH=false）
- integration/dsh/run_lane325.py — 设置 AI4S_SYSTEM_ADAPTER_FACTORY，移除全局 KC_EVIDENCE_INTEGRATION_FIXTURE
- integration/dsh/mcp_smoke.py — 新增 resolve_smoke_provider，保留调用方 provider / 缺省注入 integration provider
- integration/dsh/patches/knowledge-curator-mcp.patch.yml — 文档改为 system.mcp_stdio + provider 注入说明
- integration/system/tests/test_si15_r2_qualification_path.py — 20 个 keyless R2 回归

## 未修改 / R2

- knowledge_curator/** 全部
- system/composition.py / provider_loader.py / mcp_stdio.py
- planner/CONTRACT_GAPS.md
- dsh/knowledge-curator/cordis.patch.yml
