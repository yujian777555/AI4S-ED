# Phase 4.2.2 Executor Report — Code Parity & Real Backend Validation

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 4.2.2  

---

## 1. Commit integrity

本阶段提交包含**真实代码**（非仅报告）：

- `knowledge_curator/retrieval/flag_compat.py` — 新增。FlagEmbedding/transformers 兼容层
- `knowledge_curator/retrieval/embedder.py` — 构造参数 `devices=`；加载前调用 compat
- `knowledge_curator/retrieval/reranker.py` — 构造参数 `devices=`；加载前调用 compat
- `knowledge_curator/retrieval/faiss_index.py` — search-all-then-filter 正确性（已在 f6e6e99）
- `knowledge_curator/retrieval/fixture.py` — 合成 fixture（已在 f6e6e99）
- `knowledge_curator/retrieval/real_smoke.py` — 真实 smoke 门控；GPU + 本地模型 + 可选 reranker
- `knowledge_curator/tests/test_phase42_retrieval_backends.py` — 按依赖分组 gate（已在 f6e6e99）
- `results/phase-04-2-2-real-smoke.json` — 真实检索 smoke 结果

## 2. 环境问题与修复

本机 transformers 4.49.0 + FlagEmbedding 1.4.2 存在两个兼容性问题，已通过 `flag_compat.py` 在运行时修复：

1. **tokenizer 原生崩溃（0xC0000005）**：`transformers.models.xlm_roberta.tokenization_xlm_roberta` 经 `_LazyModule` 导入时访问违例。修复：预加载该模块（先导入依赖，再手动 exec）。
2. **`dtype=` / `torch_dtype=` 不兼容**：FlagEmbedding 1.4.2 向 `AutoModel.from_pretrained` 传 `dtype=`，transformers 4.49 将其转发给模型构造函数导致 `TypeError`。修复：在 `from_pretrained` 边界把 `dtype=` 翻译为 `torch_dtype=`。

## 3. GPU

**PASS** — 本机为 **NVIDIA GeForce RTX 3060 Laptop GPU**（6.4 GB），`torch 2.5.1+cu121`，`cuda.is_available() == True`。

| 项目 | 值 |
|---|---|
| device | cuda |
| embedding dimension | 1024 |
| BGE-M3 加载 + 探测 | ~10 s（fp16，本地 ASCII 路径） |
| 3 条文本编码 | ~0.14 s |

说明：此前 CPU 慢主要因为（a）未走 GPU；（b）tokenizer 崩溃后回退/挂起；（c）可能在下载 reranker。当前 smoke 显式使用本地模型目录 + GPU + fp16。

## 4. FlagEmbedding 1.4.2 构造参数

**PASS** — `devices=`（非 `device=`），`BGEM3FlagModel` / `FlagReranker` 签名已核实。

## 5. BGE-M3 真实加载

**PASS** — 本地模型 `D:\models\bge-m3`（由 `D:\agent_langchain学习\bge-m3` 复制到 ASCII 路径）加载成功。

## 6. FAISS sparse allowed-ref 正确性

**PASS** — search-all-then-filter；150 chunks 场景中 TARGET_REF 正确返回。

## 7. Jieba BM25

**PASS** — 中文/英文/zero-overlap 全部通过。

## 8. 合成 fixture

**PASS** — 14 chunks / 6 refs / 6 labelled queries（CN+EN+mixed）。

## 9. Real retrieval smoke

**PASS**（`results/phase-04-2-2-real-smoke.json`）

- status: PASS
- device: cuda
- load_seconds: 10.02
- recall@1: 1.0 / recall@3: 1.0 / MRR: 1.0
- 6/6 查询的期望 REF 均排在 top-1
- reranker: 本地无 `bge-reranker-v2-m3`，smoke 以 `reranker=None` 跑通 hybrid（已记入 warnings）。提供 `KC_BGE_RERANKER_MODEL` 后会自动启用。

## 10. 版本

| 包 | 版本 |
|---|---|
| torch | 2.5.1+cu121 |
| numpy | 1.26.4 |
| faiss | 1.13.0 |
| jieba | 0.42.1 |
| FlagEmbedding | 1.4.2 |
| transformers | 4.49.0 |

## 11. 测试计数

```text
knowledge_curator: 255 passed / 0 failed
integration/dsh:   70 passed / 0 failed
```

## 12. Public contracts changed?

**NO**

## 13. CONTRACT_GAPS

**无新增**
