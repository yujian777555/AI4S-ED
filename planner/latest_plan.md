# Phase SI-4-R7 Plan — Real Native ToolRuntime Closure

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

Formal R6 review:

`planner/phase-si-4-r6-review.md`

Mandatory pinned-source guides:

- `planner/SI4_R6_DSH_SOURCE_GUIDE.md`
- `planner/SI4_R7_NATIVE_HARNESS_BLUEPRINT.md`

## Goal

Close the final remaining product gap:

> Prove the shipped Knowledge Curator bridge plugin actually loads in pinned
> DSH 0.2.0-rc.1, registers real preset-scoped tools through `defineTool`,
> and executes §5 / §7 through real `ctx.tools.execute(..., agent)`.

Do not redesign business workflows.

---

## 1. Static real defineTool import

Replace any dynamic/fallback loader with:

```js
import { defineTool } from '@deepseek-ai/dsh-tools'
```

No fallback identity function.

Missing/incompatible dependency must fail plugin activation.

---

## 2. Correct pinned schemas

Use real pinned ParameterSchemaSpec / ValueSchemaSpec.

Commit tool and revision tool must compile through real `defineTool`.

Fix revision output schema so successful Python result with `error: null` is valid,
or omit the key when error is null.

The real ToolRuntime qualification must validate the canonical outputs.

---

## 3. Real pinned DSH harness is mandatory

Create a committed Node/TS harness under:

`integration/dsh/qualification/`

Adapt the official pinned:

`packages/preset/agent-preset-registry/tests/harness.ts`

Use real:

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

## 4. Exact shipped plugin bytes

Qualification must execute the exact shipped:

`dsh/knowledge-curator/runtime/bridge-plugin.js`

If copied into pinned DSH checkout for workspace resolution:
- SHA-256 shipped source;
- SHA-256 copied fixture;
- assert equality;
- remove temp fixture after run.

No test-specific reimplementation.

---

## 5. Real preset scope

Create/mount a real agent and preset.

Prove:

```
ctx.tools.schemas(agent)
```

contains:

- `knowledge_curator_commit`
- `knowledge_curator_revision`

and the global view does not incorrectly expose them if pinned scoped semantics
say they are preset-scoped.

---

## 6. Real native §5 execution

Call:

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
- `value.status === 'published'`
- `value.commit_attempted === true`

This must traverse JS plugin -> spawn/stdin -> Python bridge -> provider ->
CuratorAgentBridge -> CurationCommitWorkflow.

---

## 7. Real native §7 execution

Call:

```ts
ctx.tools.execute({
  signal,
  callId,
  name: 'knowledge_curator_revision',
  arguments: revisionPayload,
  agent,
})
```

Use the seeded qualification provider.

Assert one exact expected result for the no-approval fixture:
- `approval_required`

If valid approval is also qualified:
- exact `finalized`.

No three-way set assertions.

---

## 8. Strict AssertionSet hydration

Reject missing/empty:
- AssertionSet.ref_id;
- Assertion.id;
- Assertion.ref_id;
- Assertion.property;
- other identifiers required by the frozen compatibility model and workflow
  boundary.

Do not let empty strings stand in for required identifiers.

---

## 9. Faithful CurationReport hydration

Hydrate, do not fabricate/drop:

### CompletenessResult
- status
- issues
- metadata_valid
- assertion_count
- allows_formal_curation
- requires_manual_review
- requires_return_upstream

### CurationReport gating fields
- report_id
- source_ref_id
- status
- decisions
- returned_upstream_count

Preserve other supplied fields where implemented.

If supplied complex fields are unsupported, reject explicitly rather than
silently resetting them.

---

## 10. Faithful RevisionPackage hydration

Do not force:

`ContentDeltaPlan(mode=DELTA_SAFE)`

when the prepared package supplies different revision semantics.

Hydrate the frozen RevisionPackage fields faithfully, including supported:
- content_delta mode/details;
- supersede_actions;
- archive_actions;
- added_assertion_ids;
- requires_manual_review;
- lifecycle_reason;
- trace_id;
- provenance_id;
- diagnostics;
- transitions/carried records when supplied and supported.

If a non-default supplied field is not implemented, reject it explicitly.

Never silently drop or rewrite revision semantics.

---

