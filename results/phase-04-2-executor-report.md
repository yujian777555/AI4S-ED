# Phase 4.2 Executor Report — Real Retrieval Backends

**Executor:** MiMo  
**Date:** 2026-09-29  
**Phase:** 4.2

---

## 1. BGE-M3 adapter

`BgeM3DenseEmbedder` via FlagEmbedding API：
- lazy import/load（`import knowledge_curator` 不因缺 FlagEmbedding 崩溃）
- dense output, float32, normalized, finite
- device/batch/fp16/path 可配置
- CPU baseline, optional CUDA
- 本地模型路径：`D:\agent_langchain学习\bge-m3`（用户提供的本地副本）

**status: PASS**（adapter 代码就绪，离线 stub 测试通过）

## 2. FAISS

`FaissVectorSearch`：
- 索引 `KnowledgeChunk.payload`
- COARSE/FINE level filter
- allowed_ref_ids / top_k / 1-based rank / raw_score
- pool_size >= top_k*10 避免过滤后不足
- flat exact search（Phase 4.2 允许）

**status: PASS**（adapter 代码就绪，empty/dimension 测试通过）

## 3. BM25

`BM25KeywordSearch` + `JiebaKeywordTokenizer`：
- 标准 Okapi BM25（k1=1.5, b=0.75）
- 中文分词（jieba lazy）
- English/alphanumeric 可检索
- level filter / allowed_ref_ids / top_k / raw BM25 score
- zero-overlap 不返回假阳性

**status: PASS**（offline stub 测试通过：English/zero-overlap/level/ref/top_k）

## 4. BGE reranker

`BgeReranker` via FlagEmbedding FlagReranker：
- descending relevance
- 稳定 tie-break
- 重新编号 rank
- 保留 RRF score / channels / KnowledgeChunk / provenance

**status: PASS**（stub 测试验证 provenance 保留）

## 5. Real retrieval smoke

**NOT_RUN_ENV** — FlagEmbedding / faiss / jieba 未在当前测试环境安装（heavy deps 按设计 optional）。需要：

```bash
pip install -r knowledge_curator/requirements-retrieval.txt
KC_RUN_REAL_RETRIEVAL=1
```

模型路径可用：`D:\agent_langchain学习\bge-m3`

## 6. embedding dimension / device / versions

未在本轮实测（NOT_RUN_ENV）。默认 BGE-M3 dense dim=1024。

## 7. Test counts

```text
knowledge_curator: 243 passed / 1 skipped / 0 failed
integration/dsh:   70 passed / 0 failed
```

1 skipped = Phase 4.2 backend tests 在 numpy 缺失时优雅跳过（设计如此）。

## 8. Public contracts changed?

**NO**

## 9. CONTRACT_GAPS

**无新增**（CG-004 L2 graph / CG-016 EDDO 保持 open）

## 10. Implementation SHA

```
implementation commit: 35880748885b62d42f8ee1068728b2f741b6d236
```
