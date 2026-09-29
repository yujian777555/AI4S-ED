# Phase 4.1 Plan — §6.1 Chunking + §6.2 Hybrid Retrieval Contracts

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Goal
Implement the deterministic document-to-chunk layer from docs/03 §6.1 and the runtime-independent hybrid retrieval contracts/skeleton from §6.2.

This phase establishes:
- canonical chunk schemas and provenance prefix;
- text/table/chart/assertion-evidence-card chunk builders;
- document coarse summary vs fine chunk levels;
- vector / graph / keyword retrieval Ports;
- optional query-expansion and reranker Ports;
- deterministic RRF fusion;
- a port-driven coarse->fine retrieval service using in-memory/fake adapters for tests.

This phase does NOT implement:
- FAISS/Qdrant;
- BGE-M3 embeddings;
- Chinese tokenizer/BM25 index;
- EDDO expansion implementation;
- bge-reranker model;
- final QA answer generation;
- new Agent/MCP tools;
- §7.

## 1. Read first
- docs/01-总体架构与数据流设计.md
- docs/03-文献自动调研与知识入库流水线.md §6.1 and §6.2
- planner/KNOWLEDGE_CURATOR_BOUNDARY.md
- planner/phase-04-0-2-review.md
- planner/CONTRACT_GAPS.md
- existing knowledge_curator/schemas/assertions.py
- existing evidence schemas/guard.

## 2. Chunk compatibility schemas
Add internal temporary models, recommended under knowledge_curator/schemas/retrieval.py or chunking.py.

Required concepts:
ChunkLevel: COARSE / FINE
ChunkType: DOCUMENT_SUMMARY / TEXT / TABLE / CHART / EVIDENCE_CARD

KnowledgeChunk fields should minimally include:
- chunk_id
- ref_id
- level
- chunk_type
- payload
- page optional
- section optional
- object_id/locator optional
- provenance pointer(s)
- assertion_id optional
- confidence optional
- quality optional.

All are internal temporary compatibility models, not frozen public schemas.

## 3. Canonical metadata prefix
Every fine chunk payload must begin with the docs/03 prefix semantics:
[ref_id|page|section|type(...)]

Use deterministic rendering and escape/normalize missing fields consistently.

Map chunk type display values to the documented Chinese categories where appropriate:
- text -> 文本
- table -> 表
- chart -> 图
- evidence card -> 证据卡.

Do not hide provenance only in metadata; prefix must actually be present in payload.

## 4. Text chunking
Implement title/section-anchored text chunking.

Config defaults from docs/03:
- max_tokens = 512
- overlap_tokens = 64.

Do not hard-wire a model tokenizer into core.
Create a TokenizerPort or equivalent encode/decode/count abstraction.
Provide a deterministic test-only/simple adapter.

Rules:
- text chunks respect section boundaries where possible;
- each text chunk <= max_tokens according to the injected tokenizer;
- adjacent chunks within the same section overlap by overlap_tokens when splitting is necessary;
- never create an infinite loop when section length <= overlap;
- empty text produces no chunk.

## 5. Table chunks
TableObject is ONE whole fine chunk.

Payload must contain, when supplied by upstream:
- caption
- headers
- units
- bounded row summary/content.

Do not split a table merely because it exceeds text max_tokens.
This is an explicit docs/03 exception.

Do not invent/reparse PDF tables; accept an already parsed table compatibility input.

## 6. Chart chunks
ChartObject is ONE whole fine chunk.

Payload should carry:
- chart/object id
- caption/meta
- axes/units when available
- digitized summary when available.

Do not split charts and do not perform chart digitization here.

## 7. Assertion evidence-card chunks
For each Assertion, build one evidence-card fine chunk containing deterministically:
- subject/resolved entity
- property
- value/range
- unit
- operating conditions
- source ref_id
- locator
- confidence.

Evidence-card chunk must preserve assertion_id and be suitable for claim-level citation.

Do not change Assertion schema or curation confidence.

## 8. Coarse document chunk
Support one coarse document-summary chunk per source when an upstream summary is provided.

Do not generate summaries with an LLM in core.
The builder only wraps upstream-provided summary text plus source metadata.

Coarse chunks and fine chunks must be distinguishable by ChunkLevel.

## 9. Retrieval query/result contracts
Add internal runtime-independent models:
- RetrievalQuery
- RetrievalCandidate / RankedHit
- RetrievalChannel: VECTOR / GRAPH / KEYWORD.

