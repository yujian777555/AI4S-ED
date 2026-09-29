# Phase 3.2.1 Plan — Real Preset Mount + Live Knowledge Curator Agent Smoke

**Planner:** ChatGPT  
**Executor:** MiMo  
**State:** READY_FOR_EXECUTOR

## 0. Goal

Close the only remaining DSH Agent packaging gap.

Prove this exact chain on pinned DSH 0.2.0-rc.1:

```text
source-built DSH 0.2.0-rc.1
  -> real preset registry
  -> profile-installed @ai4s-ed/knowledge-curator-dsh bundle
  -> knowledge-curator preset activates
  -> Agent created with setup: agentPresets.mount(...)
  -> mounted Agent sees persona + curator MCP tool
  -> real DeepSeek turn
  -> exact MCP tool/call
  -> linked tool/result
  -> deterministic core summary
  -> final model response
```

This is still integration qualification. Do not start §6/§7.

## 1. Fixed baselines

AI4S-ED:
- accepted §5.1–§5.4 core;
- accepted Python MCP bridge;
- accepted DSH product bundle structure from Phase 3.2.

DeepSeek Harness:
- repo: `https://github.com/deepseek-ai/deepseek-harness`
- commit: `4878cdabd87d4041bdaff61d04c966883b9fd07a`
- version: `0.2.0-rc.1`
- Node: `^22.19.0 || >=24`
- pnpm: `11.7.0`

Use the existing external checkout. Verify its HEAD before testing.

## 2. Read first

- `planner/phase-03-2-review.md`
- `planner/latest_plan.md`
- `planner/CONTRACT_GAPS.md`
- `dsh/knowledge-curator/package.json`
- `dsh/knowledge-curator/cordis.patch.yml`
- existing Phase 3.1.1 strict MCP event parser/tests.

Pinned DSH source:
- `apps/web/tests/scaffold.ts`
- `apps/web/tests/shipped-composition.e2e.ts`
- `packages/preset/agent-preset-registry/src/index.ts`
- `packages/preset/agent-preset-registry/README.md`.

## 3. Fix config-only bundle dependency policy

Remove:

```json
"@deepseek-ai/dsh-agent-preset": "*",
"@deepseek-ai/dsh-persona": "*",
"@deepseek-ai/dsh-mcp-client": "*"
```

Prefer no DSH plugin dependencies in the product package, matching the official configuration-only MCP bundle pattern.

The running pinned DSH installation already owns these packages and runtime resolution.

Add a regression test:
- no `@deepseek-ai/*` dependency uses `"*"`;
- preferably product package has no `dependencies` field at all.

If real profile installation proves dependencies are required, stop and report the exact resolver error before adding anything. Only exact `0.2.0-rc.1` pins would be acceptable, not wildcard versions.

## 4. Use the real 0.2 Web scaffold as the qualification host

Do not create a production root-Agent factory.

Create an integration-only source qualification runner under `integration/dsh/`.

Recommended approach:
- execute it with the pinned DSH checkout's `pnpm exec tsx`;
- dynamically import the pinned source's `apps/web/tests/scaffold.ts` from `DSH_SRC`;
- do not copy or edit tracked DSH source;
- DSH checkout must be clean before and after.

Use the scaffold's **profile package** support to install/enable:

`dsh/knowledge-curator/`

as a local bundle, rather than merely copying its YAML text.

This proves:
- package manifest;
- `dsh.bundle.patch`;
- runtime plugin resolution;
- preset activation.

If the scaffold's profile package mechanism is unavailable in the exact pinned source, use its documented `extraOverlayPath` fallback and report that fallback explicitly. Profile-package qualification is preferred.

## 5. Keyless runtime activation + mount test

First run without any model call.

Boot the real scaffold with:
- isolated harness home;
- real global registry from the shipped Web composition;
- product bundle enabled;
- `AI4S_KC_PYTHON` pointing to the active Python executable;
- `AI4S_KC_WORKSPACE` pointing to the AI4S-ED repo.

Then verify from the live `ctx`:

### Registry/preset activation
- `ctx.agentPresets.list()` contains exactly the expected `knowledge-curator` row in addition to shipped rows;
- that row has no `broken` diagnostic;
- product bundle did not create a second registry;
- the MCP child actually starts successfully under `failOnStartupError=true`.

### Mount
Create one test Agent:

```ts
const handle = await ctx.agents.create({
  sessionId,
  meta: { cwd: AI4S_ED_ROOT },
  agentOptions: {
    provider: 'deepseek-official',
    model: modelFromEnv
  },
  setup: async agentCtx => {
    await ctx.agentPresets.mount(agentCtx, 'knowledge-curator')
  }
})
```

No prompt is needed for the keyless mount lane.

Assert:
- `ctx.agentPresets.composedPreset(handle.agent.ctx) === 'knowledge-curator'`;
- the mounted Agent's tool schema contains `mcp__knowledge_curator__curate_assertion_set`;
- tool schema lookup is Agent-scoped, not inferred from global catalog text;
- assembled system prompt for that Agent contains the knowledge_curator persona boundary;
- it does not contain §6/§7 claims introduced by this bundle.

