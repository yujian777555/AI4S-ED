# Phase SI-1.5 Planner Review — R2 REQUIRED

Date: 2026-10-01  
Planner: ChatGPT  
Reviewed implementation CODE SHA: `c2f2cb24580689b82551bb8f3971d1e75d07da3e`  
Reviewed executor bookkeeping HEAD: `b758ed9def4ee357a83eb5e316b9cd5d8ca8d331`

## Verdict

**NOT ACCEPTED YET — SI-1.5-R2 REQUIRED**

SI-1.5-R1 correctly migrated the product preset, generated MCP patch, documentation, and real keyless stdio subprocess path.

However, the credentialed mounted-DSH qualification path still contains deterministic incompatibilities that would make the live lane fail if executed.

Do not begin SI-2.

## What passed

Verified:

- product preset launches `system.mcp_stdio`;
- generated `integration/dsh/mcp_patch.py` launches `system.mcp_stdio`;
- mounted lane now names `AI4S_SYSTEM_ADAPTER_FACTORY`;
- product README documents the provider contract;
- real keyless stdio subprocess tests cover valid provider, exact four-tool discovery, health identity, curation round-trip, missing-provider fail-closed, and unavailable evidence;
- all frozen Knowledge Curator and SI-1 production-composition blobs remain unchanged.

Planner independently compared the frozen tree from the SI-1.5-R1 handoff to executor HEAD and found **zero frozen blob changes**.

## R2-01 — lane325 direct-vs-DSH identity check is now semantically wrong

The mounted DSH path uses the production-style provider runtime.

Therefore its returned MCP payload correctly reports:

`integration_fixture = false`

The direct reference helper intentionally uses the legacy integration fixture and reports:

`integration_fixture = true`

Current `lane325_kc_evidence_roundtrip.e2e.ts` still requires these two flags to be equal.

That comparison is now invalid by design and would fail in a credentialed live run.

### Required fix

Do not compare the two `integration_fixture` flags for equality.

Instead assert the expected boundary explicitly:

- direct legacy reference: `integration_fixture == true`;
- mounted production-composition DSH path: `integration_fixture == false`.

Continue comparing the actual evidence identity/policy fields that should remain equivalent.

## R2-02 — integration provider evidence corpus does not match the direct reference corpus

The integration-only provider currently builds `EvidenceRetrievalService` using local stub vector/keyword backends that return no candidates.

The direct reference uses the checked-in evidence fixture and therefore returns real fixture hits.

Current lane325 compares chunk identities, coverage, Abstain behavior, and claim policy between those two paths.

With the current provider, those values cannot match in a live run.

### Required fix

Keep the provider test-only and keep all backend classes local to the integration fixture, but make its evidence service operate over the same checked-in deterministic fixture corpus used by the direct reference.

Do **not** use or wrap forbidden `InMemoryVectorSearch`, `InMemoryKeywordSearch`, or `FakeReranker` classes.

Implement protocol-compatible test-local vector/keyword/reranker adapters in:

`integration/system/fixtures/dsh_provider.py`

using the checked-in fixture chunks and the same deterministic filtering/ranking semantics needed for reference parity.

Production composition must still see only test-local protocol-compatible adapter classes.

Add a keyless parity regression proving:

- same evidence chunk ids;
- same coverage keys/states;
- same Abstain decision;
- same guard policy for lane325 claims;
- direct reference is marked integration fixture;
- production-style provider result is not marked integration fixture.

## R2-03 — run_lane325 runner does not configure the new provider contract

`integration/dsh/run_lane325.py` still sets:

`KC_EVIDENCE_INTEGRATION_FIXTURE=1`

globally and does not set:

`AI4S_SYSTEM_ADAPTER_FACTORY`

This runner executes both:

- lane324 baseline control;
- lane325 evidence lane.

The baseline lane does not set the provider itself, so it can fail at MCP startup with the migrated product preset.

### Required fix

In the runner environment set:

`AI4S_SYSTEM_ADAPTER_FACTORY=integration.system.fixtures.dsh_provider:create_provider_bundle`

for both mounted lanes.

Remove global `KC_EVIDENCE_INTEGRATION_FIXTURE` from the runner environment.

The direct-reference subprocess may continue to set the old fixture flag locally and explicitly.

## R2-04 — lane324 baseline must be provider-compatible

`lane324_kc_roundtrip.e2e.ts` mounts the same product preset.

Ensure it receives the provider through the runner environment and add a structural regression proving the baseline control can no longer start without the provider contract being supplied by its qualification runner.

No need to hard-code the provider inside lane324 if the runner supplies it.

## R2-05 — legacy Python MCP live smoke also needs explicit provider wiring

`integration/dsh/mcp_smoke.py` now creates a generated patch that launches `system.mcp_stdio`, but the smoke runner does not itself supply `AI4S_SYSTEM_ADAPTER_FACTORY`.

When this integration smoke is run with a DeepSeek credential but without an externally preconfigured provider, the MCP subprocess will fail closed.

### Required fix

Because this file is integration/qualification code, explicitly provide the integration-only provider when no provider has already been supplied by the caller.

Preferred behavior:

- preserve a caller-supplied `AI4S_SYSTEM_ADAPTER_FACTORY`;
- otherwise set the integration-only provider for the duration of the smoke run;
- do not alter production code;
- do not use `KC_EVIDENCE_INTEGRATION_FIXTURE` as the provider mechanism.

## R2-06 — stale generated-patch template comment

`integration/dsh/patches/knowledge-curator-mcp.patch.yml` still documents:

`args: ['-m', 'knowledge_curator.mcp_server']`

Update this qualification template comment to:

`args: ['-m', 'system.mcp_stdio']`

and document that provider configuration is inherited/injected through the qualification environment.

## R2 acceptance gate

SI-1.5 can be accepted when all of the following hold:

1. no frozen Knowledge Curator or SI-1 production code changes;
2. integration provider uses test-local adapters over the deterministic checked-in evidence corpus;
3. no forbidden InMemory/Fake adapter is used inside the integration provider;
4. keyless provider-vs-direct evidence parity test passes;
5. integration_fixture boundary is asserted as direct=true vs DSH/provider=false, not equality;
6. run_lane325 supplies `AI4S_SYSTEM_ADAPTER_FACTORY`;
7. run_lane325 no longer globally supplies `KC_EVIDENCE_INTEGRATION_FIXTURE`;
8. lane324 baseline receives the provider contract;
9. mcp_smoke supplies an explicit integration provider when caller has not supplied one;
10. generated patch template documentation points to `system.mcp_stdio`;
11. keyless real stdio subprocess suite remains green;
12. existing regression suites remain green;
13. mounted live lane may remain `NOT_RUN_ENV` only because DeepSeek credential/runtime is unavailable, with no known deterministic mismatch remaining.

## Scope

Allowed changes:

- `integration/dsh/**`;
- `integration/system/fixtures/**`;
- `integration/system/tests/**`;
- SI-1.5 report/status bookkeeping.

Do not modify:

- `knowledge_curator/**`;
- `system/composition.py`;
- `system/provider_loader.py`;
- `system/mcp_stdio.py`;
- `planner/CONTRACT_GAPS.md`;
- product preset unless a new defect is discovered and reported first.

## Next action

Execute `planner/latest_plan.md` as **SI-1.5-R2**, push the result, and STOP.

Do not begin SI-2.
