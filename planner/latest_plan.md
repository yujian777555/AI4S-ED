# Phase 3.0 Plan — Official DSH Runtime & DeepSeek API Smoke

**Planner:** ChatGPT  
**Executor:** MiMo  
**State:** READY_FOR_EXECUTOR  
**Accepted knowledge_curator baseline:** `381ae0da2a7e4b2fcfd79d28a594bdd6b0253490`

## 0. Sources and version pin

Use the official repository and no substitute implementation:

- https://github.com/deepseek-ai/deepseek-harness
- reviewed release: `0.2.0-rc.1`
- reviewed upstream commit: `4878cdabd87d4041bdaff61d04c966883b9fd07a`

The upstream repository explicitly marks DSH as developer preview with possible compatibility-breaking changes.

Do not silently track `master` as an unpinned production dependency.

## 1. Read first

1. `docs/01-总体架构与数据流设计.md`
2. `docs/03-文献自动调研与知识入库流水线.md`
3. `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`
4. `planner/DSH_INTEGRATION_NOTES.md`
5. `planner/phase-02-2-review.md`
6. `planner/CONTRACT_GAPS.md`
7. `status.json`

Also consult the pinned official DSH documentation/source for:
- Python SDK;
- sdk / sdk-minimal profiles;
- provider/model selection;
- DSH_HOME;
- plugin/profile layering;
- runtime result/session behavior.

## 2. Goal

Prove that AI4S-ED can launch the **real official DeepSeek Harness runtime** and successfully execute a real DeepSeek-backed turn through the official Python SDK.

This phase is runtime/API validation only.

Do not implement:
- knowledge_curator MCP server;
- DSH bundle;
- knowledge-curator Agent preset;
- §6;
- §7;
- production L2/L3 adapters.

## 3. Dependency strategy

Add a small isolated integration area, recommended:

```text
integration/
└── dsh/
    ├── README.md
    ├── smoke.py
    ├── config.py
    └── tests/
        ├── test_dsh_config.py
        └── test_dsh_smoke_contract.py
```

Names may differ.

Do not place DSH imports into:
- `knowledge_curator/core/`
- `knowledge_curator/schemas/`
- deterministic Phase 1/2 code.

The existing 127 deterministic tests must remain able to run without an API key.

## 4. Official Python SDK

Use the official package/API:

```python
from deepseek_harness import DeepSeekHarness
```

The smoke path must launch an official profile, preferably `sdk-minimal` first.

Required explicit values:
- isolated absolute workspace path;
- isolated absolute `DSH_HOME`;
- `provider="deepseek-official"`;
- explicit model id from environment/config;
- bounded `max_tokens`;
- explicit session id for test runs.

Do not invent a Python `@dsh.agent` API.

## 5. Secrets

Real API credential must come only from environment/secret injection.

Allowed:
- `DEEPSEEK_API_KEY`
- optional `DEEPSEEK_BASE_URL` for a compatible endpoint if explicitly configured

Forbidden:
- committing API key;
- writing API key to report/log/test snapshots;
- printing headers/secrets;
- adding example secrets that resemble usable keys.

A keyless test suite must run cleanly when `DEEPSEEK_API_KEY` is absent.

The real live test should **skip with an explicit reason** when no key exists; do not report a skipped live test as evidence that the live API passed.

## 6. Configuration

Define a small typed/configured smoke settings layer.

Recommended environment keys:

```text
DSH_HOME
DSH_MODEL
DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL   # optional
```

For test isolation, if `DSH_HOME` is not supplied, the smoke runner may create/use an explicit temporary isolated home. Do not rely on implicit `~/.dsh` discovery.

Record the exact model used in the smoke result/report, but not credentials.

Do not hard-code `deepseek-v4-flash` as an AI4S-ED architectural requirement merely because the official example currently uses it. Make the model configurable.

## 7. Keyless runtime-contract tests

Before any live API call, test:

- official SDK import succeeds when installed;
- configuration rejects empty/invalid required paths;
- DSH_HOME is explicit/isolated;
- model/provider selection is passed through correctly;
- session ids are explicit;
- no secret is serialized into logs/results;
- deterministic knowledge_curator test suite remains independent of DSH/API;
- missing API key yields a clear live-test skip/preflight outcome, not a fake pass.

