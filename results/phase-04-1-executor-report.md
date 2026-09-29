# Phase 4.1 Executor Report — §6.1 Chunking + §6.2 Retrieval Contracts

**Executor:** MiMo  
**Date:** 2026-09-29  
**Phase:** 4.1

---

## 1. Chunk schemas (`schemas/chunk.py`)

- `ChunkLevel`: COARSE / FINE
- `ChunkType`: DOCUMENT_SUMMARY / TEXT / TABLE / CHART / EVIDENCE_CARD
- `KnowledgeChunk`: chunk_id / ref_id / level / chunk_type / payload / page / section / object_id / locator / assertion_id / confidence / quality / provenance
- `metadata_prefix()`: `[ref_id|page|section|type(...)]` 真正嵌入 `prefixed_payload()`

temporary compatibility model。

## 2. Text chunking

- `max_tokens=512`, `overlap_tokens=64`
- Tokenizer 通过 Port 注入（`WordTokenizer` 为 deterministic test adapter）
- section-aware；空文本无 chunk；overlap >= 内容不死循环

## 3. Table / Chart whole-chunk

- 整表一个 chunk（含 caption/headers/units/row_summary）
- 一个 ChartObject 一个 chunk（含 object_id/caption/axes/units/summary）
- 不解析 PDF、不做 chart digitization

## 4. Evidence cards

- 1 Assertion = 1 evidence-card chunk
- 保留 subject/property/value/conditions/ref_id/locator/confidence/assertion_id

## 5. Coarse/fine retrieval

- COARSE: DOCUMENT_SUMMARY 包装上游 summary（无 LLM）
- FINE: vector/graph/keyword 三通道
- 无 coarse 时 `coarse_filter_applied=False`, `fallback_fine_retrieval=True`

## 6. Three-channel Ports

`VectorSearchPort` / `GraphSearchPort` / `KeywordSearchPort` / `QueryExpansionPort` / `RerankerPort`

InMemory adapters 仅测试用，不伪装 FAISS/BM25。

## 7. RRF

```
score(chunk) = Σ 1/(k + rank_channel)
rank 从 1 开始；跨 channel 融合；无重复返回
tie-break: (-score, chunk_id, ref_id) 稳定确定性
k=60 可配置（非冻结超参）
```

## 8. Provenance preservation

coarse/fine/RRF/reranker 全链路保留 ref_id / locator / chunk_type / confidence / quality。

## 9. Test counts

```text
knowledge_curator: 188 passed / 0 failed  (173 + 15 新)
integration/dsh:   70 passed / 0 failed
```

## 10. 未实现

FAISS / Qdrant / BGE-M3 / BM25 / EDDO expansion / bge-reranker / §6 MCP / QA generator / §7

## 11. Public contracts changed?

**NO**

## 12. CONTRACT_GAPS

**无新增**

## 13. Implementation SHA

```
implementation commit: <pending>
```
