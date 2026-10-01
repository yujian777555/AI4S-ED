# Phase SI-1.5 Plan — DSH Production Bootstrap Wiring

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Goal

Wire the accepted SI-1 production runtime composition into the existing DSH `knowledge-curator` preset.

This phase changes **only the DSH launch path and its integration verification**.

Current path:

```
DSH knowledge-curator preset
  -> python -m knowledge_curator.mcp_server
  -> integration/default runtime
```

Target path:

```
DSH knowledge-curator preset
  -> python -m system.mcp_stdio
  -> AI4S_SYSTEM_ADAPTER_FACTORY
  -> production provider bundle
  -> system.composition
  -> CuratorRuntime / EvidenceRuntime
  -> existing create_mcp_server(...)
  -> existing four MCP tools
```

Do not implement SI-2.

Do not add an orchestrator.

Do not wire curation to commit.

---

## 1. Frozen baselines

Knowledge Curator final implementation:

`42e39121af5f6120174e088a521c9ad014abdcda`

Status:

**ACCEPTED / FROZEN / DELIVERABLE**

SI-1 production composition implementation:

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

Status:

**ACCEPTED / FROZEN**

SI-1 final Planner acceptance:

`planner/phase-si-1-final-acceptance.md`

No Phase 5.4 is authorized.

---

## 2. Scope

SI-1.5 is **DSH production bootstrap wiring only**.

Allowed work:

- change the DSH knowledge-curator MCP subprocess entry point;
- pass production provider configuration through environment;
- add/update DSH integration tests;
- add deterministic test provider fixtures under integration-only paths;
- verify exact four-tool discovery through the DSH/MCP path;
- verify startup fails when production provider configuration is absent/invalid;
- document deployment environment variables.

Do not implement new scientific behavior.

---

## 3. Required DSH preset change

Modify:

`dsh/knowledge-curator/cordis.patch.yml`

Current:

```yaml
args:
  - -m
  - knowledge_curator.mcp_server
```

Target:

```yaml
args:
  - -m
  - system.mcp_stdio
```

Keep:

- stdio transport;
- `AI4S_KC_PYTHON`;
- `AI4S_KC_WORKSPACE`;
- `failOnStartupError: true`;
- current timeout unless a demonstrated test requirement exists.

Do not hard-code a provider module into the production preset.

The production provider remains configured via:

`AI4S_SYSTEM_ADAPTER_FACTORY=package.module:factory_function`

Do not add secrets to the YAML.

---

## 4. Production startup semantics

When DSH launches the preset:

### provider configured and valid

Startup proceeds through:

`system.mcp_stdio -> provider_loader -> composition -> create_mcp_server`

### provider missing

Startup MUST fail.

Because the DSH preset has:

`failOnStartupError: true`

the Agent/MCP mount must not silently become an integration runtime.

### provider invalid

Startup MUST fail.

### evidence omitted by valid provider

This is allowed.

The MCP server starts with:

- production curator adapters;
- evidence tools present;
- evidence retrieval explicitly unavailable/fail-closed.

Do not fall back to the integration fixture.

---

## 5. Integration-only DSH provider fixture

DSH CI/smoke tests need a valid deterministic provider without relying on real production infrastructure.

Add an **integration-only external provider fixture** under a clearly test-only path, for example:

`integration/system/fixtures/dsh_provider.py`

or equivalent.

It must:

- satisfy the frozen curator Ports;
- use test-local stub classes, not Knowledge Curator InMemory/Fake adapters;
- optionally expose a deterministic EvidenceRetrievalService built from test-local protocol-compatible backends;
- never be selected by production preset automatically;
- only be selected when test environment explicitly sets `AI4S_SYSTEM_ADAPTER_FACTORY`.

Do not put this fixture under `system/` production code.

---

## 6. DSH integration test environment

Any DSH test that actually launches the `knowledge-curator` preset must explicitly provide a valid integration-only provider factory.

Example intent:

```
AI4S_SYSTEM_ADAPTER_FACTORY=
integration.system.fixtures.dsh_provider:create_provider_bundle
```

Do not modify production code to detect pytest or DSH test mode.

Do not introduce a hidden fallback when the variable is absent.

---

## 7. Mandatory end-to-end DSH/MCP verification

Add/modify tests to prove the actual DSH-configured subprocess path uses:

`python -m system.mcp_stdio`

and not:

`python -m knowledge_curator.mcp_server`

At minimum verify:

1. preset command/args point to `system.mcp_stdio`;
2. no provider => subprocess startup fails closed;
3. invalid provider => startup fails closed;
4. valid integration-only provider => subprocess initializes successfully;
5. MCP tool discovery returns exactly:
   - `curate_assertion_set`
   - `knowledge_curator_health`
   - `retrieve_evidence`
   - `validate_retrieved_claims`
6. health reports a production-style adapter note/provider identity from the injected provider;
7. curation tool completes one deterministic round-trip through the new system bootstrap;
8. if test provider includes evidence retrieval, one evidence retrieval round-trip succeeds;
9. if provider omits evidence retrieval, evidence tool returns explicit `retrieval_unavailable`;
10. no fixture is auto-enabled by `KC_EVIDENCE_INTEGRATION_FIXTURE`.

