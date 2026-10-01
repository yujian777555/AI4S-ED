# Phase SI-1.5-R1 Plan — DSH Wiring Closure

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Goal

Close the remaining DSH production-bootstrap wiring gaps identified in:

`planner/phase-si-1-5-review.md`

This is a narrow closure pass.

Do not begin SI-2.

Do not modify frozen Knowledge Curator or SI-1 production composition.

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

Reviewed SI-1.5 implementation:

`fd000223b308b209b02f3163e2eee72a6637aab2`

Planner review:

`planner/phase-si-1-5-review.md`

---

## 2. Frozen files/directories

Do not modify:

- `knowledge_curator/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `planner/CONTRACT_GAPS.md`

Do not add orchestration/workflow behavior.

---

## 3. R1-01 — Fix mounted DSH lane provider wiring

Update:

`integration/dsh/lane325_kc_evidence_roundtrip.e2e.ts`

The DSH MCP server launched from the product preset must receive:

```
AI4S_SYSTEM_ADAPTER_FACTORY=
integration.system.fixtures.dsh_provider:create_provider_bundle
```

The mounted DSH path must no longer rely on:

`KC_EVIDENCE_INTEGRATION_FIXTURE=1`

to configure the MCP server.

If `directRef(...)` still needs the old integration fixture for direct-result comparison, it may set `KC_EVIDENCE_INTEGRATION_FIXTURE=1` only inside that separate direct-reference subprocess.

The mounted DSH Agent's MCP child must use the provider factory.

Add assertions/comments making this distinction explicit.

---

## 4. R1-02 — Migrate generated DSH MCP patch

Update:

`integration/dsh/mcp_patch.py`

Generated MCP subprocess args must become:

```python
["-m", "system.mcp_stdio"]
```

Do not generate the old:

`knowledge_curator.mcp_server`

entry point.

Qualification/smoke callers using this generated patch must provide a valid explicit provider environment.

Do not hard-code a deployment production provider into the reusable patch payload.

---

## 5. Qualification/smoke environment

Any integration/qualification runner that starts the system MCP server must explicitly set:

```
AI4S_SYSTEM_ADAPTER_FACTORY=
integration.system.fixtures.dsh_provider:create_provider_bundle
```

when using the integration-only provider.

Do not auto-detect pytest.

Do not add production fallback behavior.

Do not use `KC_EVIDENCE_INTEGRATION_FIXTURE` as the system MCP provider mechanism.

---

## 6. R1-03 — Product DSH documentation

Update:

`dsh/knowledge-curator/README.md`

Document the actual child process:

`python -m system.mcp_stdio`

Document required deployment variables:

- `AI4S_KC_PYTHON`
- `AI4S_KC_WORKSPACE`
- `AI4S_SYSTEM_ADAPTER_FACTORY`

Required explanation:

### AI4S_SYSTEM_ADAPTER_FACTORY

Format:

`package.module:factory_function`

It identifies a deployment-owned dependency factory.

It is not itself a secret.

Adapter-specific credentials remain deployment-owned environment/configuration.

Never commit adapter credentials.

Missing/invalid provider => startup fails closed.

No production fallback to InMemory/Fake or the checked-in integration fixture.

Do not recommend the integration test provider as a production provider.

---

## 7. R1-04 — Real stdio subprocess acceptance

Add a deterministic keyless test that launches the actual process:

```
python -m system.mcp_stdio
```

using official MCP stdio client transport.

Valid-provider subprocess environment:

```
AI4S_SYSTEM_ADAPTER_FACTORY=
integration.system.fixtures.dsh_provider:create_provider_bundle
PYTHONPATH=<repo root>
```

Then initialize an MCP ClientSession and verify:

1. process initializes successfully;
2. exactly four tools are discovered:
   - `curate_assertion_set`
   - `knowledge_curator_health`
   - `retrieve_evidence`
   - `validate_retrieved_claims`
3. health reports the injected integration-test provider through existing metadata;
4. one `curate_assertion_set` call succeeds.

No DeepSeek credential is required.

### Negative subprocess case

Launch the same:

`python -m system.mcp_stdio`

without `AI4S_SYSTEM_ADAPTER_FACTORY`.

Prove startup exits/fails closed.

Do not accept silent empty tool discovery as a pass.

---

## 8. DSH path assertion

Add/update keyless DSH contract tests proving:

- product preset points to `system.mcp_stdio`;
- generated `mcp_patch.py` points to `system.mcp_stdio`;
- mounted lane sets `AI4S_SYSTEM_ADAPTER_FACTORY`;
- mounted lane does not set `KC_EVIDENCE_INTEGRATION_FIXTURE` for the MCP child composition path;
- product README documents the provider contract.

---

## 9. Evidence qualification semantics

The integration-only DSH provider may include its deterministic protocol-compatible EvidenceRetrievalService.

That provider is allowed only because tests select it explicitly.

Do not change `integration/system/fixtures/dsh_provider.py` into production code.

Do not import it from `system/**`.

---

## 10. No workflow changes

Do not create or implement:

- Agent Factory;
- Orchestrator;
- CurationWorkflow;
- RevisionWorkflow;
- QAEvidenceWorkflow;
- DocumentCommit workflow;
- lifecycle workflow.

Do not add curation-to-commit behavior.

---

## 11. Tests

Run at minimum:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Acceptance baselines:

### knowledge_curator

`522 passed / 0 skipped / 0 failed`

### integration/system

At least:

`52 passed / 0 skipped / 0 failed`

### integration/dsh

At least:

`90 passed / 0 skipped / 0 failed`

New tests are additive.

Mandatory SI-1.5-R1 tests:

**0 skipped**

No external network required.

If the TypeScript mounted lane cannot be run keylessly because actual DSH source/runtime is unavailable, the real stdio subprocess acceptance above is mandatory and must pass. Report the mounted-live lane environment limitation explicitly rather than claiming it ran.

---

## 12. Freeze verification

Before completion compare final tree against SI-1.5-R1 handoff.

Explicitly verify no changes under:

- `knowledge_curator/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `planner/CONTRACT_GAPS.md`

Expected: no changes.

Allowed implementation scope:

- `dsh/knowledge-curator/README.md`;
- `integration/dsh/**`;
- `integration/system/tests/**` only if needed;
- report/status bookkeeping.

---

## 13. Required report

Update/create:

`results/phase-si-1-5-executor-report.md`

Add R1 section:

```
Phase SI-1.5-R1 implementation CODE SHA:

product preset uses system.mcp_stdio:
PASS / FAILED

generated DSH mcp_patch uses system.mcp_stdio:
PASS / FAILED

mounted DSH lane supplies AI4S_SYSTEM_ADAPTER_FACTORY:
PASS / FAILED

mounted DSH MCP composition no longer relies on KC_EVIDENCE_INTEGRATION_FIXTURE:
PASS / FAILED

product README documents AI4S_SYSTEM_ADAPTER_FACTORY:
PASS / FAILED

real stdio subprocess valid-provider startup:
PASS / FAILED

real stdio subprocess exact four-tool discovery:
PASS / FAILED

real stdio subprocess health provider identity:
PASS / FAILED

real stdio subprocess curation round-trip:
PASS / FAILED

real stdio subprocess missing-provider fail-closed:
PASS / FAILED

actual mounted DSH live lane executed:
PASS / NOT_RUN_ENV / FAILED

knowledge_curator frozen tree changed:
NO

SI-1 frozen production composition changed:
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

Do not mark actual mounted DSH live lane PASS unless it was actually executed.

---

## 14. status.json

At completion set:

- module = `system_integration`
- phase = `SI-1.5-R1`
- actor = `executor`
- state = `executor_complete`
- result_expected = `results/phase-si-1-5-executor-report.md`
- latest_commit = actual R1 implementation CODE SHA

Preserve freezes:

### Knowledge Curator

`42e39121af5f6120174e088a521c9ad014abdcda`

### SI-1

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

---

## 15. Completion

Push implementation/tests/report/status to `main`.

Then STOP.

Do not begin SI-2.

Planner performs final SI-1.5 acceptance review after R1.
