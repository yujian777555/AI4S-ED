# Phase 4.1.1 Planner Review — Mostly Accepted, Final Retrieval-Contract Tightening Required

Implementation: afd5d4903f1a7c95844d98295bd3042ed76a4341
origin/main: 5f075c687081623c97372e5788fba02ee2e03e46
knowledge_curator tests: 210 passed / 0 failed
integration/dsh tests: 70 passed / 0 failed
Verdict: MOSTLY PASS.

## Accepted
- all fine chunk payloads now embed the canonical docs/03 provenance prefix;
- table/chart/evidence-card builders preserve whole-object semantics;
- text chunk ids are stable across runs and distinguish page/section/window contexts;
- RetrievalQuery is level-aware;
- in-memory adapters filter by level/allowed_ref_ids and honor top_k after filtering;
- hybrid_retrieve now performs an actual coarse stage before fine retrieval;
- fallback diagnostics are explicit;
- query top_k controls final output;
- provenance remains attached through fusion/rerank;
- no real production retrieval backend was smuggled into this phase.

## Remaining P4.1.2-01 — tokenizer is not truly reversible
TokenizerPort says encode/decode roundtrip must preserve content, but WordTokenizer uses text.split() and ' '.join(tokens).
This changes repeated whitespace/newlines and is not actually reversible for arbitrary text.
Before real tokenizer adapters are added, either make the test tokenizer truly reversible or relax/rename the contract to token-window rendering semantics.

Also, chunk_text budgets prefix/body separately but does not verify tokenizer.count(full_payload) <= max_tokens after composition.
A real tokenizer can tokenize boundaries differently, so the stored payload needs a final count check/adjustment.

## Remaining P4.1.2-02 — RRF duplicate handling is order-sensitive
rrf_fuse keeps the first duplicate seen for a chunk within one channel.
If malformed backend order is rank=5 then rank=1, rank=5 wins incorrectly.
Use the minimum valid rank per (chunk_id, channel), independent of candidate order.

## Remaining P4.1.2-03 — coarse candidates are unioned, not globally fused/ranked
The coarse stage concatenates vector and keyword candidates and derives allowed_ref_ids from the full union.
That means coarse_top_k is effectively per channel, not a global document-filter budget.
The Phase 4.1.1 plan required fused or deterministically ranked coarse hits and allowed_ref_ids derived from top coarse hits.

Use deterministic coarse RRF (or an equally explicit deterministic fusion) across VECTOR/KEYWORD coarse candidates, cap globally at coarse_top_k, then derive allowed_ref_ids.

## Remaining P4.1.2-04 — fallback semantics for truly absent coarse backend are inconsistent
When vector/keyword coarse backends are absent and allow_fine_fallback_without_coarse is false, code still proceeds to fine retrieval (e.g. graph-only).
The config name implies fallback must be explicitly allowed.
Make absent-backend and zero-hit behavior consistent: fallback=false means no unrestricted fine retrieval.

## Next
Proceed to Phase 4.1.2 only.
Once these four semantics are fixed, freeze the chunk/retrieval contract and then begin Phase 4.2 real backend integration.