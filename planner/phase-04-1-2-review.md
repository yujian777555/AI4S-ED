# Phase 4.1.2 Planner Review — Mostly Accepted, Two Final Contract Defects Remain

Implementation: c1ea8af8bde4ee44b7c83bb5e7869a5eb1f6bd99
origin/main bookkeeping tip: df99d3bc1c49055f9c92f52351a1311b18248610
knowledge_curator tests: 228 passed / 0 failed
integration/dsh tests: 70 passed / 0 failed
Verdict: MOSTLY PASS.

## Accepted
- WordTokenizer encode/decode itself is now lossless for whitespace/non-ASCII samples;
- final stored text payload is re-counted and shrunk when a boundary-sensitive tokenizer reports overflow;
- RRF duplicate handling uses minimum valid rank independent of candidate order;
- coarse VECTOR/KEYWORD candidates are globally fused before coarse_top_k;
- coarse_top_k is global after fusion;
- fallback=false blocks unrestricted fine retrieval in the tested no-coarse paths;
- provenance is preserved;
- no real production backend or public contract was introduced.

## Remaining P4.1.3-01 — chunk_text bypasses TokenizerPort for actual windowing
chunk_text calls tok.encode(text), but then ignores that result and uses text.split() plus ' '.join(...) to build windows.
This means:
- repeated spaces/newlines are still lost inside produced chunk bodies;
- the configured tokenizer does not actually define window boundaries;
- overlap_tokens is word-based rather than tokenizer-token-based;
- a future BPE/Chinese tokenizer adapter would not control chunking as the Port contract promises.

Before real backends, chunk_text must slice the tokenizer's encoded token sequence and reconstruct each body through tokenizer.decode(window).
The tokenizer contract should make it clear that encode returns the budget/window token sequence and count agrees with that sequence.

## Remaining P4.1.3-02 — coarse backend presence is inferred from returned hits
hybrid_retrieve sets coarse_backend_present from bool(coarse_channel_candidates).
If vector/keyword Ports are configured but both return zero coarse hits, diagnostics incorrectly report backend absent rather than backend ran with zero hits.

Backend presence must be based on configured Ports; hit status must be based on results.
Diagnostics should distinguish attempted coarse channels from channels that returned hits.

## Next
Proceed to Phase 4.1.3 only.
After these two fixes, freeze §6.1/§6.2 retrieval contracts and start Phase 4.2 real backend integration.