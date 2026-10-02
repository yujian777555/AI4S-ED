# Phase SI-4-R5 Plan — Executable DSH Plugin & Strict Bridge Validation

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Verdict on SI-4-R4

Reviewed implementation CODE SHA:

`3e8d69caf4c6376121418eee05f75720a827f8fb`

Reviewed bookkeeping HEAD:

`c090b27f98bdc9422edb85e1d2309e03a4e1c2d8`

Verdict:

**SI-4-R4 NOT ACCEPTED — R5 REQUIRED**

R4 fixes important production boundaries:

- no shipped integration fixture import;
- deployment provider factory is used;
- committed stdio entrypoint exists;
- both curation and revision workflows are composed;
- §6 no-content and fake-anchor cases fail closed.

However, the actual shipped DSH plugin path is still not proven executable and
contains concrete runtime/API defects.

R5 is a narrow final closure. Do not change business workflow semantics.

---

## 1. Blocking defect — async execFile does not send `input` to stdin

Current `runtime/bridge-plugin.js` does:

```js
const { stdout, stderr } = await execFileAsync(
  PYTHON_CMD,
  ['-m', 'system.curator_agent_bridge_stdio', action],
  {
    ...
    input: JSON.stringify(payload),
  }
)
```

Node asynchronous `child_process.execFile()` does not define an `input`
option. `input` is supported by synchronous child-process APIs such as
`execFileSync`, not by async `execFile`.

Therefore the Python process can receive EOF on stdin instead of the payload.

### Required fix

Use a real async stdin transport.

Preferred:

```js
spawn(...)
child.stdin.write(JSON.stringify(payload))
child.stdin.end()
```

Collect stdout/stderr with:

- timeout;
- abort/cancellation support where pinned DSH exposes `exec.signal`;
- bounded output;
- nonzero exit handling;
- JSON parse fail-closed.

Do not switch to blocking `execFileSync` inside an Agent tool.

Add a real Node test proving a payload sent through the shipped JS plugin reaches
the Python stdio entrypoint and produces the expected structured response.

---

## 2. Blocking defect — pinned DSH tool API is not implemented correctly

Pinned DSH source commit:

`4878cdabd87d4041bdaff61d04c966883b9fd07a`

documents tool registration as:

```js
import { defineTool } from '@deepseek-ai/dsh-tools'

ctx.tools.register(defineTool({
  name: '...',
  description: '...',
  parameters: {
    field: { type: 'string', required: true },
  },
  output: {
    schema: { ... },
    render: (_args, value) => [{ type: 'text', text: ... }],
  },
  async execute(args, exec) {
    return canonicalJsonValue
  },
}))
```

Current R4 plugin still registers a raw object directly and returns
`{type:'text', text: ...}` from `execute`.

That violates the pinned canonical tool contract:

- `defineTool` performs input validation;
- `execute` returns the canonical declared JSON value;
- `output.render` produces model-facing content.

### Required fix

Use the exact pinned rc.1 API.

At minimum:

- import `defineTool` from the pinned package;
- use its actual parameter schema DSL;
- declare `output.schema`;
- declare `output.render`;
- `execute` returns the canonical object, not a content block;
- propagate `exec.signal` into subprocess cancellation if supported.

Do not use latest-master-only APIs that are absent in the pinned commit.

---

## 3. Blocking defect — “plugin loaded in pinned DSH” is still not proven

R4 tests named/plugin evidence only inspect source strings such as:

- `curator_agent_bridge_stdio` exists in plugin source;
- native tool names exist in plugin source.

There is still no committed test that:

- imports/loads the shipped JS plugin under pinned DSH/Cordis;
- mounts it into a real Context with `dsh-tools`;
- observes registered tools from `ctx.tools`;
- executes those registered tools.

The required R4 qualification artifact
`results/phase-si-4-r4-dsh-qualification.md` is also missing.

### Required fix

Create a real Node/DSH qualification harness.

It must execute the pinned installed DSH packages and:

1. create the supported Cordis/DSH context;
2. mount/provide the `tools` service;
3. load the shipped `bridge-plugin.js`;
4. start/apply the plugin using the actual plugin contract;
5. verify:
   - `knowledge_curator_commit` registered;
   - `knowledge_curator_revision` registered;
6. invoke them through the actual `ctx.tools` execution path.

A source-string assertion is only a smoke test and cannot be used as runtime evidence.

---

## 4. Plugin export/lifecycle must match pinned Cordis/DSH contract

Current bridge plugin uses a default class with a `start()` method.

Pinned DSH examples use the supported Cordis plugin shape, e.g. exported
`name`, `inject`, and `apply(ctx)`, unless the pinned loader explicitly
supports the class lifecycle currently used.

### Required fix

Inspect the pinned plugin loader and use an actually supported shape.

Do not assume a class with `start()` is automatically called.

Qualification must prove that loading the exact shipped plugin registers the
tools.

---

## 5. Blocking defect — typed hydration is not fail-closed

