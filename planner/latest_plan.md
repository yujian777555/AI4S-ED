# Phase 1.1 Plan — confidence & conflict correctness fixes

**Planner:** ChatGPT  
**Executor:** MiMo  
**State:** READY_FOR_EXECUTOR  
**Base implementation:** `5cfafc39637138c836a6c4590f9b05c6aa4b4275`

Read:
1. `docs/01-总体架构与数据流设计.md`
2. `docs/03-文献自动调研与知识入库流水线.md`
3. `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`
4. `planner/phase-01-review.md`
5. `planner/CONTRACT_GAPS.md`
6. `status.json`

## Goal

Fix the four Planner-blocking correctness issues only. Do not implement §6/§7. Do not add real DeepSeek API calls in this round.

## A. Confidence gate

Required current semantics:

- missing unit / missing locator / speculative wording -> `hypothesis`
- unresolved numeric/relation conflict -> `hypothesis` + `pending_review`
- mechanism violation -> `hypothesis` + reject/manual path
- clean single-source primary literature assertion -> at most `medium`
- secondary source -> at most `medium`
- condition_difference does not create support for the same conditional claim
- `high` requires compatible multi-source evidence plus primary/no-conflict conditions
- do not auto-grant `verified`; current Phase 1 compatibility model has no frozen trusted human/experimental verification signal

Add tests:
- single primary upstream high -> medium
- single primary upstream verified -> not verified/high
- secondary + consistent existing -> not high
- primary + compatible independent existing evidence -> high

If source-family independence is unavailable, use the existing non-self ref_id rule and record the limitation; do not invent a global source-family schema.

## B. Conditions before relation contradiction

Apply operating-condition compatibility before relation/enum/text contradiction classification.

Regression tests:
- same subject/property, ENUM yes under condition A, ENUM no under condition B -> `condition_difference`
- same conditions + opposite enum/bool -> `relation_conflict`

## C. Relative tolerance

Remove the implicit 1.0 scale floor from relative tolerance expansion.

Use actual value/interval magnitude for relative tolerance and `absolute_tolerance` as the near-zero floor.

Add sub-unit tests:
- close values inside configured relative tolerance -> consistent
- materially different values -> numeric_conflict

No domain-specific threshold belongs here.

## D. Validation side effects

If possible without contract changes, make chart completeness checking non-mutating.

Add a regression test showing input ChartObjectInfo remains unchanged after validation.

## DeepSeek temporary backend policy

DeepSeek API may be used in later phases for LLM reasoning.

This round:
- no network calls
- no DeepSeek dependency
- no API key/endpoint in source
- deterministic core stays runtime-independent

Future reasoning must be accessed through a Port/Adapter so DSH can replace it.

## Completion

Run full existing suite + new tests.

Write:
`results/phase-01-1-executor-report.md`

Update `status.json`:
- phase = "1.1"
- actor = "executor"
- state = "executor_complete"
- latest_commit = actual implementation SHA

Stop after Phase 1.1.
