# Phase 4.2.1 Plan — Real Retrieval Backend Validation & Correctness Closure

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Goal
Turn the Phase 4.2 backend code from 'adapter implementation ready' into an actually validated real retrieval stack.

Do not redesign the frozen retrieval contracts.
Do not start §6 MCP, final answer generation, graph DB internals, EDDO expansion, or §7.

## 1. Fix FlagEmbedding construction against the installed official API
Install/use a real FlagEmbedding version from `requirements-retrieval.txt` in the executor environment.

For BGE-M3 and BGE reranker:
- inspect the installed constructor signature/version;
- use the supported `devices`/device argument form for that version;
- verify CPU works;
- optional CUDA may be reported if available;
- preserve lazy loading.

Do not claim compatibility based only on source reading.

Record:
- FlagEmbedding version;
- torch version;
- actual constructor args used;
- device selected;
- model path/id.

## 2. Distinguish query and corpus embedding if supported
Prefer official BGE-M3 retrieval methods when available:
- `encode_queries` for query;
- `encode_corpus` for chunk corpus;
fall back to documented equivalent only if the installed version does not expose them.

Update DenseEmbedderPort minimally if needed without changing public contracts, e.g.:
- embed_documents(texts)
- embed_query(text)
or keep a compatibility `embed()` wrapper.

Do not add ad-hoc query instructions to BGE-M3.

## 3. Fix FAISS filter correctness
For the flat exact baseline, filtered queries must be complete.

Requirements:
- if no level/ref filter: normal top-k exact search is fine;
- if level or allowed_ref_ids filters reduce the candidate universe, search/score the complete eligible candidate set or search all indexed rows before filtering;
- never rely on a fixed `top_k*10`/100 pool for correctness;
- exact deterministic tie-break by score then chunk_id;
- duplicate chunk_id policy must be explicit (reject, replace, or deterministic rebuild) and tested.

Add a regression with >150 chunks where the only allowed ref is intentionally outside the first 100 global neighbors; it still must be returned.

## 4. Make offline tests genuinely execute
Do not skip the entire Phase 4.2 module just because one optional dependency is absent.

Split tests by dependency:
- pure BM25 tests should run without numpy/faiss;
- embedder model-load tests can monkeypatch/mock FlagEmbedding;
- FAISS tests use importorskip locally only for tests that need real faiss;
- real-model tests are separately environment-gated.

Unexpected exceptions must fail tests.
Remove broad `except Exception: pass` patterns.

## 5. Test real Jieba tokenizer
When jieba is installed, add a real Chinese tokenization/retrieval test.
Example synthetic concepts may include:
- 双极膜电渗析;
- 能耗;
- 膜电阻;
- current efficiency.

Do not depend on external documents.

## 6. Add the required synthetic retrieval fixture
Create a checked-in fixture under a test/results fixture directory.

Requirements:
- >=6 refs;
- one coarse summary per ref;
- multiple fine chunks per ref;
- Chinese + English + mixed-language content;
- >=6 labelled queries;
- expected relevant ref_ids and/or chunk_ids.

Use synthetic content only.

Fixture data must preserve canonical prefix/provenance using existing chunk builders where practical.

## 7. Add real smoke harness
Create an executable opt-in smoke, for example:
`python -m knowledge_curator.retrieval.real_smoke`
gated by `KC_RUN_REAL_RETRIEVAL=1`.

Preflight must check:
- numpy;
- faiss;
- jieba;
- FlagEmbedding;
- model path/id resolvable.

Status semantics:
- PASS: full real stack executed successfully;
- NOT_RUN_ENV: preflight dependency/model unavailable, with exact reason;
- FAILED: dependencies/models loaded but execution or expected retrieval correctness failed.

Never downgrade FAILED to NOT_RUN_ENV after execution begins.

## 8. Real smoke flow
Run the actual existing hybrid pipeline:
fixture chunks
-> BGE-M3 embeddings
-> FAISS vector search
+ real Jieba BM25
-> coarse fusion/filter
-> fine vector/BM25 (+ optional fake graph only if desired)
-> RRF
-> real bge-reranker-v2-m3
-> final hits.

Do not create a parallel demo pipeline that bypasses hybrid_retrieve.

## 9. Metrics
For fixture queries compute at least:
- Recall@1;
- Recall@3 (or Recall@k matching output k);
- MRR.

Also record per-query final top-k ref_ids/chunk_ids.

Do not set a new global project-quality threshold.
Smoke FAIL condition remains minimal correctness:
- non-finite embedding/score;
- stage exception after successful preflight;
- every labelled relevant item missed for a fixture query.

## 10. Reranker validation
Real smoke must prove the reranker model actually loads and scores non-empty candidate pairs.

Check:
- score count == candidate count;
- all scores finite;
- result order deterministic for a repeated identical run on CPU within practical equality;
- provenance/RRF channel metadata preserved.

## 11. Dependency/version report
After installation/run, record exact versions actually imported:
- FlagEmbedding;
- faiss;
- numpy;
- jieba;
- torch;
- transformers if relevant.

`requirements-retrieval.txt` may be updated with compatible lower bounds or exact tested constraints only after observing the real environment.

## 12. Model path portability
Do not encode the Windows path reported by one environment into source/default config.
Support:
- default model id;
- explicit constructor path;
- optional env override, e.g. KC_BGE_M3_MODEL / KC_BGE_RERANKER_MODEL.

Local paths/weights remain uncommitted.

## 13. Baselines
Keep:
- integration/dsh >=70 passed;
- existing knowledge_curator baseline >=243 passed;
- Phase 4.2 tests should now actually run rather than whole-module skip where dependencies are present.

## 14. Deliverables
Create `results/phase-04-2-1-executor-report.md`.

Report:
- FlagEmbedding real constructor compatibility;
- FAISS filter-correctness fix;
- fixture location/query count;
- real smoke status PASS / NOT_RUN_ENV / FAILED;
- exact package versions;
- real embedding dimension;
- device;
- Recall@1;
- Recall@3/k;
- MRR;
- exact test counts and skips;
- public contracts changed? NO;
- implementation SHA.

## 15. status.json
On completion:
- phase = 4.2.1
- actor = executor
- state = executor_complete
- latest_commit = actual implementation SHA
- result_expected = results/phase-04-2-1-executor-report.md

Push main and stop.
Do not start Phase 4.3.