Dispose the Agent cleanly.

This is the first authoritative `preset_mount_passed=true` evidence.

## 6. Do not infer activation from dump-config

Update Phase 3.2 qualification semantics:
- `loader_config_passed` remains config-only;
- runtime activation fields must come only from the live scaffold/ctx;
- do not compute `preset_broken` by grepping `--dump-config`.

Keep `--dump-config` as a useful separate config qualification.

## 7. Live preset-aware DeepSeek smoke

Only after keyless activation/mount passes.

Use the same pinned 0.2 scaffold/runtime with the real DeepSeek adapter enabled.

Use:
- `DEEPSEEK_API_KEY` from environment only;
- provider `deepseek-official`;
- model from `DSH_MODEL`;
- do not hard-code an architecture-level model requirement.

Create a fresh Agent with the same official setup/mount contract.

Prompt it with the same deterministic curation fixture used by Phase 3.1.1 and explicitly require:
- call `mcp__knowledge_curator__curate_assertion_set`;
- reply only with:
  - `status=...`
  - `action=...`
  - `confidence=...`

## 8. Strict live evidence

Do not use string scanning.

Read the mounted Agent's actual Session events.

Require exactly matching structural evidence:

```text
tool/call
  data.name == mcp__knowledge_curator__curate_assertion_set
```

and a real linked:

```text
tool/result
```

paired by the official event identity/linkage available in 0.2 (callId and/or source event link as actually emitted).

Record:
- call seq;
- callId;
- exact name;
- result seq;
- isError;
- bounded argument hash/ref id.

No full sensitive prompt dump.

## 9. A == B == C again

For the same fixture:

A = direct Python `KnowledgeCurator.curate()` summary  
B = actual linked 0.2 DSH `tool/result` summary  
C = final model response summary

Require:

`A == B == C`

Expected current fixture:

```text
successful / accept / medium
```

Do not hard-code this as a substitute for computing A.

## 10. Source checkout cleanliness

Before and after Phase 3.2.1 qualification:

```bash
git -C <DSH_SRC> status --porcelain
git -C <DSH_SRC> rev-parse HEAD
```

Acceptance:
- HEAD remains exact pinned commit;
- no tracked or untracked qualification files remain in the DSH checkout.

All AI4S qualification code stays in AI4S-ED.

## 11. Product boundary

Still forbidden:
- product bundle owning global registry;
- production root Agent factory;
- editing/forking DSH source;
- adding other Agent presets;
- §6/§7 implementation;
- changing docs/01 public architecture;
- adding new scientific business tools.

The qualification scaffold is integration/test-only.

## 12. Tests

Keep:
- all 60 existing integration tests green;
- all 127 knowledge_curator tests green.

Add keyless tests for:
- no wildcard DSH dependencies;
- runtime qualification artifact fields;
- exact preset mount evidence schema;
- exact live event evidence parser for 0.2 if its event shape differs from 0.1.5;
- source checkout cleanliness result.

Live DeepSeek smoke remains separate from ordinary pytest.

## 13. Artifact

Create:

`results/phase-03-2-1-dsh-preset-live.json`

Required fields:
- upstream_commit;
- dsh_version;
- product_bundle_profile_installed;
- runtime_preset_activation_passed;
- preset_broken;
- preset_mount_tested;
- preset_mount_passed;
- composed_preset_id;
- persona_visible;
- expected_tool_visible;
- live_test_attempted;
- live_test_passed;
- tool_call_count;
- tool_result_count;
- call evidence summary;
- direct_core_summary;
- tool_result_summary;
- final_response_summary;
- summaries_match;
- credential_available;
- secret_leaked;
- dsh_source_clean_before;
- dsh_source_clean_after;
- errors/warnings.

## 14. CG-015 close rule

Close CG-015 only if all are true:
- DSH 0.2 source build already PASS;
- product bundle real Loader/profile install PASS;
- runtime preset activation PASS;
- preset mount PASS;
- mounted Agent sees persona and curator MCP tool;
- real DeepSeek preset-aware tool call PASS;
- A == B == C;
- source checkout remains clean;
- no mixed DSH plugin versions are installed.

If any item fails, keep CG-015 open and report the exact blocker.

## 15. Report

Create:

`results/phase-03-2-1-executor-report.md`

Include:
- dependency policy fix;
- profile install path used;
- live registry activation result;
- mount result;
- composed preset id;
- persona/tool visibility;
- live DeepSeek result;
- exact tool call/result evidence;
- A/B/C summaries;
- test counts;
- source cleanliness;
- CG-015 decision;
- public contracts changed? NO;
- implementation SHA.

## 16. status.json

On completion:
- phase = "3.2.1"
- actor = "executor"
- state = "executor_complete"
- latest_commit = actual implementation SHA
- result_expected = "results/phase-03-2-1-executor-report.md"

Stop. Do not start §6.
