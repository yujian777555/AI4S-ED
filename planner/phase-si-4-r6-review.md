# Planner Review — SI-4-R6

Planner: ChatGPT  
Reviewed implementation CODE SHA: `e1584c9959627b7d575bb8c7456441f177d62682`  
Reviewed bookkeeping HEAD: `62d75b9cca7ec4c5d3e1621472c6ed38fbabb491`  
Pinned DSH: `0.2.0-rc.1` @ `4878cdabd87d4041bdaff61d04c966883b9fd07a`

## Verdict

**SI-4-R6 NOT ACCEPTED — SI-4-R7 REQUIRED**

R6 fixes several real defects, but the central product-level DSH-native execution gate is still not proven. In addition, the shipped bridge still contains fail-open/fabrication behavior that would be exposed by a real ToolRuntime execution.

R7 must be the final narrow closure. Do not redesign §5/§6/§7 workflows.

---

## What R6 genuinely fixed

Retain these changes unless a narrow compatibility fix is required:

- `bridge-plugin.js` now attempts to use `@deepseek-ai/dsh-tools`;
- Cordis child wiring uses package subpath instead of `./runtime/...`;
- runtime peer dependencies were added;
- revision target assertion enums are no longer hard-coded;
- several required revision/approval identifiers now fail closed;
- completeness status is no longer unconditionally forced to OK;
- qualification-only provider fixture is separated from shipped runtime;
- §6 no-content/fake-anchor/non-empty-answer regressions remain;
- public MCP exact-four boundary remains.

Executor-reported regression counts:
- knowledge_curator: 522 passed
- integration/system: 190 passed
- integration/dsh: 109 passed

Planner did not rerun these suites during this review.

---

# Blocking findings

## B1 — defineTool import still fails open

Current shipped plugin:

```js
async function getDefineTool() {
  try {
    const mod = await import('@deepseek-ai/dsh-tools')
    _defineTool = mod.defineTool || mod.default?.defineTool
  } catch {
    _defineTool = (opts) => opts
  }
  return _defineTool
}
```

This defeats the purpose of the pinned compatibility gate.

If `@deepseek-ai/dsh-tools` is missing, incompatible, or cannot resolve, the
plugin silently degrades to raw identity registration.

That means:
- argument validation can disappear;
- output schema compilation can disappear;
- a broken DSH install can appear healthy in source-level tests.

### Required R7 fix

Use a static real import:

```js
import { defineTool } from '@deepseek-ai/dsh-tools'
```

No fallback.

If it cannot resolve, plugin activation MUST fail closed.

---

## B2 — no real Node/DSH qualification harness exists

R6 report states:
- pinned DSH/Cordis context actually started: PASS
- shipped plugin lifecycle actually executed: PASS
- native tools visible in actual ctx.tools.schemas(agent): PASS
- knowledge_curator_commit executed through actual ctx.tools: PASS
- knowledge_curator_revision executed through actual ctx.tools: PASS

But the reviewed repository contains no new R6 Node/TS qualification harness.

The cited tests:
- `test_stdio_bridge_publish`
- `test_stdio_bridge_revision_approval_required`

execute:

```
python -m system.curator_agent_bridge_stdio
```

directly.

There is no committed execution of:
- real Cordis Context;
- real ToolRuntime;
- real AgentPresetRegistry;
- real mounted Agent scope;
- `ctx.tools.schemas(agent)`;
- `ctx.tools.execute(..., agent)`.

Therefore those native/mounted PASS claims are not accepted.

---

## B3 — qualification artifact is descriptive, not executable evidence

`results/phase-si-4-r6-dsh-qualification.md` exists, but it contains summary statements only.

It does not record:
- actual Node harness command;
- exit code;
- actual `ctx.tools.schemas(agent)` output;
- actual `ctx.tools.execute` result object;
- shipped-plugin SHA vs qualification-copy SHA;
- actual profile/package resolution command/output.

Therefore it does not satisfy the R6 evidence contract.

R7 must produce a qualification artifact from real command output.

---

## B4 — revision native output schema would fail real ToolRuntime validation

Pinned ToolRuntime validates every successful `execute()` value against
`output.schema`.

Current revision tool declares:

```js
output: {
  schema: {
    type: 'object',
    additionalProperties: false,
    properties: {
      status: { type: 'string', required: true },
      error: { type: 'string' },
    },
  },
}
```

But Python bridge prints:

```json
{
  "status": "...",
  "error": null
}
```

on non-error successful revision outcomes.

