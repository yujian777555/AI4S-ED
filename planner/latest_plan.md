# Phase 4.2.3 Plan — Full Real Coarse→Fine + Reranker Smoke Closure

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Goal

Close only the two remaining full-stack validation gaps:
- real coarse->fine retrieval;
- real bge-reranker-v2-m3 execution.

Do not redesign contracts or add new retrieval features.

## 1. Use the full fixture corpus in the real backends

real_smoke.py must index BOTH:
- ChunkLevel.COARSE summary chunks;
- ChunkLevel.FINE chunks.

The same VectorSearchPort / KeywordSearchPort objects may hold both levels because RetrievalQuery.level already filters them correctly.

Do not pre-delete coarse chunks before building the real indexes.

## 2. Prove real coarse->fine happened

For every smoke query record diagnostics:
- coarse_backend_present;
- coarse_status;
- coarse_filter_applied;
- coarse_channels_attempted;
- coarse_channels_with_hits;
- coarse_fused_hit_count;
- fallback_used.

Full-stack PASS requires, for every labelled fixture query:
- coarse_backend_present == true;
- coarse_filter_applied == true;
- fallback_used == false;
- coarse_fused_hit_count > 0.

At least one expected relevant ref must survive the coarse allowed_ref_ids filter and reach fine retrieval.

## 3. Run real reranker

Provide real local weights through:
KC_BGE_RERANKER_MODEL=<path>

Recommended portable local location:
D:\models\bge-reranker-v2-m3

Source code must NOT require that exact path; env override/default model id remains the contract.

If weights are not local but network/model registry access is available, official model id BAAI/bge-reranker-v2-m3 is acceptable.

The smoke must actually call BgeReranker.rerank on a NON-EMPTY hit list.

## 4. Reranker evidence

Record:
- reranker_used = true;
- reranker_model_path/id;
- number of candidate pairs scored;
- score count;
- finite-score check;
- pre-rerank top-k;
- post-rerank top-k.

If useful, add an internal diagnostic field for rerank scores; do not change public contracts.

Full-stack PASS requires all reranker scores finite and count matching candidate count.

## 5. Tighten reranker adapter if needed

Make BgeReranker robust to actual FlagEmbedding 1.4.2 compute_score return shapes:
- scalar for one pair;
- list/tuple/ndarray-like for multiple pairs.

Normalize to a flat list[float].
Reject non-finite values.
Preserve:
- chunk/provenance;
- rrf_score;
- channels;
- final rank.

Add unit tests with mocked scalar/list/ndarray-like outputs if practical.

## 6. Smoke status semantics

Full-stack smoke terminal status remains:
- PASS
- NOT_RUN_ENV
- FAILED

PASS only when:
- real BGE-M3 used;
- real FAISS used;
- real Jieba BM25 used;
- real coarse filter applied;
- no coarse fallback;
- real bge-reranker-v2-m3 used;
- all labelled queries retrieve at least one expected evidence in final top-k;
- no invalid/non-finite score.

If reranker weights are unavailable BEFORE reranker load begins:
- full-stack status = NOT_RUN_ENV;
- you may separately record degraded_without_reranker = PASS for diagnostics.

Do not label degraded execution as full-stack PASS.

## 7. Metrics

Recompute on the COMPLETE pipeline:
- Recall@1;
- Recall@3;
- MRR;
- per-query expected refs/chunks;
- coarse candidate refs;
- pre-rerank final-fusion refs;
- post-rerank refs.

Do not require metrics to remain 1.0; report honestly.
The minimum acceptance rule remains: every labelled query has at least one expected evidence in final configured top-k.

## 8. Coarse fixture quality

If real BGE/BM25 coarse retrieval cannot find the intended ref because summaries are too weak, improve ONLY the synthetic fixture summaries so they faithfully summarize their fine chunks.

Do not special-case queries or inject expected ref IDs into search logic.

## 9. Compatibility shim

Keep flag_compat isolated and documented.
Do not broaden monkey patches beyond what is needed for the tested FlagEmbedding/transformers versions.

If a simpler version-compatible configuration eliminates the shim, that is preferable, but do not risk destabilizing the already-working BGE-M3 smoke merely for cleanup.

## 10. status.json encoding

Repair status.json as valid UTF-8 without BOM/mojibake.
Restore exact authoritative document names:
- docs/01-总体架构与数据流设计.md
- docs/03-文献自动调研与知识入库流水线.md

Do not leave garbled Chinese paths/constraints.

## 11. Tests

Maintain:
- integration/dsh >= 70 passed / 0 failed;
- knowledge_curator current baseline >= 255 passed / 0 failed.

Add/adjust tests for:
- real_smoke indexes coarse + fine, not fine-only;
- full PASS requires coarse_filter_applied;
- full PASS requires reranker_used;
- degraded no-reranker is not full PASS;
- reranker score normalization/finite validation;
- provenance survives real rerank.

## 12. Deliverables

Create:
results/phase-04-2-3-executor-report.md
results/phase-04-2-3-real-smoke.json

Report:
- implementation CODE SHA;
- BGE-M3 real load;
- real coarse->fine status;
- coarse fallback used? must be NO for PASS;
- reranker real load/use;
- candidate score count;
- device;
- package/model versions;
- Recall@1;
- Recall@3;
- MRR;
- exact test counts;
- public contracts changed? NO.

## 13. Completion

Update status.json:
- phase = 4.2.3
- actor = executor
- state = executor_complete
- latest_commit = actual CODE implementation SHA
- result_expected = results/phase-04-2-3-executor-report.md

Push main and STOP.
Do not start Phase 4.3.
