# Phase SI-1.5 Planner Review — R1 REQUIRED

Date: 2026-10-01  
Planner: ChatGPT  
Reviewed implementation CODE SHA: `fd000223b308b209b02f3163e2eee72a6637aab2`  
Reviewed executor bookkeeping HEAD: `1c2592f786eec1456f550d94d6778f231d2dbc22`

## Verdict

**NOT ACCEPTED YET — SI-1.5-R1 REQUIRED**

The product preset itself was correctly switched to `system.mcp_stdio`, and all frozen Knowledge Curator / SI-1 production-composition blobs remain unchanged.

However, the DSH production bootstrap migration is not yet complete across the actual qualification/live paths.

Do not begin SI-2.

## What passed

The committed product preset now uses:

`python -m system.mcp_stdio`

and preserves:

- stdio transport;
- `AI4S_KC_PYTHON`;
- `AI4S_KC_WORKSPACE`;
- `failOnStartupError: true`;
- the existing four public MCP tools;
- no orchestrator/workflow;
- no curation-to-commit wiring.

Planner independently compared the frozen tree from SI-1.5 handoff to final executor HEAD.

No changes were found under:

- `knowledge_curator/core/**`
- `knowledge_curator/schemas/**`
- `knowledge_curator/ports/**`
- `knowledge_curator/retrieval/**`
- `knowledge_curator/mcp_server/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `planner/CONTRACT_GAPS.md`

## R1-01 — Actual mounted-DSH live lane still uses the old fixture contract

`integration/dsh/lane325_kc_evidence_roundtrip.e2e.ts` still sets:

`KC_EVIDENCE_INTEGRATION_FIXTURE=1`

but does not set:

`AI4S_SYSTEM_ADAPTER_FACTORY`

The product preset now launches `system.mcp_stdio`, which requires a provider.

Therefore this mounted-Agent lane will fail closed at MCP startup when it actually mounts the updated product preset.

The current Python integration/system tests validate the preset text and call `build_system_mcp_server(...)` directly, but they do not prove the real DSH-mounted Agent path succeeds with the new provider contract.

### Required fix

Update the mounted DSH qualification/live lane so its environment explicitly supplies the integration-only provider:

`integration.system.fixtures.dsh_provider:create_provider_bundle`

Remove reliance on `KC_EVIDENCE_INTEGRATION_FIXTURE` for the production-bootstrap path.

If a direct-reference helper still needs the old fixture for comparison, keep that fixture usage isolated to the direct-reference process only. It must not be the DSH MCP server's production composition mechanism.

## R1-02 — Generated DSH MCP patch still launches the old server

`integration/dsh/mcp_patch.py` still generates:

`["-m", "knowledge_curator.mcp_server"]`

This is an active DSH integration path used by the Python MCP smoke/qualification tooling.

It must be migrated to:

`["-m", "system.mcp_stdio"]`

and the spawned MCP subprocess must receive an explicit provider configuration.

Do not hard-code the provider in production product configuration. Test/qualification helpers may inject the integration-only provider explicitly.

## R1-03 — Product DSH documentation is stale

`dsh/knowledge-curator/README.md` still documents:

`python -m knowledge_curator.mcp_server`

and only lists:

- `AI4S_KC_PYTHON`
- `AI4S_KC_WORKSPACE`

It does not document the new required:

`AI4S_SYSTEM_ADAPTER_FACTORY`

This violates the SI-1.5 operator-documentation requirement.

### Required fix

Update the product README to document:

- `system.mcp_stdio`;
- `AI4S_SYSTEM_ADAPTER_FACTORY`;
- missing provider => startup fails closed;
- provider variable is an identifier, not a secret;
- adapter-specific secrets remain deployment-owned and must not be committed;
- production never auto-enables the integration fixture.

## R1-04 — Add one real stdio subprocess proof

Add a deterministic keyless test that actually launches:

`python -m system.mcp_stdio`

through the same stdio MCP transport shape used by DSH.

The subprocess environment must include:

`AI4S_SYSTEM_ADAPTER_FACTORY=integration.system.fixtures.dsh_provider:create_provider_bundle`

Then initialize an MCP client session and prove:

1. subprocess starts successfully;
2. exactly four existing tools are discovered;
3. `knowledge_curator_health` reports the injected provider identity;
4. `curate_assertion_set` completes one round trip.

Also add a subprocess startup-negative case with no provider and prove it fails closed.

This test does not require a DeepSeek model/API key.

## Acceptance gate

SI-1.5-R1 is accepted only if:

1. product preset still uses `system.mcp_stdio`;
2. mounted DSH lane supplies `AI4S_SYSTEM_ADAPTER_FACTORY`;
3. mounted DSH lane no longer relies on `KC_EVIDENCE_INTEGRATION_FIXTURE` to configure the MCP server;
4. `integration/dsh/mcp_patch.py` generates `system.mcp_stdio`;
5. qualification/smoke subprocess receives explicit provider configuration;
6. product README documents the production provider contract;
7. real stdio subprocess with valid provider discovers exactly four tools;
8. real stdio subprocess without provider fails closed;
9. curation round-trip succeeds through the real stdio subprocess;
10. Knowledge Curator frozen tree remains unchanged;
11. SI-1 frozen production composition remains unchanged;
12. no orchestrator/workflow/commit wiring is added.

## Scope

Allowed changes:

- `dsh/knowledge-curator/README.md`;
- `integration/dsh/**`;
- `integration/system/tests/**` if needed;
- SI-1.5 report/status bookkeeping.

Do not modify:

- frozen Knowledge Curator files;
- frozen SI-1 production composition/bootstrap files;
- `planner/CONTRACT_GAPS.md`.

## Next action

Execute `planner/latest_plan.md` as **SI-1.5-R1**, push the result, and STOP.

Do not begin SI-2.
