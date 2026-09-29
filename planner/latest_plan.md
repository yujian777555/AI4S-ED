# Phase 4.1.2 Plan — Final Hybrid Retrieval Contract Closure

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## Scope
Fix only the remaining retrieval-contract semantics. No real FAISS/BGE/BM25/reranker yet.

## 1. Tokenizer contract
Make the test tokenizer truly reversible for arbitrary text including repeated whitespace/newlines, OR rename the Protocol semantics so decode(encode(text)) exact equality is not promised.
Preferred: implement a deterministic reversible test tokenizer using lossless token spans/chunks.

chunk_text must verify tokenizer.count(full_payload) <= max_tokens on the actual stored payload.
If composition exceeds budget, shrink the body window deterministically until it fits; fail clearly if prefix alone cannot fit.

Add tests with:
- repeated spaces;
- newlines;
- Chinese/punctuation;
- boundary-sensitive tokenizer fake where count(prefix)+count(body) differs from count(prefix+' '+body).

## 2. RRF same-channel duplicates
For each (chunk_id, channel), use minimum valid rank independent of input order.
Invalid rank <1 remains ignored/rejected deterministically.
Add reversed-order duplicate tests: rank 5 then rank 1 must score as rank 1.

## 3. Coarse fusion
Coarse VECTOR and KEYWORD candidates must be fused/ranked deterministically before filtering.
Use RRF or another explicitly deterministic rank fusion.
Apply coarse_top_k globally after fusion.
Derive allowed_ref_ids only from those top fused coarse hits.

Diagnostics should record coarse channels used and coarse hit count after fusion.

## 4. Fallback consistency
If no coarse backend is available:
- allow_fine_fallback_without_coarse=true -> explicit unrestricted/allowed-ref fine fallback;
- false -> return no fine hits.

If coarse backends run but return zero hits, apply the same policy.
No silent fine retrieval when fallback is false.

## 5. Tests
Keep baselines:
- integration/dsh >= 70;
- knowledge_curator >= 210.

Add tests for:
- tokenizer exact roundtrip with whitespace/newlines/non-ASCII;
- final full payload token count;
- boundary-sensitive token counter;
- RRF duplicate min-rank regardless of order;
- global coarse_top_k across multiple coarse channels;
- coarse fusion duplicate document behavior;
- absent coarse backend + fallback=false => no fine hits;
- absent coarse backend + fallback=true => explicit fallback;
- zero coarse hits + fallback=false => no fine hits;
- zero coarse hits + fallback=true => explicit fallback;
- provenance unchanged.

## 6. Deliverables
Create results/phase-04-1-2-executor-report.md.
Update status.json to phase=4.1.2, actor=executor, state=executor_complete, latest_commit=actual implementation SHA.
Push main and stop. Do not start Phase 4.2.