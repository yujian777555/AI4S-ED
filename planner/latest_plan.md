# Phase 1.2 Plan — confidence monotonicity & exact tolerance semantics

**Planner:** ChatGPT  
**Executor:** MiMo  
**State:** READY_FOR_EXECUTOR  
**Base implementation:** `9611bb2e86720bad6c548c2ac30c4cb8c0e36361`

Read:
1. `docs/01-总体架构与数据流设计.md`
2. `docs/03-文献自动调研与知识入库流水线.md`
3. `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`
4. `planner/phase-01-1-review.md`
5. `planner/CONTRACT_GAPS.md`
6. `status.json`

## Goal

Only close the two correctness issues from the Phase 1.1 Planner review.

Do not start §5.4, §6, §7, DSH integration, or DeepSeek API integration in this round.

## A. Confidence monotonicity for single-source capping

Replace the current "always MEDIUM" behavior with a true ceiling.

Required behavior:
- HYPOTHESIS -> HYPOTHESIS
- MEDIUM -> MEDIUM
- HIGH -> MEDIUM
- VERIFIED -> MEDIUM (until trusted verification signal contract exists)

This must hold for both primary and secondary single-source paths.

For `condition_difference`, the differing prior assertion is not support for the same conditional claim, so apply the same single-source ceiling.

For a `consistent` multi-source path:
- primary + compatible non-self consistent evidence may reach HIGH;
- secondary remains at most MEDIUM;
- **incoming HYPOTHESIS must not be promoted to HIGH** without an explicit future resolution/verification signal.

Do not add any new confidence enum.

Add tests for:
- primary hypothesis stays hypothesis
- secondary hypothesis stays hypothesis
- condition_difference + hypothesis stays hypothesis
- primary medium single-source stays medium
- high/verified single-source cap to medium
- consistent primary hypothesis does not jump to high
- existing valid primary multi-source MEDIUM/HIGH case can still produce HIGH when all gates are satisfied

## B. Exact tolerance semantics

Refactor `_intervals_compatible(new_interval, existing_interval, config)` (rename args if useful) to follow 03 §5.2 directionality:

1. Return true immediately if raw intervals overlap.
2. If not, expand only the existing/reference interval by tolerance.
3. Relative pad = `relative_tolerance * reference_magnitude`.
4. Reference magnitude should use the actual absolute magnitude of the existing/reference interval.
5. Near zero is handled only by `absolute_tolerance`.
6. Return whether the new interval intersects the expanded reference interval.

Add regression tests at default 5%:
- existing 1.00 vs new 1.04 -> consistent
- existing 1.00 vs new 1.09 -> numeric_conflict
- existing 0.0100 vs new 0.0104 -> consistent
- existing 0.0100 vs new 0.0109 -> numeric_conflict
- overlapping uncertainty intervals -> consistent regardless of tolerance expansion

Do not introduce property-specific tolerances yet; future EDDO/L3 configuration can override the generic config.

## C. Bookkeeping

Correct the Phase 1.1 executor report's per-file test count if touching that report:
- `test_curator.py` has 13 test functions, not 11.
- Total 49 was correct.

This is optional documentation cleanup and must not distract from A/B.

## DeepSeek policy

DeepSeek API remains approved as a temporary future reasoning backend behind a Port/Adapter.

**No DeepSeek/network calls in Phase 1.2.**

## Completion

Run the full test suite.

Create:
`results/phase-01-2-executor-report.md`

Update `status.json`:
- phase = "1.2"
- actor = "executor"
- state = "executor_complete"
- latest_commit = actual implementation SHA

Report whether any new CONTRACT_GAPS were found.

Stop after Phase 1.2.
