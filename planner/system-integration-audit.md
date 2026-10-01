# AI4S-ED System Integration Audit

**Date:** 2026-10-01  
**Role:** Executor / System Integration Engineer  
**Basis:** origin/main @ `c540497`  
**knowledge_curator status:** ACCEPTED / FROZEN / DELIVERABLE @ `42e3912`

---

## 1. 当前 DSH 实际调用链

```
DSH Agent (TypeScript, knowledge-curator preset)
  ↓  cordis.patch.yml → @deepseek-ai/dsh-mcp-client (stdio)
  ↓  python -m knowledge_curator.mcp_server
  ↓
MCP Server (knowledge_curator/mcp_server/app.py)
  ├─ curate_assertion_set(assertion_set: dict)
  │    → parse_assertion_set() → KnowledgeCurator.curate() → CurationReport → serialize
  ├─ knowledge_curator_health()
  ├─ retrieve_evidence(request: dict)
  │    → EvidenceRetrievalService.retrieve() → EvidenceBundle
  └─ validate_retrieved_claims(payload: dict)
       → fresh retrieve + ClaimGuardService.validate_claims()
```

**断点：** MCP 层只暴露 curate / retrieve / validate / health 四个工具。`DocumentCommitCoordinator` / `IncrementalIntakeService` / `RevisionPackageBuilder` / `RevisionPublicationCoordinator` / `LifecycleRevisionCoordinator` **无任何 production 调用**。

---

## 2. MCP Runtime 当前 composition

| 组件 | 当前 wiring | 类型 |
|---|---|---|
| `KnowledgeRepository` | `InMemoryKnowledgeRepository` | **integration/test** |
| `OntologyService` | `SimpleOntologyService` | **integration/test** |
| `MechanismValidator` | `FakeMechanismValidator` | **integration/test** |
| Evidence retrieval | 仅 `KC_EVIDENCE_INTEGRATION_FIXTURE=1` 时用 InMemory fixture | **test-only** |
| Production evidence | `retrieval_unavailable / not_configured` | **fail-closed（正确）** |

`knowledge_curator/mcp_server/runtime.py` 明确标注 `INTEGRATION_ADAPTER_NOTE = "integration-test adapters (in-memory/fake)"`。**无 production composition layer。**

---

## 3. 哪些 adapter 是 Fake / InMemory / fixture

| Adapter | 文件 | 类型 |
|---|---|---|
| `InMemoryKnowledgeRepository` | adapters/in_memory_repository.py | test |
| `SimpleOntologyService` | adapters/in_memory_repository.py | test |
| `FakeMechanismValidator` | adapters/in_memory_repository.py | test |
| `InMemoryDocumentCommitStore` | adapters/in_memory_commit.py | test |
| `InMemoryStructuralKnowledgeStore` | adapters/in_memory_commit.py | test |
| `InMemoryUSDOStore` | adapters/in_memory_commit.py | test |
| `InMemoryVectorIndex` | adapters/in_memory_commit.py | test |
| `InMemoryVersionStore` | adapters/in_memory_commit.py | test |
| `InMemoryLifecycleStore` | adapters/in_memory_lifecycle.py | test |
| `InMemoryEventOutbox` | adapters/in_memory_lifecycle.py | test |
| `InMemorySourceVersionRegistry` | adapters/in_memory_source_versions.py | test |
| `InMemoryRevisionPublicationStore` | adapters/in_memory_revision_publication.py | test |
| `InMemoryVectorSearch` / `InMemoryKeywordSearch` / `FakeReranker` | adapters/in_memory_retrieval.py | test |
| `InMemoryEvidenceStore` | adapters/in_memory_evidence.py | test |

**所有 adapter 均为 InMemory/Fake。无 SQLite / FAISS / 真实 BM25 / 真实 reranker / 真实版本存储 production adapter。**

---

## 4. 当前是否存在真正 orchestrator

**不存在。** 搜索 production 代码中 orchestrator / bootstrap / agent_factory / system_runtime 模式，仅命中 docs 文档描述，无任何 Python/TypeScript 实现。

当前仅有：
- DSH preset（配置）
- MCP server（工具接口）
- integration tests（测试）
- `knowledge_curator/dsh/__init__.py`（placeholder："No runtime API yet"）

---

## 5. curate_assertion_set 是否只 curate

**是。** 实现仅为：
```python
parsed = parse_assertion_set(assertion_set)
report = await run_curate(rt, parsed)
return {"ok": True, "report": serialize_curation_report(report)}
```
只做 AssertionSet → CurationReport。**不涉及 commit / lifecycle / publication。** 符合设计意图。

---

## 6. commit/lifecycle 当前从哪里调用

| 组件 | 调用位置 |
|---|---|
| `DocumentCommitCoordinator` | 仅 knowledge_curator core + tests |
| `RevisionPublicationCoordinator` | 仅 knowledge_curator core + tests |
| `LifecycleRevisionCoordinator` | 仅 knowledge_curator core + tests |
| `IncrementalIntakeService` | 仅 knowledge_curator core + tests |
| `RevisionPackageBuilder` | 仅 knowledge_curator core + tests |

