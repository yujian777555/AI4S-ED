# Phase 4.2 Planner Review — Adapter Code Mostly Accepted, Real Backend Validation Required

Implementation: 35880748885b62d42f8ee1068728b2f741b6d236
origin/main bookkeeping tip: 2b32aadea7a00fc502ded8496fdf643197299ba5
knowledge_curator: 243 passed / 1 skipped / 0 failed
integration/dsh: 70 passed / 0 failed
Verdict: MOSTLY PASS — backend adapter code exists, but Phase 4.2 has not yet demonstrated a real end-to-end retrieval backend run.

## Accepted
- heavy retrieval dependencies are scoped and optional;
- importing core knowledge_curator does not eagerly require FlagEmbedding/faiss/jieba;
- BGE-M3 dense, FAISS, BM25 and BGE reranker adapters are separated from frozen §5 VectorIndex semantics;
- BM25 uses real Okapi scoring rather than fake preset ranks;
- graph/L2 and EDDO expansion boundaries were respected;
- no public contract was changed.

## Blocker P4.2.1-01 — FlagEmbedding device argument mismatches current official API examples
Current code constructs BGEM3FlagModel and FlagReranker using device=...
Current official FlagEmbedding examples/documentation use devices=... for both BGEM3FlagModel and FlagReranker.
Real execution must be tested against the actually installed FlagEmbedding version and corrected accordingly.

Do not guess compatibility: record the exact installed FlagEmbedding version and the constructor path that succeeds.

## Blocker P4.2.1-02 — FAISS allowed_ref_ids filtering can under-retrieve
FaissVectorSearch searches only max(top_k*10, 100) nearest rows and filters level/ref afterwards.
With a large index and sparse allowed_ref_ids, all valid allowed rows can lie outside that pool, producing incomplete results.

Phase 4.2 explicitly required correctness-first behavior.
For IndexFlat baseline, search all indexed rows (or pre-filter/rebuild/select exact candidate rows) when level/allowed_ref_ids filters are active.

## Blocker P4.2.1-03 — backend tests were effectively skipped
`test_phase42_retrieval_backends.py` begins with pytest.importorskip('numpy').
In the reported environment numpy was absent, so the module is skipped as a whole.
Therefore FAISS/BM25/reranker correctness assertions have not actually executed in this environment.

Several tests are also too permissive:
- BGE missing-dependency test catches arbitrary Exception and passes;
- FAISS dimension test catches arbitrary Exception and passes;
- reranker dependency test passes empty hits, so the model need not load;
- no real jieba Chinese-tokenization test ran.

These tests must fail on unexpected exceptions.

## Blocker P4.2.1-04 — required fixture and real smoke harness are missing
No checked-in synthetic multilingual retrieval fixture was found.
No KC_RUN_REAL_RETRIEVAL harness was found.
No Recall@k/MRR computation path was found.

NOT_RUN_ENV is honest, but the phase cannot be considered real-backend validated until the harness exists and either:
- runs PASS in an environment with dependencies/model access; or
- exists and reports NOT_RUN_ENV with a precise preflight reason.

## Non-blocking notes
- BGE-M3 1024 dimension is consistent with official model documentation, but it was not measured in this run.
- BGE reranker model choice `BAAI/bge-reranker-v2-m3` is appropriate; validation still needs a real run.

## Next
Proceed to Phase 4.2.1 only.
Do not start §6 MCP/4.3 until one real backend smoke has been attempted with the corrected adapters.