Current `system/curator_agent_bridge_stdio.py` silently coerces invalid values:

- invalid `ValueType` -> NUMBER;
- invalid `ClaimType` -> MEASUREMENT;
- invalid `SourceClaimOrigin` -> PRIMARY;
- invalid `Confidence` -> MEDIUM;
- invalid `VersionRelation` -> PREPRINT_TO_JOURNAL;
- invalid curation action -> ACCEPT;
- invalid approval decision -> APPROVED.

This is not schema validation. It can turn malformed or hostile input into a
valid-looking publication request.

The approval fallback is especially unacceptable.

### Required fix

Hydration must be strict:

- required fields missing -> error;
- invalid enum -> error;
- invalid nested object -> error;
- invalid decision -> error;
- invalid approval -> error;
- invalid version relation -> error.

No semantic defaults for invalid values.

Defaults are allowed only when the frozen schema explicitly defines that field
as optional with that default.

Add negative tests for every critical enum family, especially:

- approval decision;
- curation action;
- relation;
- confidence;
- claim type/value type.

Assert:

- nonzero bridge exit;
- structured error;
- no workflow invocation;
- no commit/version mutation.

---

## 6. Revision workflow must fail closed if provider bundle lacks revision deps

Current `_build_bridge()` may return:

```
CuratorAgentBridge(
    curation_workflow=...,
    revision_workflow=None,
)
```

when provider bundle lacks revision configuration.

For the shipped §5/§6/§7 Knowledge Curator product, required application
capabilities should be explicit.

### Required fix

Choose and document one contract:

### Preferred production product contract

At bridge startup/build time require both:

- curation deps;
- revision deps.

If revision deps are absent:

- fail closed with a clear provider/composition error.

If you intentionally support a §5/§6-only deployment mode, it must be explicit
configuration and the DSH revision tool must not be registered/advertised in
that mode.

Do not silently advertise a revision tool backed by `None`.

---

## 7. Real native §5 invocation

The acceptance test must execute:

```
ctx.tools
  -> registered knowledge_curator_commit
  -> shipped bridge-plugin.js execute()
  -> spawn Python bridge stdio module
  -> AI4S_SYSTEM_ADAPTER_FACTORY supplied by test ENV
  -> strict hydration
  -> CuratorAgentBridge
  -> CurationCommitWorkflow
```

Assert:

- canonical DSH tool result is success;
- status == published;
- commit_attempted == true.

Then replay the same request through the SAME real tool path and assert:

- idempotent_hit;
- one-version invariant.

No direct Python subprocess test is sufficient for the “mounted/native tool”
acceptance claim.

---

## 8. Real native §7 invocation

Execute the registered `knowledge_curator_revision` through `ctx.tools`.

Use test ENV to provide a provider factory; production code must remain
fixture-agnostic.

Required cases:

### no approval

For a revision that requires approval:

- result preserves APPROVAL_REQUIRED.

### valid approval

- result reaches FINALIZED.

### invalid approval

- invalid enum/scope/shape fails closed or preserves frozen workflow rejection;
- never silently coerces to APPROVED.

### replay/history

Use exact existing frozen tests for deeper replay/history semantics if desired,
but the DSH-native tool path must at least prove real workflow reachability.

---

## 9. §6 acceptance remains fail-closed

Keep R4 improvements.

Additionally ensure final answer never becomes blank when a claim result is
allowed but validator omits claim text.

If validator returns a factual_allowed result without usable claim text:

- use the original validated candidate text only if claim identity matches;
- otherwise ABSTAIN.

Do not return `status=answered` with an empty answer.

---

## 10. Real qualification artifact is mandatory

Create:

`results/phase-si-4-r5-dsh-qualification.md`

It must contain actual captured evidence for:

- pinned DSH commit/version;
- Node version;
- pnpm version;
- package dry-run;
- plugin import/load;
- plugin lifecycle execution;
- registered native tool schemas;
- native commit tool invocation/result;
- native commit replay/result;
- native revision no-approval/result;
- native revision approved/result;
- exact four MCP discovery;
- provider ENV used in qualification;
- production runtime fixture-import scan.

Do not claim an artifact exists unless it is committed.

---

## 11. Correct tool output contract

For each native tool:

`execute` must return canonical JSON matching `output.schema`.

Example conceptually:

```js
output: {
  schema: {
    type: 'object',
    properties: {
      status: { type: 'string' },
      commit_attempted: { type: 'boolean' },
    },
    required: ['status'],
  },
  render: (_args, value) => [
    { type: 'text', text: JSON.stringify(value) }
  ],
},
async execute(args, exec) {
  return await callBridge(..., exec.signal)
}
```

Use the exact pinned schema DSL syntax, not generic JSON Schema if the API
expects the DSL.

---

## 12. Frozen boundaries

Do not modify:

