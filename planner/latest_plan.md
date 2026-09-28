# Phase 3.1 Plan — Python MCP Adapter + Live DSH MCP Bridge

**Planner:** ChatGPT  
**Executor:** MiMo  
**State:** READY_FOR_EXECUTOR

## 0. Baselines

Frozen business baseline:
- knowledge_curator §5.1–§5.4
- implementation `381ae0da2a7e4b2fcfd79d28a594bdd6b0253490`

Current executable DSH baseline:
- `deepseek-harness-sdk==0.1.5rc1`
- `deepseek-harness-runtime-bin==0.1.5rc1`
- profile/provider/model live smoke already passed

Architecture reference:
- DeepSeek Harness repository commit `4878cdabd87d4041bdaff61d04c966883b9fd07a`

Read:
1. `docs/01-总体架构与数据流设计.md`
2. `docs/03-文献自动调研与知识入库流水线.md`
3. `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`
4. `planner/DSH_INTEGRATION_NOTES.md`
5. `planner/phase-03-0-review.md`
6. `planner/CONTRACT_GAPS.md`
7. `status.json`

## 1. Goal

Create the **thin Python MCP boundary** for the existing knowledge_curator and prove the full live bridge:

```text
real DeepSeek model
 -> DSH 0.1.5rc1
 -> @deepseek-ai/dsh-mcp-client
 -> stdio MCP
 -> Python knowledge_curator MCP server
 -> existing KnowledgeCurator core
 -> CurationReport
 -> MCP result
 -> DSH model
```

This phase does not implement §6 or §7.

## 2. Official MCP Python SDK

Use the official Model Context Protocol Python SDK package `mcp`.

Current official line supports the 2026-07-28 protocol and earlier revisions. Use a pinned version compatible with the executor environment and record the exact resolved version.

Do not hand-write JSON-RPC framing.

Do not use a third-party MCP framework when the official `mcp` SDK is sufficient.

For v2, the high-level server class is `MCPServer`, not the old `FastMCP` name. If the resolved package is v1 for compatibility reasons, record that fact and its import path explicitly.

## 3. Package structure

Recommended:

```text
knowledge_curator/
└── mcp_server/
    ├── __init__.py
    ├── app.py
    ├── codec.py
    ├── runtime.py
    └── __main__.py

integration/
└── dsh/
    ├── patches/
    │   └── knowledge-curator-mcp.patch.yml
    ├── mcp_smoke.py
    └── tests/
        ├── test_mcp_server_contract.py
        ├── test_mcp_codec.py
        └── test_dsh_mcp_patch.py
```

Names may vary, but keep:
- MCP transport/codec thin;
- deterministic core unchanged;
- DSH configuration outside core.

## 4. MCP tool scope

Expose **one required business tool** in Phase 3.1:

`curate_assertion_set`

Input:
- the current temporary compatibility `AssertionSet` JSON shape;
- no new public cross-team schema.

Output:
- serialized `CurationReport`;
- exact current confidence/action vocabulary;
- warnings/completeness/conflicts/quality/decisions needed to inspect the result.

Optional one diagnostic tool:
- `knowledge_curator_health`

If added, mark it integration/diagnostic and do not treat it as a permanent scientific API.

Do **not** expose §6 search/evidence/revise tools yet.

Do not expose a fake production commit tool backed by ephemeral storage. §5.4 remains internal until a production L2 adapter is frozen.

## 5. Runtime composition inside Python

Create a small MCP application/runtime factory that wires:

```text
KnowledgeCurator
 + current repository/ontology/mechanism Ports
```

For Phase 3.1 contract/live bridge tests, in-memory/fake implementations are acceptable and must be explicitly labeled integration-test adapters.

The MCP layer must call the same existing `KnowledgeCurator.curate()`; it must not duplicate completeness/conflict/quality logic.

## 6. JSON codec rules

The MCP codec may translate JSON <-> existing dataclasses/enums, but must not redefine semantics.

Required:
- reject malformed input cleanly;
- reject unknown/invalid confidence/action/value_type enum values;
- preserve ref_id;
- preserve evidence/provenance locator fields present in compatibility schema;
- deterministic serialization;
- no Python repr leakage;
- no traceback dumped as successful tool result.

Do not silently fill fields that the Phase 1 completeness gate is supposed to judge as missing.

## 7. Direct MCP contract test without DSH/model

First prove the Python MCP server itself.

Using official MCP client/testing APIs or subprocess stdio:
- start `python -m knowledge_curator.mcp_server`;
- list tools;
- confirm `curate_assertion_set` is present;
- call it with a known fixture;
- verify result maps to the expected deterministic CurationReport;
- malformed payload yields structured MCP error/failure;
- server exits cleanly.

