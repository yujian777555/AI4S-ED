# Phase 4.2 Plan — Real Dense/Keyword/Reranker Retrieval Backends

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Goal
Implement production-capable adapters for the already-frozen §6.2 retrieval contracts:
- BGE-M3 dense embeddings;
- FAISS dense vector search;
- Chinese-aware BM25 keyword search;
- BGE reranker;
- real coarse->fine smoke/evaluation through hybrid_retrieve.

Do not change the Phase 4.1.3 retrieval semantics.

## 1. Scope / non-scope
IN:
- real local model adapters with lazy optional imports;
- CPU-compatible baseline; optional CUDA acceleration;
- VECTOR and KEYWORD real channel implementations;
- real reranker adapter;
- small deterministic retrieval fixture + optional real-model smoke;
- tested dependency manifest for retrieval extras.

OUT:
- implementing L2 graph/SQL/JSON internals;
- implementing EDDO ontology/synonym expansion itself (CG-016);
- changing §5 VectorIndex/atomic commit semantics;
- Qdrant migration;
- final answer generator;
- §6 MCP exposure;
- §7.

GraphSearchPort and QueryExpansionPort remain injectable boundaries.

## 2. Official model baseline
Use these defaults unless the installed official FlagEmbedding API requires a compatible equivalent:
- dense: `BAAI/bge-m3` via official FlagEmbedding/BGEM3FlagModel;
- reranker: `BAAI/bge-reranker-v2-m3` via official FlagEmbedding reranker.

Do not silently substitute another model.
Allow model name/path override by config for offline/local cache.

Record exact tested package/model revisions in the executor report.

## 3. Dense embedding Port
Add an internal retrieval-only protocol, e.g. DenseEmbedderPort:
- embed_documents(texts) -> float32 matrix;
- embed_query(text) -> float32 vector;
- dimension property if known.

`BgeM3DenseEmbedder` requirements:
- lazy import/load; importing knowledge_curator must not require FlagEmbedding;
- dense output only for this phase;
- return finite float32 vectors;
- normalized vectors suitable for inner-product/cosine FAISS search;
- configurable model path/device/batch_size/fp16;
- no hard-coded CUDA requirement;
- no network call after model is loaded/cached.

Use official BGE-M3 dense output (`dense_vecs`) rather than inventing pooling.

## 4. FAISS VectorSearchPort adapter
Add `FaissVectorSearch` (name may vary) implementing existing VectorSearchPort.

Correctness requirements:
- index KnowledgeChunk.payload;
- preserve exact KnowledgeChunk metadata/provenance;
- support both COARSE and FINE levels;
- honor RetrievalQuery.allowed_ref_ids exactly;
- honor RetrievalQuery.top_k;
- return 1-based ranks and similarity raw_score;
- deterministic tie-breaking for equal scores;
- IndexFlatIP/cosine-style correctness baseline is acceptable;
- empty corpus/query results handled cleanly;
- dimension mismatch fails clearly.

For allowed_ref_ids correctness, do not under-retrieve and then filter away valid hits.
Because the baseline may use flat search, retrieving all rows then filtering is acceptable for correctness-first Phase 4.2; document performance limitations.

Do not wire this adapter into the frozen §5 VectorIndex commit Port in this phase.

## 5. Index lifecycle in Phase 4.2
Support at least in-process build/rebuild from a list of KnowledgeChunk.

Optional save/load is welcome if implemented cleanly, but do not redesign snapshot/version semantics.
Production atomic index lifecycle belongs to a later integration phase.

## 6. Real Chinese BM25 KeywordSearchPort
Implement a real BM25 keyword adapter, not a preset/fake ranking.

Requirements:
- Chinese-aware tokenization;
- recommended adapter: Jieba-based tokenizer, injectable behind a small KeywordTokenizerPort;
- deterministic Okapi BM25 scoring;
- English/alphanumeric terms remain searchable;
- build separate level-aware corpus state or filter correctly by ChunkLevel;
- honor allowed_ref_ids and top_k exactly;
- return 1-based ranks + raw BM25 score;
- zero-overlap query returns no misleading positive hits;
- preserve KnowledgeChunk provenance.

You may use a maintained BM25 library or implement the standard deterministic formula locally; whichever is used must be isolated behind the adapter and tested.

Do not use BGE-M3 sparse output as a substitute for the docs/03 BM25 channel.

## 7. BGE reranker adapter
Implement existing RerankerPort with the official BGE reranker baseline.