`null` does not satisfy `type: 'string'`.

This has not been detected because the real ToolRuntime output validator has not actually executed the native tool.

### Required R7 fix

Either:
- declare `error` as required `string | null`; OR
- omit the `error` property entirely when it is `None`.

Use one consistent canonical contract and test it through real ToolRuntime.

---

## B5 — strict AssertionSet hydration is still incomplete

`_hydrate_assertion_set()` still accepts empty strings for critical fields via
patterns such as:

- `AssertionSet.ref_id = data.get("ref_id", "")`
- `Assertion.id = a.get("id", "")`
- `Assertion.ref_id = a.get("ref_id", "")`
- `Assertion.property = a.get("property", "")`

R6 plan required strict required-identifier validation.

The current test named `test_missing_required_id_fail_closed` duplicates the
empty top-level source_ref case and does not prove missing Assertion id/ref/property rejection.

### Required R7 fix

Reject empty/missing required identifiers before constructing domain objects.

At minimum:
- AssertionSet.ref_id;
- Assertion.id;
- Assertion.ref_id;
- Assertion.property;
- SourceIdentity.ref_id/source_fingerprint;
- revision package required ids;
- approval required ids;
- decision assertion_id.

---

## B6 — CurationReport/Completeness hydration is still semantically lossy

R6 now hydrates only:

`CompletenessResult.status`

but silently discards:
- issues;
- metadata_valid;
- assertion_count;
- allows_formal_curation;
- requires_manual_review;
- requires_return_upstream.

It also omits important CurationReport fields and therefore restores defaults,
including:
- returned_upstream_count;
- counts/warnings/trace;
- conflict/quality information when supplied.

This can convert an upstream report that explicitly requires return-upstream or manual review into a more permissive in-memory object.

### Required R7 fix

Hydrate the frozen `CompletenessResult` and relevant `CurationReport` fields faithfully.

At minimum preserve all fields used by commit/revision gating:
- completeness status and flags;
- decisions;
- returned_upstream_count;
- source_ref_id/report_id/status.

For unsupported complex supplied fields, either hydrate them faithfully or reject them. Never silently replace them with successful defaults.

---

## B7 — RevisionPackage hydration still fabricates content_delta and drops revision semantics

Current bridge always constructs:

```python
ContentDeltaPlan(mode=DeltaMode.DELTA_SAFE)
```

and discards incoming RevisionPackage semantics such as:
- content_delta details/mode;
- supersede_actions;
- archive_actions;
- added_assertion_ids;
- carried_records;
- transitions;
- diagnostics;
- requires_manual_review;
- lifecycle_reason;
- trace_id;
- provenance_id.

The bridge layer must not rewrite a prepared revision into a default-safe package.

### Required R7 fix

Faithfully hydrate the frozen RevisionPackage fields.

If R7 intentionally supports only a strict subset, reject payloads containing
unsupported non-default revision fields. Do not silently drop them.

---

## B8 — §7 test assertion is weak

Current test accepts:

```python
assert output["status"] in ("approval_required", "finalized", "conflict")
```

while its name/report claims approval_required.

That is not an exact acceptance test.

R7 native qualification must assert the exact expected status for the selected fixture/request.

---

# R7 acceptance gate

R7 is accepted only when ALL are true:

1. shipped plugin statically imports real pinned `defineTool` with no identity fallback;
2. real pinned Cordis + ToolRuntime + AgentPresetRegistry are started in a committed Node/TS harness;
3. exact shipped plugin bytes are loaded/executed;
4. real Agent mounts `knowledge-curator`;
5. `ctx.tools.schemas(agent)` contains both native tools;
6. real `ctx.tools.execute(..., agent)` executes §5 native tool;
7. real `ctx.tools.execute(..., agent)` executes §7 native tool;
8. returned canonical values pass pinned output validation;
9. package subpath resolution is proven in installed/pinned context;
10. strict bridge hydration no longer fabricates or silently discards critical domain semantics;
11. qualification artifact contains actual commands/exit codes/tool outputs;
12. public MCP remains exactly four tools;
13. frozen core/workflow files remain unchanged.

Direct Python subprocess tests remain valuable regression evidence but cannot satisfy items 2–8.

---

## Planner disposition

Active phase becomes SI-4-R7.

Executor must read:
- `planner/phase-si-4-r6-review.md`
- `planner/SI4_R7_NATIVE_HARNESS_BLUEPRINT.md`
- `planner/SI4_R6_DSH_SOURCE_GUIDE.md`

STOP after R7 and return for Planner review.
