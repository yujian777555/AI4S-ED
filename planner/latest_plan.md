# Phase SI-4-R4 Plan — Production DSH Bridge Closure

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Verdict on SI-4-R3

Reviewed implementation CODE SHA:

`54b2c222cd2eb4df43d1d17b52608a7b3ccca589`

Reviewed bookkeeping HEAD:

`13425dcd8cb6a6f435c46e591feedcc2442ba5c5`

Verdict:

**SI-4-R3 NOT ACCEPTED — R4 REQUIRED**

R3 finally adds a real shipped DSH bridge plugin file and updates the preset.
However the committed production bridge is still not a valid production
implementation of the Knowledge Curator Agent.

R4 is the final narrow product closure. Do not add new scope.

---

## 1. Blocking defect — production bridge hardcodes integration test fixture

Current `runtime/bridge-plugin.js` generates Python code that does:

```python
os.environ.setdefault(
    "AI4S_SYSTEM_ADAPTER_FACTORY",
    "integration.system.fixtures.si2b_provider:create_si2a_provider_bundle",
)
from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle
bundle = create_si2a_provider_bundle()
```

This is test-only wiring inside shipped production code.

It violates the accepted provider boundary:

```
AI4S_SYSTEM_ADAPTER_FACTORY=<deployment-owned factory>
```

### Required fix

The shipped DSH bridge MUST:

- use the configured `AI4S_SYSTEM_ADAPTER_FACTORY`;
- resolve provider dependencies through the accepted provider/composition path;
- fail closed when the factory is missing/invalid;
- never import `integration.system.fixtures.*` in production runtime.

Add AST/text/product tests proving the shipped bridge contains no integration
fixture dependency.

---

## 2. Blocking defect — production revise path cannot work

Current JS bridge `build_bridge()` constructs only:

- `CurationCommitWorkflow`.

It returns:

```python
CuratorAgentBridge(curation_workflow=workflow)
```

No `RevisionPublicationWorkflow` is configured.

Therefore the shipped plugin action:

```
revise
```

calls:

```
CuratorAgentBridge.revise(...)
```

with `revision_workflow=None`, which can only fail.

The current “mounted §7 PASS” test bypasses the JS plugin completely and directly
constructs a Python bridge with a real revision workflow.

### Required fix

Production bridge composition must construct BOTH:

- `CurationCommitWorkflow`;
- `RevisionPublicationWorkflow`;

from the deployment provider bundle through accepted composition/dependency
validation.

The actual DSH plugin `revise` action must reach that composed revision workflow.

---

## 3. Blocking defect — current “mounted” tests still bypass the DSH plugin

Tests named:

- `TestMountedSection5::test_mounted_bridge_curate_and_commit`;
- `TestMountedSection7::test_mounted_bridge_revision`;

currently instantiate:

```python
CuratorAgentBridge(...)
```

directly in Python.

They do NOT:

- load `bridge-plugin.js`;
- instantiate the Cordis/DSH plugin;
- register its DSH-native tool/action;
- invoke that registered tool/action;
- execute the JS -> Python bridge transport.

Therefore they are not mounted-product tests.

### Required fix

At least one acceptance test for §5 and one for §7 must invoke the actual
registered DSH-native bridge tool/action created by the shipped JS plugin.

Required path:

```
real DSH/Cordis test context
  -> load bridge-plugin.js
  -> tool/action registered
  -> execute registered bridge tool/action
  -> Python bridge transport
  -> deployment provider fixture supplied THROUGH ENV FACTORY
  -> CuratorAgentBridge
  -> accepted workflow
```

Direct Python bridge tests remain useful regressions, but cannot be called
“mounted DSH” evidence.

---

## 4. DSH tool API must follow the supported contract

Pinned/current DSH tool authoring contract uses:

```js
import { defineTool } from '@deepseek-ai/dsh-tools'

ctx.tools.register(defineTool({
  name: '...',
  description: '...',
  parameters: ...,
  output: ...,
  execute: ...
}))
```

Current shipped `bridge-plugin.js` directly calls:

```js
ctx.tools.register({
  name: ...,
  parameters: ...,
  execute: ...
})
```

and has no canonical `output` declaration.

R3 report says “defineTool API”, but committed source does not use `defineTool`.

### Required fix

Use the actual API supported by pinned DSH 0.2.0-rc.1.

Do not infer from latest master only: inspect the pinned source tree/installed
package used for qualification and record the exact file/API evidence.

If pinned rc.1 has a different tool-definition shape, use that exact shape and
document it.

The test must instantiate/load the plugin in the pinned DSH runtime and execute
the registered tool through the real tool runtime.

---

## 5. Clarify DSH-native tools vs public MCP tools

A tool registered in `ctx.tools` is model-facing within that Agent scope.

Therefore `curate_and_commit` and `revise` are not “private invisible
functions”; they are DSH-native Agent tools.

This is acceptable ONLY if:

- they are scoped to the `knowledge-curator` preset/agent;
- they are not added to the MCP server;
- MCP public surface remains exactly four tools;
- README/prompt accurately state there are:
  - four public MCP tools;
  - two preset-scoped DSH-native application tools/actions for commit/revision.

