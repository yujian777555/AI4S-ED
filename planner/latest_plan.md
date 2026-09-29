# Phase 4.2.2 Plan — Remote-Code Parity + Real Retrieval Smoke Closure

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Purpose

Recover the missing Phase 4.2.1 implementation into origin/main and close real BGE-M3/reranker smoke validation.

GitHub main is the source of truth. A report is not implementation evidence.

Do not start Phase 4.3.

## 1. First diagnose the missing code

Before editing, run:
- git status
- git diff
- git diff --cached
- git log --all --decorate --oneline -30
- git reflog -30

Determine whether the Phase 4.2.1 source changes:
- exist uncommitted;
- exist in a local-only commit/branch;
- were lost and must be reimplemented.

If recoverable, cherry-pick/commit them cleanly.
If not recoverable, reimplement from planner/phase-04-2-review.md and this plan.

Do not merely update the executor report again.

## 2. Required remote source changes

The implementation commit must contain actual source/test changes where applicable, including at minimum:
- knowledge_curator/retrieval/embedder.py
- knowledge_curator/retrieval/faiss_index.py
- knowledge_curator/retrieval/reranker.py
- knowledge_curator/tests/test_phase42_retrieval_backends.py

And for the missing smoke requirement, add:
- synthetic multilingual retrieval fixture;
- real smoke module/script;
- tests for fixture/metrics/preflight.

If a listed production file genuinely needs no change after inspecting FlagEmbedding 1.4.2, explain why in the report; but the claimed fixes must be visible in committed files.

## 3. FlagEmbedding 1.4.2 real API

Use the ACTUAL installed FlagEmbedding 1.4.2 API.

Inspect constructor/method signatures at runtime and implement the supported device argument form.

Requirements:
- BGE-M3 model can actually instantiate on CPU;
- BGE reranker can actually instantiate on CPU;
- lazy import remains;
- source defaults remain portable;
- no hard-coded D:\ local path;
- allow model id/path/env override.

Record exact constructor signatures/args in report.

## 4. Dense embedder real path

Prefer installed official query/corpus methods if FlagEmbedding 1.4.2 provides them.

Expose internally:
- embed_documents(texts)
- embed_query(text)

A compatibility embed(texts) wrapper may remain.

Requirements:
- real returned ndarray float32;
- finite;
- normalized when cosine/IP mode expects normalization;
- measured dimension recorded from actual model, not documentation only.

## 5. FAISS exact filtered correctness

REMOVE correctness dependence on fixed oversampling such as top_k*10/100.

For IndexFlat baseline:
- if level/allowed_ref_ids filter is active, evaluate the complete eligible candidate universe, or search all indexed rows then filter;
- return exact top_k among eligible rows;
- deterministic equal-score tie break by chunk_id;
- 1-based ranks after filtering.

Mandatory regression:
- >150 indexed chunks;
- only allowed ref deliberately outside global first 100;
- query.top_k=1;
- allowed ref MUST still be returned.

Also test:
- level filter;
- empty eligible set;
- dimension mismatch;
- duplicate chunk-id policy.

## 6. Tests must really run

Remove module-level numpy importorskip.

Split dependency gates locally:
- pure BM25 tests run without numpy/faiss;
- real Jieba test gated only on jieba;
- FAISS tests gated only where faiss/numpy required;
- mocked FlagEmbedding API tests do not need model weights;
- real-model smoke separately env-gated.

Delete broad `except Exception: pass` acceptance.
Unexpected exceptions fail.

## 7. Real Jieba BM25

Run real Jieba tests for Chinese and English/mixed synthetic content.

At minimum verify:
- 双极膜电渗析 / 能耗 retrieval;
- current efficiency retrieval;
- zero-overlap returns zero hits;
- level/ref/top_k semantics.

## 8. Synthetic fixture

Add checked-in synthetic fixture:
- >= 6 refs;
- coarse summary each;
- multiple fine chunks each;
- Chinese, English, mixed language;
- >= 6 labelled queries;
- expected ref_ids and/or chunk_ids.

No copyrighted paper text.

## 9. Real smoke harness

Add executable harness, e.g.:
`KC_RUN_REAL_RETRIEVAL=1 python -m knowledge_curator.retrieval.real_smoke`

It MUST use existing hybrid_retrieve:
fixture
-> real BGE-M3
-> real FAISS
+ real Jieba BM25
-> coarse fusion
-> fine retrieval
-> RRF
-> real BGE reranker
-> final ranked hits

No parallel demo pipeline.

## 10. Smoke terminal status

Only:
- PASS
- NOT_RUN_ENV
- FAILED

"PARTIAL" is not terminal.

Rules:
- NOT_RUN_ENV only if preflight cannot access required dependency/model;
- once model loading/execution starts, an execution error is FAILED;
- "takes longer" is not an environment absence by itself.

If local BGE-M3 path exists and dependencies are installed, run the load to completion for this phase.

## 11. Metrics

For all labelled fixture queries record:
- Recall@1
- Recall@3
- MRR
- per-query expected and returned top-k refs/chunks.

PASS cannot contain a fixture query with zero relevant evidence anywhere in the configured final top-k.

Do not invent a broader project quality threshold.

## 12. Reranker validation

Must score a non-empty candidate set with real bge-reranker-v2-m3.

Verify:
- score count matches candidates;
- finite scores;
- final ranking produced;
- RRF score/channels/chunk provenance preserved.

## 13. Commit integrity gate

Before reporting completion:
1. git status must show intended state;
2. git diff origin/main...HEAD must include the actual Phase 4.2.2 implementation;
3. push main;
4. fetch/verify origin/main SHA;
5. verify at least these remote blobs changed relative to Phase 4.2 where fixes apply.

The "implementation SHA" must be the commit containing CODE, not a later report-only bookkeeping commit.

Report separately:
- implementation_code_sha
- origin/main_sha

## 14. Baselines

Maintain:
- integration/dsh >= 70 passed / 0 failed;
- knowledge_curator existing baseline;
- report exact passed/skipped/failed counts.

## 15. Deliverables

Create results/phase-04-2-2-executor-report.md.

Update status.json:
- phase = 4.2.2
- actor = executor
- state = executor_complete
- latest_commit = actual CODE implementation SHA
- result_expected = results/phase-04-2-2-executor-report.md

Push and STOP. Do not start Phase 4.3.
