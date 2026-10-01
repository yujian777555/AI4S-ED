# Phase SI-2A Final Planner Acceptance

Date: 2026-10-01  
Planner: ChatGPT  
Executor: MiMo/Kimi/Codex

## Verdict

**ACCEPTED / FROZEN**

SI-2A implementation CODE SHA:

`95d55e71390a2e7266b2084243161101c5aff60a`

Executor bookkeeping HEAD reviewed:

`410d03a45c6c439f8971226386943221a7e06fa9`

## Accepted capability

SI-2A adds the application-layer curation-to-commit path without changing the frozen Knowledge Curator core or the frozen SI-1 / SI-1.5 DSH bootstrap.

Accepted application flow:

```
SourceIdentity + AssertionSet
        |
        v
CuratorRuntime
        |
        v
CurationReport
        |
        v
conservative precommit gate
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

Accepted implementation:

- `system/application_composition.py`
  - reuses `AI4S_SYSTEM_ADAPTER_FACTORY`;
  - extracts the provider `commit` group;
  - validates all five runtime-checkable commit Ports before workflow startup;
  - rejects known checked-in InMemory/test adapters as production dependencies;
  - constructs the existing frozen `DocumentCommitCoordinator`.
- `system/workflows/curation_commit.py`
  - requires caller-supplied non-empty `SourceIdentity.source_fingerprint`;
  - fails closed on ref mismatch;
  - curates through the existing runtime;
  - short-circuits only clearly terminal curation outcomes;
  - constructs the existing `CommitRequest`;
  - calls `DocumentCommitCoordinator.commit()` exactly once per workflow invocation;
  - does not add hidden retries;
  - returns existing commit status semantics through a small application result wrapper.
- `integration/system/fixtures/si2a_provider.py`
  - provides test-local protocol-compatible commit dependencies and explicit failure injection;
  - is not a production adapter.

## Commit dependency boundary

The accepted composition validates:

- `DocumentCommitStore`
- `StructuralKnowledgeStore`
- `VectorIndex`
- `USDOStore`
- `VersionStore`

Known checked-in InMemory commit adapters remain forbidden for production composition.

## Precommit behavior

The application workflow does not attempt commit for:

- `report.status == "return_upstream"`;
- `returned_upstream_count > 0`;
- empty decisions;
- all decisions `REJECT`.

The workflow does not invent or derive the source fingerprint.

## Retry / recovery semantics

Accepted behavior:

- first successful publication returns `PUBLISHED`;
- replay with the same `(ref_id, source_fingerprint)` delegates idempotency to the frozen coordinator and returns `IDEMPOTENT_HIT`;
- `PENDING_VECTOR` is surfaced immediately, without hidden workflow retry;
- a later invocation with the same identity may resume and publish;
- `PENDING_FINALIZE` is surfaced immediately, without hidden workflow retry;
- a later invocation may recover idempotently;
- the workflow does not implement its own commit state machine.

## Trace and metadata

Caller-supplied metadata and trace dictionaries are copied into `CommitRequest`.

The committed regression suite includes checks for preserving:

- `trace_id`;
- `provenance_id`;
- arbitrary metadata.

## Public interface boundary

SI-2A does **not** change the public DSH/MCP contract.

The existing Knowledge Curator MCP surface remains exactly the previously frozen four-tool contract:

- `curate_assertion_set`
- `knowledge_curator_health`
- `retrieve_evidence`
- `validate_retrieved_claims`

No public commit/publish MCP tool is authorized by SI-2A.

## Test evidence

Executor-reported regression evidence:

- `knowledge_curator`: **522 passed / 0 skipped / 0 failed**
- `integration/system`: **107 passed / 0 skipped / 0 failed**
- `integration/dsh`: **90 passed / 0 skipped / 0 failed**

The SI-2A implementation adds 29 integration/system tests (19 composition + 10 workflow).

Planner did **not** independently rerun these suites. Planner independently reviewed:

- committed implementation;
- committed SI-2A tests;
- executor report;
- commit scope;
- frozen-tree integrity.

Review note: several gate assertions exercise the gate/helper path directly or through a localized patched test path rather than only through a full end-to-end workflow invocation. The production workflow control flow itself was reviewed and performs the gate immediately before request construction/commit. This test-shape limitation is non-blocking for SI-2A acceptance but should be strengthened opportunistically if these tests are revisited.

## Frozen-tree verification

Planner compared the SI-2A handoff commit:

`dc105916ead34497bf4cff0a3302a34fffa50f42`

through executor/bookkeeping HEAD:

`410d03a45c6c439f8971226386943221a7e06fa9`

The compare contains only SI-2A application/fixture/test/report/status changes. No changes were found in the frozen boundaries:

- `knowledge_curator/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `dsh/knowledge-curator/**`
- `planner/CONTRACT_GAPS.md`

Therefore the upstream freezes remain intact.

### Knowledge Curator freeze

`42e39121af5f6120174e088a521c9ad014abdcda`

Status:

**ACCEPTED / FROZEN / DELIVERABLE**

### SI-1 production-composition freeze

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

Status:

**ACCEPTED / FROZEN**

### SI-1.5 DSH production-wiring freeze

`0f014f0a3aad75a6cada18874fead10414469d6b`

Status:

**ACCEPTED / FROZEN**

## Architecture after SI-2A

```
DSH / other caller
        |
        +--> existing four MCP tools (unchanged)
        |
        +--> application layer
                |
                v
        CurationCommitWorkflow
                |
                +--> CuratorRuntime
                |
                v
        DocumentCommitCoordinator
                |
                +--> StructuralKnowledgeStore
                +--> VectorIndex
                +--> USDOStore
                +--> VersionStore
                +--> DocumentCommitStore
```

The application workflow is transport-independent and is not itself exposed as a new public MCP tool by this phase.

## Still not implemented / not authorized by SI-2A

SI-2A does not authorize or implement:

- global AI4S-ED Orchestrator;
- Agent Factory;
- revision/lifecycle publication workflow;
- retraction/corrigendum orchestration;
- manual approval workflow;
- new public MCP tools;
- concrete production repository/vector/ontology/mechanism/commit adapters;
- packaging/release extraction into the final distributable Knowledge Curator code package.

## Decision

**SI-2A is complete and frozen.**

Do not reopen SI-2A except for:

1. confirmed implementation defect;
2. newly frozen external application contract;
3. explicit Planner-approved requirement.

SI-2B is not started by this acceptance document alone.
