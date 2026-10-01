# Phase SI-1-R1 Plan — Production Composition Hardening

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Goal

Close the remaining SI-1 production-composition integrity gaps identified in:

`planner/phase-si-1-review.md`

This is a **narrow R1 hardening pass**.

Do not begin SI-2.

Do not add orchestrator/workflows.

Do not change frozen Knowledge Curator core behavior.

---

## 1. Frozen baseline

Knowledge Curator remains:

- ACCEPTED
- FROZEN
- DELIVERABLE

Frozen implementation CODE SHA:

`42e39121af5f6120174e088a521c9ad014abdcda`

Reviewed SI-1 implementation CODE SHA:

`e5ccf224def859357ac0f9f14605817829815a06`

Current R1 review:

`planner/phase-si-1-review.md`

---

## 2. Frozen files/directories

Do not modify:

- `knowledge_curator/core/**`
- `knowledge_curator/schemas/**`
- `knowledge_curator/ports/**`
- `knowledge_curator/retrieval/**`
- `knowledge_curator/mcp_server/app.py`
- `knowledge_curator/mcp_server/runtime.py`
- `knowledge_curator/mcp_server/evidence_runtime.py`
- `planner/CONTRACT_GAPS.md`
- `dsh/knowledge-curator/cordis.patch.yml`

R1 should be implemented entirely in the system composition/bootstrap layer and system integration tests.

---

## 3. R1-01 — Reject nested test adapters inside EvidenceRetrievalService

The production guard must not only inspect the outer evidence object.

A production provider may supply an `EvidenceRetrievalService` whose nested components are test adapters.

For a configured production `EvidenceRetrievalService`, inspect its configured backend dependencies at minimum:

- vector backend;
- keyword backend;
- reranker.

Apply the existing deterministic forbidden-adapter rule to those nested objects.

The checked-in integration fixture produced by:

`knowledge_curator.mcp_server.evidence_runtime.build_fixture_evidence_service()`

MUST be rejected by production composition.

Do not change `EvidenceRetrievalService`.

Do not use heuristic scientific-quality checks.

Only prevent known test/integration adapters from masquerading as production.

### Required tests

1. `build_fixture_evidence_service()` is rejected by production composition;
2. an `EvidenceRetrievalService` containing `InMemoryVectorSearch` is rejected;
3. containing `InMemoryKeywordSearch` is rejected;
4. containing `FakeReranker` is rejected;
5. a service built from non-test protocol-compatible stubs is accepted.

---

## 4. R1-02 — Validate production dependencies against existing frozen contracts

Use the existing runtime-checkable frozen Ports to validate curator dependency shape before MCP startup.

Required curator contracts:

- `KnowledgeRepository`
- `OntologyService`
- `MechanismValidator`

Production composition must reject dependencies that do not satisfy those Ports.

For evidence:

- configured retrieval must be an `EvidenceRetrievalService`;
- optional evidence mechanism validator must satisfy `MechanismValidator`;
- nested evidence backends must pass R1-01 isolation checks.

Do not modify the Port definitions.

### Required negative tests

Reject before `create_mcp_server(...)`:

- `repository=object()`;
- `ontology=object()`;
- `mechanism_validator=object()`;
- `retrieval=object()`;
- evidence `mechanism_validator=object()`.

### Required positive tests

Use complete external stubs that satisfy the existing Protocols.

The positive curator stub must implement all methods required by the frozen Port, not merely the method reached by one happy-path test.

---

## 5. R1-03 — Sanitize external provider exceptions

In `system/provider_loader.py`, external provider/import exception text must not be copied verbatim into user-visible errors.

Forbidden pattern:

`... {exc}`

for arbitrary provider/import execution exceptions.

Allowed diagnostic material:

- provider module name;
- factory attribute name;
- exception class/type;
- stable category such as `provider_module_import_failed` or `provider_factory_failed`.

Preserve the original exception as the chained cause:

`raise ProviderLoadError(...) from exc`

but do not expose `str(exc)` in the outer message.

### Required tests

Create deterministic external test modules/factories that raise with:

`TOP_SECRET_SENTINEL`

Verify:

- load fails;
- exposed `ProviderLoadError` string does not contain the sentinel.

Cover both:

- module import execution failure where practical;
- factory execution failure.

At minimum factory failure sentinel coverage is mandatory.

---

## 6. R1-04 — Mandatory MCP checks must run, not skip

The SI-1 report showed:

`19 passed / 2 skipped / 0 failed`

The two MCP contract tests are mandatory acceptance checks.

Do not use `pytest.importorskip("mcp")` for mandatory SI-1 MCP tests.

Run `integration/system/tests` in the MCP-qualified environment used by the DSH suite.

Final SI-1-R1 system suite must report:

- **0 skipped**

unless an unrelated pre-existing non-mandatory test is explicitly documented and approved by Planner.

---

## 7. Add real system-bootstrap MCP test

Add a test that exercises the actual SI-1 path:

```
provider factory
  -> load_provider_bundle
  -> _extract_deps
  -> compose_system_runtime
  -> create_mcp_server
```

