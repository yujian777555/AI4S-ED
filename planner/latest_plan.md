# Phase 4.0.2 Plan — Separate H1 Violations from Locator Validation Status

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Scope
This is the final closure round for the deterministic §6 evidence guard foundation.

Do not add retrieval engines, FAISS, BM25, RRF, reranker, §6 MCP tools, or §7.

## 1. Introduce explicit H1 check result
Create an internal result model, recommended:

H1CheckResult:
- findings: list[HallucinationFinding]
- locator_checks: list[LocatorCheck]
- fully_checked: bool

LocatorCheck:
- ref_id
- locator
- status: VERIFIED_PRESENT / VERIFIED_ABSENT / NOT_CHECKED

These are internal temporary compatibility models.

## 2. Add detect_h1_with_status
Implement:
detect_h1_with_status(claim, metadata) -> H1CheckResult

Rules:
- no anchors => actual H1 finding;
- empty ref_id => actual H1 finding;
- unknown ref_id => actual H1 finding;
- empty locator => actual H1 finding;
- anchor_exists == False => actual H1 finding + VERIFIED_ABSENT;
- anchor_exists == True => no H1 finding + VERIFIED_PRESENT;
- anchor_exists == None => NO H1 finding + NOT_CHECKED.

fully_checked must be false if any required locator validation is NOT_CHECKED.

Do not convert NOT_CHECKED into a hallucination finding.

## 3. Preserve detect_h1 compatibility
Keep detect_h1(claim, metadata) returning list[HallucinationFinding].

Implement it as a thin compatibility wrapper:
return detect_h1_with_status(...).findings

This avoids unnecessary caller churn.

## 4. Metric safety
Add tests proving:
- H1 metric/count based on findings does not increase when locator validation is unavailable;
- fabricated locator still produces one H1 finding;
- missing ref can still produce H1 independently of locator status.

No global metrics engine is needed; just prove the detector output semantics.

## 5. Preserve H2
Do not change accepted H2 DOI/title behavior unless required by type imports.

## 6. Tests
Keep current baselines:
- integration/dsh: 70 passed / 0 failed;
- knowledge_curator: 166 passed / 0 failed.

Add deterministic tests for:
- valid locator -> VERIFIED_PRESENT, no finding;
- fabricated locator -> VERIFIED_ABSENT + H1 finding;
- unavailable locator -> NOT_CHECKED + no H1 finding;
- mixed anchors -> fully_checked false when one locator is unavailable;
- detect_h1 compatibility wrapper returns only actual findings;
- H1+H2 missing-reference dual finding remains possible.

## 7. Report
Create results/phase-04-0-2-executor-report.md.

Report:
- H1 result model;
- NOT_CHECKED semantics;
- compatibility wrapper;
- exact test counts;
- public contracts changed? NO;
- CONTRACT_GAPS changes;
- implementation SHA.

## 8. status.json
On completion:
- phase = 4.0.2
- actor = executor
- state = executor_complete
- latest_commit = actual implementation SHA
- result_expected = results/phase-04-0-2-executor-report.md

Push main and stop.
Do not begin Phase 4.1.