Requirements:
- default model `BAAI/bge-reranker-v2-m3`;
- lazy load / optional dependency;
- score pairs [query.text, hit.chunk.payload];
- descending relevance order;
- stable deterministic tie-break by existing rank/chunk_id;
- preserve `rrf_score`, channels and KnowledgeChunk provenance;
- add optional internal `rerank_score` to RankedHit only if useful; mark it internal/temporary;
- final rank re-numbered 1..N after rerank;
- no hard-coded GPU.

## 8. Dependency isolation
This repository currently has no root dependency manager for retrieval models.
Create a scoped optional dependency file such as:
`knowledge_curator/requirements-retrieval.txt`

Include only dependencies actually used by Phase 4.2.
Do not guess version pins. After successful real execution, pin or constrain the versions that were actually tested and report them.

Normal unit tests must still import/run without installing heavyweight retrieval extras.

## 9. Real retrieval fixture
Add a small checked-in fixture corpus containing both Chinese and English AI4S/electrodialysis-style text.
Use only synthetic/test text; do not add copyrighted papers.

Fixture should contain:
- >= 6 refs;
- a coarse summary per ref;
- multiple fine text/evidence-card chunks;
- known relevant ref/chunk labels for >= 6 queries;
- Chinese, English and mixed-language queries.

Do not claim this fixture is a scientific benchmark.

## 10. Keyless unit tests
Keep the full baseline 243 KC + 70 integration tests.

Real backend classes must be testable with injected lightweight fake embedding/scoring models so default CI stays keyless/offline.

Add unit tests for at least:
- FAISS exact nearest ranking on deterministic numeric embeddings;
- coarse/fine level filtering;
- allowed_ref_ids exact filter;
- top_k/rank semantics;
- empty index;
- duplicate/rebuild policy deterministic;
- BM25 Chinese exact-term retrieval;
- BM25 English term retrieval;
- BM25 zero-overlap query;
- reranker reorders hits using injected scorer;
- reranker preserves provenance/RRF score;
- optional dependency missing -> clear actionable error, not import crash.

## 11. Real-model smoke
Add an explicitly opt-in real smoke, e.g. environment gate `KC_RUN_REAL_RETRIEVAL=1`.

When enabled, it must:
1. load real BGE-M3;
2. embed the fixture corpus/query;
3. build/search FAISS;
4. run real BM25;
5. run hybrid coarse->fine;
6. run real BGE reranker;
7. verify returned chunks retain provenance and expected labels are retrievable.

Real smoke must record:
- device;
- model ids/paths;
- embedding dimension;
- package versions;
- per-query top-k refs/chunks;
- simple Recall@k / MRR summary.

Do not invent a global acceptance threshold not specified by 01/03.
At minimum, fail the smoke if the expected relevant evidence is never retrieved for a fixture query or if any stage produces invalid/non-finite scores.

If the executor environment cannot download/load the real models, report `NOT_RUN_ENV` with the exact reason and do NOT claim real backend validation PASS.

## 12. Hybrid integration
Use the existing frozen hybrid_retrieve service unchanged as much as possible.

Expected executable composition:
BgeM3DenseEmbedder + FaissVectorSearch
+ BM25KeywordSearch
+ optional injected GraphSearchPort
+ optional QueryExpansionPort
-> existing coarse RRF/filter
-> fine vector/graph/keyword RRF
-> BgeReranker.

Do not bypass hybrid_retrieve with a separate competing pipeline.

## 13. Graph and EDDO boundaries
Do not create SQLite/JSON graph internals in knowledge_curator.
Do not create a homemade EDDO synonym dictionary as the production expansion engine.

CG-004 continues to cover the real L2 graph/query API.
CG-016 records the missing EDDO query-expansion contract.

Use fake/in-memory GraphSearchPort / QueryExpansionPort only in composition tests.

## 14. Security/reproducibility
- no API keys required;
- no secrets in model config/logs;
- local model paths allowed;
- model download/cache paths must not be committed;
- generated FAISS indexes/model weights must not be committed;
- add gitignore entries if needed.

## 15. Deliverables
Create `results/phase-04-2-executor-report.md`.

Report:
- adapter classes/files;
- real models/package versions;
- FAISS index type/dimension;
- BM25 tokenizer/formula/library;
- real smoke status PASS / NOT_RUN_ENV / FAILED;
- fixture retrieval metrics;
- exact unit/integration counts;
- public contracts changed? NO;
- CONTRACT_GAPS changes;
- implementation SHA.

## 16. status.json
On completion:
- phase = 4.2
- actor = executor
- state = executor_complete
- latest_commit = actual implementation SHA
- result_expected = results/phase-04-2-executor-report.md

Push main and stop.
Do not start Phase 4.3, §6 MCP exposure, or §7.