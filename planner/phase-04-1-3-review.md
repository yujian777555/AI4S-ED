# Phase 4.1.3 Planner Review — Chunk/Hybrid Retrieval Contracts Frozen

Implementation: a4637c723ade46953ebf02dce1f10a5a97167771
origin/main bookkeeping tip: 841eccf31703d007dff28e673ba4dbb7e91bac48
knowledge_curator tests: 243 passed / 0 failed
integration/dsh tests: 70 passed / 0 failed
Verdict: PASS.

## Accepted
- chunk_text is now genuinely driven by TokenizerPort.encode -> token-window slice -> decode;
- body formatting including repeated spaces/newlines/non-ASCII is preserved by the deterministic tokenizer;
- overlap_tokens applies to encoded tokenizer tokens, not Python words;
- full stored payload remains subject to final tokenizer.count(payload) <= max_tokens validation;
- coarse backend presence is based on configured vector/keyword Ports, not returned candidates;
- diagnostics distinguish attempted channels, channels with hits, zero-hit and absent-backend cases;
- fallback semantics remain explicit and fail closed when disabled;
- global coarse RRF, coarse_top_k, fine RRF, top_k and provenance behavior from 4.1.2 remain intact;
- no real backend, public schema, DSH, §5 or §7 behavior was changed.

## Freeze
docs/03 §6.1 chunking and the §6.2 runtime-independent retrieval contract are now frozen:
- canonical chunk prefix and chunk identity;
- TokenizerPort window semantics;
- coarse/fine RetrievalQuery;
- VECTOR/GRAPH/KEYWORD channel Ports;
- deterministic RRF;
- coarse->fine fallback/diagnostics;
- provenance invariants.

Future backend phases may implement these Ports but must not silently reinterpret them.

## Repository scan before Phase 4.2
No existing BGE-M3, FAISS, BM25 or reranker implementation was found in AI4S-ED main.
Existing §5 VectorIndex is a staged-write identity Port over VectorPayload and is not sufficient by itself to implement search embeddings.
Phase 4.2 therefore adds retrieval adapters without changing the frozen §5 commit semantics.

## Next
Proceed to Phase 4.2 real retrieval backends: BGE-M3 dense + FAISS, Chinese BM25, and BGE reranker.
Graph/L2 storage remains behind GraphSearchPort; do not implement 02/L2 database internals.