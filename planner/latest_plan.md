# Phase SI-2A Plan — Curation → Commit Application Workflow

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Goal

Implement the first system-level application workflow that connects the already accepted/frozen curation runtime to the already accepted/frozen atomic document commit coordinator.

Target:

```
SourceIdentity + AssertionSet + trace/metadata
            |
            v
      CuratorRuntime
            |
            v
      CurationReport
            |
       conservative
       precommit gate
            |
            v
      CommitRequest
            |
            v
DocumentCommitCoordinator
            |
            v
        CommitResult
```

This phase is **application orchestration only**.

Do not implement the global AI4S-ED Orchestrator.

Do not implement revision/lifecycle orchestration.

Do not add a public MCP commit tool.

---

## 1. Frozen baselines

### Knowledge Curator

Implementation CODE SHA:

`42e39121af5f6120174e088a521c9ad014abdcda`

Status:

**ACCEPTED / FROZEN / DELIVERABLE**

### SI-1 production composition

Implementation CODE SHA:

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

Status:

**ACCEPTED / FROZEN**

### SI-1.5 DSH production wiring

Final closure implementation SHA:

`0f014f0a3aad75a6cada18874fead10414469d6b`

Status:

**ACCEPTED / FROZEN**

Final acceptance:

`planner/phase-si-1-5-final-acceptance.md`

---

## 2. Authoritative existing commit behavior

Do not reimplement the logic already owned by:

`knowledge_curator.core.commit.DocumentCommitCoordinator`

The coordinator already owns:

- CommitRequest binding validation;
- publishability enforcement;
- document-level atomic staging/finalization;
- structural/USDO compensation;
- vector pending recovery;
- deterministic snapshot creation;
- version publication;
- idempotency by `(ref_id, source_fingerprint)`;
- `PENDING_VECTOR`;
- `PENDING_FINALIZE`;
- `PUBLISHED`;
- `IDEMPOTENT_HIT`;
- `NOT_PUBLISHABLE`;
- `FAILED`.

The application layer must delegate these semantics.

Do not reproduce its internal state machine.

Do not call private coordinator methods.

---

## 3. Existing frozen commit dependency Ports

SI-2A commit composition consumes the existing runtime-checkable Ports:

- `DocumentCommitStore`
- `StructuralKnowledgeStore`
- `VectorIndex`
- `USDOStore`
- `VersionStore`

Do not modify those Port definitions.

Do not create replacement public contracts.

---

## 4. New application-layer package/files

Recommended minimum:

```
system/application_composition.py
system/workflows/__init__.py
system/workflows/curation_commit.py
```

Optional:

```
system/workflows/models.py
```

only if it materially improves clarity.

Do not put the workflow inside `knowledge_curator/**`.

Do not put it inside `system/mcp_stdio.py`.

---

## 5. Provider bundle extension

Reuse the already frozen deployment variable:

`AI4S_SYSTEM_ADAPTER_FACTORY=package.module:factory_function`

Do not create a second provider environment variable.

The same provider bundle may now contain:

```python
{
    "curator": {
        "repository": ...,
        "ontology": ...,
        "mechanism_validator": ...,
        "provider_identity": "...",
    },
    "evidence": {
        # optional existing SI-1 group
    },
    "commit": {
        "commit_store": ...,
        "structural_store": ...,
        "vector_index": ...,
        "usdo_store": ...,
        "version_store": ...,
        "provider_identity": "...",
    },
}
```

Existing SI-1 MCP bootstrap must continue to ignore the additional `commit` group and expose exactly the same four MCP tools.

Do not modify `system/provider_loader.py`.

Its current bundle validation already permits additional keys as long as `curator` exists.

---

## 6. Application composition

Implement in:

`system/application_composition.py`

Suggested internal data classes:

- `CommitDependencies`
- `CurationCommitApplicationRuntime`

The application runtime should contain at minimum:

- existing production `CuratorRuntime`;
- composed `DocumentCommitCoordinator`;
- provider identity/notes useful for diagnostics.

### Required composition behavior

1. load the same provider bundle through the existing `load_provider_bundle()`;
2. extract curator dependencies without modifying frozen SI-1 files;
3. compose the curator through existing `compose_system_runtime(...)`;
4. extract the new `commit` dependency group;
5. validate all five commit dependencies before returning an application runtime;
6. construct the existing `DocumentCommitCoordinator`;
7. never fall back to checked-in InMemory/Fake adapters.

