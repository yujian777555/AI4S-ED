# Phase 4.2.3 Executor Report — Full Real Coarse→Fine + Reranker Closure

**Executor:** MiMo  
**Date:** 2026-09-30  
**Phase:** 4.2.3  

---

## 1. Commit integrity

本轮提交包含**真实代码 + smoke 结果**：

- `knowledge_curator/retrieval/real_smoke.py` — 完整改写：索引 COARSE+FINE、记录 coarse 诊断、真实 reranker 证据、full-stack PASS 语义
- `knowledge_curator/retrieval/reranker.py` — `compute_score` 返回值规范化（scalar/list/tuple/ndarray）+ 有限性校验
- `knowledge_curator/tests/test_phase423_full_stack.py` — 新增 14 项测试
- `results/phase-04-2-3-real-smoke.json` — 全链路 smoke 结果

## 2. Real BGE-M3

**PASS** — 本地 `D:\models\bge-m3`，CUDA，embedding dimension = 1024。

## 3. Real coarse→fine

**PASS** — smoke 索引全部 fixture（6 COARSE + 8 FINE = 14 chunks），不再只索引 fine。

每条 labelled query 记录：

| 诊断字段 | 要求 | 结果 |
|---|---|---|
| coarse_backend_present | true | 6/6 true |
| coarse_filter_applied | true | 6/6 true |
| fallback_used | false | 6/6 false |
| coarse_fused_hit_count | > 0 | 6/6 = 6 |
| coarse_channels_with_hits | — | vector(+keyword) |

config: `allow_fine_fallback_without_coarse=False`，**不靠 fallback 获得 PASS**。

## 4. Coarse fallback used

**NO**

## 5. Real bge-reranker-v2-m3

**PASS**

- 权重位置：`D:\models\bge-reranker-v2-m3`（hf-mirror 下载 `model.safetensors` 2.27GB）
- 模型 id 契约不变：`KC_BGE_RERANKER_MODEL` 或默认 `BAAI/bge-reranker-v2-m3`（源码不写死路径）
- `XLMRobertaForSequenceClassification`，GPU + fp16 加载 ~1.3s

## 6. Reranker execution evidence

| 项 | 值 |
|---|---|
| reranker_used | true |
| candidate_pair_count | 5 |
| score_count | 5 |
| scores finite | PASS |
| sample scores | [0.999293, 0.108189, 0.078642, 0.007877, 0.022074] |
| pre-rerank top-k | 记录于 per_query.pre_rerank_refs |
| post-rerank top-k | 记录于 per_query.post_rerank_refs |

`BgeReranker.rerank` 对 non-empty candidate set 真实执行；score 形状兼容 scalar/list/tuple/ndarray，`len(scores)==len(candidates)` 且 all finite，否则 FAILED。

## 7. Full-stack PASS 定义

`status = PASS` **仅当**全部满足：

- real BGE-M3 = YES  
- real FAISS = YES  
- real Jieba BM25 = YES  
- real coarse filter = YES  
- fallback = NO  
- real bge-reranker-v2-m3 = YES  
- 每条 labelled query final top-k 至少一条 expected evidence  
- embedding / rerank scores 全部 finite  

缺 reranker 权重时：`status = NOT_RUN_ENV`，可另记 `degraded_without_reranker`，**不作为 full-stack PASS**。

**本次结果：status = PASS，full_stack_pass = true。**

## 8. Metrics（完整 pipeline）

Query → real BGE-M3/FAISS coarse + real BM25 coarse → coarse RRF → allowed_ref_ids → fine VECTOR+KEYWORD → RRF → real reranker → final hits

| 指标 | 值 |
|---|---|
| Recall@1 | 1.0 |
| Recall@3 | 1.0 |
| MRR | 1.0 |

6/6 queries：expected REF 均在 final top-1。指标不要求保持 1.0，此处如实记录。

## 9. Fixture

coarse summaries 本轮未修改 — 真实 coarse retrieval 已能命中正确 ref（每 query coarse_fused_hit_count=6，expected ref 进入 allowed_ref_ids）。

## 10. 兼容层

`flag_compat.py` 保持隔离，仅覆盖已测 FlagEmbedding 1.4.2 / transformers 4.49 所需的两处（tokenizer 预加载 + `dtype`→`torch_dtype`）。

## 11. status.json 编码

Planner 已修复 UTF-8/中文路径；本轮更新字段时保持无 BOM、中文文档名不乱码。

## 12. 测试

```text
knowledge_curator: 269 passed / 0 skipped / 0 failed  (baseline 255 + 14 new)
integration/dsh:    70 passed / 0 failed
```

新增覆盖：

- real smoke 索引 coarse + fine（非 fine-only）
- full PASS 要求 coarse_filter_applied
- full PASS 要求 reranker_used
- no reranker → NOT_RUN_ENV / degraded，非 full PASS
- reranker score 标量/list/array 规范化 + finite/count 校验
- provenance 在 rerank 后保留

## 13. 版本

| 包 | 版本 |
|---|---|
| torch | 2.5.1+cu121 |
| numpy | 1.26.4 |
| faiss | 1.13.0 |
| jieba | 0.42.1 |
| FlagEmbedding | 1.4.2 |
| transformers | 4.49.0 |

device: **NVIDIA GeForce RTX 3060 Laptop GPU**

## 14. Public contracts changed?

**NO**

## 15. CONTRACT_GAPS

**无新增**
