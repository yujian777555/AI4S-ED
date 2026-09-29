# Phase 3.2 Plan — DSH 0.2 Source-Pinned Knowledge Curator Agent Package

**Planner:** ChatGPT  
**Executor:** MiMo  
**State:** READY_FOR_EXECUTOR

## 0. Goal

Produce the first **real DSH Agent package artifact** for `knowledge_curator`, while keeping the module boundary correct.

This round is about:
1. qualifying official DSH 0.2.0-rc.1 from source;
2. creating a configuration-only `knowledge-curator` Agent Preset bundle;
3. validating that bundle with the real 0.2 Loader/config/preset implementation.

This round does **not** yet run the final live preset-aware DeepSeek turn. That will be the next small acceptance round after package qualification.

## 1. Fixed upstream baseline

Use only:

- repository: `https://github.com/deepseek-ai/deepseek-harness`
- commit: `4878cdabd87d4041bdaff61d04c966883b9fd07a`
- package version at that commit: `0.2.0-rc.1`

Official source requirements at this revision:
- Node: `^22.19.0 || >=24.0.0`
- pnpm: `11.7.0`

Official source run path:
```bash
git clone https://github.com/deepseek-ai/deepseek-harness.git
git checkout 4878cdabd87d4041bdaff61d04c966883b9fd07a
pnpm install
pnpm run build
pnpm dsh --version
```

Do not follow `master` implicitly.

Do not commit the DSH source tree into AI4S-ED.

Use an external/cache directory and record its exact commit.

## 2. Read before implementation

AI4S-ED:
- `docs/01-总体架构与数据流设计.md`
- `docs/03-文献自动调研与知识入库流水线.md`
- `planner/KNOWLEDGE_CURATOR_BOUNDARY.md`
- `planner/DSH_INTEGRATION_NOTES.md`
- `planner/phase-03-1-1-review.md`
- `planner/CONTRACT_GAPS.md`
- `status.json`

Official DSH at the pinned commit:
- root `README.md`
- root `package.json`
- `packages/preset/agent-preset/README.md`
- `packages/preset/agent-preset-registry/README.md`
- `packages/preset/persona/README.md`
- `packages/mcp/mcp-client/README.md`
- `apps/cli/reference/README.md`
- `packages/sdk/server/src/server.ts`

## 3. Product boundary: what this module owns

The final knowledge_curator package **may own**:
- one Agent Preset declaration;
- its persona/instructions;
- its MCP client child capability;
- its Python MCP server already implemented;
- tests/contract evidence for the package.

It **must not own**:
- the system-wide `agent-preset-registry`;
- the overall project's root Agent/session factory;
- orchestrator;
- other agents' presets;
- global provider/model selection;
- global DSH profile.

Therefore the product bundle must not silently insert a new global registry as if it owns the platform.

## 4. Create the product DSH bundle

Recommended:

```text
dsh/
└── knowledge-curator/
    ├── package.json
    ├── cordis.patch.yml
    └── README.md
```

Prefer a **configuration-only bundle**. No TypeScript Host/Client code is needed unless the official Loader proves it is strictly necessary.

Official bundle manifest pattern:

```json
{
  "name": "@ai4s-ed/knowledge-curator-dsh",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "dsh": {
    "bundle": {
      "patch": "./cordis.patch.yml"
    }
  }
}
```

Do not invent a JS plugin just to wrap YAML.

## 5. Bundle must declare exactly one Agent Preset

Insert one row:

```text
@deepseek-ai/dsh-agent-preset
config.id = knowledge-curator
```

Recommended metadata:
- id: `knowledge-curator`
- name: `AI4S-ED Knowledge Curator`
- description: narrowly describe §5 curation / trusted knowledge gate.

Do not declare this preset as the system default inside the product bundle.

The deployment/integration host chooses defaults.

## 6. Persona belongs inside the preset

Use the official:

`@deepseek-ai/dsh-persona`

Keep the persona short and boundary-oriented. It should state, in substance:

- role = AI4S-ED knowledge_curator;
- normalize/check evidence completeness, conflicts and quality through provided curator tools;
- do not act as lit_researcher, orchestrator, proposer, critic, validator, or evaluation scheduler;
- do not invent scientific facts;
- when asked to curate an AssertionSet, use the curator MCP tool rather than reproducing deterministic §5 rules in model prose.

Do not put §6 behavior in the persona yet.

Do not paste huge architecture docs into the prompt.

## 7. MCP client belongs inside the preset child plugins

Inside `config.plugins`, include:

`@deepseek-ai/dsh-mcp-client`

with:
- `serverName: knowledge_curator`
- `transport: stdio`
- `args: ["-m", "knowledge_curator.mcp_server"]`
- `failOnStartupError: true`
- bounded `toolCallTimeoutMs`.

Do not hard-code a developer-specific Python absolute path.

Use non-secret runtime configuration, e.g. Loader expressions/environment:
- `AI4S_KC_PYTHON` with safe fallback appropriate for the environment;
- `AI4S_KC_WORKSPACE` / cwd with explicit integration override.

Do not copy `DEEPSEEK_API_KEY` into the MCP child environment.

Remember official MCP stdio scrubs ambient secret-like variables; pass only what the child actually needs.

