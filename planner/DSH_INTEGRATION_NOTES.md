# DSH Integration Notes — Knowledge Curator

**Official source:** https://github.com/deepseek-ai/deepseek-harness  
**Reviewed revision:** `4878cdabd87d4041bdaff61d04c966883b9fd07a`  
**Release at reviewed revision:** `0.2.0-rc.1`  
**Status:** developer preview; compatibility-breaking changes are explicitly expected upstream.

This document records how the existing Python `knowledge_curator` package maps onto the real DeepSeek Harness architecture. It does not replace AI4S-ED docs 01/03.

## 1. What DSH actually is

Official DSH architecture is **everything-is-a-plugin** on Cordis.

A normal plugin is a TypeScript module:

```ts
import type { Context } from '@deepseek-ai/cordis'

export const name = 'my-plugin'

export function apply(ctx: Context) {
  // register capabilities
}
```

Dependencies are declared with `inject`; for example a model-facing tool waits for `ctx.tools`.

There is no official Python `@dsh.agent` decorator API in the reviewed architecture.

## 2. Agent composition

DSH separates:
- runtime Agent/AgentLoop;
- model/tool/persistence services;
- **agent presets** that select child plugins for an Agent;
- profiles/bundles that compose the application at boot.

Official preset shape:

```yaml
- id: agent-preset-registry
  name: '@deepseek-ai/dsh-agent-preset-registry'
  config:
    default: knowledge-curator

- id: preset-knowledge-curator
  name: '@deepseek-ai/dsh-agent-preset'
  config:
    id: knowledge-curator
    plugins:
      # knowledge-curator-specific capability rows here
```

Therefore AI4S-ED's `knowledge_curator` identity should ultimately be represented by an Agent preset/capability composition, not by replacing DSH AgentLoop.

## 3. Tool registration

Native DSH tools are registered on `ctx.tools` with `defineTool`:

```ts
import { defineTool } from '@deepseek-ai/dsh-tools'

export const inject = ['tools']

export function apply(ctx: Context) {
  ctx.tools.register(defineTool({
    name: '...',
    description: '...',
    parameters: { /* ... */ },
    output: { /* ... */ },
    async execute(args) {
      // ...
    },
  }))
}
```

This is the correct DSH-facing surface for deterministic curator capabilities that the model/agent must invoke.

## 4. Python SDK role

The official Python SDK:

```py
from deepseek_harness import DeepSeekHarness

with DeepSeekHarness(
    dsh_home='/absolute/isolated-home',
    cwd='/absolute/workspace',
    provider='deepseek-official',
    model='...',
) as harness:
    result = harness.run('...', session_id='...')
```

The SDK does **not** host a separate Python Agent implementation.

It launches the bundled `dsh` process (normally `--profile sdk`) and talks to it via line-delimited JSON-RPC.

The selected profile owns:
- agent composition;
- credentials;
- persistence;
- tools;
- shutdown behavior.

The SDK is ideal for:
- integration/e2e tests;
- programmatically driving a DSH-hosted knowledge-curator Agent;
- selecting provider/model;
- exercising real DeepSeek API calls.

It is not a replacement for the DSH plugin/preset layer.

## 5. Recommended bridge for the existing Python core

The existing `knowledge_curator` Python core should **not be rewritten into TypeScript**.

Preferred architecture:

```text
DeepSeek Harness
  profile / bundle
       |
       v
knowledge-curator Agent preset
       |
       v
@deepseek-ai/dsh-mcp-client
       |
       | stdio MCP
       v
Python knowledge_curator MCP server
       |
       v
existing Python core
  §5 curation/commit
  §6 evidence guard
  §7 revision lifecycle
```

Reason:
- DSH officially supports external MCP servers as native model-facing tools;
- local programs are explicitly supported through `transport: stdio`;
- discovered tools are registered into `ctx.tools`;
- reconnect/timeout/tool discovery are DSH-owned;
- Python domain code remains reusable/testable outside DSH;
- no custom cross-language wire protocol needs to be invented.

Illustrative DSH row:

```yaml
- id: mcp-knowledge-curator
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: knowledge_curator
    transport: stdio
    command: python
    args: ['-m', 'knowledge_curator.mcp_server']
    failOnStartupError: true
```

Exact executable/env/cwd and Python MCP implementation are not frozen yet.

DSH will expose server tools with stable names such as:

```text
mcp__knowledge_curator__curate
mcp__knowledge_curator__search_evidence
mcp__knowledge_curator__revise
```

Final tool names must match the 03 boundaries and should remain minimal.

## 6. Bundle/package shape

A DSH bundle declares its patch in `package.json`:

```json
{
  "dsh": {
    "bundle": {
      "patch": "./cordis.patch.yml"
    }
  }
}
```

Expected final repository shape can therefore become:

```text
knowledge_curator/
  ... existing Python core ...
  mcp_server/                  # Python MCP adapter, thin

dsh/
  knowledge-curator-bundle/
    package.json
    cordis.patch.yml
    src/index.ts               # thin bundle/plugin entry if required
    tests/
  agent-preset/
    ... composition rows or bundle-owned preset ...
```

Do not move deterministic science logic into the TS wrapper.

## 7. DeepSeek model/API

Official SDK supports:
- `provider`
- `model`
- optional `reasoning_effort`
- optional `max_tokens`
- explicit `dsh_home`
- optional `base_url` / `api_key` override

Default shipped composition registers `deepseek-official`.

For AI4S-ED, real API testing should use the official DSH route rather than a hand-written HTTP client when testing the final Agent behavior.

## 8. Revised implementation sequence

Current Phase 2.2 remains unchanged.

After §5.4 is accepted:

### Phase 3.0 — DSH runtime/API smoke
- pin a DSH release/revision;
- install `deepseek-harness-sdk`;
- create isolated `DSH_HOME`;
- launch `sdk-minimal` / `sdk`;
- verify provider/model/API credential path;
- verify session lifecycle and error handling;
- no curator business logic rewrite.

### Phase 3.1 — Python MCP adapter
- expose the minimum curator capabilities as MCP tools;
- deterministic unit tests remain direct Python tests;
- MCP contract tests run without a real LLM.

### Phase 3.2 — DSH bundle + knowledge-curator Agent preset
- install/configure `dsh-mcp-client`;
- select curator tools and prompt/persona for the preset;
- ensure other agents' tools are not accidentally included;
- e2e launch through official Python SDK.

### Phase 3.3 — §6 evidence/citation/Abstain
- implement the remaining §6 core;
- expose only the intended capabilities through the MCP/DSH surface;
- use real model reasoning only where deterministic logic is insufficient.

### Later — §7 lifecycle + full project integration

## 9. Stability rule

DSH upstream is explicitly developer preview.

Before any final integration/release:
- pin the DSH package version/commit;
- do not track master implicitly in production;
- keep DSH-specific code thin;
- run adapter contract + e2e tests against the pinned revision;
- upstream changes must not force a rewrite of `knowledge_curator/core`.
