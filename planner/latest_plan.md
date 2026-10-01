# Phase SI-1 Plan — Production Runtime Composition

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Goal

Create the **system-level production runtime composition boundary** for AI4S-ED without reopening the frozen `knowledge_curator` implementation.

SI-1 must make it possible for a deployment to provide real implementations of the existing Knowledge Curator ports and to construct an MCP server from those dependencies through the already-existing runtime injection points.

This phase is **composition/bootstrap only**.

Do not implement workflow orchestration yet.

---

## 1. Frozen baseline

Knowledge Curator remains:

- ACCEPTED
- FROZEN
- DELIVERABLE

Frozen implementation CODE SHA:

`42e39121af5f6120174e088a521c9ad014abdcda`

System integration audit:

`planner/system-integration-audit.md`

Planner audit review:

`planner/system-integration-audit-review.md`

No Phase 5.4 is authorized.

---

## 2. Files/directories that MUST remain semantically frozen

Do not modify:

- `knowledge_curator/core/**`
- `knowledge_curator/schemas/**`
- `knowledge_curator/ports/**`
- `knowledge_curator/retrieval/**`
- `knowledge_curator/mcp_server/app.py`
- `planner/CONTRACT_GAPS.md`

Do not change public MCP tool names, input schemas, output schemas, or business behavior.

If a confirmed bug is discovered in a frozen file, STOP and report it to Planner with reproduction. Do not fix it inside SI-1.

---

## 3. SI-1 architecture

Use the existing MCP application injection point:

`create_mcp_server(runtime=..., evidence_runtime=...)`

Target shape:

```
deployment / external provider package
            |
            v
     AI4S-ED system bootstrap
            |
            +--> Curator dependencies
            |      - KnowledgeRepository
            |      - OntologyService
            |      - MechanismValidator
            |
            +--> Evidence dependencies
                   - EvidenceRetrievalService
                   - optional MechanismValidator
            |
            v
     CuratorRuntime / EvidenceRuntime
            |
            v
       create_mcp_server(...)
            |
            v
          stdio MCP
```

Do not put composition policy into Knowledge Curator core.

---

## 4. Required new system package

Create a new top-level Python package:

`system/`

Minimum recommended files:

```
system/
  __init__.py
  composition.py
  provider_loader.py
  mcp_stdio.py
```

Names may be adjusted slightly if needed, but keep responsibilities separated.

### 4.1 `system/composition.py`

Define internal system-level dependency containers.

At minimum represent:

### curator dependencies

- `KnowledgeRepository`
- `OntologyService`
- `MechanismValidator`
- human-readable adapter/provider identity

### evidence dependencies

- optional `EvidenceRetrievalService`
- optional `MechanismValidator`
- human-readable adapter/provider identity

Create a composed system runtime that yields:

- `CuratorRuntime`
- `EvidenceRuntime`

Do not duplicate curation or retrieval algorithms.

---

## 5. Narrow runtime constructors

Allowed modifications:

- `knowledge_curator/mcp_server/runtime.py`
- `knowledge_curator/mcp_server/evidence_runtime.py`

### 5.1 Curator runtime constructor

Add a narrow constructor that accepts externally supplied implementations of the existing ports.

Example intent only:

```python
create_curator_runtime(
    repository=...,
    ontology=...,
    mechanism_validator=...,
    adapter_note=...,
)
```

It must construct the existing `KnowledgeCurator`.

The current `create_default_runtime()` integration behavior must remain available for existing tests.

Do not make the default integration runtime silently become production.

### 5.2 Evidence production constructor

Add a narrow constructor for a real/injected retrieval service.

Example intent only:

```python
create_production_evidence_runtime(
    retrieval=...,
    mechanism_validator=...,
    adapter_note=...,
)
```

Required properties:

- `integration_fixture=False`
- `retrieval_available=True`
- no synthetic fixture
- no hidden fallback to `build_fixture_evidence_service()`

The current fail-closed production-default behavior must remain unchanged.

The current explicit integration fixture mode must remain available for tests.

---

## 6. Provider loading

Create an internal provider-loading boundary under `system/`.

Recommended deployment contract:

`AI4S_SYSTEM_ADAPTER_FACTORY=package.module:factory_function`

The exact environment-variable name may be changed only if documented consistently.

The factory should return the system dependency bundle required by `composition.py`.

Rules:

- missing provider factory in production mode => hard fail before MCP server starts;
- invalid import => hard fail;
- non-callable factory => hard fail;
- invalid returned dependency shape => hard fail;
- factory exception => hard fail;
- do not fall back to InMemory/Fake adapters;
- never log environment secrets or the entire environment;
- error messages may include provider module/function identity but not secret values.

Dynamic import is an internal deployment mechanism, not a public cross-team scientific contract.

---

## 7. Production-vs-integration isolation

Production composition must never silently use the checked-in test adapters.

At minimum reject known integration/test implementations from:

- `knowledge_curator.adapters.in_memory_repository`
- `knowledge_curator.adapters.in_memory_commit`
- `knowledge_curator.adapters.in_memory_lifecycle`
- `knowledge_curator.adapters.in_memory_source_versions`
- `knowledge_curator.adapters.in_memory_revision_publication`
- `knowledge_curator.adapters.in_memory_retrieval`
- `knowledge_curator.adapters.in_memory_evidence`

Also reject:

- `FakeMechanismValidator`
- `SimpleOntologyService`
- explicit integration evidence fixture as a production runtime

