# Phase SI-4-R8 Plan — Exact Pinned DSH Runtime Execution

Planner: ChatGPT
Executor: MiMo / Kimi / Codex
State: READY_FOR_EXECUTOR

Formal R7 review:

`planner/phase-si-4-r7-review.md`

Mandatory execution recipe:

`planner/SI4_R8_EXACT_DSH_EXECUTION_RECIPE.md`

Pinned-source background:

- `planner/SI4_R7_NATIVE_HARNESS_BLUEPRINT.md`
- `planner/SI4_R6_DSH_SOURCE_GUIDE.md`

## Goal

This is the final product-qualification closure for SI-4.

Do not add new Knowledge Curator features.

Prove, using the actual pinned DeepSeek Harness runtime, that the exact shipped
Knowledge Curator bridge plugin is mounted and executed through real
`ctx.tools.execute(..., agent)`.

If the pinned runtime cannot be executed in the available environment, STOP and
report BLOCKER with exact command/error/stack. Do not simulate PASS.

---

## 1. Real pinned DSH runtime only

Use:

- DeepSeek Harness `0.2.0-rc.1`
- source SHA `4878cdabd87d4041bdaff61d04c966883b9fd07a`

Run qualification inside the pinned DSH workspace or an installed environment
that genuinely resolves the pinned packages.

The AI4S-side Node script from R7 is not sufficient because it never imported or
started DSH.

---

## 2. Execute exact shipped plugin bytes

Qualification must execute:

`dsh/knowledge-curator/runtime/bridge-plugin.js`

If copied into the pinned DSH checkout for workspace resolution:
- SHA-256 the shipped file;
- SHA-256 the qualification copy;
- require exact equality;
- do not modify copied bytes;
- remove temp DSH files after qualification.

---

## 3. Use official AgentPresetRegistry harness architecture

Mirror pinned:

`packages/preset/agent-preset-registry/tests/harness.ts`

Create/start actual:

- Context
- Loader
- Group
- LlmRuntime
- SessionStore
- SessionProjectionRegistry
- SystemPrompt
- ToolRuntime
- AgentRegistry
- AgentLoop
- AgentPresetRegistry

No fake ctx/tools.

---

## 4. Mount real preset-scoped bridge tool

Register/mount a `knowledge-curator` preset containing the exact shipped bridge
plugin.

Create a real Agent scope.

Run:

```ts
ctx.tools.schemas(agent)
```

and prove both:

- `knowledge_curator_commit`
- `knowledge_curator_revision`

are actually visible.

Also record the unscoped global tool view.

---

## 5. Execute real native §5 tool

Run:

```ts
ctx.tools.execute({
  signal,
  callId,
  name: 'knowledge_curator_commit',
  arguments: commitPayload,
  agent,
})
```

Assert exact:

- `isError === false`
- canonical `value.status === 'published'`
- canonical `value.commit_attempted === true`

This execution must traverse:
ToolRuntime validation -> plugin execute -> JS spawn/stdin -> Python bridge ->
provider factory -> CuratorAgentBridge -> CurationCommitWorkflow -> ToolRuntime
output validation/rendering.

---

## 6. Execute real native §7 tool

Run through the same real ToolRuntime:

`knowledge_curator_revision`

Use a qualification provider with seeded revision state.

For the no-approval fixture assert exact:

`approval_required`

If the fixture also supplies valid approval, assert exact:

`finalized`.

Do not use a multi-status acceptance set.

---

## 7. Finish bridge transport strictness

### CurationReport

Safety-relevant fields must not silently acquire permissive defaults when the
serialized report is intended to carry them.

Either require or explicitly define/test optionality for:

- completeness.metadata_valid
- completeness.assertion_count
- completeness.allows_formal_curation
- completeness.requires_manual_review
- completeness.requires_return_upstream
- returned_upstream_count

Hydrate supplied completeness issues faithfully.

### RevisionPackage

Do not let raw dicts leak into typed fields.

Faithfully hydrate or explicitly reject supplied non-empty:

- unchanged_pairs
- modified_pairs
- carried_records
- transitions

Preserve:
- content_delta semantics
- supersede/archive/added ids
- diagnostics
- manual-review/lifecycle flags
- trace/provenance

No silent rewrite to default-safe semantics.

---

## 8. Real package-subpath qualification

Pack/install the bundle into a pinned DSH environment/profile and prove the
product row:

`@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`

resolves without broken preset/plugin diagnostics.

A YAML string assertion is not enough.

---

## 9. Qualification artifact

