# SI-4-R6 — Pinned DeepSeek Harness Source Guide for MiMo

Planner: ChatGPT  
Pinned DSH version: `0.2.0-rc.1`  
Pinned DSH source SHA: `4878cdabd87d4041bdaff61d04c966883b9fd07a`

## Purpose

This guide removes the remaining guesswork from SI-4-R6.

It is based on direct inspection of the pinned DeepSeek Harness source, not on
assumptions about a newer DSH release.

The immediate goal is to make the shipped AI4S-ED Knowledge Curator DSH bundle
follow the same plugin/tool/preset execution model that the pinned DSH itself
uses in production and in its own tests.

Read this file before modifying SI-4-R6.

---

# 1. Pinned source files inspected

The following files at DSH SHA
`4878cdabd87d4041bdaff61d04c966883b9fd07a` are authoritative for this R6
integration:

- `docs/cordis-tutorial/01-first-plugin.md`
- `docs/user/develop/basic/tool.md`
- `docs/cookbook/adding-a-tool.md`
- `packages/core/tools/src/schema.ts`
- `packages/core/tools/src/index.ts`
- `packages/core/tools/tests/tools.spec.ts`
- `packages/core/tools/tests/scoped.spec.ts`
- `packages/interaction/tool-ask-user/src/index.ts`
- `packages/shell/tool-bash/src/index.ts`
- `packages/preset/agent-preset-registry/tests/harness.ts`
- `packages/preset/agent-preset-registry/tests/registry.spec.ts`
- `packages/preset/agent-preset-registry/src/index.ts`
- `packages/preset/agent-preset-registry/src/mount.ts`
- `packages/preset/agent-preset/README.md`
- `packages/boot/app-boot/src/index.ts`
- `packages/boot/app-boot/src/compatibility-preflight.ts`
- `packages/boot/app-boot/src/profile-resolution/service.ts`
- `packages/boot/app-boot/src/profile-resolution/resolver.ts`
- `packages/boot/app-boot/README.md`
- `apps/cli/reference/README.md`
- `packages/preset/agent-preset/skills/cordis-plugin-development/references/host-plugin.md`

Do not substitute behavior from master/latest when it differs from this pinned
revision.

---

# 2. Cordis plugin shape: the current R5 lifecycle shape is basically correct

Pinned DSH uses ordinary Cordis plugins.

The canonical function-plugin shape is:

```js
export const name = 'curator-bridge'
export const inject = ['tools']

export function apply(ctx, config) {
  // register resources here
}
```

This is supported.

Therefore R6 does NOT need another class-based lifecycle or a custom
`start()` convention.

Use `name + inject + apply`.

The important missing piece is the tool definition itself.

---

# 3. The tool MUST actually use defineTool

Pinned DSH tool authoring is explicit.

Source:

- `packages/core/tools/src/schema.ts`
- `docs/user/develop/basic/tool.md`
- `packages/interaction/tool-ask-user/src/index.ts`

Required shape:

```js
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'curator-bridge'
export const inject = ['tools']

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'knowledge_curator_commit',
    description: '...',
    parameters: {
      // ParameterSchemaSpec: properties live directly here.
    },
    output: {
      schema: {
        // ValueSchemaSpec
      },
      render: (_args, value) => [
        { type: 'text', text: JSON.stringify(value) },
      ],
    },
    async execute(args, exec) {
      return await callBridge('curate_and_commit', args, exec.signal)
    },
  }))
}
```

R5's current:

```js
ctx.tools.register({
  ...
})
```

is NOT the desired R6 implementation even though `ToolRuntime.register()` can
accept a raw ToolDefinition.

Why use `defineTool` here:

1. it compiles the pinned ParameterSchemaSpec;
2. it validates model-generated arguments before the body;
3. it compiles and validates the canonical output;
4. it gives the exact execution contract used by first-party DSH tools.

R6 acceptance should assert actual import and execution of `defineTool`, not
the presence of the word in a comment.

---

# 4. Correct schema shape

## 4.1 Parameters

Pinned `defineTool` takes a per-property parameter DSL, not a JSON-Schema
object root.

For application-domain payloads that Python validates again, the simplest
honest surface is to use the pinned JSON value field type where supported:

```js
parameters: {
  source_ref_id: {
    type: 'string',
    required: true,
    description: 'Source reference id',
  },
  source_fingerprint: {
    type: 'string',
    required: true,
    description: 'Stable source fingerprint',
  },
  assertion_set: {
    type: 'json',
    required: true,
    description: 'Serialized AssertionSet',
  },
  metadata: {
    type: 'json',
  },
  trace: {
    type: 'json',
  },
}
```

