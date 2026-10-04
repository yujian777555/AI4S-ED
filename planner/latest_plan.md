# Phase SI-4-R9-R2 Plan — Installed Product Preset Activation Evidence

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

Formal review:

`planner/phase-si-4-r9-r1-review.md`

## Scope

Evidence-only final closure.

Do not modify Knowledge Curator business logic, workflows, or accepted R9
transport semantics unless the installed product activation exposes a concrete
package-only bug.

---

## 1. Preserve accepted baseline

Do not reopen:
- real pinned native DSH architecture;
- native §5 exact PUBLISHED;
- native §7 exact APPROVAL_REQUIRED;
- ToolRuntime validation;
- R9 typed/fail-closed hydration;
- clean tarball install;
- installed bridge subpath import;
- MCP exact-four boundary.

---

## 2. Hard-assert global scope isolation

In the existing native harness, after:

```js
const global = ctx.tools.schemas().map(row => row.name)
```

add a hard assertion that neither native curator tool is present globally.

Rerun the real pinned native harness.

Expected:
- exit 0;
- scoped view contains both curator native tools;
- global view excludes both;
- §5 = PUBLISHED;
- §7 = APPROVAL_REQUIRED.

---

## 3. Activate the installed tarball's own product patch

Use a clean installed environment containing the R9-R1 packed tarball.

Resolve the installed path for:

`@ai4s-ed/knowledge-curator-dsh/cordis.patch.yml`

The path MUST point under the clean environment's
`node_modules/@ai4s-ed/knowledge-curator-dsh`, not the AI4S source checkout.

Then use pinned DeepSeek Harness 0.2.0-rc.1 / SHA
`4878cdabd87d4041bdaff61d04c966883b9fd07a` to consume that installed patch
through its real Loader/app-boot/profile path.

Record:
- exact resolved installed patch path;
- exact DSH command;
- cwd;
- exit code;
- stdout/stderr relevant lines;
- `knowledge-curator` preset declared;
- no broken diagnostic.

A source patch or YAML string check does not satisfy this step.

---

## 4. Prefer installed preset mount

If the pinned API/profile permits it without changing product code, additionally:
- mount the installed `knowledge-curator` preset into a real Agent;
- record `ctx.tools.schemas(agent)`;
- verify the two native curator tools.

This is preferred but the hard minimum is real installed-patch Loader activation
with preset healthy/not broken, because the exact bridge subpath import and
native runtime execution are already separately proven.

---

## 5. Qualification artifact

Create:

`results/phase-si-4-r9-r2-dsh-qualification.md`

Include:
- pinned DSH SHA;
- native harness command/exit;
- explicit global isolation assertion result;
- native §5 result;
- native §7 result;
- clean install directory;
- installed package path;
- installed `cordis.patch.yml` resolved path;
- DSH Loader/app-boot activation command/exit;
- preset declared result;
- preset broken=false evidence;
- public MCP exact-four result.

---

## 6. Regression

Because this is evidence-only:
- rerun the real native DSH harness;
- rerun installed-package activation qualification;
- run the existing relevant integration/dsh regression at minimum.

If implementation/package files change, rerun all mandatory pytest suites:
- knowledge_curator/tests;
- integration/system/tests;
- integration/dsh/tests.

No skipped/xfailed mandatory tests.

---

## 7. Frozen boundaries

Do not modify:
- `knowledge_curator/**`;
- frozen system composition/workflows;
- `planner/CONTRACT_GAPS.md`;
- accepted R9 transport hydration.

Allowed:
- qualification harness;
- qualification results;
- test evidence;
- package metadata/patch only if actual installed activation exposes a concrete
  package bug;
- status/report.

---

## 8. Executor report

Create:

`results/phase-si-4-r9-r2-executor-report.md`

Required:

```
Phase SI-4-R9-R2 CODE SHA:

R9-R1 native baseline preserved:
PASS/FAILED

global isolation hard-asserted:
PASS/FAILED
evidence:

native §5 exact PUBLISHED:
PASS/FAILED

native §7 exact APPROVAL_REQUIRED:
PASS/FAILED

clean tarball install preserved:
PASS/FAILED

installed package path:
...

installed cordis.patch.yml resolved path:
...

pinned DSH consumed installed patch:
PASS/FAILED
command:
...
exit:
...

knowledge-curator preset declared:
PASS/FAILED

installed preset broken:
NO / YES

installed preset native tools:
... / NOT_RUN

public MCP exactly four:
PASS/FAILED

qualification artifact committed:
PASS/FAILED

frozen implementation changed:
NO / describe package-only fix

deviations:
NONE
```

---

## 9. Completion

1. add global hard assertion;
2. rerun native harness;
3. activate installed tarball's own patch with pinned DSH;
4. prove preset declared/not broken;
5. commit qualification artifact;
6. commit executor report;
7. push;
8. update status:
   - phase = SI-4-R9-R2
   - actor = executor
   - state = executor_complete
   - latest_commit = <CODE/EVIDENCE SHA>
   - result_expected = results/phase-si-4-r9-r2-executor-report.md
9. push bookkeeping;
10. verify HEAD == origin/main and clean tree;
11. STOP.

Do not start SI-5.

If installed product activation cannot be performed, return BLOCKER with the real
command/error instead of PASS.