Evidence composition is not required for SI-2A workflow execution.

Do not require evidence merely to run curation→commit.

---

## 7. Commit dependency validation

Validate against the existing runtime-checkable Ports:

- `DocumentCommitStore`
- `StructuralKnowledgeStore`
- `VectorIndex`
- `USDOStore`
- `VersionStore`

Invalid or missing dependency => hard fail during application composition.

Do not wait for a workflow call to discover malformed dependency shape.

### Known test adapters forbidden as production

At minimum reject:

- `InMemoryDocumentCommitStore`
- `InMemoryStructuralKnowledgeStore`
- `InMemoryVectorIndex`
- `InMemoryUSDOStore`
- `InMemoryVersionStore`

and objects originating from the known checked-in in-memory commit adapter module.

Validation must be narrow and deterministic.

Do not pretend to certify arbitrary third-party adapter scientific correctness.

---

## 8. Workflow API

Implement:

`system.workflows.curation_commit.CurationCommitWorkflow`

Recommended call shape:

```python
await workflow.run(
    source=SourceIdentity(...),
    assertion_set=AssertionSet(...),
    metadata={...},
    trace={...},
)
```

### Source identity rules

The caller MUST supply:

- `source.ref_id`;
- non-empty `source.source_fingerprint`.

The workflow MUST NOT:

- invent a fingerprint;
- hash the AssertionSet and pretend it is the source fingerprint;
- derive source identity from title/DOI heuristics.

Fail closed when:

- source fingerprint is empty;
- `source.ref_id != assertion_set.ref_id`.

Use a system/application-layer input exception or equivalent explicit failure.

Do not modify frozen commit validation.

---

## 9. Workflow execution semantics

### Step 1 — validate application input

Validate source binding before scientific work where possible.

### Step 2 — curate

Call the existing curator runtime.

Prefer the existing delegation path:

`knowledge_curator.mcp_server.runtime.run_curate(...)`

or directly the injected curator only if no semantics are duplicated.

Do not call the public MCP transport from inside the application workflow.

This is an in-process application workflow.

### Step 3 — conservative precommit gate

The workflow may short-circuit only clearly terminal curation outcomes:

- `report.status == "return_upstream"`;
- `report.returned_upstream_count > 0`;
- empty decisions;
- all decisions are `CurationAction.REJECT`.

For these outcomes:

- do not call `DocumentCommitCoordinator.commit()`;
- return the CurationReport;
- make it explicit that commit was not attempted;
- include a simple diagnostic reason.

This gate is a conservative application optimization.

The frozen `DocumentCommitCoordinator` remains authoritative for commit eligibility if a request reaches it.

Do not duplicate future/private coordinator eligibility rules.

### Step 4 — build CommitRequest

Use the existing frozen model:

`CommitRequest`

with exactly:

- caller-supplied `SourceIdentity`;
- original `AssertionSet`;
- generated `CurationReport`;
- copied metadata;
- copied trace.

Do not mutate the caller's dictionaries.

### Step 5 — commit once

Call:

`await DocumentCommitCoordinator.commit(request)`

exactly once per workflow invocation.

### Step 6 — return result

Return a small application result wrapper.

Recommended fields:

- `report: CurationReport`;
- `commit_attempted: bool`;
- `commit_result: Optional[CommitResult]`;
- `blocked_reason: Optional[str]`.

Do not invent a parallel commit-status enum.

When commit is attempted, authoritative status is:

`commit_result.status`

---

## 10. No automatic retry loop

The workflow MUST NOT internally retry:

- `PENDING_VECTOR`;
- `PENDING_FINALIZE`;
- `FAILED`.

Return the coordinator result immediately.

Recovery is achieved by the caller invoking the workflow again with the same:

`(ref_id, source_fingerprint)`

The frozen coordinator owns safe retry/idempotency.

This prevents hidden loops, duplicated side effects, and unbounded application retries.

---

## 11. Retry semantics

On a second workflow invocation with the same source identity:

- curation may run again;
- commit must reuse the same coordinator/store state;
- the commit coordinator decides whether to resume or return `IDEMPOTENT_HIT`.

Required behaviors:

### published replay

First run:

`PUBLISHED`

Second identical run:

