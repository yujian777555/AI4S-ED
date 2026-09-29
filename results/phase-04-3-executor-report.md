# Phase 4.3 Executor Report — Evidence Bundle + Guard + MCP

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 4.3  

---

## 1. Commit integrity

本轮提交包含**真实代码 + smoke 证据**：

- `knowledge_curator/retrieval/evidence_models.py` — INTERNAL EvidenceBundle / RetrievalEvidenceRecord（fail closed）
- `knowledge_curator/retrieval/evidence_service.py` — EvidenceRetrievalService（只调 frozen `hybrid_retrieve`）
- `knowledge_curator/retrieval/guard_service.py` — ClaimGuardService（复用 classify/abstain/H1-H2-H3）
- `knowledge_curator/retrieval/retrieval_metadata.py` — H1 绑定当前 retrieval set
- `knowledge_curator/retrieval/fixture.py` — FINE 证据补 confidence/quality/locator（合成数据）
- `knowledge_curator/retrieval/real_guard_smoke.py` — 真实 retrieval→guard smoke
- `knowledge_curator/mcp_server/evidence_codec.py` / `evidence_runtime.py` / `app.py` — MCP `retrieve_evidence` / `validate_retrieved_claims`
- `knowledge_curator/tests/test_phase43_evidence_guard.py` — 21 项 core 测试
- `integration/dsh/tests/test_mcp_evidence_tools.py` — 8 项 MCP/DSH 测试
- `results/phase-04-3-guard-smoke.json` / `results/phase-04-3-mcp-dsh-smoke.json`

## 2. EvidenceRetrievalService

**PASS** — runtime-independent。输入支持 query / subqueries[] / top_k / allowed_ref_ids / coverage keys / privacy。内部**只**调用 `hybrid_retrieve`，无第二套 ranking。

## 3. Evidence normalization

**PASS** — fail closed：

- 保留 chunk_id / ref_id / locator / page / confidence / quality / access_pointer / sentence / chunk_type / provenance / channels / rank / scores
- **不发明 confidence**；缺失 → 仅作 retrieval context，不可授权 factual claim
- **locator 缺失** → 不可作 claim anchor
- `RetrievalChannel.GRAPH` **不**推断 `EvidenceType.GRAPH`；evidence_type 仅来自显式 provenance
- literature corpus 可配置默认 `EvidenceType.LITERATURE`

## 4. Retrieval-set anchor binding

**PASS** — claim 只能用 `anchor_chunk_ids` 从**当前 retrieval set** 解析 EvidenceAnchor。未知 chunk → unresolved → H1 → Abstain。KB 中真实但本轮未返回的 ref 不能作本次 anchor。

## 5. Confidence policy

**PASS** — 冻结规则保持：

| confidence | policy |
|---|---|
| verified / high | FACTUAL_ALLOWED |
| medium | CAVEATED_ONLY |
| hypothesis | PENDING_HYPOTHESIS_ONLY |
| 数值 sources ranges 冲突 | CONFLICT_DISCLOSURE_REQUIRED |

## 6. Abstain / coverage

**PASS**

- required subquery 仅在 `>=1 guardable evidence` 时 covered
- 未覆盖 → SUBQUESTION_NOT_COVERED → Abstain
- 无有效 anchor → Abstain（fail closed）
- private unauthorized → Abstain
- **CG-017**：不把 RRF/BM25/FAISS/reranker 原始分喂给 0.3 阈值；无 calibrated_support 时 `retrieval_support_checked=false`，其它门照常

## 7. H1

**PASS** — EvidenceMetadataPort adapter 绑定当前 evidence bundle：ref 存在 + locator 在当前 set 中 + chunk 在检索结果内。

## 8. H2

**PASS** — 本地 KB 存在性 + DOI/title 比对；无 Crossref/web。metadata 不可用时显式 `checked=false` / unavailable，不假装 PASS。

## 9. H3

**PASS** — 有结构化 Assertion + validator 时走 `detect_h3`；无 validator → `MECHANISM_UNAVAILABLE` / `NOT_CHECKED`，不假装机理通过。

## 10. Real retrieval→guard smoke

**PASS**（`results/phase-04-3-guard-smoke.json`）

| 项 | 结果 |
|---|---|
| device | cuda（RTX 3060） |
| real BGE-M3 / FAISS / BM25 / reranker | YES |
| evidence_normalization | PASS |
| confidence_policy | PASS |
| abstain_coverage | PASS |
| H1 / H2 / H3 | PASS / PASS / PASS |
| HIGH claim | factual_allowed，无 Abstain/H1 |
| MEDIUM claim | caveated_only |
| unknown anchor | H1 + Abstain |
| private unauthorized | Abstain |
| provenance | retrieval→rerank→EvidenceRecord 不丢失 |

## 11. MCP

**PASS** — 扩展现有 `knowledge_curator.mcp_server`，不新建 Server / Agent。

- `retrieve_evidence`：结构化 EvidenceBundle + diagnostics/coverage/Abstain，无科学 prose
- `validate_retrieved_claims`：**stateless**，server 重跑 deterministic retrieval，不信客户端 bundle
- 默认 production runtime：`retrieval_unavailable / not_configured`，**不**偷跑 synthetic fixture
- integration fixture mode 显式标记 `integration_fixture=true`

## 12. DSH

**PASS** — 复用 `knowledge-curator` preset。

- tool discovery：stdio MCP 列出 `retrieve_evidence` / `validate_retrieved_claims`
- direct service vs MCP tool：bundle_id / chunk ids / abstain / policy / H1 结构一致
- live DeepSeek 逐字 prose 不比较；结构化 identity/policy 一致即通过

## 13. 测试

```text
knowledge_curator: 290 passed / 0 skipped / 0 failed  (baseline 269 + 21)
integration/dsh:    78 passed / 0 failed              (baseline 70 + 8)
```

覆盖：HIGH→FACTUAL / MEDIUM→CAVEATED / HYPOTHESIS critical numeric→Abstain / unknown anchor→H1+Abstain / missing subquery→Abstain / disjoint ranges→CONFLICT / H3 violation→finding / private→Abstain。

## 14. 边界

- 未生成最终 QA 文本
- 未新建 Agent
- 未修改 §5 / Phase 4.0-4.2 冻结语义
- 未启动 §7

## 15. Public contracts changed?

**NO** — EvidenceBundle / ClaimGuardResult 为 INTERNAL temporary model。

## 16. CONTRACT_GAPS

**无新增**（CG-017 已按约定遵守）