**无任何 production 调用链。** 零 DSH / MCP / orchestrator 集成。

---

## 7. Production evidence retrieval 是否已接通

**未接通。** `evidence_runtime.py` production 默认 `retrieval_unavailable / not_configured`（fail-closed，正确）。无 production retrieval stack 注入路径。

---

## 8. 当前 DSH live integration 能证明什么

- config contract PASS（preset 形状 / 密钥脱敏 / patch 合法性）
- MCP protocol PASS（工具列表 / call_tool / codec）
- tool discovery PASS（mounted Agent schema 含 4 个 MCP 工具）
- fixture PASS（InMemory adapter + synthetic fixture）
- raw MCP PASS（stdio subprocess 调用 curate / retrieve / validate）
- historical live smoke PASS（Phase 3.2.4 curate_assertion_set live round-trip，已 CG-015 CLOSED）

---

## 9. 当前 DSH live integration 不能证明什么

- **real production repository adapter** — 无
- **real retrieval backend**（FAISS/BGE-M3/BM25 production 配置）— 无
- **real system orchestrator** — 无
- **real curation→commit application wiring** — 无
- **real end-to-end application runtime**（parser→curate→commit→lifecycle→publish）— 无
- **production evidence retrieval** — 无

---

## 10. 系统级 integration gaps

| Gap | 状态 | 描述 |
|---|---|---|
| **A. Production Runtime Composition** | **真实存在** | MCP runtime 全部 InMemory/Fake，无 production adapter 注入路径 |
| **B. System-Level Orchestrator** | **真实存在** | 无 Agent Factory / Orchestrator / Bootstrap / System Runtime |
| **C. Curation→Commit Wiring** | **真实存在** | curate 只返回 CurationReport，无 commit/lifecycle/publication 调用链 |

---

## 11. 推荐的最小实现边界

```
AI4S-ED System Runtime (新)
         |
    +----+----+
    |         |
 DSH Agent  Orchestrator (新)
 Factory      |
    |         +-- CurationWorkflow (curate → commit)
 knowledge-curator    +-- RevisionWorkflow (delta → publish → lifecycle)
  MCP tools           +-- QAEvidenceWorkflow (retrieve → validate)
    |
 KnowledgeCurator (frozen)
```

**新增层（不侵入冻结核心）：**
1. `system/` 目录 — orchestrator + workflow + production adapter composition
2. Production adapter implementations（可先用可配置的外部服务桩）
3. 最小系统入口（CLI / bootstrap）

**不动：** knowledge_curator core / schemas / ports / adapters / retrieval / mcp_server 业务逻辑

---

## 12. 哪些文件允许修改

| 文件/目录 | 允许操作 |
|---|---|
| `system/`（新） | 新增 |
| `knowledge_curator/mcp_server/runtime.py` | 扩展 production composition 注入（不改 curate 逻辑） |
| `knowledge_curator/mcp_server/evidence_runtime.py` | 扩展 production adapter 注入（保留 fail-closed） |
| `integration/dsh/` | 新增系统级集成测试 |
| `dsh/knowledge-curator/` | 仅 persona 文本追加（如需要） |

## 13. 哪些 frozen 文件禁止修改

- `knowledge_curator/core/*`（全部冻结算法）
- `knowledge_curator/schemas/*`（全部 INTERNAL 模型）
- `knowledge_curator/ports/*`（全部 Port）
- `knowledge_curator/retrieval/*`（§6 全部）
- `knowledge_curator/mcp_server/app.py` 的工具业务逻辑
- `planner/CONTRACT_GAPS.md`

---

## 14. 下一轮 implementation plan

### Phase SI-1: Production Runtime Composition
- 新增 `system/bootstrap.py`：production adapter 注入框架
- 扩展 `runtime.py` / `evidence_runtime.py` 支持外部 adapter 注入
- 保持 integration fixture 与 production 明确隔离

### Phase SI-2: System Orchestrator + Workflow
- 新增 `system/orchestrator.py`：workflow owner
- 实现 CurationWorkflow（curate → commit）
- 实现 RevisionWorkflow（delta → publish → lifecycle）
- 最小 CLI 入口

### Phase SI-3: DSH Integration Wiring
- DSH Agent → orchestrator 调用链
- 系统级 E2E 测试（production adapter stub）

---

## 附：Frozen CONTRACT_GAPS（不可私自发明最终标准）

- CG-016: real EDDO query-expansion adapter
- CG-017: calibrated common retrieval-support score/threshold
- CG-018: external lifecycle event-bus consumer contract
- CG-019: public WorkIdentity/SourceVersion lineage contract
- CG-020: public stable cross-version content-unit/alignment contract
- CG-021: public manual revision approval/auditor contract

允许：internal narrow adapter / compatibility layer / fail-closed placeholder / dependency interface  
不允许：将临时内部 schema 宣布为 public frozen contract
