# Phase SI-4-R9-R1 Plan — Final Evidence Closure

Planner: ChatGPT
Executor: MiMo / Kimi / Codex
State: READY_FOR_EXECUTOR

Formal R9 review:

`planner/phase-si-4-r9-review.md`

## Scope

This is a final evidence-only closure.

Do NOT redesign:
- DSH integration architecture;
- bridge plugin architecture;
- §5/§6/§7 workflows;
- accepted R9 typed hydration.

Only close the remaining native §7 and installed-package evidence gaps.

---

## 1. Preserve accepted R8/R9 baseline

Must remain true:
- pinned DSH SHA = `4878cdabd87d4041bdaff61d04c966883b9fd07a`;
- real Context starts;
- real ToolRuntime mounts;
- real AgentPresetRegistry mounts;
- real Agent mounts `knowledge-curator`;
- exact shipped plugin SHA matches qualification copy;
- scoped schemas contain exactly the two native curator application tools;
- native §5 returns exact PUBLISHED;
- ToolRuntime input/output validation passes;
- R9 fail-closed/typed hydration remains intact.

---

## 2. Native §7 must be exact APPROVAL_REQUIRED

Fix qualification fixture/request only.

Through real:

```ts
ctx.tools.execute({
  ...,
  name: 'knowledge_curator_revision',
  agent,
})
```

require:

```text
isError == false
value.status == approval_required
```

Change harness from:

```js
['approval_required', 'conflict'].includes(...)
```

to exact:

```js
revision.value?.status === 'approval_required'
```

Any other status must throw and exit nonzero.

Do not change frozen workflow/coordinator semantics.

---

## 3. Hard-assert global isolation

After:

```js
const global = ctx.tools.schemas().map(...)
```

assert neither native curator tool appears globally.

---

## 4. Real package installation qualification

From `dsh/knowledge-curator`:

1. run `pnpm pack`;
2. compute tarball SHA-256;
3. create a clean temporary qualification directory/environment;
4. install the tarball there;
5. install/resolve the pinned DSH runtime dependencies needed for package
   activation;
6. from the installed environment, execute real module resolution/import for:

`@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`

7. record the resolved path;
8. load/activate the package's own `cordis.patch.yml` via the pinned DSH
   product/bundle loading path;
9. prove `knowledge-curator` is not broken;
10. preferably mount the installed preset and record
    `ctx.tools.schemas(agent)`.

Do not count:
- YAML string assertions;
- tarball file listing;
- package.json export presence alone

as installed-package resolution.

---

## 5. Mandatory qualification artifact

Create:

`results/phase-si-4-r9-r1-dsh-qualification.md`

It must contain actual:
- DSH HEAD command/result;
- Node/pnpm versions;
- native harness command/exit code;
- plugin SHA pair;
- scoped/global schemas;
- §5 ToolExecutionResult;
- §7 ToolExecutionResult == approval_required;
- pack command/exit code;
- tarball path/SHA;
- install command/exit code;
- installed package location;
- resolved bridge-plugin module path;
- product preset activation result;
- MCP exact-four result.

---

## 6. Regression

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Also run:
- real pinned native DSH harness;
- real installed-package qualification.

Required:
- 0 failed
- 0 skipped
- 0 xfailed

---

## 7. Frozen boundaries

Do not modify:
- `knowledge_curator/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `system/application_composition.py`
- `system/workflows/curation_commit.py`
- `system/workflows/revision_publication.py`
- `planner/CONTRACT_GAPS.md`

Avoid changing `system/curator_agent_bridge_stdio.py` unless final evidence
exposes a concrete regression; R9 transport hydration is already accepted.

Allowed:
- qualification harness/fixtures/tests;
- package metadata only if real install exposes a package bug;
- results artifacts;
- status/report.

No dependency on:
- `system/workflow_orchestration/**`
- `system/task_planner/**`

---

## 8. Executor report

Create:

`results/phase-si-4-r9-r1-executor-report.md`

Required:

```
Phase SI-4-R9-R1 CODE SHA:

real pinned native chain preserved:
PASS/FAILED

native §5 exact PUBLISHED:
PASS/FAILED

native §7 exact APPROVAL_REQUIRED:
PASS/FAILED

native harness exits nonzero on wrong §7 status:
PASS/FAILED

global scoped isolation hard-asserted:
PASS/FAILED

pnpm pack:
PASS/FAILED

tarball SHA:
...

tarball actually installed:
PASS/FAILED

installed package path:
...

package subpath actually resolved/imported:
PASS/FAILED

resolved bridge path:
...

installed product preset activated:
PASS/FAILED

qualification artifact committed:
PASS/FAILED

R9 typed/fail-closed hydration preserved:
PASS/FAILED

public MCP exactly four:
PASS/FAILED

frozen files changed:
NO

knowledge_curator:
...

integration/system:
...

integration/dsh:
...

native qualification:
...

installed package qualification:
...

mandatory skipped:
0
mandatory xfailed:
0

deviations:
NONE
```

---

## 9. Completion

1. close only these evidence gaps;
2. commit qualification artifact;
3. commit executor report;
4. push implementation/evidence;
5. update `status.json`:
   - phase = SI-4-R9-R1
   - actor = executor
   - state = executor_complete
   - latest_commit = <CODE SHA>
   - result_expected = results/phase-si-4-r9-r1-executor-report.md
6. push bookkeeping;
7. verify clean tree and HEAD == origin/main;
8. STOP.

Do not start SI-5.

If any required real qualification cannot be performed, return BLOCKER with the
actual command/error instead of PASS.