## 8. No registry in the product bundle

Do **not** insert:

`@deepseek-ai/dsh-agent-preset-registry`

into the product bundle.

Reason: registry ownership is global/project-level.

For standalone qualification only, create a separate integration overlay/fixture that provides:
- one registry;
- default = knowledge-curator;
- the product bundle/preset declaration.

That integration fixture is not the product bundle.

## 9. Important official 0.2 creation rule

At this revision, neither the ordinary SDK server nor headless runner automatically joins a configured roster for their root Agent.

Official source explicitly requires preset composition to happen during Agent creation:

```ts
setup: agentCtx =>
  ctx.agentPresets.mount(agentCtx, 'knowledge-curator')
```

`mount()` is intended for an unpublished Agent inside `agents.create(... setup ...)`.

Therefore:
- do not use `agent/created` as a late mount workaround;
- do not patch/fork official `packages/sdk/server/src/server.ts`;
- do not claim preset execution merely because the preset appears in config.

Phase 3.2 only qualifies package/config activation. The next live phase will use a test-only host that creates its Agent with the official setup/mount contract.

## 10. Source build qualification

On the executor machine, build the pinned official checkout.

Record:
- exact commit;
- Node version;
- pnpm version;
- OS;
- `pnpm install` outcome;
- `pnpm run build` outcome;
- `pnpm dsh --version`.

Expected DSH version: `0.2.0-rc.1`.

If source build fails:
- capture the first real blocking error;
- do not silently fall back to 0.1.5;
- do not change the pinned commit;
- do not patch upstream source unless the failure is purely environment-specific and the workaround changes no source.

## 11. Real Loader/config qualification

Using the source-built 0.2 dsh:

- initialize an isolated DSH_HOME/profile suitable for config inspection;
- install/link the local AI4S-ED bundle using the official plugin/bundle mechanism or apply its patch as an invocation overlay where appropriate;
- run `--dump-config` / `--dump-config-schema` or the nearest official config inspection path;
- prove the product row resolves as `@deepseek-ai/dsh-agent-preset`;
- prove the child persona and MCP client package names resolve under the source-built installation;
- prove no duplicate registry is introduced by the product bundle.

Do not treat YAML text parsing alone as qualification.

The real 0.2 Loader must parse/resolve it.

## 12. Preset activation qualification without live LLM

Create a test-only integration composition that supplies the registry and the product preset.

Use the official preset registry API/test seam where practical to verify:
- roster contains `knowledge-curator`;
- preset diagnostic/broken is absent;
- child plugins activate;
- no service leaks are reported by preset activation;
- product preset can be mounted into a test Agent scope using the official `agentPresets.mount(...)` contract.

A real DeepSeek turn is **not required in Phase 3.2**.

If mounting a full Agent scope requires too much non-product harness code, stop at real Loader + registry activation and document exactly what remains for Phase 3.2.1. Do not fake a mounted Agent.

## 13. Bundle contract tests in AI4S-ED

Add keyless tests that inspect the product bundle:
- exactly one knowledge-curator preset declaration;
- no registry row in product bundle;
- persona is present and boundary-safe;
- MCP serverName is `knowledge_curator`;
- MCP args target `knowledge_curator.mcp_server`;
- no hard-coded local Python/user path;
- no API key/secret value;
- no §6/§7 tool names;
- no other Agent presets.

Keep:
- 49 integration tests green;
- 127 knowledge_curator tests green.

## 14. Do not change accepted MCP

The Python MCP server and public tool are frozen:

`mcp__knowledge_curator__curate_assertion_set`

Phase 3.2 may adjust only packaging/config needed to launch it from the 0.2 preset.

Do not rewrite codec/core/tool semantics.

## 15. Deliverables

Create:
- `dsh/knowledge-curator/package.json`
- `dsh/knowledge-curator/cordis.patch.yml`
- `dsh/knowledge-curator/README.md`
- integration-only qualification scripts/fixtures under `integration/dsh/`
- `results/phase-03-2-dsh-package-qualification.json`
- `results/phase-03-2-executor-report.md`

The JSON artifact should include:
- upstream repo;
- upstream commit;
- DSH version;
- node_version;
- pnpm_version;
- source_build_passed;
- loader_config_passed;
- preset_declared;
- preset_broken;
- preset_mount_tested;
- preset_mount_passed;
- product_bundle_contains_registry=false;
- public MCP tool expected;
- errors/warnings.

## 16. CG-015

Keep CG-015 open until:
- 0.2 source build succeeds;
- product preset resolves/activates;
- a later live preset-aware Agent smoke succeeds.

Do not close it merely because package.json says 0.2.0-rc.1.

## 17. Forbidden

Do not:
- modify DeepSeek Harness source;
- vendor its source into AI4S-ED;
- own the system registry;
- implement the overall root Agent factory;
- start §6 or §7;
- add production L2/L3 adapters;
- expose new scientific business tools;
- change docs/01 public architecture.

## 18. status.json

On completion:
- phase = "3.2"
- actor = "executor"
- state = "executor_complete"
- latest_commit = actual AI4S-ED implementation SHA
- result_expected = "results/phase-03-2-executor-report.md"

Stop after Phase 3.2.
