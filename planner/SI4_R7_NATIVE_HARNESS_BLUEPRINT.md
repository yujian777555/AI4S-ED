# SI-4-R7 Native DSH Harness Blueprint

Pinned DSH: `0.2.0-rc.1`  
Pinned SHA: `4878cdabd87d4041bdaff61d04c966883b9fd07a`

This blueprint is based directly on:
- `packages/preset/agent-preset-registry/tests/harness.ts`
- `packages/preset/agent-preset-registry/tests/registry.spec.ts`
- `packages/core/tools/tests/scoped.spec.ts`

The goal is to stop guessing and execute the shipped curator plugin through the
same services used by pinned DSH tests.

## 1. Real service stack

Use the pinned packages:

```ts
import { Context } from '@deepseek-ai/cordis'
import Loader from '@deepseek-ai/cordis-plugin-loader'
import Group from '@deepseek-ai/cordis-plugin-group'
import LlmRuntime from '@deepseek-ai/dsh-llm'
import SessionStore, { SessionId } from '@deepseek-ai/dsh-session'
import SessionProjectionRegistry from '@deepseek-ai/dsh-session-projection'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import AgentRegistry from '@deepseek-ai/dsh-agent'
import AgentLoop from '@deepseek-ai/dsh-agent-loop'
import AgentPresets from '@deepseek-ai/dsh-agent-preset-registry'
```

If the exact package export for AgentPresets is not published by package name
in the pinned workspace, import the pinned source module exactly as the official
test does. Do not substitute a fake registry.

## 2. Harness initialization

Mirror the official harness:

```ts
const ctx = new Context()
ctx.baseUrl = new URL('./fixtures/', import.meta.url).href

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

## 3. Register the preset using the exact shipped plugin

For a source-checkout qualification, copy the exact shipped
`bridge-plugin.js` bytes into a temporary pinned-DSH fixture location where
workspace package resolution can resolve `@deepseek-ai/dsh-tools`.

Compute SHA-256 before and after copy and assert equality.

Use a complete `file:` URL for the qualification fixture plugin, like pinned
official tests do.

The product `cordis.patch.yml` must still use the installed package subpath:

`@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`

These are two separate proofs:
- source harness proves exact plugin behavior;
- installed-profile qualification proves product package resolution.

## 4. Register a test preset

Conceptually:

```ts
await ctx.plugin({
  inject: ['agentPresets'],
  async* apply(child) {
    yield await child.agentPresets.register({
      id: 'knowledge-curator',
      plugins: [
        {
          name: shippedPluginFileUrl,
          config: {},
        },
      ],
    })
  },
})
```

For full product qualification, also mount persona/MCP children or prove their
existing bundle tests independently. The native bridge acceptance specifically
must load the exact shipped bridge child.

## 5. Create/mount the real agent

Mirror official `agentOn()`:

```ts
const handle = await ctx.agents.create({
  sessionId: SessionId('kc-r7'),
  setup: async (agentCtx) => {
    await ctx.agentPresets.mount(agentCtx, 'knowledge-curator')
  },
})

const agent = handle.agent
```

## 6. Verify scoped visibility

```ts
const scoped = ctx.tools.schemas(agent).map(row => row.name)
if (!scoped.includes('knowledge_curator_commit')) throw new Error(...)
if (!scoped.includes('knowledge_curator_revision')) throw new Error(...)

const global = ctx.tools.schemas().map(row => row.name)
if (global.includes('knowledge_curator_commit')) throw new Error(...)
if (global.includes('knowledge_curator_revision')) throw new Error(...)
```

## 7. Execute commit through real ToolRuntime

```ts
import { ToolCallId } from '@deepseek-ai/dsh-llm'

const commit = await ctx.tools.execute({
  signal: new AbortController().signal,
  callId: ToolCallId('kc-r7-commit'),
  name: 'knowledge_curator_commit',
  arguments: commitPayload,
  agent,
})

if (commit.isError) {
  throw new Error(JSON.stringify(commit.error))
}

if (commit.value.status !== 'published') {
  throw new Error(`unexpected commit status: ${JSON.stringify(commit.value)}`)
}
```

This call MUST traverse:
- ToolRuntime input validation;
- plugin execute;
- JS spawn/stdin;
- Python stdio bridge;
- provider factory from ENV;
- CuratorAgentBridge;
- CurationCommitWorkflow;
- ToolRuntime output validation/rendering.

## 8. Execute revision through real ToolRuntime

```ts
const revision = await ctx.tools.execute({
  signal: new AbortController().signal,
  callId: ToolCallId('kc-r7-revision'),
  name: 'knowledge_curator_revision',
  arguments: revisionPayload,
  agent,
})

if (revision.isError) {
  throw new Error(JSON.stringify(revision.error))
}
```

Assert one exact fixture-defined outcome, preferably:
- `approval_required` without approval.

If qualification also supplies a valid approval, assert:
- `finalized`.

Do not allow a three-way status set in an acceptance test.

## 9. Static defineTool import

The shipped plugin should begin with:

```js
import { spawn } from 'node:child_process'
import { defineTool } from '@deepseek-ai/dsh-tools'
```

No try/catch identity fallback.

Dependency-resolution failure is a product failure and should stop plugin mount.

## 10. Revision output contract

Because Python currently returns `error: null` on successful non-error outcomes,
use either:

```js
error: {
  required: true,
  oneOf: [
    { type: 'string' },
    { type: 'null' },
  ],
}
```

or omit the key in Python when `error is None`.

Test through real `ctx.tools.execute` so ToolRuntime's
`validateJsonSchemaValue(tool.output.schema, value)` actually runs.

## 11. Product package resolution proof

Separately from the source harness:

1. `pnpm pack` the AI4S curator bundle;
2. install it into an isolated pinned DSH profile/workspace;
3. ensure peer deps resolve;
4. use product `cordis.patch.yml` containing:
   `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`;
5. run config/profile activation;
6. record no broken preset/plugin diagnostic.

`--dump-config` is useful but not enough by itself.

## 12. Qualification artifact

Write actual captured outputs to:

`results/phase-si-4-r7-dsh-qualification.md`

Include:
- exact command;
- exit code;
- Node/pnpm versions;
- pinned DSH SHA;
- shipped plugin SHA;
- copied fixture SHA;
- `ctx.tools.schemas(agent)` output;
- commit ToolExecutionResult summary;
- revision ToolExecutionResult summary;
- installed package resolution result;
- public MCP exact-four result.

No naked PASS lines.