If the exact pinned installed build rejects `type: 'json'` in parameters,
use an explicit object node with `additionalProperties: true`; do not invent
another schema dialect.

Python remains the authority for frozen domain hydration.

## 4.2 Output

Pinned `output.schema` is a ValueSchemaSpec.

An object result needs an explicit object node, e.g.:

```js
output: {
  schema: {
    type: 'object',
    additionalProperties: false,
    properties: {
      status: { type: 'string', required: true },
      commit_attempted: { type: 'boolean', required: true },
      blocked_reason: {
        required: true,
        oneOf: [
          { type: 'string' },
          { type: 'null' },
        ],
      },
    },
  },
  render: (_args, value) => [
    { type: 'text', text: JSON.stringify(value) },
  ],
},
```

The exact output emitted by Python must match the declared schema.

Do not return a content block from `execute`.

`execute` returns the canonical JSON value.
`output.render` produces model-facing text.

This is exactly how pinned first-party tools work.

---

# 5. Tool execution API: use ctx.tools.execute, not direct function calls

Pinned `ToolRuntime` executes a tool with:

```js
const result = await ctx.tools.execute({
  signal: new AbortController().signal,
  callId: 'kc-r6-commit-1',
  name: 'knowledge_curator_commit',
  arguments: payload,
  agent,
})
```

At runtime:

- `result.isError` is the authoritative success/failure bit;
- successful canonical value is `result.value`;
- model-facing rendering is in `result.content`.

For a preset-scoped tool, the `agent` argument is material.

Pinned scoped-tool tests prove:

- `ctx.tools.schemas(agent)` sees scoped tools;
- `ctx.tools.schemas()` does not see a preset-scoped-only tool;
- `ctx.tools.execute(..., agent)` can execute it;
- the same execution without the scoped agent resolves as unknown when the tool
  is not globally visible.

Therefore R6 must execute both curator native tools with the mounted Agent
passed to `ctx.tools.execute`.

---

# 6. Official DSH preset harness: copy this architecture instead of inventing one

The pinned repository already contains almost exactly the qualification harness
we need:

`packages/preset/agent-preset-registry/tests/harness.ts`

Its real service stack is:

```text
Context
  -> Loader
  -> Group builtin
  -> LlmRuntime
  -> SessionStore
  -> SessionProjectionRegistry
  -> SystemPrompt
  -> ToolRuntime
  -> AgentRegistry
  -> AgentLoop
  -> AgentPresetRegistry
```

The source does, conceptually:

```ts
const ctx = new Context()
await ctx.plugin(Loader)
ctx.loader.builtins.group = Group
await ctx.plugin(LlmRuntime)
await ctx.plugin(SessionStore)
await ctx.plugin(SessionProjectionRegistry)
await ctx.plugin(SystemPrompt, { personaPrefix: '' })
await ctx.plugin(ToolRuntime)
await ctx.plugin(AgentRegistry)
await ctx.plugin(AgentLoop, { agents: [] })
await ctx.plugin(AgentPresets, { default: 'knowledge-curator' })
```

The official helper creates an Agent and mounts a preset in its scoped context:

```ts
const handle = await ctx.agents.create({
  sessionId: SessionId('kc-r6'),
  setup: async (agentCtx) => {
    await ctx.agentPresets.mount(agentCtx, 'knowledge-curator')
  },
})

const agent = handle.agent
```

Then the official tests inspect:

```ts
ctx.tools.schemas(agent)
```

This is the source-grounded R6 pattern.

Do NOT replace it with a handwritten fake `ctx.tools`.

---

# 7. Critical newly-discovered bug: do NOT keep './runtime/bridge-plugin.js' inside config.plugins

Current AI4S bundle has used a child row similar to:

```yaml
config:
  plugins:
    - id: curator-bridge
      name: './runtime/bridge-plugin.js'
```

This is risky/wrong for the product wiring.

Pinned app-boot source:

`packages/boot/app-boot/src/index.ts`

contains `anchorInsertedPluginNames()`.

It converts relative plugin names only for actual patch `insert` rows and,
recursively, true Loader `group` rows:

```ts
for (const patch of patches) patch.insert?.forEach(visit)

if (entry.group && Array.isArray(entry.config)) {
  entry.config.forEach(visit)
}
```

An `@deepseek-ai/dsh-agent-preset` row's
`config.plugins` array is NOT a Loader group row.

Therefore the patch parser does not guarantee that:

```
./runtime/bridge-plugin.js
```

