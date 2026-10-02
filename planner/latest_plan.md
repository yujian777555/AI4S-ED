# Phase SI-4-R6 Plan — Actual Pinned DSH Execution Closure

Planner: ChatGPT
Executor: MiMo / Kimi / Codex
State: READY_FOR_EXECUTOR

## 0. Verdict on SI-4-R5

Reviewed implementation CODE SHA:

`18937dbafb36764c322c3a86d8935b8c54368ec1`

Reviewed bookkeeping HEAD:

`234e364df3e58d4a67f64936121b3e4039c00766`

Verdict:

**SI-4-R5 NOT ACCEPTED — R6 REQUIRED**

R5 fixed:
- async spawn transport implementation;
- several strict enum fallbacks;
- missing revision capability now fails closed;
- §6 non-empty/fail-closed behavior;
- production fixture imports remain absent.

But the central acceptance claim is still unproven:

> the shipped DSH plugin is actually loaded and its registered native tools are executed through pinned DSH/Cordis `ctx.tools`.

R6 is the final qualification closure. Do not change §5/§6/§7 business semantics unless a directly observed runtime defect requires a narrow fix.

---

## 1. Blocking defect — shipped plugin still does NOT use defineTool

Pinned DSH commit:

`4878cdabd87d4041bdaff61d04c966883b9fd07a`

documents:

```js
import { defineTool } from '@deepseek-ai/dsh-tools'

ctx.tools.register(defineTool({
  name: '...',
  description: '...',
  parameters: { ... },
  output: {
    schema: { ... },
    render: (_args, value) => [{ type: 'text', text: ... }],
  },
  async execute(args, exec) {
    return canonicalJsonValue
  },
}))
```

Current R5 `bridge-plugin.js` contains comments saying "defineTool", but actually does:

```js
ctx.tools.register({
  ...
})
```

There is no import/use of `defineTool`.

The R5 test only checks that source contains `output:`, `schema:`, and
`render:`; it does not prove the pinned tool contract.

### Required fix

Actually:

```js
import { defineTool } from '@deepseek-ai/dsh-tools'
```

and register:

```js
ctx.tools.register(defineTool({...}))
```

using the exact pinned schema DSL.

Do not satisfy this with comments or string tests.

---

## 2. Blocking defect — no real pinned DSH/Cordis runtime test exists

R5 report claims:

- plugin lifecycle actually executed: PASS;
- native tools actually registered in ctx.tools: PASS;
- native commit tool actually executed through ctx.tools: PASS.

But committed tests do not create a DSH/Cordis context or invoke `ctx.tools`.

`test_stdin_payload_reaches_python` directly runs:

```
python -m system.curator_agent_bridge_stdio curate_and_commit
```

That proves Python stdio behavior only.

### Required fix

Create a real Node qualification harness against the pinned DSH source/packages.

It must:

1. use the pinned DSH/Cordis packages;
2. construct/start the actual supported Context/tool runtime;
3. load/apply the exact shipped `runtime/bridge-plugin.js`;
4. verify registration through real `ctx.tools`;
5. execute `knowledge_curator_commit` through real tool execution;
6. execute `knowledge_curator_revision` through real tool execution.

Do NOT use a handwritten fake:

```js
{ tools: { register() {} } }
```

as acceptance evidence.

---

## 3. Mandatory qualification harness

Add a committed harness, for example:

```
integration/dsh/qualification/knowledge-curator-r6.mjs
```

Use the actual pinned packages from the isolated DSH source/install.

The harness must accept configuration only through environment/arguments.

Recommended qualification environment:

```
DSH_SOURCE=<path to pinned DSH source/install>
AI4S_KC_WORKSPACE=<AI4S-ED workspace>
AI4S_KC_PYTHON=<python>
AI4S_SYSTEM_ADAPTER_FACTORY=<qualification provider factory>
```

The shipped plugin/runtime must still contain no test-fixture hardcoding.

---

## 4. Qualification must execute actual tool registry

The harness must query/use the actual tool service.

Prove schemas include:

```
knowledge_curator_commit
knowledge_curator_revision
```

Then execute via the real registry/execution API.

Record:

- tool schema;
- execution success/failure;
- canonical returned value;
- rendered result if accessible.

Do not call exported plugin functions directly and label it ctx.tools execution.

---

## 5. Native §5 product test

Required actual path:

```
pinned DSH/Cordis
  -> load shipped bridge-plugin.js
  -> defineTool
  -> ctx.tools
  -> execute knowledge_curator_commit
  -> JS spawn/stdin
  -> Python stdio bridge
  -> provider factory from ENV
  -> typed hydration
  -> CuratorAgentBridge
  -> CurationCommitWorkflow
```

Assert:

```
status == published
commit_attempted == true
```

### Replay

If the qualification provider persists state across child-process invocations,
invoke the same tool again and assert exact frozen idempotent result.

If the provider fixture is purely per-process in-memory and cannot prove replay
across subprocess calls:

- do NOT claim native replay PASS;
- keep the accepted direct SI-2A replay test as workflow evidence;
- report native replay as NOT_APPLICABLE_PROVIDER_ISOLATION with explanation.

Do not fabricate shared state.

---

## 6. Native §7 product test

Through actual `ctx.tools`, execute:

`knowledge_curator_revision`.

At minimum prove the native tool reaches the real revision application path.

Required test(s):

- valid typed revision request reaches the workflow;
- approval-required case preserves exact frozen outcome OR
- approved case reaches FINALIZED.

Prefer both if the qualification provider can construct persistent prerequisite
state.

Do not cite an unrelated system test as proof that the native tool itself was
executed.

Deeper SI-2B history/replay semantics may still cite exact frozen system tests.

---

## 7. Strict hydration is still incomplete

R5 removed several enum fallbacks, but production hydration still contains
semantic hardcoding in revision target assertions:

- `ValueType.NUMBER`;
- `ClaimType.MEASUREMENT`;
- `SourceClaimOrigin.PRIMARY`;
- `Confidence.MEDIUM`.

It also still allows many required identifiers to become empty strings through
`.get(..., "")`.

### Required fix

Revision target assertions must hydrate from their input values exactly as the
frozen schema requires.

Strictly validate:

- value_type;
- claim_type;
- source_claim_origin;
- confidence.

Do not force defaults unless the frozen schema explicitly defines them.

Also reject missing/empty required identifiers for:

- AssertionSet.ref_id;
- Assertion.id/ref_id;
- SourceIdentity.ref_id/source_fingerprint;
- RevisionPackage package/work/source-version/ref identifiers;
- CommitRequest required report/source fields;
- RevisionApproval required identifiers.

Use frozen dataclass/schema requirements as the authority.

---

## 8. Curation report hydration must not fabricate successful completeness

Current bridge constructs:

```python
CompletenessResult(status=CompletenessStatus.OK)
```

regardless of incoming report data.

### Required fix

Hydrate the actual report/completeness fields supported by the frozen
`CurationReport` schema.

Do not silently turn malformed/incomplete reports into completeness OK.

If required report fields are absent/invalid, fail closed before workflow
invocation.

---

## 9. §6 remains frozen except one safety regression

Do not redesign §6.

Keep:

- no scientific content -> ABSTAIN;
- fake anchor -> ABSTAIN;
- validation rejection -> ABSTAIN;
- supported answer non-empty and evidence-derived.

Add/retain:

- factual_allowed result with no usable validated claim text and no safely
  matching candidate -> ABSTAIN.

---

## 10. Mandatory qualification artifact

R5 required:

`results/phase-si-4-r5-dsh-qualification.md`

but it is absent.

R6 MUST create:

`results/phase-si-4-r6-dsh-qualification.md`

This is a hard acceptance gate.

It must contain actual outputs from the real Node/DSH harness.

---

## 11. Qualification artifact contents

At minimum:

```
Pinned DSH version:
0.2.0-rc.1

Pinned source SHA:
4878cdabd87d4041bdaff61d04c966883b9fd07a

Node version:
...

pnpm version:
...

DSH source/install path:
...

plugin load command:
...

exit code:
...

actual registered tool names:
...

knowledge_curator_commit canonical result:
...

knowledge_curator_revision canonical result:
...

public MCP discovered names:
...

provider factory supplied by ENV:
...

production fixture-import scan:
PASS

temporary-source scan:
PASS
```

No secrets.

---

## 12. Report evidence discipline

Every PASS in R6 report must map to semantics that directly prove it.

Examples:

Valid:

```
native commit tool executed through ctx.tools:
PASS
evidence:
- command: node integration/dsh/qualification/knowledge-curator-r6.mjs ...
- artifact: results/phase-si-4-r6-dsh-qualification.md
- observed tool: knowledge_curator_commit
- canonical result.status: published
```