Create:

`results/phase-si-4-r8-dsh-qualification.md`

It must include actual:

- DSH source SHA;
- Node/pnpm versions;
- command(s);
- exit code(s);
- plugin SHA pair;
- `ctx.tools.schemas(agent)` output;
- global schema output;
- commit ToolExecutionResult summary;
- revision ToolExecutionResult summary;
- package-resolution result;
- public MCP exact-four result;
- stderr/error details if any.

No descriptive-only PASS lines.

---

## 10. Regression

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Also run the real pinned DSH qualification.

Required mandatory regressions:
- 0 failed
- 0 skipped
- 0 xfailed

---

## 11. Frozen boundaries

Do not modify:

- `knowledge_curator/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `system/application_composition.py`
- `system/workflows/curation_commit.py`
- `system/workflows/revision_publication.py`
- `planner/CONTRACT_GAPS.md`

Allowed:
- `dsh/knowledge-curator/**`
- `system/curator_agent_bridge_stdio.py`
- `integration/dsh/qualification/**`
- `integration/dsh/fixtures/**`
- DSH integration tests/results.

Do not depend on:
- `system/workflow_orchestration/**`
- `system/task_planner/**`

---

## 12. R8 executor report

Create:

`results/phase-si-4-r8-executor-report.md`

Required minimum:

```
Phase SI-4-R8 implementation CODE SHA:

real pinned DSH workspace/runtime executed:
PASS / FAILED / BLOCKER
evidence:

exact shipped plugin bytes executed:
PASS / FAILED
evidence:

real Context started:
PASS / FAILED
evidence:

real ToolRuntime mounted:
PASS / FAILED
evidence:

real AgentPresetRegistry mounted:
PASS / FAILED
evidence:

knowledge-curator mounted into real Agent:
PASS / FAILED
evidence:

ctx.tools.schemas(agent) contains native curator tools:
PASS / FAILED
evidence:

knowledge_curator_commit executed via real ctx.tools:
PASS / FAILED
evidence:

native §5 canonical result:
...

knowledge_curator_revision executed via real ctx.tools:
PASS / FAILED
evidence:

native §7 canonical result:
...

real ToolRuntime input/output validation passed:
PASS / FAILED
evidence:

installed package subpath resolved:
PASS / FAILED
evidence:

CurationReport safety semantics faithfully hydrated:
PASS / FAILED
evidence:

RevisionPackage nested structured semantics faithful or explicitly rejected:
PASS / FAILED
evidence:

§6 regressions:
PASS / FAILED
evidence:

public MCP exactly four:
PASS / FAILED
evidence:

qualification artifact committed:
PASS / FAILED
evidence:

frozen files changed:
NO

production fixture imports:
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

native DSH qualification:
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

## 13. Hard blocker rule

If real pinned DSH execution cannot be performed:

STOP and return:

`BLOCKER`

with:
- exact command;
- exact exit code;
- stacktrace;
- module/package resolution problem;
- relevant pinned DSH source/API location.

Do NOT replace the missing runtime proof with:
- static Node source checks;
- direct Python subprocess;
- fake Context;
- fake ToolRuntime;
- report-only PASS.

---

## 14. Completion protocol

1. read formal R7 review and R8 exact execution recipe;
2. perform real pinned DSH qualification;
3. fix only runtime defects exposed by that qualification;
4. finish remaining faithful transport hydration;
5. run package resolution qualification;
6. run all regressions;
7. commit `results/phase-si-4-r8-dsh-qualification.md`;
8. create `results/phase-si-4-r8-executor-report.md`;
9. commit implementation;
10. push main;
11. update status.json:
   - phase = SI-4-R8
   - actor = executor
   - state = executor_complete OR blocker
   - latest_commit = <R8 CODE SHA>
   - result_expected = results/phase-si-4-r8-executor-report.md
12. commit/push bookkeeping;
13. verify clean tree and HEAD == origin/main;
14. STOP.

Do not start SI-5.

## 15. Final acceptance question

SI-4 is accepted only when the actual pinned DSH runtime itself executes the
exact shipped plugin through:

```
real Context
 -> real ToolRuntime
 -> real AgentPresetRegistry
 -> real Agent scope
 -> defineTool
 -> ctx.tools.schemas(agent)
 -> ctx.tools.execute(..., agent)
 -> JS spawn/stdin
 -> Python bridge
 -> deployment provider
 -> faithful typed hydration
 -> accepted §5/§7 workflows
```

If that cannot be demonstrated, report BLOCKER rather than PASS.