Candidate must carry a KnowledgeChunk or stable chunk id plus:
- channel
- channel rank
- optional raw score
- provenance preserved end-to-end.

Do not define a new cross-team public API.

## 10. Retrieval Ports
Define narrow Protocols, recommended:

VectorSearchPort:
- search(query, *, level, allowed_ref_ids?, top_k) -> hits

GraphSearchPort:
- search(query, *, allowed_ref_ids?, top_k) -> hits

KeywordSearchPort:
- search(query, *, level, allowed_ref_ids?, top_k) -> hits

QueryExpansionPort:
- expand(query) -> expanded terms/query representation

RerankerPort:
- rerank(query, candidates, top_k) -> candidates

Do not hard-code FAISS/SQL/BM25/BGE implementations in these Ports.

## 11. Coarse -> fine retrieval service
Implement a deterministic service driven only by Ports.

Expected flow:
1. optional concept/query expansion;
2. coarse document filtering using available coarse channels (vector/keyword as configured);
3. derive allowed_ref_ids from coarse hits;
4. run fine retrieval on vector + graph + keyword channels;
5. RRF fuse the fine ranked lists;
6. optional reranker;
7. return top_k EvidenceRecords/KnowledgeChunks with full provenance.

If no coarse backend is configured or no coarse chunks exist, support an explicit configured fallback to fine retrieval; do not silently pretend coarse filtering happened.

Return diagnostic metadata indicating which channels ran and whether coarse filtering was applied.

## 12. RRF
Implement pure deterministic Reciprocal Rank Fusion.

Configurable k constant; use a documented default such as 60 unless project docs specify otherwise.

For each unique chunk identity:
score = sum(1 / (k + rank_channel))

Requirements:
- rank starts at 1;
- duplicate same chunk across channels is fused, not duplicated;
- stable deterministic tie-breaking using chunk_id/ref_id;
- raw channel scores do not replace rank-based RRF.

Do not claim RRF k is a frozen project-wide hyperparameter.

## 13. In-memory/fake adapters only
Provide minimal in-memory retrieval adapters for tests.

They may return predefined ranked hits; they should not pretend to be FAISS/BM25 implementations.

## 14. Provenance invariants
Every returned fine hit must preserve:
- ref_id;
- locator/object id when present;
- chunk type;
- confidence/quality when present.

No retrieval stage may strip provenance needed by Phase 4.0 H1/H2 guard.

Add explicit tests for this.

## 15. Boundaries
Do not:
- implement lit_researcher;
- parse PDFs/XML;
- digitize charts;
- own L2 graph/database implementation;
- implement EDDO ontology expansion itself;
- implement final user answer wording;
- add trusted_rag_agent/qa_agent;
- add DSH/MCP tool exposure in this phase.

External engines remain adapters owned/integrated later.

## 16. Tests
Maintain baselines:
- integration/dsh: 70 passed / 0 failed;
- knowledge_curator: 173 passed / 0 failed.

Add deterministic tests for at least:
- metadata prefix exact presence;
- text <=512 token config limit;
- 64-token overlap;
- section boundary behavior;
- table remains one chunk even over text limit;
- chart remains one chunk;
- one assertion -> one evidence card;
- evidence card preserves locator/confidence;
- coarse/fine levels distinct;
- RRF duplicate fusion;
- RRF stable tie-break;
- coarse allowed_ref_ids restrict fine search;
- explicit no-coarse fallback diagnostic;
- graph/vector/keyword channel labels retained;
- provenance survives fusion/rerank.

Do not require API keys/models for ordinary tests.

## 17. No changes to frozen guard semantics
Phase 4.0/4.0.1/4.0.2 evidence guard behavior is frozen.
Do not reinterpret H1/H2/H3, confidence policy or Abstain to suit retrieval implementation.

## 18. Deliverables
Create results/phase-04-1-executor-report.md.

Report:
- chunk schemas/types;
- tokenizer abstraction;
- chunking behavior;
- retrieval Ports;
- coarse->fine flow;
- RRF behavior;
- test counts;
- public contracts changed? NO;
- CONTRACT_GAPS changes;
- implementation SHA.

## 19. status.json
On completion:
- phase = 4.1
- actor = executor
- state = executor_complete
- latest_commit = actual implementation SHA
- result_expected = results/phase-04-1-executor-report.md

Push main and stop.
Do not start real FAISS/BM25/BGE-M3/reranker or Phase 4.2.