# Phase 4.3.1 Executor Report — Guardability / H2 / Mounted DSH Closure

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 4.3.1  

---

## 1. Commit integrity

本轮提交包含**真实代码 + smoke 证据**：

- `knowledge_curator/retrieval/evidence_models.py` — guardable 不变量 + `evaluate_anchorability` helper
- `knowledge_curator/retrieval/evidence_service.py` — coverage 仅计可构建 anchor 的记录
- `knowledge_curator/retrieval/guard_service.py` — H2 诚实 checked 语义（`evaluate_h2_checked` / `H2CheckedStatus`）
- `knowledge_curator/mcp_server/app.py` — UTF-8 乱码修复
- `knowledge_curator/mcp_server/evidence_runtime.py` — `KC_EVIDENCE_INTEGRATION_FIXTURE` 显式开关
- `knowledge_curator/mcp_server/__init__.py` — MCP 惰性导入
- `dsh/knowledge-curator/cordis.patch.yml` — persona 最小扩展（仍为 knowledge-curator）
- `integration/dsh/lane325_kc_evidence_roundtrip.e2e.ts` — mounted Agent evidence E2E
- `integration/dsh/run_lane325.py` / `vitest.phase431.config.ts` — runner
- `knowledge_curator/tests/test_phase431_semantics.py` — 21 项
- `integration/dsh/tests/test_phase431_dsh_preset.py` — 5 项
- `results/phase-04-3-1-executor-report.md` / `results/phase-04-3-1-dsh-evidence-smoke.json`

## 2. guardability / evidence_type invariant

**PASS**

- `guardable_as_anchor == (build_evidence_anchor(record) is not None)`
- 合法 anchor 要求：ref_id + locator + confidence + **valid evidence_type**
- evidence_type 缺失且无合法 default → `missing_evidence_type`
- evidence_type 显式非法 → `invalid_evidence_type`（**不**回落 default/GRAPH）
- literature default 仅在 provenance 未显式给出类型时生效

## 3. coverage-anchor consistency

**PASS**

- 统一 helper `evaluate_anchorability`
- coverage `guardable_count` 只计 `build_evidence_anchor` 能成功的记录
- 测试：confidence+locator 但 evidence_type=None/default=None → NOT_COVERED
- invalid explicit evidence_type → unguardable
- valid literature default → COVERED
- 双向不变量成立

## 4. H2 checked semantics

**PASS**

| 场景 | h2_checked | 状态 |
|---|---|---|
| 未提供 cited DOI/title | true（ref-existence 范围） | CHECKED |
| cited DOI + KB DOI 可比 | true | CHECKED（可产生 mismatch finding） |
| cited DOI + KB DOI 不可用 | false | METADATA_UNAVAILABLE |
| cited title + KB title 不可用 | false | METADATA_UNAVAILABLE |
| DOI+title 都提供但缺一 | false | PARTIAL |
| 空 retrieval set | false | NOT_APPLICABLE / unavailable |

**metadata unavailable ≠ H2 hallucination finding**。只有真实 DOI/title mismatch 才生成 H2 finding。无 Crossref/web。

## 5. MCP UTF-8 cleanup

**PASS** — `app.py` 中 `搂5.1鈥撀?.3` / `鈥?` 等乱码已修为 `§5.1–§5.3` / `—`。业务逻辑不变。

## 6. Integration fixture 显式开关

**PASS**

- `KC_EVIDENCE_INTEGRATION_FIXTURE=1` → 标记 `integration_fixture=true` 的 synthetic fixture
- 未设置 / 其它值 → production `retrieval_unavailable: not_configured`
- 默认不泄漏 fixture

## 7. raw MCP tools

**PASS** — stdio 发现 `curate_assertion_set` / `knowledge_curator_health` / `retrieve_evidence` / `validate_retrieved_claims`。

## 8. mounted DSH Agent tool discovery

**PASS** — 复用 Phase 3.2.4 `launchWebScaffold` + `ctx.agents.create(agentPreset=knowledge-curator)` + `ctx.agentPresets.mount` + `ctx.tools.schemas(handle.agent)`。

mounted Agent schema 实测包含：

```
mcp__knowledge_curator__curate_assertion_set
mcp__knowledge_curator__knowledge_curator_health
mcp__knowledge_curator__retrieve_evidence
mcp__knowledge_curator__validate_retrieved_claims
```

preset id 仍为 `knowledge-curator`，未新建 Agent。

## 9. mounted DSH live roundtrip

**FAILED**（prerequisite 齐备后执行失败）

- credential_available = true
- DSH runtime / scaffold 可启动
- 但 DeepSeek live turn 产生 **0** `tool/call` 事件（`assistant/attempt` 后 `turn/end`，无文本）
- 同一时间窗口内 baseline `lane324`（curate_assertion_set）同样 0 tool/call
- 判定：EMPTY_RESPONSE 类 API/模型波动，非 evidence 工具特有缺陷
- 已重试 1 次，仍为 0

| 项 | 状态 |
|---|---|
| mounted DSH retrieve_evidence live | **FAILED** |
| mounted DSH validate_retrieved_claims live | **FAILED** |
| direct-vs-DSH evidence identity match | **NOT_RUN_ENV**（无 live tool result 可比） |
| direct-vs-DSH policy match | **NOT_RUN_ENV** |

## 10. 测试

```text
knowledge_curator: 311 passed / 0 skipped / 0 failed  (baseline 290 + 21)
integration/dsh:    83 passed / 0 failed              (baseline 78 + 5)
```

## 11. 边界

- 未开始 §7
- 未新建 Agent
- 未实现 final QA generator
- 未改 Phase 4.0/4.1/4.2 冻结语义

## 12. Public contracts changed?

**NO**

## 13. CONTRACT_GAPS

**无新增**