Use:

`system.mcp_stdio.build_system_mcp_server(...)`

with a valid protocol-compatible provider.

Then verify using the MCP server API:

exact tool set:

- `curate_assertion_set`
- `knowledge_curator_health`
- `retrieve_evidence`
- `validate_retrieved_claims`

No fifth tool is allowed.

Call `knowledge_curator_health` and verify existing response fields expose:

- curator production adapter note/provider identity;
- evidence production adapter note or explicit unavailable state.

Do not add or change health response schema.

No network call.

---

## 8. Provider bundle validation semantics

It is acceptable for `provider_loader._validate_bundle()` to perform only structural top-level validation if `compose_system_runtime()` performs the complete dependency validation immediately afterward.

The invariant is:

**invalid dependencies must fail before the MCP server is returned/started.**

No lazy failure only when a scientific tool is later invoked.

---

## 9. Production fail-closed invariants

After R1, all of these must remain true:

- no configured provider => hard fail;
- invalid provider import => hard fail;
- invalid factory => hard fail;
- provider exception => hard fail;
- invalid dependency shape => hard fail;
- known integration/test adapters => hard fail;
- nested fixture retrieval adapters => hard fail;
- missing evidence retrieval => explicit `retrieval_unavailable`, not fixture fallback;
- no secret-bearing external exception text copied into stderr-facing errors;
- no default fallback to InMemory/Fake.

---

## 10. Scope limits

Do not create or implement:

- Agent Factory;
- Orchestrator;
- CurationWorkflow;
- RevisionWorkflow;
- QAEvidenceWorkflow;
- commit/lifecycle wiring;
- new production database implementation;
- new vector database implementation;
- new ontology implementation;
- new public MCP tool;
- DSH preset migration.

Do not call:

- `DocumentCommitCoordinator`
- `RevisionPublicationCoordinator`
- `LifecycleRevisionCoordinator`

from `system/**`.

---

## 11. Tests

Required:

```bash
pytest knowledge_curator/tests
pytest integration/dsh/tests
pytest integration/system/tests
```

Acceptance targets:

### knowledge_curator

At least frozen baseline:

`522 passed / 0 skipped / 0 failed`

### integration/dsh

At least frozen baseline:

`90 passed / 0 failed`

### integration/system

All mandatory SI-1/SI-1-R1 tests pass.

**0 skipped.**

No network.

Do not remove or weaken existing SI-1 tests.

---

## 12. Freeze verification

Before completion compare the final tree against the pre-SI-1 frozen baseline and explicitly report no changes under:

- `knowledge_curator/core/**`
- `knowledge_curator/schemas/**`
- `knowledge_curator/ports/**`
- `knowledge_curator/retrieval/**`
- `knowledge_curator/mcp_server/app.py`
- `planner/CONTRACT_GAPS.md`
- `dsh/knowledge-curator/cordis.patch.yml`

Also report whether either SI-1 runtime constructor file changed during R1:

- `knowledge_curator/mcp_server/runtime.py`
- `knowledge_curator/mcp_server/evidence_runtime.py`

Expected: **NO**.

---

## 13. Deliverable

Update:

`results/phase-si-1-executor-report.md`

with an R1 section containing exactly:

```
Phase SI-1-R1 implementation CODE SHA:

checked-in integration fixture rejected as production:
PASS / FAILED

nested InMemory vector rejected:
PASS / FAILED

nested InMemory keyword rejected:
PASS / FAILED

nested Fake reranker rejected:
PASS / FAILED

production curator Port validation:
PASS / FAILED

production evidence type/Port validation:
PASS / FAILED

external protocol-compatible composition:
PASS / FAILED

provider exception secret redaction:
PASS / FAILED

system bootstrap exact four-tool contract:
PASS / FAILED

health production adapter identity:
PASS / FAILED

production missing-provider fail-closed:
PASS / FAILED

evidence unavailable remains fail-closed:
PASS / FAILED

orchestrator/workflow added:
NO

DSH preset changed:
NO

frozen knowledge_curator tree changed:
NO

SI-1 runtime constructor files changed during R1:
NO

CONTRACT_GAPS changed:
NO

knowledge_curator tests:
X passed / Y skipped / Z failed

integration/dsh tests:
X passed / Z failed

integration/system tests:
X passed / 0 skipped / Z failed

origin/main SHA:

deviations:
NONE / describe
```

---

## 14. status.json

At completion:

- module = `system_integration`
- phase = `SI-1-R1`
- actor = `executor`
- state = `executor_complete`
- current_plan = `planner/latest_plan.md`
- result_expected = `results/phase-si-1-executor-report.md`
- latest_commit = actual R1 implementation CODE SHA

Preserve:

`knowledge_curator_freeze.implementation_code_sha = 42e39121af5f6120174e088a521c9ad014abdcda`

---

## 15. Completion rule

Push SI-1-R1 implementation, tests, updated report, and status to `main`.

Then STOP.

Do not begin SI-2.

Planner will perform final SI-1 acceptance review after R1.
