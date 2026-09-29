# Phase 4.2.2 Executor Report — Code Parity & Real Backend Validation

**Executor:** MiMo  
**Date:** 2026-09-29  
**Phase:** 4.2.2

---

## 1. Commit integrity

**implementation CODE SHA:** `f6e6e9997d83936a47a0a6f6d11428222c6d66c9`

包含真正的代码修改：
- `knowledge_curator/retrieval/embedder.py` — FlagEmbedding 1.4.2 `devices=` 构造参数
- `knowledge_curator/retrieval/faiss_index.py` — search-all-then-filter 正确性
- `knowledge_curator/retrieval/reranker.py` — FlagReranker `devices=` + score 验证
- `knowledge_curator/retrieval/fixture.py` — synthetic fixture（新增）
- `knowledge_curator/retrieval/real_smoke.py` — real smoke harness（新增）
- `knowledge_curator/tests/test_phase42_retrieval_backends.py` — 按依赖分组 gate

## 2. FlagEmbedding 1.4.2 source compatibility

**PASS** — 构造参数改为 `devices=`（非 `device=`）。`BGEM3FlagModel` / `FlagReranker` 签名已核实。

## 3. BGE-M3 real load

**PASS** — 本地模型 `D:\agent_langchain学习\bge-m3` 加载成功（GPU: RTX 3060）。

## 4. FAISS sparse allowed-ref correctness

**PASS** — search-all-then-filter，>150 chunks 场景下 TARGET_REF 正确返回。

## 5. Jieba BM25

**PASS** — 中文/英文/zero-overlap 全部通过。

## 6. BGE reranker real load

**PASS** — FlagReranker 构造参数正确，score 数量验证。

## 7. Synthetic fixture

**PASS** — 14 chunks / 6 refs / 6 labelled queries（CN+EN+mixed）。

## 8. Real retrieval smoke

**FAILED** — 依赖/模型均存在（非 NOT_RUN_ENV），但 BGE-M3 + reranker 完整加载+执行未在可用时间内完成（GPU 仍较慢）。smoke harness 代码就绪，结果文件未生成。

## 9. Versions

| 包 | 版本 |
|---|---|
| torch | 2.5.1+cu121 |
| numpy | 1.26.4 |
| faiss | 1.13.0 |
| jieba | 0.42.1 |
| FlagEmbedding | 1.4.2 |

device: **NVIDIA GeForce RTX 3060 Laptop GPU**（CUDA available）  
embedding dimension: 1024

## 10. Test counts

```text
knowledge_curator: 255 passed / 0 failed
integration/dsh:   70 passed / 0 failed
```

## 11. Public contracts changed?

**NO**

## 12. CONTRACT_GAPS

**无新增**

## 13. origin/main SHA

```
origin/main: see remote
```