## 11. §6 remains regression-only in R7

Do not redesign §6.

Keep fail-closed regressions:
- no content -> ABSTAIN;
- fake anchor -> ABSTAIN;
- rejected validation -> ABSTAIN;
- no safely recoverable validated claim text -> ABSTAIN;
- supported answer non-empty and grounded.

---

## 12. Installed package resolution

Run real package qualification:
- pack bundle;
- install into isolated pinned DSH environment/profile;
- resolve peer dependencies;
- activate product patch using package subpath:
  `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`;
- record no broken plugin/preset diagnostics.

Do not rely only on source-string tests.

---

## 13. Qualification artifact

Create:

`results/phase-si-4-r7-dsh-qualification.md`

Record actual:
- command(s);
- exit code(s);
- pinned DSH version/SHA;
- Node/pnpm versions;
- shipped/copy plugin SHA;
- `ctx.tools.schemas(agent)` output;
- commit execution result;
- revision execution result;
- package resolution result;
- public MCP exact-four result.

No descriptive-only PASS artifact.

---

## 14. Public MCP boundary

Remain exactly four:

- curate_assertion_set
- knowledge_curator_health
- retrieve_evidence
- validate_retrieved_claims

Native DSH tools remain preset-scoped and separate from MCP.

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
- `system/curator_agent_bridge_stdio.py`;
- `integration/dsh/qualification/**`;
- `integration/dsh/fixtures/**`;
- DSH integration tests/results.

Do not depend on:
- `system/workflow_orchestration/**`;
- `system/task_planner/**`.

---

## 16. Regression gates

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Also run the real Node/DSH qualification harness.

Required:
- 0 failed
- 0 skipped
- 0 xfailed

---

## 17. R7 report

Create:

`results/phase-si-4-r7-executor-report.md`

Every PASS must cite direct evidence.

Required minimum:

```
Phase SI-4-R7 implementation CODE SHA:

static real defineTool import, no fallback:
PASS/FAILED
evidence:

pinned DSH/Cordis context started:
PASS/FAILED
evidence:

exact shipped plugin SHA executed:
PASS/FAILED
evidence:

package subpath resolved in installed environment:
PASS/FAILED
evidence:

native tools visible in ctx.tools.schemas(agent):
PASS/FAILED
evidence:

knowledge_curator_commit executed via ctx.tools:
PASS/FAILED
evidence:

native §5 canonical result:
...

knowledge_curator_revision executed via ctx.tools:
PASS/FAILED
evidence:

native §7 canonical result:
...

real ToolRuntime output validation passed:
PASS/FAILED
evidence:

AssertionSet required IDs strict:
PASS/FAILED
evidence:

CurationReport/Completeness hydration faithful:
PASS/FAILED
evidence:

RevisionPackage hydration faithful/no silent defaults:
PASS/FAILED
evidence:

§6 fail-closed regressions:
PASS/FAILED
evidence:

public MCP exactly four:
PASS/FAILED
evidence:

qualification artifact:
PASS/FAILED
evidence:

production fixture imports:
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

1. implement only SI-4-R7;
2. run real pinned Node/DSH harness;
3. execute both native tools via actual `ctx.tools`;
4. run installed package-subpath qualification;
5. finish strict faithful hydration;
6. run all regressions;
7. commit R7 qualification artifact;
8. create R7 executor report;
9. commit implementation;
10. push main;
11. update `status.json`:
   - phase = SI-4-R7
   - actor = executor
   - state = executor_complete
   - latest_commit = <R7 CODE SHA>
   - result_expected = results/phase-si-4-r7-executor-report.md
12. commit/push bookkeeping;
13. verify clean tree and HEAD == origin/main;
14. STOP.

Do not start SI-5.

## 19. Acceptance question

R7 passes only if a real pinned ToolRuntime successfully validates and executes
the exact shipped plugin through:

```
real Context
 -> real AgentPresetRegistry
 -> real agent scope
 -> defineTool
 -> ctx.tools.schemas(agent)
 -> ctx.tools.execute(..., agent)
 -> JS spawn/stdin
 -> Python bridge
 -> deployment provider
 -> faithful typed hydration
 -> accepted §5/§7 workflows
```

No source-string test and no direct Python subprocess can satisfy this native
product acceptance gate.
