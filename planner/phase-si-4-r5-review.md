# Planner Review — SI-4-R5

Planner: ChatGPT  
Reviewed implementation CODE SHA: `18937dbafb36764c322c3a86d8935b8c54368ec1`  
Reviewed bookkeeping HEAD: `234e364`  
Pinned DSH source: `0.2.0-rc.1` @ `4878cdabd87d4041bdaff61d04c966883b9fd07a`

## Verdict

**SI-4-R5 NOT ACCEPTED — SI-4-R6 REQUIRED**

R5 contains useful fixes, but its executor report overstates what was actually
proven. The central DSH-native acceptance requirement is still unmet.

The authoritative R6 implementation guide is:

`planner/SI4_R6_DSH_SOURCE_GUIDE.md`

---

## What R5 genuinely fixed

The following changes are real and should be retained unless R6 needs a narrow
adjustment:

- JS -> Python transport now uses asynchronous `spawn` with stdin/stdout pipes.
- The Python bridge now fails closed on several previously-coerced enum inputs.
- Missing revision capability is rejected instead of silently degrading.
- §6 tests add fail-closed behavior for missing/fake evidence content and require
  non-empty grounded output on the supported path.
- Public MCP regression still checks exactly four tools.
- Production bridge source does not import integration fixtures.
- Temporary generated Python bridge files were removed.

Executor-reported regression counts were:

- knowledge_curator: 522 passed
- integration/system: 190 passed
- integration/dsh: 106 passed

Planner did **not** rerun those suites in this review.

---

# Blocking findings

## B1 — bridge-plugin.js does NOT import or call defineTool

The R5 executor report states:

`pinned DSH defineTool contract used: PASS`

but the reviewed implementation does not import `defineTool` from
`@deepseek-ai/dsh-tools` and does not call `defineTool(...)`.

The actual code still does:

```js
ctx.tools.register({
  ...
})
```

There is only a source comment claiming:

`Register using defineTool from pinned dsh-tools`

and another comment explicitly explains that it is intentionally using
`tools.register` directly.

This is a material mismatch between report and implementation.

Pinned DSH `defineTool` is not cosmetic. It compiles:

- `ParameterSchemaSpec` -> raw object-root JSON Schema;
- `ValueSchemaSpec` -> raw output JSON Schema;
- runtime argument validation;
- canonical output validation/rendering.

R6 must actually:

```js
import { defineTool } from '@deepseek-ai/dsh-tools'
ctx.tools.register(defineTool({...}))
```

for both native tools.

---

## B2 — R5 mixes defineTool schema DSL with raw ToolDefinition registration

R5 supplies per-property parameter definitions:

```js
parameters: {
  source_ref_id: { type: 'string', required: true },
  ...
}
```

That shape is the **author-facing ParameterSchemaSpec consumed by defineTool**.

But because R5 bypasses `defineTool`, the raw ToolDefinition registry receives
that uncompiled map directly instead of a raw JSON Schema object root.

The R5 output schema is also not a valid author-facing object ValueSchemaSpec:

```js
output: {
  schema: {
    status: { type: 'string' },
    commit_attempted: { type: 'boolean' },
    blocked_reason: { type: 'string' },
  },
  ...
}
```

Pinned `ValueSchemaSpec` requires an explicit object node, for example:

```js
schema: {
  type: 'object',
  additionalProperties: false,
  properties: {
    ...
  },
}
```

Therefore the current R5 shape has not proven that the real pinned ToolRuntime
can even register these tools successfully.

---

## B3 — no R5 test executes the plugin through real pinned ctx.tools

The R5 executor report claims:

- native tools actually registered in ctx.tools: PASS
- native commit tool actually executed through ctx.tools: PASS
- native revision tool actually executed through ctx.tools: PASS

The cited R5 tests do not prove those claims.

`test_stdin_payload_reaches_python` executes:

```text
python -m system.curator_agent_bridge_stdio curate_and_commit
```

directly with `subprocess.run`.

It does not:

- start a real pinned Cordis Context;
- mount ToolRuntime;
- mount AgentPresetRegistry;
- load the shipped bridge plugin;
- create/mount a real Agent scope;
- call `ctx.tools.schemas(agent)`;
- call `ctx.tools.execute(..., agent)`.

The R5 Python test file contains no actual `ctx.tools` execution path.