No external network call is required.

---

## 8. Preserve MCP public contract

Do not change:

- tool names;
- input schemas;
- output schemas;
- health response schema;
- CurationReport semantics;
- EvidenceBundle semantics;
- claim-guard semantics.

The DSH Agent should see the same four tools as before.

Only the runtime underneath changes from integration/default composition to production composition.

---

## 9. Frozen files/directories

Do not modify:

- `knowledge_curator/core/**`
- `knowledge_curator/schemas/**`
- `knowledge_curator/ports/**`
- `knowledge_curator/retrieval/**`
- `knowledge_curator/mcp_server/app.py`
- `knowledge_curator/mcp_server/runtime.py`
- `knowledge_curator/mcp_server/evidence_runtime.py`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `planner/CONTRACT_GAPS.md`

SI-1 and Knowledge Curator remain frozen.

If a real defect is found in these files, STOP and report it instead of fixing it inside SI-1.5.

---

## 10. No orchestrator / no commit workflow

SI-1.5 must not add:

- Agent Factory;
- system Orchestrator;
- CurationWorkflow;
- RevisionWorkflow;
- QAEvidenceWorkflow;
- commit workflow;
- lifecycle workflow.

Do not call from new SI-1.5 code:

- `DocumentCommitCoordinator`
- `RevisionPublicationCoordinator`
- `LifecycleRevisionCoordinator`.

The purpose of SI-1.5 is only:

**DSH -> production MCP bootstrap**

not:

**DSH -> whole application workflow**.

---

## 11. Documentation

Update the relevant DSH integration README/documentation so operators know:

Required production variables:

```
AI4S_KC_PYTHON
AI4S_KC_WORKSPACE
AI4S_SYSTEM_ADAPTER_FACTORY
```

Clarify:

- `AI4S_SYSTEM_ADAPTER_FACTORY` identifies a deployment-owned production dependency factory;
- it is not a secret;
- secrets needed by adapters remain deployment-specific environment/configuration and must not be committed;
- missing provider causes fail-closed startup;
- no default integration fixture is used in production.

Do not document the integration test provider as a production recommendation.

---

## 12. Tests

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

Existing accepted baseline:

`38 passed / 0 skipped / 0 failed`

All must remain green.

### integration/dsh

Existing accepted baseline:

`90 passed / 0 failed`

New SI-1.5 tests are additive.

Mandatory SI-1.5 tests must have **0 skipped**.

No network requirement.

---

## 13. Freeze verification

Before completion, compare against the SI-1 accepted tree and verify no changes under:

- frozen Knowledge Curator paths listed above;
- frozen SI-1 `system/*.py` production composition/bootstrap files;
- `planner/CONTRACT_GAPS.md`.

The intended code/config changes should be limited to:

- `dsh/knowledge-curator/cordis.patch.yml`;
- `integration/dsh/**`;
- optionally integration-only fixture under `integration/system/**`;
- integration documentation;
- executor report/status bookkeeping.

---

## 14. Required report

Create:

`results/phase-si-1-5-executor-report.md`

Report exactly:

```
Phase SI-1.5 implementation CODE SHA:

DSH preset uses system.mcp_stdio:
PASS / FAILED

AI4S_SYSTEM_ADAPTER_FACTORY required:
PASS / FAILED

missing provider DSH startup fail-closed:
PASS / FAILED

invalid provider DSH startup fail-closed:
PASS / FAILED

valid integration-only provider DSH startup:
PASS / FAILED

system bootstrap exact four-tool discovery via DSH path:
PASS / FAILED

health production adapter identity via DSH path:
PASS / FAILED

curation round-trip via DSH/system bootstrap:
PASS / FAILED

evidence configured round-trip via DSH/system bootstrap:
PASS / FAILED / NOT CONFIGURED IN TEST PROVIDER

evidence omitted remains retrieval_unavailable:
PASS / FAILED

KC_EVIDENCE_INTEGRATION_FIXTURE cannot bypass production composition:
PASS / FAILED

public MCP contract changed:
NO

orchestrator/workflow added:
NO

curation-to-commit wiring added:
NO

knowledge_curator frozen tree changed:
NO

SI-1 frozen system composition changed:
NO

CONTRACT_GAPS changed:
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

## 15. status.json

At completion set:

- module = `system_integration`
- phase = `SI-1.5`
- actor = `executor`
- state = `executor_complete`
- current_plan = `planner/latest_plan.md`
- result_expected = `results/phase-si-1-5-executor-report.md`
- latest_commit = actual SI-1.5 CODE SHA

Preserve both freezes:

### Knowledge Curator

`42e39121af5f6120174e088a521c9ad014abdcda`

### SI-1

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

---

## 16. Completion rule

Push implementation, integration tests, report, and status to `main`.

Then STOP.

Do not begin SI-2.

Planner will review the DSH production bootstrap wiring before authorizing any orchestrator/workflow work.
