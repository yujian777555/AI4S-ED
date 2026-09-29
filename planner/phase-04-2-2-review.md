# Phase 4.2.2 Planner Review — Remote Parity Restored, Full Real Stack Still Not Closed

Implementation code chain:
- f6e6e9997d83936a47a0a6f6d11428222c6d66c9 — backend correctness + fixture + smoke harness
- 7ba57bb34b37fc37f640dd3c473c947aa6d40def — FlagEmbedding/transformers compatibility + real BGE-M3 GPU smoke
Bookkeeping:
- 28299f4570bd7d48723a63b173ef884a96991a8e

Verdict: MOSTLY PASS.

## Accepted

- Remote-code parity is restored: actual source/test/smoke changes are present on origin/main.
- BGE-M3 real model loaded and encoded successfully on CUDA.
- Measured dense dimension is 1024.
- FAISS exact filtered correctness is fixed via search-all-then-filter.
- Real Jieba BM25 is exercised.
- Synthetic fixture exists: 6 refs / 14 chunks / 6 labelled multilingual queries.
- Real smoke result records Recall@1=1.0, Recall@3=1.0, MRR=1.0 for the executed non-reranked fine-stage pipeline.
- FlagEmbedding 1.4.2 / transformers 4.49 compatibility shim is committed.
- No public contract changed.

## Remaining blocker P4.2.3-01 — real smoke bypasses the coarse stage

The fixture includes COARSE summary chunks, but real_smoke.py does:

fine_chunks = [c for c in chunks if c.level == ChunkLevel.FINE]
fine_vector.add_chunks(fine_chunks)
fine_keyword.add_chunks(fine_chunks)

Those same fine-only indexes are passed to hybrid_retrieve.

Therefore the real smoke's coarse query returns zero coarse hits and the service takes allow_fine_fallback_without_coarse=True.

The recorded Recall/MRR validates:
BGE-M3 + FAISS + Jieba BM25 + fine RRF

It does NOT validate the frozen production path:
real coarse retrieval -> coarse RRF/filter -> allowed_ref_ids -> real fine retrieval.

## Remaining blocker P4.2.3-02 — reranker is absent but smoke is labelled PASS

The result explicitly records:
- reranker_used = false
- reranker_model_path = null
- warning: reranker model not present locally

Phase 4.2.2 required a real non-empty bge-reranker-v2-m3 scoring pass before full-stack PASS.

Running without reranker is a valid degraded smoke, but it cannot be labelled full Phase 4.2 PASS because docs/03 §6.2 specifies RRF -> bge-reranker.

## Remaining blocker P4.2.3-03 — smoke terminal status must expose degraded/full-stack state

PASS currently means only "no fixture query missed expected evidence", even when:
- coarse stage falls back;
- reranker is unused.

For Phase 4.2.3:
- PASS must mean coarse_filter_applied=true on the real path AND reranker_used=true.
- missing reranker model before execution may be NOT_RUN_ENV for the full-stack smoke.
- retrieval-without-reranker may still be recorded as a separate degraded diagnostic, not the acceptance PASS.

## Test-quality note

Some dependency-error tests remain intentionally loose and should be tightened where convenient, but this is not a new architecture blocker.

## Next

Proceed to Phase 4.2.3 only:
1. index both coarse + fine fixture chunks in the real VECTOR/KEYWORD backends;
2. prove real coarse filtering is applied;
3. install/provide bge-reranker-v2-m3 weights and score a non-empty candidate set;
4. rerun the same 6-query metrics through the complete hybrid pipeline.

After this, Phase 4.2 can be frozen and Phase 4.3 may begin.
