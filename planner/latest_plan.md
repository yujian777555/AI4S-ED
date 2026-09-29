# Phase 4.3.2 Plan — Strict Mounted-DSH Live Evidence Acceptance

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Scope

Fix ONLY the mounted-DSH live validation harness and obtain trustworthy evidence.

Do not change:
- EvidenceRetrievalService business semantics;
- guard semantics;
- Phase 4.1/4.2 retrieval;
- MCP business tools except if a live test exposes a real bug;
- Agent identity/preset id;
- public contracts.

Do not start §7.

## 1. Make lane325 fail on live failure

When live credentials/model/runtime prerequisites are available:
- retrieve_evidence must produce >=1 exact matching tool/call;
- a linked tool/result must exist;
- structured result parsing must succeed.

If any of those fail:
- dump diagnostic event types/text safely;
- FAIL the Vitest test.

Do not return successfully after LANE325_LIVE_NO_TOOLCALL.

When credentials/model route are absent before the run:
- discovery-only may be reported separately as NOT_RUN_ENV for live.

## 2. Separate success markers

Emit distinct markers only after assertions pass:

- LANE325_DISCOVERY_OK=1
- LANE325_RETRIEVE_TOOLCALL_OK=1
- LANE325_RETRIEVE_RESULT_OK=1
- LANE325_RETRIEVE_IDENTITY_MATCH=1
- LANE325_VALIDATE_TOOLCALL_OK=1
- LANE325_VALIDATE_RESULT_OK=1
- LANE325_VALIDATE_POLICY_MATCH=1
- LANE325_LIVE_COMPLETE=1

Do not use one generic marker to infer multiple statuses.

## 3. Compute direct reference for retrieve_evidence

Inside lane325, compute a direct deterministic reference result for the SAME integration fixture query.

Recommended:
- invoke Python via execFileSync using the same KC integration fixture runtime/service factory;
- call EvidenceRetrievalService.retrieve(EvidenceRequest(...));
- serialize the same stable identities used by the MCP tool.

Compare direct vs mounted-DSH tool result:
- evidence chunk_id sequence (or clearly defined stable identity set if ordering is not contractually required);
- bundle/query coverage key identities;
- Abstain boolean/reasons;
- integration_fixture flag.

Do not compare prose.

Emit LANE325_RETRIEVE_IDENTITY_MATCH=1 only after actual equality assertions.

## 4. Compute direct reference for validate_retrieved_claims

For the same query and claim payload:
- compute direct fresh retrieval;
- run ClaimGuardService on the same proposed claims;
- compare to mounted DSH tool result.

At minimum compare:
- C1 policy;
- C1 Abstain;
- C2 unresolved anchor ids;
- C2 policy;
- C2 Abstain;
- C2 H1 finding presence/type.

Emit LANE325_VALIDATE_POLICY_MATCH=1 only after equality assertions.

## 5. Strict result linking

For both tools:
- identify exact tool/call events by tool name;
- link tool/result by sourceEventSeq/callId as lane324 already does;
- require at least one linked result;
- parse structured result;
- never infer result success from keyword presence.

## 6. Add a control baseline probe

In the same runner window, run or invoke the already accepted lane324 curate_assertion_set live baseline, or an equivalent mounted knowledge-curator control turn.

Purpose: distinguish external DeepSeek/runtime failure from evidence-tool regression.

Record:
- baseline_live_status;
- evidence_live_status.

Classification:

### A. baseline PASS + evidence PASS
Full Phase 4.3.2 PASS.

### B. baseline PASS + evidence FAIL
FAILED — evidence integration regression.

### C. baseline EMPTY_RESPONSE/zero-tool + evidence EMPTY_RESPONSE/zero-tool
EXTERNAL_RUNTIME_UNAVAILABLE for the validation attempt.
Do not modify core code merely to chase it.
Do not call the evidence lane PASS.

### D. baseline FAIL for another deterministic reason
FAILED / investigate baseline environment.

Use exact markers/log evidence, not intuition.

## 7. Runner status mapping must be strict

Update run_lane325.py so statuses are derived independently:

mounted_dsh_tool_discovery:
- PASS only from discovery marker/assertion.

mounted_dsh_retrieve_evidence_live:
- PASS only if retrieve toolcall + linked result markers pass.
- NOT_RUN_ENV only if prerequisite absent before execution or control/evidence both hit confirmed external EMPTY_RESPONSE classification.
- FAILED otherwise.

mounted_dsh_validate_retrieved_claims_live:
- PASS only if validate toolcall + linked result markers pass.
- same NOT_RUN_ENV/FAILED rules.

direct_vs_dsh_evidence_identity_match:
- PASS only from actual identity comparison marker.
- never inferred from retrieve tool call alone.

direct_vs_dsh_policy_match:
- PASS only from actual policy comparison marker.
- never inferred from retrieve success.

## 8. Do not treat Vitest green as live PASS by itself

The runner must require semantic markers.
A test process return code 0 without live markers is NOT live PASS.

Conversely, if the test is intentionally discovery-only because no credential exists, report:
- discovery PASS;
- live NOT_RUN_ENV.

## 9. Optional retry policy

Because EMPTY_RESPONSE has been observed:
- at most 3 live attempts for a turn is acceptable;
- retries must create a fresh turn or fresh Agent session as needed;
- record attempt count and event-type summary;
- do not hide failed attempts.

No infinite retry loop.

## 10. Preserve secret hygiene

Never print:
- API key;
- credential file content;
- authorization headers.

Keep current redaction behavior.

## 11. Tests

Maintain:
- knowledge_curator >= 311 passed / 0 failed;
- integration/dsh >= 83 passed / 0 failed.

Add keyless tests for runner classification/marker parsing if practical, covering:
- generic retrieve marker cannot imply validate PASS;
- missing identity marker => identity NOT PASS;
- zero toolcall with live prerequisites => failed attempt;
- no credential => NOT_RUN_ENV;
- baseline+evidence simultaneous EMPTY_RESPONSE => external runtime unavailable classification.

## 12. Live acceptance artifact

Create/update:
- results/phase-04-3-2-executor-report.md
- results/phase-04-3-2-dsh-evidence-smoke.json

The smoke JSON must include:
- baseline control status;
- discovery status;
- retrieve toolcall/result status;
- retrieve identity-match status;
- validate toolcall/result status;
- validate policy-match status;
- live attempt count;
- external-runtime-unavailable classification if applicable;
- no secrets.

## 13. Final acceptance rules

Phase 4.3.2 PASS requires:
- mounted discovery PASS;
- retrieve live PASS;
- validate live PASS;
- direct-vs-DSH evidence identity PASS;
- direct-vs-DSH policy PASS.

If both baseline and evidence lanes are externally EMPTY_RESPONSE after bounded retries:
- report LIVE_VALIDATION_BLOCKED_EXTERNAL;
- do not alter accepted §6 core code;
- Planner will decide whether to freeze code with an external validation note.

## 14. Completion

Update status.json:
- phase = 4.3.2
- actor = executor
- state = executor_complete
- latest_commit = actual CODE/harness implementation SHA
- result_expected = results/phase-04-3-2-executor-report.md

Push main and STOP.
Do not start §7.