If the official SDK package cannot be installed in the executor environment, capture the exact installation/runtime error and do not fabricate success.

## 8. Real DeepSeek API smoke

With a real `DEEPSEEK_API_KEY`, execute at least one official SDK turn through the real DSH runtime.

Use a simple, deterministic prompt that does not depend on repository modification, for example asking for a short sentinel response.

Capture:
- profile used;
- provider;
- model;
- session id;
- `finish_reason`;
- non-empty `final_response`;
- runtime initialization success;
- whether a second turn in the **same session** succeeds.

Recommended two-turn smoke:

Turn 1:
- ask the model to return a unique harmless sentinel token/text.

Turn 2, same session:
- ask it to state the sentinel from the previous turn.

Acceptance:
- both turns complete;
- session continuity is demonstrated;
- no credential is printed.

Do not test knowledge_curator business behavior yet.

## 9. Error-path smoke

Where practical without burning excessive API calls, cover:
- missing API key;
- invalid model;
- invalid/nonexistent profile or configuration;
- initialization failure surfaces clearly;
- request timeout configuration plumbing;
- runtime close/cleanup.

Do not intentionally spam 429/5xx endpoints.

For network/provider errors that cannot be deterministically induced, test the wrapper's handling with fakes/mocks while keeping one real live-path test.

## 10. Version evidence

Record in the executor report:
- installed `deepseek-harness-sdk` version;
- DSH runtime version if exposed;
- pinned/reviewed upstream commit/release;
- Python version;
- OS/platform;
- provider/model used for live smoke.

If the published SDK version differs from the reviewed `0.2.0-rc.1`, stop before claiming compatibility and record the mismatch for Planner review. Do not silently test a different major/minor behavior and call it the same baseline.

## 11. Artifacts

Create a machine-readable smoke artifact without secrets, e.g.:

`results/phase-03-0-dsh-smoke.json`

Suggested fields:
- timestamp;
- sdk_version;
- reviewed_dsh_revision;
- profile;
- provider;
- model;
- live_test_attempted;
- live_test_passed;
- session_continuity_passed;
- finish_reason(s);
- secret_present = false;
- errors/warnings.

Do not store full sensitive environment.

## 12. Tests

Keep all existing **127** knowledge_curator tests green.

Add keyless tests for the Phase 3.0 wrapper/config.

Live API testing must be marked/separated so ordinary unit tests do not require a secret.

Recommended:
- `pytest` -> all deterministic/keyless tests;
- a separate command/marker for real DSH live smoke.

Do not inflate the ordinary test count with a skipped live test and describe it as passed.

## 13. No MCP yet

Phase 3.0 must not create:
- `knowledge_curator.mcp_server`;
- FastMCP/server implementation;
- `@deepseek-ai/dsh-mcp-client` bundle rows;
- DSH Agent preset.

Those begin only after the runtime/API path is proven.

## 14. Completion report

Create:

`results/phase-03-0-executor-report.md`

Include:
- SDK/runtime installation result;
- exact version evidence;
- keyless test command/result;
- live smoke command/method;
- whether live API was actually attempted;
- live result;
- session continuity result;
- provider/model/profile;
- secret-handling proof;
- failures/limitations;
- CONTRACT_GAPS changes;
- public project contracts changed? -> NO;
- implementation commit SHA.

If no API key was available, report:
`LIVE_SMOKE_NOT_RUN_NO_SECRET`
and do not claim Phase 3.0 fully validated.

If API key was available and both turns succeed, report:
`LIVE_SMOKE_PASS`.

## 15. status.json

On completion update:

- phase = "3.0"
- actor = "executor"
- state = "executor_complete"
- latest_commit = actual implementation SHA
- result_expected = "results/phase-03-0-executor-report.md"

If live smoke was not run because no API key was available, retain an explicit field or report status showing that runtime/API validation is incomplete.

## 16. Stop

Stop after Phase 3.0.

Do not start Phase 3.1 MCP bridge or §6.