`IDEMPOTENT_HIT`

and no second KB version.

### vector recovery

First run:

`PENDING_VECTOR`

Second run after transient vector failure clears:

`PUBLISHED`

and exactly one KB version.

### finalize recovery

First run:

`PENDING_FINALIZE`

Second run after transient failure clears:

publish/reuse the same deterministic snapshot/version semantics without duplicate publication.

Do not implement these recovery rules in the workflow.

Prove the workflow delegates them correctly.

---

## 12. Trace and metadata preservation

The workflow must place caller-supplied application context into:

- `CommitRequest.metadata`;
- `CommitRequest.trace`.

At minimum tests must prove exact propagation for:

- `trace_id`;
- `provenance_id`;

when supplied.

Do not make those keys mandatory unless an already frozen contract requires them.

Do not silently fabricate trace IDs in SI-2A.

---

## 13. Integration-only SI-2A provider fixture

Add a separate fixture, for example:

`integration/system/fixtures/si2a_provider.py`

Do not turn the SI-1.5 DSH fixture into the SI-2A application fixture unless there is a compelling reason.

The SI-2A fixture must use test-local protocol-compatible implementations for all five commit Ports.

It MUST NOT:

- import;
- instantiate;
- subclass;
- wrap;
- delegate to

the forbidden checked-in `InMemory*Commit/Structural/Vector/USDO/Version` implementations.

Test-local failure injection is allowed and encouraged.

Keep all fixture code under `integration/**`.

Production `system/**` must never import this fixture.

---

## 14. Required application composition tests

Add under:

`integration/system/tests/**`

At minimum:

1. provider bundle without `commit` group fails closed for SI-2A composition;
2. missing `commit_store` fails;
3. missing `structural_store` fails;
4. missing `vector_index` fails;
5. missing `usdo_store` fails;
6. missing `version_store` fails;
7. malformed commit-store shape fails Port validation;
8. malformed structural-store shape fails;
9. malformed vector-index shape fails;
10. malformed USDO-store shape fails;
11. malformed version-store shape fails;
12. known checked-in in-memory commit adapters are rejected;
13. complete protocol-compatible external/test-local dependency set composes successfully;
14. the resulting object contains the existing `DocumentCommitCoordinator`;
15. existing provider bundle with an extra `commit` group still builds the existing four-tool MCP server unchanged.

---

## 15. Required workflow tests

At minimum:

### success

- valid source + valid AssertionSet;
- curation succeeds;
- commit attempted;
- result = `PUBLISHED`;
- exactly one published version.

### return_upstream

- curation returns upstream;
- commit coordinator is not called;
- no commit record;
- no version.

### all rejected

- all curation decisions reject;
- commit coordinator is not called;
- no version.

### invalid source

- empty fingerprint => fail before commit;
- source/assertion-set ref mismatch => fail closed.

### idempotency

- first = `PUBLISHED`;
- second same source fingerprint = `IDEMPOTENT_HIT`;
- one version only.

### pending vector

- injected transient vector write failure;
- workflow returns `PENDING_VECTOR`;
- workflow does not auto-retry;
- second invocation after failure clears => `PUBLISHED`;
- no duplicate structural assertion/version.

### pending finalize

Inject at least one deterministic snapshot/version finalize failure.

Verify:

- first result = `PENDING_FINALIZE`;
- no hidden workflow retry;
- second invocation resumes/reuses coordinator state;
- no duplicate snapshot/version publication.

### trace/metadata

Capture the actual `CommitRequest` reaching the coordinator and verify:

- original SourceIdentity;
- original AssertionSet;
- generated report;
- metadata copied correctly;
- trace copied correctly;
- supplied `trace_id` and `provenance_id` are preserved.

### pending review

A curation result containing `PENDING_REVIEW` must not be promoted to verified/high by the workflow.

The existing coordinator controls its admitted visibility.

---

## 16. MCP / DSH boundary

SI-2A MUST NOT add:

- `commit_document`;
- `curate_and_commit`;
- `publish_document`;

or any other new public MCP business tool.

Existing public tools remain exactly:

- `curate_assertion_set`
- `knowledge_curator_health`
- `retrieve_evidence`
- `validate_retrieved_claims`

Do not modify:

`dsh/knowledge-curator/cordis.patch.yml`

DSH remains an Agent/tool boundary.

SI-2A is an internal application workflow.

