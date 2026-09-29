# Phase 4.1 Planner Review — Chunk/Retrieval Skeleton Mostly Accepted, Contract Closure Required

Implementation: bb7a3cf2f809c4d69988722a8f8d5ee390fab12a
origin/main bookkeeping tip: cb766462eaa22491050091c0ed726b3e9698719b
knowledge_curator tests: 188 passed / 0 failed
integration/dsh tests: 70 passed / 0 failed
Verdict: MOSTLY PASS — table/chart/evidence-card shape, RRF, provenance retention and port boundaries are directionally correct; four contract defects must be closed before real retrieval backends.

## Accepted
- ChunkLevel and ChunkType are internal temporary compatibility models.
- table objects remain one chunk regardless of text length.
- chart objects remain one chunk.
- one Assertion produces one evidence-card chunk preserving assertion_id, locator, confidence and quality.
- coarse document summary wraps upstream-provided summary only; no LLM generation in core.
- vector/graph/keyword/query-expansion/reranker are Protocol boundaries, not concrete production backends.
- in-memory retrieval adapters are clearly test-only.
- RRF is rank-based, deterministic, fuses duplicate chunk ids across channels and preserves the KnowledgeChunk object/provenance.
- no FAISS/Qdrant/BGE-M3/BM25/reranker model, new Agent, MCP tool or §7 scope was introduced.

## Blocker P4.1.1-01 — prefix is not actually embedded in fine chunk payloads
docs/03 §6.1 requires each chunk payload to carry the provenance prefix.
Current builders store raw payload and expose a separate prefixed_payload() helper.
The actual KnowledgeChunk.payload returned by chunk_text/table/chart/evidence_card does not begin with the prefix.

The current prefix format is also not the documented form.
Implementation produces e.g. [REF-1|-|-|text].
Required semantics are [ref_id|page|section|type(文本/表/图/证据卡)].

The Phase 4.1 test only calls prefixed_payload(), so it does not catch the actual contract violation.

## Blocker P4.1.1-02 — text chunk ids collide across sections/pages
chunk_text uses chunk_id = f'{ref_id}:text:{idx}' and resets idx to zero for every call.
Two sections in the same document can therefore both create REF:text:0.

RRF keys by chunk_id, so distinct chunks can be incorrectly fused/deduplicated.
Text chunk identity must be deterministic and unique within the document, including section/page/span identity.

## Blocker P4.1.1-03 — tokenizer abstraction is not backend-safe
The Tokenizer Protocol exposes count() and split(), and reconstruction is ' '.join(tokens).
That is sufficient for the WordTokenizer test double but not for a real BPE/subword/Chinese tokenizer: joining token pieces with spaces can change content.

The contract should expose a reversible encode/decode (or equivalent span-preserving) API before real BGE/tokenizer adapters are added.

Text max-token accounting must apply to the actual stored prefixed payload or explicitly reserve prefix budget so the final payload remains within max_tokens.

## Blocker P4.1.1-04 — coarse->fine is not actually port-driven
hybrid_retrieve accepts precomputed coarse_candidates instead of performing coarse retrieval through the vector/keyword Ports.
RetrievalQuery has no ChunkLevel field and the search Ports cannot distinguish COARSE from FINE requests.

This means the service does not yet implement the planned flow:
coarse search -> allowed_ref_ids -> fine vector/graph/keyword -> RRF.

Also, RetrievalQuery.top_k is currently not authoritative: in-memory adapters do not truncate to it and final fusion uses RetrievalConfig.top_k instead.

## Required closure
Phase 4.1.1 must:
- put the exact provenance prefix into every fine KnowledgeChunk.payload;
- use documented type(...) labels;
- make text chunk ids deterministic and collision-free across section/page calls;
- use reversible/token-span-safe tokenizer abstraction;
- make final prefixed text payload respect max_tokens;
- add level-aware retrieval queries/Port behavior;
- have hybrid_retrieve perform coarse vector/keyword retrieval itself when coarse backends are configured;
- derive allowed_ref_ids from those coarse hits;
- explicitly diagnose fallback when coarse retrieval is unavailable/empty according to config;
- make query.top_k behavior deterministic and testable.

## Next
Proceed to Phase 4.1.1 only.
Do not start real embedding/index/reranker backends until these contracts are corrected.