- `knowledge_curator/**`;
- `system/composition.py`;
- `system/provider_loader.py`;
- `system/mcp_stdio.py`;
- `system/application_composition.py`;
- `system/workflows/curation_commit.py`;
- `system/workflows/revision_publication.py`;
- `planner/CONTRACT_GAPS.md`.

Allowed:

- `dsh/knowledge-curator/**`;
- `system/curator_agent_bridge_stdio.py`;
- narrow additive `system/curator_agent_bridge.py` change only if required;
- integration DSH qualification harness/tests;
- results artifacts.

No dependency on generic:

- `system/workflow_orchestration/**`;
- `system/task_planner/**`.

---

## 13. Mandatory tests

### Production bridge boundary

- no shipped test fixture imports;
- provider factory comes only from deployment env;
- both workflows required/configured;
- no temp source generation.

### Strict hydration

Negative cases:

- invalid confidence;
- invalid claim type;
- invalid value type;
- invalid relation;
- invalid curation action;
- invalid approval decision;
- missing required identifiers.

Each must fail closed before workflow side effects.

### JS transport

- real JS plugin sends stdin payload to Python;
- Python receives exact payload;
- nonzero Python exit -> tool error;
- invalid JSON response -> tool error;
- timeout/cancellation -> process terminated/fails closed.

### Pinned DSH plugin/runtime

- plugin actually loaded;
- tools actually registered;
- tools actually executed through `ctx.tools`.

### §5

- native publish;
- native replay/idempotent_hit.

### §7

- native approval_required;
- native finalized with valid approval.

### §6

- no content -> abstain;
- fake anchor -> abstain;
- supported claim -> non-empty grounded answer.

### MCP

- exact four public MCP tools.

---

## 14. Regression

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Also run the real Node/DSH qualification harness.

Requirements:

- 0 failed;
- 0 skipped;
- 0 xfailed.

---

## 15. R5 report

Create:

`results/phase-si-4-r5-executor-report.md`

Every PASS must cite exact evidence.

Required minimum:

```
Phase SI-4-R5 implementation CODE SHA:

async JS->Python stdin transport proven:
PASS/FAILED
evidence:

pinned DSH defineTool contract used:
PASS/FAILED
evidence:

plugin lifecycle actually executed:
PASS/FAILED
evidence:

native tools actually registered in ctx.tools:
PASS/FAILED
evidence:

native commit tool actually executed through ctx.tools:
PASS/FAILED
evidence:

native §5 PUBLISHED:
PASS/FAILED
evidence:

native §5 replay IDEMPOTENT_HIT:
PASS/FAILED
evidence:

native revision tool actually executed through ctx.tools:
PASS/FAILED
evidence:

native §7 APPROVAL_REQUIRED:
PASS/FAILED
evidence:

native §7 FINALIZED with valid approval:
PASS/FAILED
evidence:

strict enum hydration:
PASS/FAILED
evidence:

invalid approval never coerces to APPROVED:
PASS/FAILED
evidence:

missing revision provider fails closed:
PASS/FAILED
evidence:

§6 empty evidence content -> ABSTAIN:
PASS/FAILED
evidence:

§6 fake anchor -> ABSTAIN:
PASS/FAILED
evidence:

§6 supported answer non-empty and grounded:
PASS/FAILED
evidence:

public MCP exactly four:
PASS/FAILED
evidence:

production runtime fixture imports:
NO

temporary bridge source generation:
NO

frozen files changed:
NO

workflow_orchestration dependency:
NO

task_planner dependency:
NO

knowledge_curator:
...

integration/system:
...

integration/dsh:
...

node/dsh qualification:
...

mandatory skipped:
0
mandatory xfailed:
0

live remote model:
PASS / NOT_RUN_ENV

deviations:
NONE / describe
```

---

## 16. Completion protocol

1. implement SI-4-R5 only;
2. run real pinned DSH/Node plugin qualification;
3. run native §5 and §7 tool calls;
4. run strict hydration negatives;
5. run §6 fail-closed tests;
6. run all regressions;
7. create R5 DSH qualification artifact;
8. create R5 executor report;
9. commit implementation;
10. push main;
11. update `status.json`:
    - phase = SI-4-R5
    - actor = executor
    - state = executor_complete
    - latest_commit = <R5 CODE SHA>
    - result_expected = results/phase-si-4-r5-executor-report.md
12. commit/push bookkeeping;
13. verify clean tree and HEAD == origin/main;
14. STOP.

Do not start SI-5.

---

## 17. Final acceptance question

R5 passes only if this is proven by actual execution:

```
Pinned DSH/Cordis
  -> load shipped bridge plugin
  -> defineTool(...)
  -> ctx.tools registry
  -> execute registered native tool
  -> real async stdin transport
  -> committed Python stdio bridge
  -> deployment provider factory
  -> strict typed hydration
  -> CuratorAgentBridge
      -> CurationCommitWorkflow
      -> RevisionPublicationWorkflow
```

and malformed inputs fail closed before state changes.

No source-string-only test may satisfy runtime acceptance.
No direct Python subprocess may be called a mounted/native DSH test.
