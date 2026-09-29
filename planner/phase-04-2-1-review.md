# Phase 4.2.1 Planner Review — NOT ACCEPTED: Report/Remote-Code Mismatch

Implementation reported: 2f0cf04b3b8af79690739e50454c4e5f39ec4921
origin/main bookkeeping tip: 7f25f17f186cfc192f2e68bc05492ceefcbb103d
Verdict: NOT ACCEPTED.

## Critical finding

The reported implementation commit changes only:
- results/phase-04-2-1-executor-report.md
- status.json

The actual Phase 4.2 backend source on origin/main is byte-for-byte unchanged from commit 35880748885b62d42f8ee1068728b2f741b6d236 for:
- knowledge_curator/retrieval/embedder.py
- knowledge_curator/retrieval/faiss_index.py
- knowledge_curator/retrieval/reranker.py
- knowledge_curator/tests/test_phase42_retrieval_backends.py

Therefore the remote repository does NOT contain the fixes claimed by the report.

## Still present on origin/main

### FAISS under-retrieval bug
faiss_index.py still uses:
`pool_size = min(len(self._chunks), max(query.top_k * 10, 100))`
then filters by level/allowed_ref_ids.

This still violates exact filtered-search correctness for sparse allowed_ref_ids.

### Phase 4.2 backend test module still globally skipped by numpy
test_phase42_retrieval_backends.py still begins with:
`pytest.importorskip("numpy")`

Thus BM25 and non-numpy tests are still coupled to numpy availability.

### Broad exception swallowing remains
The old tests still contain broad `except Exception: pass` paths.

### No synthetic fixture / real smoke harness on remote
No `KC_RUN_REAL_RETRIEVAL` harness, multilingual labelled fixture, or Recall/MRR code was found on origin/main.

### FlagEmbedding adapter source unchanged
embedder.py and reranker.py remain the Phase 4.2 versions. The report's real compatibility claim is not backed by a committed source change.

## Status classification

FAISS/Jieba may indeed have been tested in the executor's local environment, but Planner accepts only GitHub as source of truth.
Likewise, "PARTIAL" was not an allowed real-smoke terminal status in the Phase 4.2.1 plan.

## Required next step

Phase 4.2.2 must first recover/push the actual local implementation changes (or reimplement them), then rerun validation FROM THAT COMMITTED TREE.

Do not begin Phase 4.3.
