# Phase SI-1.5-R2 Plan — Qualification Path Closure

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Goal

Close the remaining qualification-path mismatches identified in:

`planner/phase-si-1-5-r2-review.md`

This is a narrow DSH/integration closure pass.

Do not begin SI-2.

Do not modify frozen production code.

---

## 1. Frozen baselines

Knowledge Curator:

`42e39121af5f6120174e088a521c9ad014abdcda`

Status:

**ACCEPTED / FROZEN / DELIVERABLE**

SI-1 production composition:

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

Status:

**ACCEPTED / FROZEN**

Reviewed SI-1.5-R1 CODE SHA:

`c2f2cb24580689b82551bb8f3971d1e75d07da3e`

Current Planner review:

`planner/phase-si-1-5-r2-review.md`

---

## 2. Frozen files/directories

Do not modify:

- `knowledge_curator/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `planner/CONTRACT_GAPS.md`
- `dsh/knowledge-curator/cordis.patch.yml`

The product preset itself is already correct and should remain unchanged.

---

## 3. R2-01 — Fix lane325 integration_fixture semantics

Update:

`integration/dsh/lane325_kc_evidence_roundtrip.e2e.ts`

Current comparison incorrectly requires:

`direct.integration_fixture == mounted_dsh.integration_fixture`

After SI-1.5 this is no longer valid.

Expected:

- direct reference path: `integration_fixture == true`
- mounted DSH production-composition path: `integration_fixture == false`

Change the live identity assertion to:

1. compare evidence identities/coverage/Abstain semantics that should match;
2. separately assert direct fixture marker is true;
3. separately assert mounted DSH/provider marker is false.

Do not weaken evidence identity comparison beyond removing the now-invalid equality of the fixture marker.

---

## 4. R2-02 — Make integration-only provider evidence match the reference corpus

Update:

`integration/system/fixtures/dsh_provider.py`

The integration-only provider must continue to use **test-local adapter classes**.

Do not import, instantiate, wrap, or delegate to:

- `InMemoryVectorSearch`
- `InMemoryKeywordSearch`
- `FakeReranker`

or other known forbidden Knowledge Curator integration adapters.

Instead:

1. load the checked-in deterministic evidence fixture chunks from the existing frozen fixture-data builder;
2. implement test-local protocol-compatible vector/keyword adapters over those chunks;
3. implement a test-local deterministic reranker;
4. preserve the same relevant filtering/rank behavior required for direct-reference parity;
5. construct an ordinary `EvidenceRetrievalService` from those test-local components.

This fixture remains under `integration/**` only.

It must never be imported by `system/**` production code.

---

## 5. Keyless evidence parity regression

Add a deterministic keyless test proving the direct reference corpus and the integration provider's production-style evidence runtime remain semantically aligned.

Use the same lane325 query/request.

Verify at minimum:

- same evidence chunk-id sequence/set as appropriate to the frozen retrieval contract;
- same coverage keys;
- same coverage states;
- same query-level Abstain result/reasons;
- same relevant claim-guard policy for the lane325 C1/C2 claims.

Also verify explicitly:

- direct reference request/bundle is integration fixture = true;
- production-style provider runtime/bundle is integration fixture = false.

The difference in the fixture marker is expected and must not cause identity failure.

---

## 6. R2-03 — Fix run_lane325 environment

Update:

`integration/dsh/run_lane325.py`

Set in the qualification environment:

```
AI4S_SYSTEM_ADAPTER_FACTORY=
integration.system.fixtures.dsh_provider:create_provider_bundle
```

This environment is shared by the mounted lane324 baseline and lane325 evidence lane.

Remove the runner-global:

`KC_EVIDENCE_INTEGRATION_FIXTURE=1`

The direct-reference helper already owns its own explicit old-fixture behavior and may keep it locally.

Do not rely on the parent qualification runner's fixture flag for MCP composition.

---

## 7. R2-04 — lane324 baseline provider compatibility

The lane324 baseline mounts the same product preset.

Do not hard-code a provider into production product config.

It is acceptable for lane324 to inherit the provider from `run_lane325.py`.

Add/update a keyless structural regression proving:

- the qualification runner sets `AI4S_SYSTEM_ADAPTER_FACTORY`;
- lane324 is launched under that environment;
- the runner no longer depends on `KC_EVIDENCE_INTEGRATION_FIXTURE` to start the MCP child.

---

## 8. R2-05 — Fix integration/dsh/mcp_smoke provider environment

Update:

`integration/dsh/mcp_smoke.py`

This is integration/qualification code.

When the caller already supplies:

`AI4S_SYSTEM_ADAPTER_FACTORY`

preserve it.

When the caller does not supply one, the integration smoke must explicitly use:

`integration.system.fixtures.dsh_provider:create_provider_bundle`

for the duration of the smoke run.

Do not change production system code.

Do not use `KC_EVIDENCE_INTEGRATION_FIXTURE` as the provider mechanism.

Do not overwrite a caller-supplied real provider.

Add a test proving both:

- caller-supplied provider is preserved;
- absent provider resolves to the integration-only provider for the qualification smoke.

---

## 9. R2-06 — Update generated patch template documentation

Update:

`integration/dsh/patches/knowledge-curator-mcp.patch.yml`

Its logical-shape comment must show:

```
args: ['-m', 'system.mcp_stdio']
```

Add a comment that:

- provider configuration is supplied by the qualification/deployment environment;
- the patch does not hard-code a provider.

---

## 10. Existing real stdio acceptance must remain green

Preserve the real keyless subprocess tests added in R1.

They must continue to prove:

- valid explicit provider starts;
- exact four tools;
- health identity;
- curation round-trip;
- missing-provider fail-closed;
- evidence omitted remains unavailable;
- `KC_EVIDENCE_INTEGRATION_FIXTURE` cannot bypass production composition.

---

## 11. Mounted live lane status

If no DeepSeek credential/runtime is available:

`actual mounted DSH live lane executed = NOT_RUN_ENV`

is acceptable **only if**:

- all keyless structural/bootstrap checks pass;
- parity tests prove no known deterministic evidence mismatch remains;
- lane324/lane325 runner provider wiring is correct.

Do not report the live lane as PASS unless it actually ran.

---

## 12. No workflow changes

Do not add:

- Agent Factory;
- Orchestrator;
- CurationWorkflow;
- RevisionWorkflow;
- QAEvidenceWorkflow;
- commit/lifecycle wiring.

Do not begin SI-2.

---

## 13. Tests

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Acceptance minimums:

### knowledge_curator

`522 passed / 0 skipped / 0 failed`

### integration/system

At least current baseline:

`58 passed / 0 skipped / 0 failed`

plus new R2 tests.

### integration/dsh

At least current baseline:

`90 passed / 0 skipped / 0 failed`

plus new R2 tests.

Mandatory SI-1.5-R2 tests:

**0 skipped**

No external network required.

---

## 14. Freeze verification

Before completion verify no changes under:

- `knowledge_curator/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `planner/CONTRACT_GAPS.md`
- `dsh/knowledge-curator/cordis.patch.yml`

Expected: **NO CHANGES**.

Allowed implementation changes are limited to:

- `integration/dsh/**`;
- `integration/system/fixtures/**`;
- `integration/system/tests/**`;
- SI-1.5 report/status bookkeeping.

---

## 15. Required report

Update:

`results/phase-si-1-5-executor-report.md`

Add an R2 section:

```
Phase SI-1.5-R2 implementation CODE SHA:

direct reference integration_fixture=true asserted:
PASS / FAILED

mounted/provider integration_fixture=false asserted:
PASS / FAILED

integration provider fixture-corpus parity:
PASS / FAILED

evidence chunk identity parity:
PASS / FAILED

coverage/Abstain parity:
PASS / FAILED

claim-guard policy parity:
PASS / FAILED

integration provider uses forbidden InMemory/Fake adapters:
NO

run_lane325 supplies AI4S_SYSTEM_ADAPTER_FACTORY:
PASS / FAILED

run_lane325 globally sets KC_EVIDENCE_INTEGRATION_FIXTURE:
NO

lane324 baseline receives provider contract:
PASS / FAILED

mcp_smoke preserves caller-supplied provider:
PASS / FAILED

mcp_smoke supplies integration provider when absent:
PASS / FAILED

patch template documents system.mcp_stdio:
PASS / FAILED

real stdio subprocess acceptance remains green:
PASS / FAILED

actual mounted DSH live lane executed:
PASS / NOT_RUN_ENV / FAILED

known deterministic mounted-live mismatch remains:
NO / YES

knowledge_curator frozen tree changed:
NO

SI-1 frozen production composition changed:
NO

product preset changed during R2:
NO

CONTRACT_GAPS changed:
NO

orchestrator/workflow added:
NO

curation-to-commit wiring added:
NO

knowledge_curator tests:
X passed / Y skipped / Z failed

integration/system tests:
X passed / Y skipped / Z failed

integration/dsh tests:
X passed / Y skipped / Z failed

origin/main SHA:

deviations:
NONE / describe
```

---

## 16. status.json

At completion set:

- module = `system_integration`
- phase = `SI-1.5-R2`
- actor = `executor`
- state = `executor_complete`
- result_expected = `results/phase-si-1-5-executor-report.md`
- latest_commit = actual R2 implementation CODE SHA

Preserve freezes:

### Knowledge Curator

`42e39121af5f6120174e088a521c9ad014abdcda`

### SI-1

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

---

## 17. Completion

Push implementation/tests/report/status to `main`.

Then STOP.

Do not begin SI-2.

Planner performs the final SI-1.5 acceptance review after R2.
