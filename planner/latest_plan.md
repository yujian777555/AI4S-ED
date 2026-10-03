# Phase SI-4-R9 Plan — Final Package & Semantic Closure

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

Formal R8 review:

`planner/phase-si-4-r8-review.md`

## Goal

Preserve the now-proven real pinned DSH native execution chain from R8 and close
only the remaining package-resolution and transport-semantic gaps.

Do not redesign DSH integration.
Do not redesign §5/§6/§7 workflows.
Do not start SI-5.

---

## 1. Preserve R8 native DSH proof

Keep the real pinned DSH harness architecture.

The following is now an accepted baseline and must not regress:

```
real pinned Context
 -> real ToolRuntime
 -> real AgentPresetRegistry
 -> real Agent
 -> exact shipped bridge plugin
 -> ctx.tools.schemas(agent)
 -> ctx.tools.execute
 -> §5 published
 -> real ToolRuntime output validation
```

R9 may update the harness only to make assertions hard-fail and to obtain the
exact §7 approval-required result.

---

## 2. Make harness failures fatal

The qualification process MUST exit nonzero if any acceptance condition fails.

At minimum hard-fail if:
- native tool names are missing;
- global visibility is wrong;
- §5 `isError` is true;
- §5 status != published;
- §5 commit_attempted != true;
- §7 `isError` is true;
- §7 status != approval_required;
- shipped/copy SHA mismatch;
- DSH HEAD mismatch.

Do not only log `FAILED`.

---

## 3. Fix native §7 qualification fixture/request

Use the seeded qualification provider to construct a deterministic no-approval
revision that reaches the frozen approval gate.

Expected exact result through real `ctx.tools.execute`:

`approval_required`

If it returns conflict, inspect the frozen SI-2B revision preconditions and seed
the fixture/request accordingly.

Do not change frozen revision workflow/coordinator logic.

---

## 4. Real installed-package subpath qualification

This is mandatory.

From `dsh/knowledge-curator`:

1. run `pnpm pack`;
2. install the tarball into an isolated pinned DSH environment/profile;
3. resolve:
   `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`;
4. activate/use the package's own `cordis.patch.yml`;
5. verify no broken plugin/preset diagnostic;
6. record command, exit code and resolved file/module path.

Prefer additionally mounting the installed product preset and checking
`ctx.tools.schemas(agent)`.

A source/YAML string test is not sufficient.

---

## 5. CurationReport safety-field hydration

For prepared serialized reports, fail closed on missing safety-relevant fields
unless an existing accepted serialization contract explicitly defines them
optional.

Preferred required fields:

### completeness
- status
- metadata_valid
- assertion_count
- allows_formal_curation
- requires_manual_review
- requires_return_upstream

### report
- report_id
- source_ref_id
- status
- returned_upstream_count
- decisions

Hydrate issues faithfully.

Add negative tests proving missing safety fields fail before workflow side
effects.

---

## 6. RevisionPackage nested typed hydration

Hydrate real frozen nested types.

### ContentDeltaPlan
`unchanged_pairs` / `modified_pairs`:
- build `AlignedPair`;
- validate `DeltaCategory`.

### carried_records
- build `CarriedAssertionRecord`.

### transitions
- build `AssertionTransition`;
- validate `TransitionAction`.

Invalid/malformed -> fail closed.

No raw dicts in typed fields.
No silent dropping of non-empty supplied fields.

---

## 7. Preserve other RevisionPackage semantics

Continue preserving:
- content_delta.mode;
- added/removed/extraction unit ids;
- supersede_actions;
- archive_actions;
- added_assertion_ids;
- diagnostics;
- requires_manual_review;
- lifecycle_reason;
- trace_id;
- provenance_id.

Do not force default-safe values over supplied semantics.

---

## 8. §6 remains regression-only

No redesign.

Keep:
- no content -> ABSTAIN;
- fake anchor -> ABSTAIN;
- invalid validation -> ABSTAIN;
- supported evidence -> non-empty grounded answer.

---

## 9. Public MCP boundary

Remain exactly four:

- curate_assertion_set
- knowledge_curator_health
- retrieve_evidence
- validate_retrieved_claims

Native DSH tools remain separate preset-scoped tools.

---

## 10. Frozen boundaries

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
- `integration/dsh/tests/**`;
- `results/**`.

No dependency on:
- `system/workflow_orchestration/**`;
- `system/task_planner/**`.

---

## 11. Regression gates

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Also run:
- real pinned DSH native harness;
- installed package/subpath qualification.

Required:
- 0 failed
- 0 skipped
- 0 xfailed

---

## 12. Qualification artifact

Create:

`results/phase-si-4-r9-dsh-qualification.md`

Include actual:
- pinned DSH SHA;
- Node/pnpm;
- native harness command + exit code;
- `ctx.tools.schemas(agent)`;
- §5 ToolExecutionResult;
- §7 ToolExecutionResult == approval_required;
- package pack/install command;
- package subpath resolution output;
- product preset activation result;
- public MCP exact-four result.

No descriptive-only PASS.

---

## 13. R9 executor report

Create:

`results/phase-si-4-r9-executor-report.md`

Required minimum:

```
Phase SI-4-R9 implementation CODE SHA:

R8 real native DSH chain preserved:
PASS/FAILED
evidence:

native harness hard-fails on failed assertions:
PASS/FAILED
evidence:

native §5 exact PUBLISHED:
PASS/FAILED
evidence:

native §7 exact APPROVAL_REQUIRED:
PASS/FAILED
evidence:

real ToolRuntime input/output validation:
PASS/FAILED
evidence:

bundle pnpm pack:
PASS/FAILED
evidence:

tarball installed into pinned DSH environment:
PASS/FAILED
evidence:

package subpath actually resolved:
PASS/FAILED
evidence:

product preset activated without broken diagnostic:
PASS/FAILED
evidence:

CurationReport safety fields fail closed:
PASS/FAILED
evidence:

AlignedPair typed hydration:
PASS/FAILED
evidence:

CarriedAssertionRecord typed hydration:
PASS/FAILED
evidence:

AssertionTransition typed hydration:
PASS/FAILED
evidence:

§6 regressions:
PASS/FAILED
evidence:

public MCP exactly four:
PASS/FAILED
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

installed package qualification:
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

## 14. Completion protocol

1. implement only SI-4-R9;
2. make the real native harness fail hard on assertion failures;
3. make native no-approval §7 return exact approval_required;
4. perform real package pack/install/subpath qualification;
5. finish fail-closed CurationReport safety hydration;
6. finish typed RevisionPackage nested hydration;
7. run all regressions;
8. create R9 qualification artifact;
9. create R9 executor report;
10. commit implementation;
11. push main;
12. update `status.json`:
    - phase = SI-4-R9
    - actor = executor
    - state = executor_complete
    - latest_commit = <R9 CODE SHA>
    - result_expected = results/phase-si-4-r9-executor-report.md
13. commit/push bookkeeping;
14. verify clean tree and HEAD == origin/main;
15. STOP.

Do not start SI-5.

## 15. Final acceptance question

R9 passes only if:

```
real pinned DSH native execution = proven
AND
native §5 = PUBLISHED
AND
native §7 no approval = APPROVAL_REQUIRED
AND
installed package subpath = actually resolved
AND
transport hydration = fail-closed/typed
AND
public MCP = exactly four
AND
frozen core = unchanged
```

Then Planner may mark the Knowledge Curator DSH package
ACCEPTED / FROZEN / DELIVERABLE.
