# Phase 1.1 Planner Review — knowledge_curator

**Reviewed commit:** `9611bb2e86720bad6c548c2ac30c4cb8c0e36361`  
**Executor-reported tests:** 49 passed / 0 failed  
**Planner verdict:** **MOSTLY PASSED — Phase 1.2 narrow correctness closure required**

## Confirmed fixed

- P1-01: upstream single-source HIGH/VERIFIED is no longer blindly preserved.
- P1-02: secondary + consistent evidence no longer auto-promotes to HIGH.
- P1-03: condition-domain comparison now precedes enum/text relation contradiction.
- P1-04 original sub-unit floor bug was removed.
- Chart completeness validation no longer mutates the input object.
- 01/03 and public confidence enum remain unchanged.
- No DSH/DeepSeek/network dependency was introduced.

## Additional blockers found in review

### P1.2-01 — "at most medium" was implemented as "always medium"

`_cap_single_source()` currently returns `MEDIUM` for every clean single-source primary/secondary assertion.

That can **upgrade** an incoming `hypothesis` to `medium`, which violates the confidence gate.

Required invariant:

- single-source `hypothesis` -> remain `hypothesis`
- single-source `medium` -> remain `medium`
- single-source `high` -> cap to `medium`
- single-source `verified` -> cap to `medium` until a frozen trusted verification signal exists
- secondary obeys the same ceiling and must never be promoted by the cap

More generally, a capping function must never increase confidence.

For multi-source promotion:
- primary + compatible independent consistent support may promote to `high`
- but an input `hypothesis` must not jump directly to `high` without an explicit documented resolution/verification signal
- speculative/missing-evidence gates still take precedence

### P1.2-02 — configured tolerance is effectively applied on both sides

Current `_intervals_compatible()` expands both the new interval and the existing interval. For point values this can make a configured 5% tolerance behave close to a 10% acceptance window.

03 §5.2 states consistency as:
- raw intervals overlap, OR
- the new value/range falls within the existing value domain ± tolerance.

Required implementation semantics:

1. If raw intervals overlap -> consistent.
2. Otherwise expand the **existing/reference interval only** by configured tolerance.
3. Test whether the new interval intersects that expanded reference interval.
4. Relative tolerance scale comes from the existing/reference magnitude; `absolute_tolerance` is the near-zero floor.
5. Do not add domain-specific thresholds.

Regression examples for 5% tolerance:
- existing 1.00, new 1.04 -> consistent
- existing 1.00, new 1.09 -> numeric_conflict
- existing 0.0100, new 0.0104 -> consistent
- existing 0.0100, new 0.0109 -> numeric_conflict
- genuine uncertainty intervals that overlap before tolerance remain consistent

## Report bookkeeping note

The Phase 1.1 executor report lists `test_curator.py = 11 passed`, but the repository contains **13** test functions in that file. The total 49 is consistent with the actual test-function count:

10 + 6 + 13 + 13 + 7 = 49.

This is documentation-only and not a code blocker.

## Exit criteria

Phase 1.2 is deliberately narrow:
- fix P1.2-01 and P1.2-02 only;
- add regression tests;
- all prior tests remain green;
- no §5.4/§6/§7 implementation yet;
- no DeepSeek call yet;
- no public contract changes.

After this passes, Phase 1 core is accepted and Planner will move to §5.4.