inside `config.plugins` is anchored to the Knowledge Curator bundle's patch
directory.

Later, `AgentPresetRegistry` mounts those child plugin rows against its preset
context/base URL.

Pinned official preset tests avoid this ambiguity by using complete `file:`
URLs for local fixture plugins.

Pinned production presets use package specifiers.

## R6 product fix

Prefer the installed package subpath:

```yaml
- id: curator-bridge
  name: '@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js'
```

The current package already exports:

```json
"./runtime/bridge-plugin.js": "./runtime/bridge-plugin.js"
```

Keep that export.

Then verify this exact package-subpath row through a real installed profile.

Do not simply assume it resolves.

---

# 8. Package peer dependencies

The bridge plugin imports:

```js
import { defineTool } from '@deepseek-ai/dsh-tools'
```

Pinned first-party DSH tool packages declare DSH/Cordis peers.

For this out-of-tree bundle, add compatible peer declarations instead of
pretending the plugin has no runtime dependency.

For the pinned delivery, the safest contract is:

```json
"peerDependencies": {
  "@deepseek-ai/dsh-tools": "0.2.0-rc.1",
  "@deepseek-ai/cordis": "~4.0.4"
}
```

If MiMo chooses a semver-compatible range instead, it must still pass pinned
compatibility and runtime qualification.

Pinned app-boot checks `@deepseek-ai/dsh` and `@deepseek-ai/dsh-*` peers
against the running DSH runtime before activation, so this also makes an
incompatible Harness version fail visibly instead of producing an obscure
runtime import error.

---

# 9. Two separate qualifications are needed

Do not try to make one weak test prove everything.

## Qualification A — product bundle resolution

Use a clean isolated DSH 0.2.0-rc.1 profile.

Recommended sequence:

1. initialize a custom profile from the shipped `web` template, because the
   pinned web composition owns `@deepseek-ai/dsh-agent-preset-registry`;
2. install/add the local
   `dsh/knowledge-curator` bundle to that profile;
3. set:
   - `AI4S_KC_WORKSPACE`;
   - `AI4S_KC_PYTHON`;
   - `AI4S_SYSTEM_ADAPTER_FACTORY` for qualification;
4. boot or run the appropriate config/runtime qualification;
5. verify the preset is not broken.

Why web/template with preset support matters:

- base contains ToolRuntime and AgentLoop;
- web adds the AgentPresetRegistry and shipped preset declarations.

A base-only custom profile is not enough to prove this product preset.

Also run:

```text
dsh --profile <qualification-profile> --dump-config
```

This is only a composition check, not the native-tool execution proof.

## Qualification B — actual preset-scoped tool execution

Use the official AgentPreset test architecture described in §6.

The acceptance condition is:

```text
real Context
 -> real ToolRuntime
 -> real AgentPresetRegistry
 -> mounted Agent
 -> ctx.tools.schemas(agent)
 -> ctx.tools.execute(..., agent)
 -> exact shipped bridge plugin
 -> JS spawn/stdin
 -> Python stdio bridge
 -> workflow
```

This is the proof R5 never produced.

---

# 10. Practical way to reuse the pinned official test harness

The pinned registry test fixtures deliberately keep their local test plugins
import-free because plain Node fixture resolution inside the source checkout
does not automatically resolve every workspace TypeScript package from an
arbitrary external file.

Therefore do NOT conclude that a failed ad-hoc import from the AI4S checkout
means the production profile resolver is broken.

Recommended R6 qualification approach:

1. Commit the R6 qualification source under AI4S, e.g.
   `integration/dsh/qualification/knowledge-curator-r6.spec.ts`.
2. During qualification only, copy the exact shipped
   `runtime/bridge-plugin.js` bytes into a uniquely named temporary fixture
   location inside the pinned DSH checkout where
   `@deepseek-ai/dsh-tools` is resolvable.
3. Record/compare a SHA-256 of the source and copied fixture to prove the exact
   shipped plugin was executed.
4. Run the pinned package's Vitest harness using its own workspace dependency
   graph.
5. Remove the temporary fixture/test copy afterward.
6. Commit only the AI4S qualification source and resulting evidence artifact;
   do not commit changes to the DSH repository.

The copied fixture is a test execution location, not a modified implementation.

Alternatively, if the isolated profile installation path already provides a
fully resolvable installed package and MiMo can programmatically access the
real DSH Context there, use that. The requirement is real DSH/Cordis
`ctx.tools` execution, not a particular file location.

---

# 11. Minimal source-grounded native execution assertions