The validation should be narrow and deterministic.

Do not attempt to prove that an arbitrary third-party adapter is scientifically correct; SI-1 only prevents known test adapters from masquerading as production.

---

## 8. Production bootstrap

Implement a system-level MCP stdio bootstrap.

Recommended entry point:

`python -m system.mcp_stdio`

Behavior:

1. load configured production provider;
2. validate dependency bundle;
3. compose `CuratorRuntime`;
4. compose `EvidenceRuntime`;
5. call existing `create_mcp_server(...)`;
6. start stdio server.

If evidence retrieval is intentionally not configured by the provider, it is acceptable to compose:

- production curator runtime;
- fail-closed unavailable evidence runtime.

Do not substitute a fixture.

---

## 9. Do NOT change the current DSH preset in SI-1

Do not modify:

`dsh/knowledge-curator/cordis.patch.yml`

to use the new system entry point yet.

Reason:

SI-1 must first prove that the composition/bootstrap layer works independently.

DSH migration belongs to a later accepted system-integration phase.

---

## 10. No orchestrator in SI-1

Do not create:

- CurationWorkflow;
- RevisionWorkflow;
- QAEvidenceWorkflow;
- DocumentCommit workflow;
- lifecycle workflow;
- Agent Factory;
- global Orchestrator.

Do not call:

- `DocumentCommitCoordinator`
- `RevisionPublicationCoordinator`
- `LifecycleRevisionCoordinator`

from the new system package in SI-1.

Those belong to the next phase after SI-1 acceptance.

---

## 11. Tests

Add system-level tests.

Preferred location:

`integration/system/tests/`

Create the package if absent.

Minimum required tests:

### production provider loading

1. missing provider config fails closed;
2. invalid module fails closed;
3. missing factory attribute fails closed;
4. non-callable factory fails closed;
5. factory exception fails closed;
6. invalid bundle fails closed.

### adapter isolation

7. production composition rejects `InMemoryKnowledgeRepository`;
8. rejects `SimpleOntologyService`;
9. rejects `FakeMechanismValidator`;
10. rejects in-memory retrieval adapters / integration fixture as production evidence.

### valid injected composition

11. protocol-compatible test provider bundle can compose a curator runtime;
12. injected curator runtime can execute one curation round-trip without using the default in-memory factory;
13. injected production evidence service creates `integration_fixture=False`;
14. evidence omitted intentionally => retrieval remains explicitly unavailable;
15. provider identity is visible through existing health metadata/adapter note without changing health schema.

### MCP contract preservation

16. tool names remain exactly the existing four tools;
17. no new public MCP business tool;
18. existing MCP input/output behavior remains compatible.

### isolation

19. `system/**` does not get imported by frozen Knowledge Curator core modules;
20. production bootstrap does not read `KC_EVIDENCE_INTEGRATION_FIXTURE` as a way to create production evidence.

Use deterministic local stubs inside tests only.

No network calls.

---

## 12. Regression suites

All previously accepted tests must remain green.

Required evidence:

```
pytest knowledge_curator/tests
pytest integration/dsh/tests
pytest integration/system/tests
```

Expected previous baselines:

- knowledge_curator: 522 passed / 0 skipped / 0 failed
- integration/dsh: 90 passed / 0 failed

New system test count is additive.

Do not weaken or delete prior tests.

---

## 13. Freeze verification

Before completion, explicitly verify no modifications occurred under:

```
knowledge_curator/core/
knowledge_curator/schemas/
knowledge_curator/ports/
knowledge_curator/retrieval/
planner/CONTRACT_GAPS.md
```

Also confirm:

- `knowledge_curator/mcp_server/app.py` unchanged;
- DSH preset unchanged;
- no public MCP tool added.

---

## 14. Required documentation

Create:

`results/phase-si-1-executor-report.md`

Report exactly:

```
Phase SI-1 implementation CODE SHA:

production provider loader:
PASS / FAILED

production missing-provider fail-closed:
PASS / FAILED

known test adapters rejected in production:
PASS / FAILED

external curator dependency injection:
PASS / FAILED

external evidence dependency injection:
PASS / FAILED

evidence unavailable remains fail-closed:
PASS / FAILED

integration fixture isolated from production:
PASS / FAILED

MCP public tool contract unchanged:
PASS / FAILED

DSH preset unchanged:
PASS / FAILED

orchestrator/workflow added:
NO

frozen knowledge_curator core changed:
NO

CONTRACT_GAPS changed:
NO

knowledge_curator tests:
X passed / Y skipped / Z failed

integration/dsh tests:
X passed / Z failed

integration/system tests:
X passed / Z failed

origin/main SHA:

deviations:
NONE / describe
```

---

## 15. status.json

At completion set:

- module = `system_integration`
- phase = `SI-1`
- actor = `executor`
- state = `executor_complete`
- current_plan = `planner/latest_plan.md`
- result_expected = `results/phase-si-1-executor-report.md`
- latest_commit = actual SI-1 CODE SHA

Preserve an explicit constraint that Knowledge Curator remains frozen at:

`42e39121af5f6120174e088a521c9ad014abdcda`

---

## 16. Completion rule

Push all SI-1 implementation, tests, report, and status to `main`.

Then STOP.

Do not begin SI-2.

Do not implement an orchestrator.

Do not wire curation to commit.

Do not change the DSH preset.

Planner will review SI-1 before authorizing the next phase.