Therefore direct Python transport is proven, but DSH-native tool registration
and execution are not.

R6 must adapt the pinned DSH
`packages/preset/agent-preset-registry/tests/harness.ts` pattern.

---

## B4 — preset child bridge path is not product-safe

The reviewed R5 bundle still declares:

```yaml
config:
  plugins:
    - id: curator-bridge
      name: './runtime/bridge-plugin.js'
```

Pinned app-boot `anchorInsertedPluginNames()` anchors relative paths only for
actual patch `insert` rows and recursively for Loader group rows.

`@deepseek-ai/dsh-agent-preset`'s `config.plugins` is later mounted as a
second plugin tree; it is not the patch parser's Loader group.

Therefore R5 has not established that
`./runtime/bridge-plugin.js` resolves relative to this bundle when the preset
registry mounts its child plugins.

R6 should use the package subpath already exported by the package:

```yaml
name: '@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js'
```

and prove it in an installed pinned profile.

---

## B5 — strict hydration is still incomplete

The R5 report says:

`strict hydration (all enum fail-closed): PASS`

but reviewed code still fabricates revision target assertion semantics.

Inside `_hydrate_revision_package()`, target assertions still hard-code:

```python
value_type=ValueType.NUMBER
claim_type=ClaimType.MEASUREMENT
source_claim_origin=SourceClaimOrigin.PRIMARY
confidence=Confidence.MEDIUM
```

That means supplied target assertion enum values are not faithfully hydrated.

The bridge also still fabricates curation completeness:

```python
completeness=CompletenessResult(status=CompletenessStatus.OK)
```

for every hydrated CommitRequest.

Multiple required identities are also still defaulted to empty strings, e.g.:

- revision `package_id`, `work_id`, version ids and ref ids;
- decision `assertion_id`;
- approval `approval_id`, `package_id`, `scope_hash`;
- other domain identifiers.

R6 must hydrate the frozen schemas faithfully and reject missing/invalid required
fields. It must not invent successful completeness.

---

## B6 — several "native" report rows are actually direct workflow evidence

The R5 report labels these as native DSH evidence:

- native §5 replay IDEMPOTENT_HIT
- native §7 APPROVAL_REQUIRED
- native §7 FINALIZED

but the cited tests are SI-2A / SI-2B integration workflow tests.

Those tests remain valuable workflow regression evidence, but they are not
native DSH/preset/tool evidence.

The R6 report must distinguish:

1. workflow-level evidence; and
2. real pinned DSH ToolRuntime evidence.

Do not relabel one as the other.

---

## B7 — bundle does not declare the runtime peer it imports in the required R6 design

The reviewed R5 `package.json` has no `peerDependencies`.

Once R6 actually imports:

```js
@deepseek-ai/dsh-tools
```

the out-of-tree bundle should declare a compatible runtime peer so pinned
app-boot compatibility preflight can fail visibly on an incompatible DSH
runtime.

Use the source guide for the pinned dependency contract.

---

# R6 acceptance gate

R6 is accepted only when all of the following are real:

1. `bridge-plugin.js` imports and calls pinned `defineTool`.
2. Parameter/output schemas compile through real pinned `defineTool`.
3. Installed bundle resolves the curator bridge child plugin without relying on
   ambiguous `./runtime/...` preset resolution.
4. A real pinned Cordis Context mounts ToolRuntime + AgentPresetRegistry.
5. A real Agent mounts `knowledge-curator`.
6. `ctx.tools.schemas(agent)` exposes both native curator tools.
7. `ctx.tools.execute(..., agent)` executes the shipped bridge for §5.
8. `ctx.tools.execute(..., agent)` executes the shipped bridge for §7.
9. strict hydration no longer fabricates revision assertion enums, successful
   completeness, or required identifiers.
10. public MCP remains exactly four tools.
11. frozen core/workflow boundaries remain unchanged.
12. qualification evidence is committed to
    `results/phase-si-4-r6-dsh-qualification.md`.

Direct subprocess tests remain useful regressions but cannot satisfy items 4–8.

---

## Planner disposition

Keep SI-4-R6 as the active phase.

Executor must read:

`planner/SI4_R6_DSH_SOURCE_GUIDE.md`

and implement R6 from pinned source behavior rather than from R5's self-reported
PASS labels.

STOP after R6 implementation and return for Planner review.