This test must not require DeepSeek API.

## 8. DSH 0.1.5rc1 MCP patch

Create a patch for the **actual executable baseline**.

Expected row shape:

```yaml
- insert:
    - id: mcp-knowledge-curator
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: knowledge_curator
        transport: stdio
        command: <python executable>
        args:
          - -m
          - knowledge_curator.mcp_server
        cwd: <repo/workspace path>
        failOnStartupError: true
        toolCallTimeoutMs: 60000
```

Do not hard-code a developer-specific absolute Python path into the committed patch.

Use a generated runtime patch or environment-backed Loader expression/config where appropriate.

Before live testing, verify on the real 0.1.5rc1 runtime that `@deepseek-ai/dsh-mcp-client` resolves. If it does not, capture exact error and use the official plugin/profile mechanism to install the **matching 0.1.5rc1 MCP package**, not a mixed 0.2.0 package.

Do not mix DSH package minors in one runtime.

## 9. Live DSH MCP bridge test

With the real DeepSeek API key:

Launch `DeepSeekHarness` using:
- executable 0.1.5rc1 runtime;
- `profile="sdk-minimal"` or `sdk` as actually required;
- patch that inserts the knowledge_curator MCP client;
- provider `deepseek-official`;
- configurable model.

Ask the model explicitly to call:

`mcp__knowledge_curator__curate_assertion_set`

with a small deterministic fixture.

The prompt should make tool use mandatory and request a concise report of returned status/confidence.

Acceptance requires evidence that:
- DSH discovered the MCP tool;
- a real `tool/call` event occurred for the expected public tool name;
- MCP server received the call;
- result corresponds to deterministic core output;
- model final response reflects the returned result;
- finish_reason is completed;
- no key/secret appears in artifacts.

Do not accept a model answer that merely describes what it *would* call.

## 10. Tool-call evidence

Persist a secret-free machine-readable artifact:

`results/phase-03-1-dsh-mcp-smoke.json`

Include:
- dsh sdk/runtime version;
- mcp Python SDK version;
- profile/provider/model;
- public DSH tool name;
- tool_discovered;
- tool_called;
- tool_call_count;
- expected deterministic result summary;
- observed tool result summary;
- final_response_nonempty;
- finish_reason;
- secret_present=false;
- errors/warnings.

Do not store full API secrets or unnecessary raw conversation.

## 11. Version skew rule

Phase 3.1 explicitly targets executable DSH `0.1.5rc1`.

Do not introduce Agent Preset.

Do not copy 0.2.0-only package/config assumptions into the live patch.

Keep CG-015 open.

## 12. Tests

All existing:
- 127 knowledge_curator tests;
- 15 Phase 3.0 keyless DSH tests

must remain green.

Add:
- codec tests;
- MCP server list/call/error tests;
- patch/config tests;
- optional live bridge test separated from keyless suite.

Ordinary test suite must not require `DEEPSEEK_API_KEY`.

## 13. Secrets and telemetry

No secret values in repository or results.

Because official DSH may have session-log/telemetry contributors depending on profile/config, the live test should use an isolated DSH_HOME and disable optional telemetry/session upload where the 0.1.5rc1 profile supports an explicit opt-out, unless required for the provider request itself.

Do not change model behavior to fake privacy; configure the runtime correctly.

## 14. Forbidden in Phase 3.1

Do not:
- implement Agent Preset;
- create final TypeScript DSH bundle;
- implement §6 RAG/evidence/citation/Abstain;
- implement §7 revision lifecycle;
- add production SQLite/FAISS adapters;
- rewrite Phase 1/2 core;
- directly call DeepSeek with requests/httpx/OpenAI.

## 15. Report

Create:

`results/phase-03-1-executor-report.md`

Include:
- MCP SDK/version;
- exposed tools;
- codec approach;
- direct MCP contract test result;
- DSH MCP client resolution on 0.1.5rc1;
- live tool discovery/call evidence;
- exact public DSH tool name;
- deterministic expected vs observed result;
- all test counts;
- live smoke result;
- version-skew note;
- CONTRACT_GAPS;
- public contracts changed? NO;
- implementation commit SHA.

## 16. status.json

Update on completion:
- phase = "3.1"
- actor = "executor"
- state = "executor_complete"
- latest_commit = actual implementation SHA
- result_expected = "results/phase-03-1-executor-report.md"

Stop after Phase 3.1.

Do not begin Phase 3.2.
