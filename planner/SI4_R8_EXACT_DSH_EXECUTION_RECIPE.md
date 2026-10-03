# SI-4-R8 — Exact Pinned DSH Execution Recipe

This is not a design document. It is the minimum runtime recipe required for
final acceptance.

Pinned DSH source:
- version: 0.2.0-rc.1
- SHA: 4878cdabd87d4041bdaff61d04c966883b9fd07a

Authoritative model:
`packages/preset/agent-preset-registry/tests/harness.ts`

## A. Run inside the pinned DSH workspace

The simplest trustworthy qualification path is to execute the test from the
pinned DSH workspace, where all workspace packages resolve naturally.

Do not try to simulate the DSH module graph from the AI4S checkout.

Qualification procedure:

1. locate/clone the exact pinned DSH checkout;
2. verify:
   `git rev-parse HEAD == 4878cdabd87d4041bdaff61d04c966883b9fd07a`;
3. install/build with the same successful pinned environment already used in
   earlier DSH qualification;
4. copy the exact AI4S shipped bridge-plugin.js into a temporary pinned-DHS test
   fixture location;
5. SHA-256 both files and require exact equality;
6. create a temporary Vitest file inside the pinned
   `packages/preset/agent-preset-registry/tests/` tree;
7. run that exact Vitest file with pinned workspace resolution;
8. delete temporary DSH test/fixture files;
9. commit only the AI4S-side recipe/evidence, not DSH changes.

## B. The temporary Vitest must use the official harness services

Use imports equivalent to pinned official harness:

```ts
import { Context } from '@deepseek-ai/cordis'
import Loader from '@deepseek-ai/cordis-plugin-loader'
import Group from '@deepseek-ai/cordis-plugin-group'
import LlmRuntime, { ToolCallId } from '@deepseek-ai/dsh-llm'
import SessionStore, { SessionId } from '@deepseek-ai/dsh-session'
import SessionProjectionRegistry from '@deepseek-ai/dsh-session-projection'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import AgentRegistry from '@deepseek-ai/dsh-agent'
import AgentLoop from '@deepseek-ai/dsh-agent-loop'
import AgentPresets from '../src/index.ts'
```

Mirror official `harness()`, `declare()`, and `agentOn()`.

## C. Minimal real test

The test must:

```ts
const ctx = await harness()

await declare(ctx, {
  id: 'knowledge-curator',
  plugins: [
    { name: exactCopiedPluginFileUrl },
  ],
})

const agent = await agentOn(ctx, 'kc-r8', 'knowledge-curator')

const names = ctx.tools.schemas(agent).map(x => x.name)

expect(names).toContain('knowledge_curator_commit')
expect(names).toContain('knowledge_curator_revision')
```

Then execute:

```ts
const commit = await ctx.tools.execute({
  signal: new AbortController().signal,
  callId: ToolCallId('kc-r8-commit'),
  name: 'knowledge_curator_commit',
  arguments: COMMIT_PAYLOAD,
  agent,
})

expect(commit.isError).toBe(false)
expect(commit.value).toMatchObject({
  status: 'published',
  commit_attempted: true,
})
```

Then execute revision similarly and assert the exact fixture-defined status,
preferably `approval_required`.

## D. Environment for the spawned Python bridge

Set on the Vitest process:

- `AI4S_KC_WORKSPACE=<AI4S-ED checkout>`
- `AI4S_KC_PYTHON=<python executable>`
- `AI4S_SYSTEM_ADAPTER_FACTORY=<qualification provider factory>`

The plugin inherits these env vars and spawns the real AI4S Python bridge.

The shipped plugin/runtime itself must contain no fixture imports.

## E. Evidence capture

Capture:
- DSH git SHA;
- command;
- exit code;
- Vitest stdout;
- exact tool names;
- commit `ToolExecutionResult.value`;
- revision `ToolExecutionResult.value`;
- plugin SHA pair.

Write those to:

`results/phase-si-4-r8-dsh-qualification.md`

## F. If the test cannot run

Do NOT replace it with:
- string checks;
- direct Python subprocess;
- a fake ctx;
- manual report claims.

Return:

`BLOCKER: <exact reason>`

with:
- command;
- stack trace;
- package/module resolution error;
- pinned source path involved.

That is preferable to another false PASS.
