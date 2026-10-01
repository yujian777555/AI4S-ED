# Phase SI-1.5 Final Planner Acceptance

Date: 2026-10-01  
Planner: ChatGPT  
Executor: MiMo/Kimi/Codex

## Verdict

**ACCEPTED / FROZEN**

Final SI-1.5 closure implementation tip SHA:

`0f014f0a3aad75a6cada18874fead10414469d6b`

Executor bookkeeping HEAD reviewed:

`6921bcf730503b41184c6810d599cdb65952a0f2`

Planner bookkeeping correction:

`1029f95125ce7fad8525ed34f8a29f23ed52b2ef`

## Accepted implementation chain

SI-1.5 initial DSH production-bootstrap wiring:

`fd000223b308b209b02f3163e2eee72a6637aab2`

SI-1.5-R1 DSH wiring closure:

`c2f2cb24580689b82551bb8f3971d1e75d07da3e`

SI-1.5-R2 qualification-path closure:

`0f014f0a3aad75a6cada18874fead10414469d6b`

## Accepted capability

The DSH `knowledge-curator` product preset now launches:

`python -m system.mcp_stdio`

and therefore uses the accepted SI-1 production composition boundary.

The deployment contract is:

`AI4S_SYSTEM_ADAPTER_FACTORY=package.module:factory_function`

Accepted behavior:

- missing provider fails closed;
- invalid provider fails closed;
- no fallback to Knowledge Curator InMemory/Fake adapters;
- no fallback to `KC_EVIDENCE_INTEGRATION_FIXTURE` for production composition;
- valid provider composes CuratorRuntime / EvidenceRuntime;
- MCP public contract remains exactly four tools;
- evidence may remain explicitly unavailable when omitted by the provider;
- DSH product preset remains configuration-only and does not own orchestration.

## Qualification closure

Planner reviewed the R2 implementation and regression sources.

The mounted DSH qualification path now:

- treats direct legacy fixture as `integration_fixture=true`;
- treats provider-backed DSH path as `integration_fixture=false`;
- compares evidence identity/coverage/Abstain/policy independently of that marker;
- uses test-local protocol-compatible evidence adapters over the same checked-in deterministic fixture corpus;
- contains no forbidden Knowledge Curator InMemory/Fake retrieval adapters;
- supplies `AI4S_SYSTEM_ADAPTER_FACTORY` to both lane324 baseline and lane325 evidence qualification;
- no longer globally configures the MCP child through `KC_EVIDENCE_INTEGRATION_FIXTURE`;
- wires legacy MCP smoke to an explicit provider contract;
- preserves caller-supplied providers;
- documents `system.mcp_stdio` in the generated-patch template.

## Test evidence

Executor-reported final regression evidence:

- `knowledge_curator`: **522 passed / 0 skipped / 0 failed**
- `integration/system`: **78 passed / 0 skipped / 0 failed**
- `integration/dsh`: **90 passed / 0 skipped / 0 failed**

The credentialed mounted DSH live model round-trip was:

`NOT_RUN_ENV`

because a DeepSeek credential/runtime was unavailable in the executor environment.

This does **not** block SI-1.5 acceptance because the final keyless acceptance now covers:

- real `python -m system.mcp_stdio` subprocess startup;
- exact four-tool discovery;
- health provider identity;
- curation round-trip;
- missing-provider fail-closed;
- provider-vs-direct deterministic evidence parity;
- coverage/Abstain parity;
- claim-guard policy parity;
- explicit fixture-marker boundary semantics.

No known deterministic mounted-live mismatch remains in the reviewed source.

Planner did not independently rerun the reported 522 / 78 / 90 test suites; Planner independently reviewed committed implementation, regression sources, commit scope, and frozen-tree integrity.

## Frozen-tree verification

Planner independently compared the R2 handoff tree to the executor final HEAD.

No blob changes were found under:

- `knowledge_curator/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `planner/CONTRACT_GAPS.md`
- `dsh/knowledge-curator/cordis.patch.yml`

Therefore both upstream freezes remain intact.

### Knowledge Curator freeze

`42e39121af5f6120174e088a521c9ad014abdcda`

Status:

**ACCEPTED / FROZEN / DELIVERABLE**

### SI-1 production-composition freeze

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

Status:

**ACCEPTED / FROZEN**

## Architecture after SI-1.5

```
DSH knowledge-curator preset
        |
        v
python -m system.mcp_stdio
        |
        v
AI4S_SYSTEM_ADAPTER_FACTORY
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
exact four MCP tools
```

## Still not implemented

SI-1.5 does not authorize or implement:

- Agent Factory;
- system Orchestrator;
- CurationWorkflow;
- RevisionWorkflow;
- curation-to-commit wiring;
- commit/lifecycle orchestration;
- concrete production repository/vector/ontology/mechanism adapters.

Those remain future system-integration work.

## Decision

**SI-1.5 is complete and frozen.**

Do not reopen SI-1.5 except for:

1. confirmed DSH/bootstrap defect;
2. newly frozen external deployment contract;
3. explicit Planner-approved requirement.

No SI-2 implementation is authorized by this acceptance document alone.
