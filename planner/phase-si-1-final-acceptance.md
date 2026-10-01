# Phase SI-1 Final Planner Acceptance

Date: 2026-10-01  
Planner: ChatGPT  
Executor: MiMo/Kimi/Codex

## Verdict

**ACCEPTED / FROZEN**

Accepted implementation CODE SHA:

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

Reviewed executor bookkeeping HEAD:

`270586b302db4cca5633cc5f9ebca2d3827bb6bd`

## Accepted capability

Phase SI-1 establishes the production runtime composition/bootstrap boundary for AI4S-ED.

Accepted properties:

- external production curator dependency injection;
- external production evidence dependency injection;
- fail-closed production provider loading;
- rejection of known InMemory/Fake integration adapters;
- rejection of checked-in integration evidence fixture as production;
- nested vector/keyword/reranker contamination checks;
- validation against frozen runtime-checkable curator Ports;
- strict EvidenceRetrievalService type gate for configured evidence;
- provider exception redaction;
- system-level MCP stdio bootstrap;
- exact preservation of the existing four public MCP tools;
- explicit unavailable evidence behavior when production retrieval is not configured.

## R1 closure verification

Planner reviewed the committed R1 implementation and regression tests.

The following R1 issues are closed:

1. nested integration fixture/test retrieval bypass;
2. malformed production dependency shape;
3. provider exception secret leakage;
4. mandatory MCP system checks previously skipped.

The final system test report records:

- `knowledge_curator`: **522 passed / 0 skipped / 0 failed**
- `integration/dsh`: **90 passed / 0 failed**
- `integration/system`: **38 passed / 0 skipped / 0 failed**

These counts are executor-run evidence. Planner independently reviewed the source-level implementation and regression coverage.

## Independent freeze verification

Planner compared the repository tree between the pre-R1 handoff and final executor HEAD.

No blob changes were found under:

- `knowledge_curator/core/**`
- `knowledge_curator/schemas/**`
- `knowledge_curator/ports/**`
- `knowledge_curator/retrieval/**`
- `knowledge_curator/mcp_server/app.py`
- `planner/CONTRACT_GAPS.md`
- `dsh/knowledge-curator/cordis.patch.yml`

Planner also compared the SI-1 runtime constructor files between the original SI-1 implementation and R1 final HEAD:

- `knowledge_curator/mcp_server/runtime.py`
- `knowledge_curator/mcp_server/evidence_runtime.py`

No R1 changes were found.

Therefore the Knowledge Curator frozen implementation remains intact at:

`42e39121af5f6120174e088a521c9ad014abdcda`

## Architecture boundary after SI-1

The accepted architecture is:

```
external provider
      |
      v
system.provider_loader
      |
      v
system.composition
      |
      +--> CuratorRuntime
      |
      +--> EvidenceRuntime
      |
      v
create_mcp_server(...)
      |
      v
stdio MCP
```

SI-1 does not own workflow orchestration.

It does not call:

- `DocumentCommitCoordinator`
- `RevisionPublicationCoordinator`
- `LifecycleRevisionCoordinator`

It does not modify the DSH preset.

## Remaining work

Not yet implemented:

- system orchestrator;
- curation -> commit workflow;
- revision -> lifecycle workflow;
- DSH production bootstrap migration;
- concrete production repository/vector/ontology/mechanism adapters.

Those require a separately authorized system-integration phase.

## Decision

**SI-1 is complete and frozen.**

Do not reopen SI-1 except for:

1. confirmed composition/bootstrap bug;
2. newly frozen external deployment contract;
3. explicit Planner-approved requirement.

No SI-2 implementation is authorized by this acceptance document alone.
