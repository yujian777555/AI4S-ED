# Phase 4.1.3 Plan — Tokenizer-Driven Windows + Correct Coarse Diagnostics

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Scope
Fix only the final two Phase 4.1 retrieval-contract defects.
No FAISS/Qdrant/BGE-M3/BM25/reranker model yet. No MCP/§7.

## 1. Make tokenizer the actual chunk-window authority
chunk_text must not use text.split() or ' '.join(...) for body windows.

Use the TokenizerPort encoded sequence directly:
- encoded = tokenizer.encode(text)
- each body window is a slice of encoded;
- body_text = tokenizer.decode(window)
- overlap_tokens applies to encoded tokenizer tokens.

Define/clarify the temporary TokenizerPort invariant:
- encode(text) returns the actual window/budget token sequence;
- decode(encode(text)) == text for the test adapter;
- count(text) == len(encode(text)) for the test adapter and preferably for adapters unless explicitly documented otherwise.

Implement the deterministic test tokenizer so tokens can preserve whitespace exactly while still being sliceable.
A practical test implementation may bundle surrounding whitespace with lexical units; exact design is executor choice.

Requirements:
- repeated spaces/newlines inside chunk bodies are preserved;
- Chinese/punctuation remain preserved;
- same tokenizer determines max-token window and overlap;
- no fallback to Python str.split for production chunk logic.

## 2. Full payload budget remains authoritative
Keep the Phase 4.1.2 final tokenizer.count(full_payload) <= max_tokens validation.
If shrinking is needed, shrink the encoded body-token window, not a word-split surrogate.

## 3. Correct coarse diagnostics
coarse_backend_present must be true when vector_port or keyword_port is configured for coarse retrieval, even when zero hits are returned.

Track separately, recommended:
- coarse_channels_attempted
- coarse_channels_with_hits
- coarse_fused_hit_count.

Semantics:
- no vector/keyword port configured -> COARSE_ABSENT;
- port(s) configured and searched, zero fused hits -> COARSE_ZERO;
- port(s) configured and fused hits >0 -> COARSE_HIT.

Fallback policy remains:
- absent or zero + fallback=false -> no fine hits;
- absent or zero + fallback=true -> explicit fine fallback.

## 4. Tests
Keep baselines:
- integration/dsh >= 70;
- knowledge_curator >= 228.

Add tests for:
- chunk body preserves repeated spaces;
- chunk body preserves newline(s) when within one window;
- tokenizer encode sequence, not text.split, controls boundaries;
- overlap is exactly overlap_tokens in encoded-token terms;
- boundary-sensitive full-payload shrinking still works using encoded windows;
- configured coarse port + zero coarse hits -> coarse_backend_present=true and COARSE_ZERO;
- no coarse ports -> coarse_backend_present=false and COARSE_ABSENT;
- attempted coarse channels recorded even with zero hits;
- channels-with-hits recorded separately;
- fallback behavior unchanged;
- provenance unchanged.

## 5. Deliverables
Create results/phase-04-1-3-executor-report.md.
Update status.json: phase=4.1.3, actor=executor, state=executor_complete, latest_commit=actual SHA.
Push main and stop. Do not start Phase 4.2.