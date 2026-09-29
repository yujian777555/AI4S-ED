# Phase 4.1.1 Executor Report — Chunk/Retrieval Contract Defects Closure

**Executor:** MiMo  
**Date:** 2026-09-29  
**Phase:** 4.1.1

---

## 1. Canonical payload prefix

`KnowledgeChunk.payload` 本身以 `[ref_id|page|section|type(类型)]` 开头：
- TEXT → type(文本)
- TABLE → type(表)
- CHART → type(图)
- EVIDENCE_CARD → type(证据卡)

## 2. Text token budget

payload 整体 ≤ max_tokens(512)。prefix token budget 先算，再切正文。64-token overlap 只针对正文。prefix ≥ max_tokens 时 fail clearly。

## 3. Tokenizer reversible contract

`TokenizerPort`: encode/decode/count。`WordTokenizer` 支持英文标点与中文/non-ASCII roundtrip。

## 4. Collision-free chunk ids

`stable_chunk_id` = SHA-256(ref_id|page|section|kind|window_digest)。相同输入→相同 id；不同 section/page/window→不同 id。

## 5. Level-aware retrieval

`RetrievalQuery.level` (COARSE/FINE)。InMemory adapters 按 level 过滤，过滤后重新 1-based rank，honour top_k。

## 6. True coarse→fine

`hybrid_retrieve` 主流程：COARSE query → coarse vector/keyword → allowed_ref_ids → FINE query → vector+graph+keyword → RRF → reranker → top_k。graph 仅参与 fine。

## 7. Coarse fallback diagnostics

区分：coarse_backend_absent / ran_with_hits / ran_zero_hits / fallback_used / fallback_not_allowed。fallback 需 `allow_fine_fallback_without_coarse=True`。

## 8. top_k semantics

channel search ≤ query.top_k；final output ≤ top_k；rerank 后 slice。测试 top_k=1/2。

## 9. RRF robustness

rank ≥ 1 强制；同 channel 同 chunk 只取首次/最佳 rank 不重复加分；tie-break 稳定确定性。

## 10. Provenance preservation

全链路保留 ref_id / locator / chunk_type / confidence / quality。

## 11. Test counts

```text
knowledge_curator: 210 passed / 0 failed  (188 + 22 新)
integration/dsh:   70 passed / 0 failed
```

## 12. Public contracts changed?

**NO**

## 13. CONTRACT_GAPS

**无新增**

## 14. Implementation SHA

```
implementation commit: afd5d4903f1a7c95844d98295bd3042ed76a4341
```
