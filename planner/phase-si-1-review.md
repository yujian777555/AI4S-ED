# Phase SI-1 Planner Review — R1 REQUIRED

Date: 2026-10-01  
Planner: ChatGPT  
Reviewed implementation CODE SHA: `e5ccf224def859357ac0f9f14605817829815a06`  
Reviewed executor bookkeeping HEAD: `2acefe5ca02e57ae805e574d4c1c783c5a91063c`

## Verdict

**NOT ACCEPTED YET — SI-1-R1 REQUIRED**

The SI-1 implementation is directionally correct and stayed inside the authorized file boundary, but three production-composition invariants are not fully closed.

Do **not** begin SI-2.

## What passed review

The implementation correctly added:

- `system/composition.py`;
- `system/provider_loader.py`;
- `system/mcp_stdio.py`;
- narrow external runtime constructors;
- missing-provider fail-closed behavior;
- no orchestrator/workflow;
- no curation→commit wiring;
- no DSH preset migration.

Planner independently compared the frozen tree between the SI-1 handoff baseline and current executor HEAD.

No changes were found under:

- `knowledge_curator/core/**`
- `knowledge_curator/schemas/**`
- `knowledge_curator/ports/**`
- `knowledge_curator/retrieval/**`
- `knowledge_curator/mcp_server/app.py`
- `planner/CONTRACT_GAPS.md`
- `dsh/knowledge-curator/cordis.patch.yml`

The Knowledge Curator freeze therefore remains intact.

## R1-01 — Nested integration fixture can bypass production adapter isolation

### Problem

`system.composition._validate_evidence_deps()` validates only the outer `retrieval` object.

The checked-in:

`build_fixture_evidence_service()`

returns an ordinary `EvidenceRetrievalService` whose internal components are:

- `InMemoryVectorSearch`
- `InMemoryKeywordSearch`
- `FakeReranker`

Because the outer class is `EvidenceRetrievalService`, the current blacklist does not see those nested test adapters.

Therefore a provider can pass the integration fixture service as production evidence and it will be accepted.

This violates the frozen SI-1 requirement:

> integration fixture / known in-memory retrieval adapters must never masquerade as production.

### Required fix

In the **system composition layer only**, when a production `EvidenceRetrievalService` is supplied, validate its configured backend components and reject known test/integration adapters.

At minimum inspect the service's configured vector, keyword, and reranker dependencies and apply the same deterministic forbidden-adapter guard.

Do not modify frozen retrieval implementation.

### Required regression

Construct the real checked-in integration fixture using:

`build_fixture_evidence_service()`

and prove that production composition rejects it.

Also prove that an `EvidenceRetrievalService` built from protocol-compatible non-test stubs is accepted.

## R1-02 — Production dependency shape is not protocol-validated

### Problem

Current production composition accepts any non-None object that is not on the blacklist.

For example, an arbitrary `object()` can pass the repository/ontology/mechanism-validator guard even though it does not implement the existing frozen Port.

That means an invalid provider bundle may survive composition and fail only during a later tool call.

SI-1 requires invalid dependency shape to fail before MCP startup.

### Required fix

Validate injected curator dependencies against the existing runtime-checkable frozen Ports:

- `KnowledgeRepository`
- `OntologyService`
- `MechanismValidator`

For configured evidence:

- require the expected `EvidenceRetrievalService` composition object;
- validate optional evidence mechanism validator against `MechanismValidator`;
- validate its nested retrieval/reranker components for known test-adapter contamination per R1-01.

Do not change the frozen Port definitions.

### Required regressions

Reject malformed production dependencies before `create_mcp_server(...)`:

- invalid repository shape;
- invalid ontology shape;
- invalid mechanism-validator shape;
- invalid evidence retrieval shape;
- invalid evidence mechanism-validator shape.

Use complete protocol-compatible external stubs for positive tests.

## R1-03 — Provider exception text may leak secrets

### Problem

`system/provider_loader.py` currently includes raw exception text in messages such as:

- module import failure: `{exc}`
- provider factory failure: `{exc}`

Provider code is external and may include credentials or secret values in its exception message.

SI-1 explicitly forbids secret leakage through bootstrap diagnostics.

### Required fix

Do not include arbitrary external exception message text in user-visible/stderr provider-load errors.

It is acceptable to include:

- configured module/factory identity;
- exception class/type;
- a stable sanitized error category.

Do not include `str(exc)` from external provider execution/import.

Preserve exception chaining internally with `raise ... from exc`.

### Required regression

Use a provider/import path that raises an exception containing a sentinel secret such as:

`TOP_SECRET_SENTINEL`

Assert that:

- startup/load fails;
- the sentinel does not appear in the exposed exception string.

## R1-04 — Required MCP contract tests must not be skipped

Executor reported:

`integration/system: 19 passed / 2 skipped / 0 failed`

The two skipped tests are the MCP contract checks using `pytest.importorskip("mcp")`.

Those were mandatory SI-1 acceptance checks, not optional tests.

### Required fix/test execution

Run the system integration suite in the MCP-qualified environment used for DSH integration and obtain:

- **0 skipped** for the mandatory SI-1 suite.

Add one stronger system-bootstrap test that builds the server through:

`system.mcp_stdio.build_system_mcp_server(...)`

with a valid provider and verifies:

- exactly the existing four MCP tools are present;
- no new tool is introduced;
- health metadata exposes the production adapter note/provider identity without schema expansion.

No network call is required.

## Acceptance gate for SI-1-R1

R1 is accepted only if all of the following hold:

1. checked-in evidence fixture service is rejected as production;
2. nested known test retrieval adapters cannot bypass isolation;
3. malformed curator/evidence dependencies fail before server startup;
4. protocol-compatible external dependencies compose successfully;
5. provider/import exception secret sentinel is not exposed;
6. system MCP bootstrap exposes exactly the existing four tools;
7. mandatory `integration/system` tests have 0 skipped;
8. `knowledge_curator` baseline remains 522 passed / 0 skipped / 0 failed;
9. `integration/dsh` remains 90 passed / 0 failed;
10. frozen tree remains unchanged;
11. no orchestrator/workflow is added;
12. no DSH preset migration occurs.

## Scope

This is a narrow SI-1 closure.

Allowed implementation changes:

- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py` only if required for fail-closed normalization
- `integration/system/tests/**`
- SI-1 result/status bookkeeping

Do not modify frozen Knowledge Curator files for R1.

The two runtime constructor additions already made in:

- `knowledge_curator/mcp_server/runtime.py`
- `knowledge_curator/mcp_server/evidence_runtime.py`

should remain unchanged unless Planner identifies a separate confirmed defect.

## Next action

Execute `planner/latest_plan.md` as **SI-1-R1**, push the result, and STOP.

Do not begin SI-2.
