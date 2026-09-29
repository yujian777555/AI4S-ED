# Phase 4.1.1 Plan — Chunk Identity/Prefix + True Port-Driven Coarse→Fine Closure

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Scope
Close the Phase 4.1 contract defects only.

Do not implement real FAISS/Qdrant/BGE-M3/BM25/reranker.
Do not add §6 MCP exposure.
Do not change frozen Phase 4.0 H1/H2/H3/Abstain semantics.
Do not start §7.

## 1. Fine payload prefix must be real
Every FINE KnowledgeChunk produced by the builders must have payload beginning with the canonical docs/03 prefix.

Exact format:
[ref_id|page|section|type(类型)]

Type labels:
- TEXT -> 文本
- TABLE -> 表
- CHART -> 图
- EVIDENCE_CARD -> 证据卡.

Use '-' for missing page/section.

Examples:
[ED2025-0042|8|Results|type(文本)] ...
[ED2025-0042|8|Results|type(表)] ...

Do not require callers to remember to call prefixed_payload().
Either remove that helper or make it idempotently return the already-prefixed payload.

Coarse DOCUMENT_SUMMARY may use a documented internal summary prefix if desired, but this phase's hard requirement is all fine chunks.

## 2. Token budget includes prefix
For text chunks, the stored prefixed payload must remain <= max_tokens according to the injected tokenizer.

Reserve the prefix token budget before slicing body tokens.
Overlap applies to BODY token windows, not repeated prefix tokens.

If the prefix alone consumes >= max_tokens, fail clearly with a configuration error rather than loop/truncate silently.

## 3. Replace split/join tokenizer contract
Use a reversible abstraction, recommended:

TokenizerPort:
- encode(text) -> token sequence
- decode(tokens) -> text
- count(text) may be derived or retained.

Do not reconstruct arbitrary tokenizers via ' '.join(token pieces).

Keep a deterministic test tokenizer adapter.

Tests must prove round-trip preservation for punctuation/non-ASCII sample text with the test adapter.

## 4. Deterministic collision-free text chunk ids
Text chunk IDs must distinguish different page/section/span contexts within the same ref_id.

Recommended identity inputs:
- ref_id
- page
- section
- body token start/end offsets or deterministic context hash.

Do not use Python hash().
Use a stable serialized key / SHA-256 digest if hashing.

Requirements:
- same input => same chunk ids across runs;
- different sections in same ref => no collision;
- different pages in same section => no collision;
- adjacent windows in one section => no collision.

## 5. Add ChunkLevel to retrieval query
RetrievalQuery must explicitly carry level: COARSE or FINE.

Ports must receive enough information to honor:
- query text;
- level;
- allowed_ref_ids;
- top_k.

Keep this internal/temporary; do not define a public cross-team API.

## 6. In-memory adapters honor level/top_k
Test adapters must:
- filter chunks by query.level;
- filter by allowed_ref_ids when supplied;
- return at most query.top_k;
- assign 1-based ranks after filtering, not before.

Do not pretend these are semantic search implementations.

## 7. True coarse retrieval in hybrid_retrieve
hybrid_retrieve must no longer depend on caller-supplied precomputed coarse_candidates as the main path.

When coarse retrieval is configured:
1. build a COARSE RetrievalQuery;
2. run coarse vector and/or keyword channel(s);
3. fuse or deterministically union/rank coarse hits;
4. derive allowed_ref_ids from the top coarse hits;
5. build FINE RetrievalQuery with those allowed_ref_ids;
6. run fine vector + graph + keyword;
7. RRF fuse;
8. optional rerank;
9. final top_k.

Graph is fine-stage unless a future contract explicitly defines coarse graph retrieval.

If a legacy coarse_candidates argument is retained temporarily, mark it deprecated/test-only and do not let it bypass diagnostics silently.

## 8. Coarse fallback semantics
Add explicit config, e.g.:
allow_fine_fallback_without_coarse = true/false.

Diagnostics must distinguish:
- coarse backend absent;
- coarse backend ran and returned hits;
- coarse backend ran and returned zero hits;
- fallback fine retrieval used.

Do not silently convert an empty coarse result into unrestricted fine retrieval unless config explicitly allows it.

## 9. top_k semantics
RetrievalQuery.top_k must be honored by channel adapters.

Define final service behavior clearly:
- coarse_top_k configurable;
- fine/output top_k comes from query.top_k unless an explicit config override is documented.

After reranking, slice final output to requested top_k.

Add tests for query.top_k=1/2.

## 10. RRF safety
Keep the accepted RRF formula.

Add validation/normalization so ranks must be >=1.
Within a single channel, the same chunk_id must not contribute multiple times to score; retain its best/first rank only.

This prevents a malformed backend from inflating one chunk by duplicate rows.

## 11. Provenance invariants
After actual prefixing, coarse filtering, fine retrieval, RRF and rerank:
- ref_id
- locator/object_id
- chunk_type
- confidence
- quality
- provenance
must remain intact.

## 12. Tests
Keep baselines:
- integration/dsh = 70 passed;
- knowledge_curator = 188 passed.

Add tests for at least:
- actual TEXT payload starts canonical type(文本) prefix;
- TABLE payload starts type(表);
- CHART payload starts type(图);
- EVIDENCE_CARD payload starts type(证据卡);
- final prefixed text payload <= max_tokens;
- body overlap remains 64 tokens;
- prefix does not count as overlap;
- tokenizer encode/decode preserves punctuation/non-ASCII;
- same input gives stable chunk ids;
- same ref different sections/pages have distinct chunk ids;
- RetrievalQuery level honored;
- in-memory adapters honor top_k and rank after filter;
- hybrid service itself runs coarse stage;
- coarse hits restrict fine allowed_ref_ids;
- coarse zero-hit fallback is explicit;
- coarse zero-hit with fallback disabled returns no unrestricted fine results;
- query.top_k controls final size;
- duplicate same chunk in one RRF channel is not double-counted;
- rank <=0 rejected/ignored deterministically;
- provenance survives final rerank.

## 13. Report
Create results/phase-04-1-1-executor-report.md.

Report:
- canonical prefix behavior;
- tokenizer contract;
- chunk identity scheme;
- level-aware retrieval contracts;
- actual coarse->fine flow;
- fallback diagnostics;
- top_k semantics;
- RRF safety;
- exact test counts;
- public contracts changed? NO;
- CONTRACT_GAPS changes;
- implementation SHA.

## 14. status.json
On completion:
- phase = 4.1.1
- actor = executor
- state = executor_complete
- latest_commit = actual implementation SHA
- result_expected = results/phase-04-1-1-executor-report.md

Push main and stop.
Do not start Phase 4.2.