After mounting `knowledge-curator` into a real agent scope:

```ts
const names = ctx.tools.schemas(agent).map(row => row.name)

expect(names).toContain('knowledge_curator_commit')
expect(names).toContain('knowledge_curator_revision')
```

Then:

```ts
const commit = await ctx.tools.execute({
  signal: new AbortController().signal,
  callId: 'kc-r6-commit',
  name: 'knowledge_curator_commit',
  arguments: commitPayload,
  agent,
})

if (commit.isError) {
  throw new Error(JSON.stringify(commit))
}

expect(commit.value).toMatchObject({
  status: 'published',
  commit_attempted: true,
})
```

This is materially different from invoking
`python -m system.curator_agent_bridge_stdio` directly.

For revision, perform the same real ToolRuntime call:

```ts
const revision = await ctx.tools.execute({
  signal: new AbortController().signal,
  callId: 'kc-r6-revision',
  name: 'knowledge_curator_revision',
  arguments: revisionPayload,
  agent,
})
```

Use a qualification provider fixture supplied only through
`AI4S_SYSTEM_ADAPTER_FACTORY`.

The fixture may seed the prior source/work/version required by SI-2B.

The shipped runtime must never import that fixture.

---

# 12. Native replay caveat: do not fake persistence

Each DSH native tool call currently launches a new Python process.

An in-memory qualification provider is therefore recreated for each subprocess.

That means a native §5 replay test cannot honestly prove cross-process
IDEMPOTENT_HIT unless the provider used for qualification persists the stores
across those child processes.

Acceptable choices:

1. use a qualification provider backed by temporary persistent stores and
   prove native replay; OR
2. mark native replay as
   `NOT_APPLICABLE_PROVIDER_PROCESS_ISOLATION`, explain why, and cite the
   already-qualified SI-2A direct workflow replay for workflow semantics.

Do NOT make a fresh in-memory provider return a synthetic
`IDEMPOTENT_HIT`.

---

# 13. Qualification-only revision fixture

For native §7, the new Python process needs prerequisite revision state.

Use a test-only provider factory under integration tests that:

- calls the existing SI-2B provider builder;
- seeds a known WorkRecord;
- seeds the prior SourceVersionRecord;
- creates/publishes the prior snapshot/version;
- binds the prior source version.

Expose that factory only by test environment:

```
AI4S_SYSTEM_ADAPTER_FACTORY=integration.dsh.fixtures.r6_provider:create_r6_provider_bundle
```

Production code still only reads the environment variable.

Then the real native revision tool can reach:

- APPROVAL_REQUIRED without approval;
- FINALIZED with a valid approval, if the fixture/request scope is consistent.

---

# 14. Strict hydration: use frozen schemas, do not invent defaults

R6 still needs to remove remaining semantic fabrication from
`system/curator_agent_bridge_stdio.py`.

Especially fix revision target assertions that currently force:

- `ValueType.NUMBER`;
- `ClaimType.MEASUREMENT`;
- `SourceClaimOrigin.PRIMARY`;
- `Confidence.MEDIUM`.

Hydrate the provided frozen enum values and reject invalid/missing required
values.

Likewise reject empty required identifiers rather than letting
`.get(..., '')` create invalid domain objects.

Also do not fabricate:

```python
CompletenessResult(status=CompletenessStatus.OK)
```

for every incoming CurationReport.

Hydrate the real incoming completeness result according to the frozen
`CurationReport` schema or fail closed.

---

# 15. Recommended bridge-plugin structure

Use this as a shape, adapting schemas to the exact pinned DSL:

```js
import { spawn } from 'node:child_process'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'curator-bridge'
export const inject = ['tools']

function callBridge(action, payload, signal) {
  // Keep the R5 async spawn/stdin implementation.
  // Ensure timeout/abort kills the child and JSON failures reject.
}

const commitTool = defineTool({
  name: 'knowledge_curator_commit',
  description: 'Commit a publishable curated AssertionSet through the accepted application workflow.',
  parameters: {
    source_ref_id: { type: 'string', required: true },
    source_fingerprint: { type: 'string', required: true },
    assertion_set: { type: 'json', required: true },
    metadata: { type: 'json' },
    trace: { type: 'json' },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        status: { type: 'string', required: true },
        commit_attempted: { type: 'boolean', required: true },
        blocked_reason: {
          required: true,
          oneOf: [{ type: 'string' }, { type: 'null' }],
        },
      },
    },
    render: (_args, value) => [
      { type: 'text', text: JSON.stringify(value) },
    ],
  },
  async execute(args, exec) {
    return await callBridge('curate_and_commit', args, exec.signal)
  },
})

const revisionTool = defineTool({
  name: 'knowledge_curator_revision',
  description: 'Apply a prepared revision through RevisionPublicationWorkflow.',
  parameters: {
    package: { type: 'json', required: true },
    target_commit_request: { type: 'json', required: true },
    approval: { type: 'json' },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        status: { type: 'string', required: true },
        error: { type: 'string' },
      },
    },
    render: (_args, value) => [
      { type: 'text', text: JSON.stringify(value) },
    ],
  },
  async execute(args, exec) {
    return await callBridge('revise', args, exec.signal)
  },
})

export function apply(ctx) {
  ctx.effect(() => ctx.tools.register(commitTool))
  ctx.effect(() => ctx.tools.register(revisionTool))
}
```