Invalid:

```
native commit tool executed through ctx.tools:
PASS
evidence:
- Python subprocess test
```

or:

```
plugin lifecycle executed:
PASS
evidence:
- source contains "export function apply"
```

---

## 13. Public MCP boundary

Remain exactly:

- curate_assertion_set
- knowledge_curator_health
- retrieve_evidence
- validate_retrieved_claims

Native DSH application tools are separate preset-scoped tools.

Do not add them to MCP.

---

## 14. Frozen boundaries

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
- integration DSH qualification harness/tests;
- results artifacts.

No dependency on:

- `system/workflow_orchestration/**`;
- `system/task_planner/**`.

---

## 15. Mandatory tests

### JS/DSH runtime

- real pinned plugin load;
- real defineTool construction;
- actual registry shows both native tools;
- actual registry executes commit tool;
- actual registry executes revision tool;
- JS spawn/stdin transport used in those executions.

### Hydration

Negative tests:

- invalid revision target value_type;
- invalid revision target claim_type;
- invalid revision target source_claim_origin;
- invalid revision target confidence;
- empty source fingerprint;
- empty required revision IDs;
- malformed curation completeness/report;
- invalid approval.

All fail closed before workflow side effects.

### §6

- no content -> abstain;
- fake anchor -> abstain;
- no validated claim text -> abstain;
- supported -> grounded non-empty answer.

### MCP

- exact four.

---

## 16. Regression gates

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Run real Node/DSH qualification harness separately.

Required:

- 0 failed;
- 0 skipped;
- 0 xfailed.

---

## 17. R6 executor report

Create:

`results/phase-si-4-r6-executor-report.md`

Required minimum:

```
Phase SI-4-R6 implementation CODE SHA:

defineTool actually imported and used:
PASS/FAILED
evidence:

pinned DSH/Cordis context actually started:
PASS/FAILED
evidence:

shipped plugin lifecycle actually executed:
PASS/FAILED
evidence:

native tools visible in actual ctx.tools:
PASS/FAILED
evidence:

knowledge_curator_commit executed through actual ctx.tools:
PASS/FAILED
evidence:

native §5 result:
...

knowledge_curator_revision executed through actual ctx.tools:
PASS/FAILED
evidence:

native §7 result:
...

actual JS spawn/stdin path exercised by native calls:
PASS/FAILED
evidence:

revision target assertion hydration strict:
PASS/FAILED
evidence:

required identifier validation strict:
PASS/FAILED
evidence:

curation completeness/report hydration truthful:
PASS/FAILED
evidence:

invalid approval fail closed:
PASS/FAILED
evidence:

§6 no content -> ABSTAIN:
PASS/FAILED
evidence:

§6 fake anchor -> ABSTAIN:
PASS/FAILED
evidence:

§6 missing validated claim text -> ABSTAIN:
PASS/FAILED
evidence:

§6 grounded non-empty answer:
PASS/FAILED
evidence:

public MCP exactly four:
PASS/FAILED
evidence:

qualification artifact committed:
PASS/FAILED
evidence:

production fixture imports:
NO

temporary source generation:
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

## 18. Completion protocol

1. implement only R6 closure;
2. run real pinned DSH/Cordis Node harness;
3. execute both native tools through actual `ctx.tools`;
4. fix remaining strict hydration gaps;
5. run §6 safety regressions;
6. run all pytest suites;
7. commit qualification artifact;
8. create R6 executor report;
9. commit implementation;
10. push main;
11. update status.json:
    - phase = SI-4-R6
    - actor = executor
    - state = executor_complete
    - latest_commit = <R6 CODE SHA>
    - result_expected = results/phase-si-4-r6-executor-report.md
12. commit/push bookkeeping;
13. verify clean tree and HEAD == origin/main;
14. STOP.

Do not start SI-5.

---

## 19. Acceptance question

R6 passes only if an actual pinned DSH/Cordis tool runtime executes:

```
knowledge_curator_commit
knowledge_curator_revision
```

from the shipped plugin through:

```
defineTool
 -> ctx.tools
 -> JS spawn/stdin
 -> Python bridge
 -> deployment provider
 -> strict domain hydration
 -> accepted workflows
```

Source-string checks and direct Python subprocess tests remain useful regressions
but cannot satisfy this product-level acceptance gate.