---

## 17. Explicitly out of scope

Do not implement:

- global AI4S-ED Orchestrator;
- task planning/routing;
- lit_researcher workflow;
- parser/extractor workflow;
- RevisionPublicationCoordinator composition;
- lifecycle event orchestration;
- retraction/corrigendum workflow;
- manual approval workflow;
- Agent Factory;
- additional MCP tools;
- real SQLite/FAISS/Qdrant/ontology adapters.

Those belong to later phases.

---

## 18. Frozen files/directories

Do not modify:

- `knowledge_curator/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `dsh/knowledge-curator/**`
- `planner/CONTRACT_GAPS.md`

SI-2A code belongs in new application-layer files under `system/**` and integration tests/fixtures.

If a confirmed defect is found in frozen code, STOP and report it to Planner instead of fixing it inside SI-2A.

---

## 19. Architectural dependency direction

Allowed:

```
system/workflows
  -> system/application_composition
  -> system/composition
  -> knowledge_curator public/internal frozen Python APIs
```

Forbidden:

```
knowledge_curator
  -> system

knowledge_curator
  -> DSH

system/workflows
  -> DSH

system/workflows
  -> MCP transport
```

The workflow is transport-independent.

---

## 20. Tests and regression gates

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Accepted frozen baselines before SI-2A:

### knowledge_curator

`522 passed / 0 skipped / 0 failed`

### integration/system

`78 passed / 0 skipped / 0 failed`

### integration/dsh

`90 passed / 0 skipped / 0 failed`

New SI-2A tests are additive.

Mandatory SI-2A tests:

**0 skipped**

No network requirement.

Do not weaken/delete/skip previous tests.

---

## 21. Freeze verification

Before completion compare final tree against the SI-2A Planner handoff tree.

Explicitly verify no changes under:

- `knowledge_curator/**`;
- `system/composition.py`;
- `system/provider_loader.py`;
- `system/mcp_stdio.py`;
- `dsh/knowledge-curator/**`;
- `planner/CONTRACT_GAPS.md`.

Also verify public MCP tool names remain exactly four.

---

## 22. Required report

Create:

`results/phase-si-2a-executor-report.md`

Report exactly:

```
Phase SI-2A implementation CODE SHA:

application commit dependency composition:
PASS / FAILED

missing commit group fail-closed:
PASS / FAILED

five commit Ports validated before workflow startup:
PASS / FAILED

known InMemory commit adapters rejected as production:
PASS / FAILED

valid external/test-local commit dependencies compose:
PASS / FAILED

curation -> commit happy path:
PASS / FAILED

return_upstream skips commit:
PASS / FAILED

all-rejected skips commit:
PASS / FAILED

empty fingerprint fail-closed:
PASS / FAILED

source ref mismatch fail-closed:
PASS / FAILED

published replay returns IDEMPOTENT_HIT:
PASS / FAILED

pending_vector surfaced without hidden retry:
PASS / FAILED

pending_vector second invocation recovers:
PASS / FAILED

pending_finalize surfaced without hidden retry:
PASS / FAILED

pending_finalize second invocation recovers idempotently:
PASS / FAILED

trace_id preserved into CommitRequest:
PASS / FAILED

provenance_id preserved into CommitRequest:
PASS / FAILED

metadata preserved into CommitRequest:
PASS / FAILED

new public MCP tool added:
NO

DSH preset changed:
NO

global orchestrator added:
NO

revision/lifecycle workflow added:
NO

knowledge_curator frozen tree changed:
NO

SI-1/SI-1.5 frozen production files changed:
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

## 23. status.json

At completion set:

- module = `system_integration`
- phase = `SI-2A`
- actor = `executor`
- state = `executor_complete`
- current_plan = `planner/latest_plan.md`
- result_expected = `results/phase-si-2a-executor-report.md`
- latest_commit = actual SI-2A implementation CODE SHA

Preserve all accepted freezes:

### Knowledge Curator

`42e39121af5f6120174e088a521c9ad014abdcda`

### SI-1

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

### SI-1.5

`0f014f0a3aad75a6cada18874fead10414469d6b`

---

## 24. Completion rule

Push implementation, tests, report, and status to `main`.

Then STOP.

Do not begin SI-2B.

Do not begin global Orchestrator work.

Planner will perform SI-2A acceptance review first.