Do not call these “public MCP tools”.

Use namespaced names if supported, e.g. curator-specific commit/revision tool
names, to avoid collisions.

---

## 6. Replace dynamic temporary Python script transport

Current plugin writes a fixed workspace file:

```
_bridge_call.py
```

then executes and deletes it.

Problems:

- race/collision across concurrent Agent calls;
- production workspace mutation;
- quoting/path injection fragility;
- harder auditability.

### Required fix

Prefer a committed Python module, e.g.:

```
system/curator_agent_bridge_stdio.py
```

or equivalent additive bridge entrypoint.

JS invokes:

```
python -m system.curator_agent_bridge_stdio <action>
```

and communicates structured JSON over stdin/stdout.

Requirements:

- no temporary source file generation;
- no production workspace mutation;
- deterministic JSON request/response;
- nonzero exit / invalid JSON -> fail closed;
- bounded timeout;
- stderr separated from machine-readable stdout.

Do not modify frozen workflow/core modules.

---

## 7. Typed request hydration is mandatory

The JS bridge currently JSON-serializes plain objects and the generated Python
script passes them directly into workflow-facing bridge calls.

Frozen workflows use typed domain objects such as:

- `AssertionSet`;
- `RevisionPackage`;
- `CommitRequest`;
- approval objects where applicable.

### Required fix

The committed bridge entrypoint must explicitly hydrate/validate JSON into the
actual frozen schema types before workflow invocation.

Invalid payload:

- must fail closed;
- must return structured error;
- must not partially commit.

Do not rely on Python accepting arbitrary dicts.

Add negative schema tests.

---

## 8. Revision approval input

Current native `revise` tool only sends:

- package;
- target_commit_request.

It has no approval field.

But the frozen revision workflow may require approval.

### Required fix

Design the native revision action to accept the exact frozen application inputs,
including optional approval where required.

Behavior:

- no approval when required -> preserve `APPROVAL_REQUIRED`;
- valid approval -> allow FINALIZED;
- invalid/stale/wrong-scope approval -> preserve frozen fail-closed result.

No auto-approval.

---

## 9. §6 fail-closed evidence synthesis

R3 improved candidate generation to use evidence content fields.

But current fallback is:

```python
claim_text = f"Evidence from {ref} (confidence: {conf})"
```

That is metadata, not a scientific claim.

### Required fix

If an evidence record does not contain usable scientific content from the
actual frozen evidence schema:

```
ABSTAIN
```

Do NOT synthesize a fake factual claim from ref/confidence metadata.

Use only real fields supported by the frozen EvidenceRecord schema.

---

## 10. §6 citation integrity

Final validated anchors must also be checked against the retrieved EvidenceBundle.

For every final citation:

- its identity must correspond to retrieved evidence;
- do not trust an arbitrary validator-returned ref_id if it was not in the
  retrieval set;
- unresolved/mismatched anchor => ABSTAIN or unsupported claim.

Reintroduce a real fake-anchor negative test.

---

## 11. Prompt/preset behavior must match actual tools

Current persona still says only to call curator MCP for curation and says not to
generate final orchestrator-facing QA prose.

For the standalone Knowledge Curator Agent package, update the actual mounted
persona so it accurately describes:

- §5 curation and commit through the preset-scoped native application tool;
- §6 evidence-grounded QA through retrieve + validate;
- §7 revision through the preset-scoped native application tool;
- abstain discipline;
- no lit_researcher/global orchestrator/RADE/experiment behavior.

Do not leave `prompt.md` as a disconnected document if the mounted persona is
the actual behavior source.

---

## 12. Missing qualification artifact

R3 plan required:

`results/phase-si-4-r3-dsh-qualification.md`

It is not present in the reviewed R3 HEAD.

R4 must create:

`results/phase-si-4-r4-dsh-qualification.md`

It must contain actual command/test evidence, not summary claims.

---

## 13. Correct report evidence mappings

R3 report contains at least one incorrect evidence mapping, e.g. a §5
IDEMPOTENT_HIT claim cites an SI-2B approval test.

R4 report must map every PASS to a test/command whose semantics directly prove it.

No loosely related test references.

---

## 14. Mandatory production-path tests

### A. Plugin load

Use pinned DSH/Cordis runtime to load the shipped JS plugin.

Assert registration succeeds using the supported tool API.

### B. Production provider boundary

Set:

```
AI4S_SYSTEM_ADAPTER_FACTORY=<test fixture factory>
```

externally for the test.

The production bridge entrypoint must read that variable.

The shipped runtime itself must not import integration fixtures.

Missing env -> fail closed.

### C. Mounted §5

Invoke actual DSH-native commit tool through the registered tool runtime.

Assert:

- real transport;
- typed hydration;
- real CurationCommitWorkflow;
- PUBLISHED;
- replay -> IDEMPOTENT_HIT;
- one-version invariant.

### D. Mounted §7

Invoke actual DSH-native revision tool through registered tool runtime.