Using `ctx.effect` for resource registration mirrors pinned plugin practice and
ensures disposal unwinds registrations.

If the exact pinned installed build rejects any shown `json` schema field,
replace only that field with the exact supported object DSL; do not revert to
raw ToolDefinition registration.

---

# 16. Recommended cordis.patch.yml product wiring

Change the child plugin row from a relative filesystem specifier to the bundle
package subpath:

```yaml
- insert:
    - id: preset-knowledge-curator
      name: '@deepseek-ai/dsh-agent-preset'
      config:
        id: knowledge-curator
        name: AI4S-ED Knowledge Curator
        plugins:
          - id: persona
            name: '@deepseek-ai/dsh-persona'
            config:
              # existing persona

          - id: curator-bridge
            name: '@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js'

          - id: mcp-knowledge-curator
            name: '@deepseek-ai/dsh-mcp-client'
            config:
              # existing MCP stdio config
```

Then prove that the installed bundle resolves this row.

Do not call the change complete from `--dump-config` alone.

---

# 17. Product package.json direction

Keep the subpath export:

```json
"./runtime/bridge-plugin.js": "./runtime/bridge-plugin.js"
```

Add the runtime peers required by the plugin:

```json
"peerDependencies": {
  "@deepseek-ai/dsh-tools": "0.2.0-rc.1",
  "@deepseek-ai/cordis": "~4.0.4"
}
```

Do not add DSH packages as copied/vendor code to AI4S.

The product should run against the pinned Harness installation.

---

# 18. What counts as PASS now

## Valid evidence

- real DSH package/preset activation with no broken diagnostic;
- `ctx.tools.schemas(agent)` from real ToolRuntime contains both native tools;
- `ctx.tools.execute(..., agent)` executes the exact shipped bridge plugin;
- returned `ToolExecutionResult.value` contains the expected workflow result;
- SHA evidence shows the qualification copy equals shipped plugin bytes;
- qualification artifact records commands, exit codes and results.

## Not valid evidence

- source contains `defineTool`;
- YAML contains `curator-bridge`;
- direct call to `apply()` with a handwritten fake context;
- direct Python subprocess;
- direct `CuratorAgentBridge`;
- direct workflow call;
- README/report claim.

Those can remain unit/regression tests but do not satisfy native DSH acceptance.

---

# 19. Suggested order for MiMo

Do the work in this order to avoid another long loop:

1. fix `bridge-plugin.js` to truly use pinned `defineTool`;
2. fix its ParameterSchemaSpec / ValueSchemaSpec;
3. change the preset child bridge name to package subpath;
4. add runtime peer dependencies;
5. finish strict Python hydration;
6. create qualification-only seeded provider fixture;
7. implement the real pinned DSH harness by adapting the official
   `agent-preset-registry/tests/harness.ts`;
8. prove `ctx.tools.schemas(agent)`;
9. prove `ctx.tools.execute(..., agent)` for §5;
10. prove `ctx.tools.execute(..., agent)` for §7;
11. run bundle/profile resolution qualification;
12. run pytest regressions;
13. create `results/phase-si-4-r6-dsh-qualification.md`;
14. create R6 executor report;
15. STOP.

---

# 20. Planner expectation

Do not spend another round trying to infer DSH behavior from file names.

The pinned source already gives the intended model:

```text
Bundle patch
  -> AgentPreset definition
  -> preset registry eagerly mounts child plugins
  -> child plugin apply(ctx)
  -> ctx.tools.register(defineTool(...))
  -> Agent joins preset scope
  -> ctx.tools.schemas(agent)
  -> ctx.tools.execute({ ..., agent })
  -> bridge-plugin spawn/stdin
  -> Python application bridge
  -> frozen workflow
```

Implement and qualify exactly that model.