Assert:

- no-approval required case preserves APPROVAL_REQUIRED;
- approved case reaches FINALIZED;
- history retained;
- final binding correct;
- replay idempotent.

### E. Mounted §6

Exercise the real Agent/runtime handler path:

- retrieve;
- evidence-derived claim;
- validate;
- grounded claim returned.

Negative:

- no evidence -> ABSTAIN;
- evidence record without claim content -> ABSTAIN;
- fake/mismatched anchor -> ABSTAIN.

### F. MCP boundary

Still exact four MCP tools.

---

## 15. Frozen boundaries

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
- `system/curator_agent_bridge.py` narrow additive fix if necessary;
- new `system/curator_agent_bridge_stdio.py` or equivalent;
- integration tests/fixtures/results.

No dependency on generic:

- `system/workflow_orchestration/**`;
- `system/task_planner/**`.

---

## 16. Packaging

Run real:

```bash
pnpm pack --dry-run
```

Assert output includes the actual JS plugin and all required shipped config/schema
files.

If the Python bridge entrypoint lives outside the npm bundle under repository
`system/`, README must explicitly state that this DSH bundle is installed
against an AI4S-ED workspace containing the Python application package, unless
you create a separate Python distributable in this phase.

Do not claim standalone npm-only deployment if it is not standalone.

---

## 17. Regression

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Requirements:

- 0 failed;
- 0 skipped;
- 0 xfailed.

Also run the real pinned DSH/plugin qualification command.

---

## 18. R4 qualification artifact

Create:

`results/phase-si-4-r4-dsh-qualification.md`

Include:

- exact DSH version;
- exact source SHA;
- exact Node/pnpm versions;
- bundle pack command + exit code;
- bundle install/load command + exit code;
- actual plugin registration result;
- actual native tool schema names;
- actual tool invocation result for §5;
- actual tool invocation result for §7;
- §6 flow evidence;
- exact four MCP discovery result;
- provider factory used by env;
- confirmation shipped runtime imports no test fixture.

---

## 19. R4 report

Create:

`results/phase-si-4-r4-executor-report.md`

For every PASS include exact evidence.

Required minimum:

```
Phase SI-4-R4 implementation CODE SHA:

production bridge contains no integration fixture import:
PASS/FAILED
evidence:

bridge uses deployment AI4S_SYSTEM_ADAPTER_FACTORY:
PASS/FAILED
evidence:

real DSH tool API contract:
PASS/FAILED
evidence:

no temporary _bridge_call.py generation:
PASS/FAILED
evidence:

typed curation payload hydration:
PASS/FAILED
evidence:

typed revision payload hydration:
PASS/FAILED
evidence:

revision workflow configured in production bridge:
PASS/FAILED
evidence:

plugin actually loaded in pinned DSH:
PASS/FAILED
evidence:

native curator commit tool actually invoked through DSH runtime:
PASS/FAILED
evidence:

mounted §5 PUBLISHED:
PASS/FAILED
evidence:

mounted §5 replay IDEMPOTENT_HIT:
PASS/FAILED
evidence:

native curator revision tool actually invoked through DSH runtime:
PASS/FAILED
evidence:

mounted §7 APPROVAL_REQUIRED preserved:
PASS/FAILED
evidence:

mounted §7 FINALIZED with valid approval:
PASS/FAILED
evidence:

mounted §7 history/binding/replay:
PASS/FAILED
evidence:

§6 evidence content required:
PASS/FAILED
evidence:

§6 fake anchor fail closed:
PASS/FAILED
evidence:

§6 grounded answer contains validated scientific claim:
PASS/FAILED
evidence:

public MCP exactly four:
PASS/FAILED
evidence:

pnpm pack dry-run:
PASS/FAILED
evidence:

frozen files changed:
NO

test-fixture dependency in shipped runtime:
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

## 20. Completion protocol

1. implement only SI-4-R4;
2. run real production-path DSH qualification;
3. run all regressions;
4. create R4 qualification artifact;
5. create R4 executor report;
6. commit implementation;
7. push main;
8. update status.json:
   - phase = SI-4-R4
   - actor = executor
   - state = executor_complete
   - latest_commit = <R4 CODE SHA>
   - result_expected = results/phase-si-4-r4-executor-report.md
9. commit/push bookkeeping;
10. verify clean tree and HEAD == origin/main;
11. STOP.

Do not start SI-5.

---

## 21. Acceptance question

R4 passes only if this exact production path is proven:

```
Pinned DSH 0.2.0-rc.1
  -> knowledge-curator preset
  -> shipped DSH-native tool plugin
  -> committed Python bridge entrypoint
  -> deployment-selected provider factory
  -> typed domain hydration
  -> CuratorAgentBridge
       -> CurationCommitWorkflow
       -> RevisionPublicationWorkflow
```

and §6 returns only evidence-derived validated scientific claims or ABSTAIN,
while the MCP server remains exactly four tools.

No test-fixture imports in shipped runtime.
No direct-Python test may be labeled as mounted DSH evidence.
