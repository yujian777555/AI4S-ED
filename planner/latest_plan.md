# Phase SI-4-R1 Plan — DSH Knowledge Curator Agent Package Closure

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Verdict on SI-4 implementation ec15f6c

SI-4 implementation CODE SHA:

`ec15f6cb78e71ff0139edf915fabd6c419f5acab`

Bookkeeping HEAD reviewed:

`aa7419161e0a8696203e274a97afcfe6460854dd`

Planner verdict:

**R1 REQUIRED — NOT YET ACCEPTED/FROZEN**

The new files are a useful scaffold, but the committed code does not yet deliver the original task:

> a real DSH-loadable `knowledge_curator` agent package implementing document 03 §5 curation+commit, §6 evidence-grounded anti-hallucination QA, and §7 revision/lifecycle governance.

This R1 is a closure phase only. Do not broaden into a generic scientific agent/orchestrator.

---

## 1. Authoritative product scope

The deliverable is:

`dsh/knowledge-curator`

A DSH 0.2.0-rc.1 package for the **AI4S-ED Knowledge Curator Agent**.

The agent owns only document 03:

- §5 策审与入库;
- §6 反幻觉检索问答;
- §7 更新与增量治理.

It does NOT own:

- `lit_researcher` (§2);
- parser/extractor stages (§3/§4);
- generic scientific workflow orchestration;
- experiment planning/execution;
- RADE;
- global system orchestrator.

Input boundaries may therefore start from already-extracted `AssertionSet`, evidence query, or already-prepared revision material.

---

## 2. Planner findings that MUST be closed

### R1-01 — New agent files are not actually part of the DSH bundle

Current `dsh/knowledge-curator/package.json` still declares:

- exports only `cordis.patch.yml` + `package.json`;
- files only `cordis.patch.yml` + `README.md`;
- description says configuration-only.

Therefore these SI-4 additions are currently not shipped by the package:

- `agent.yaml`
- `prompt.md`
- `tools.yaml`
- `schemas/**`
- `runtime/**`

Fix the packaging contract.

At minimum, `pnpm pack --dry-run` / equivalent must show every runtime/config/schema file required by the shipped Knowledge Curator Agent.

Do not keep files that are never consumed by the DSH loading path merely to satisfy existence tests.

### R1-02 — DSH native loading path does not consume the new runtime

The authoritative DSH bundle is still loaded through:

`package.json -> dsh.bundle.patch -> cordis.patch.yml`

Current `cordis.patch.yml` does not consume:

- `agent.yaml`;
- `prompt.md`;
- `tools.yaml`;
- `runtime/agent.py`;
- `runtime/handlers.py`.

Prove a real DSH 0.2.0-rc.1 loading/invocation path.

Allowed approaches:

1. update the supported DSH preset/plugin composition so these artifacts are actually consumed; or
2. implement a small DSH-local plugin/bridge using supported 0.2.0-rc.1 APIs.

Do NOT invent unsupported DSH configuration semantics.

Before implementing, inspect the pinned DSH source/API and use a real supported mechanism.

### R1-03 — README contradicts the claimed SI-4 capability

Current README still says:

`§6 / §7 尚未实现的能力`

while SI-4 reports §6 and §7 PASS.

Update README so it accurately describes:

- what the package actually implements;
- DSH version;
- install/mount instructions;
- environment/provider requirements;
- public MCP surface;
- internal workflow bridge, if used;
- §5/§6/§7 examples;
- what remains out of scope.

No contradictory product claims.

### R1-04 — §5 currently curates but does NOT perform “策审入库”

Current `CurationHandler` only calls:

`curate_assertion_set`

and returns a CurationReport wrapper.

It never invokes the already accepted:

`CurationCommitWorkflow`

Therefore it does not satisfy document §5.4 atomic ingestion/version snapshot.

Required real behavior:

```
AssertionSet + SourceIdentity/application context
        |
        v
curation
        |
        v
CurationReport
        |
        v
CurationCommitWorkflow
        |
        v
CommitResult
```

For a publishable request, prove:

- commit is attempted;
- result reaches frozen coordinator semantics such as PUBLISHED / IDEMPOTENT_HIT;
- exactly one version is published;
- retry/idempotency semantics remain owned by the frozen workflow/coordinator.

For terminal curation outcomes, prove no commit occurs.

Do not add a public MCP commit tool.

The DSH package may use a DSH-local/internal application bridge to the existing workflow, but must not change the frozen four-tool MCP public contract.

### R1-05 — §6 does not call validate_retrieved_claims

Current `EvidenceQAHandler` performs:

`retrieve_evidence -> directly answer`

It does NOT call:

`validate_retrieved_claims`

despite the package prompt claiming that it does.

This is a blocking anti-hallucination defect.

Required path:

```
Question
   |
   v
retrieve_evidence
   |
   v
EvidenceBundle
   |
   v
candidate claim(s)
   |
   v
validate_retrieved_claims
   |
   +--> factual_allowed -> grounded answer
   |
   +--> guard/abstain -> ABSTAIN
```

No supported answer may bypass validation.

### R1-06 — §6 current “answer” is not evidence-derived

Current answer text is effectively:

`Based on N evidence records: {question}`

This is not an evidence-grounded scientific answer.

Do not synthesize unsupported prose inside a deterministic Python handler.

Choose one supported architecture and prove it:

- DSH LLM synthesizes candidate claims strictly from the retrieved EvidenceBundle, then the claims are validated before final response; OR
- a deterministic answer formatter returns evidence/claim objects without pretending to generate scientific prose.

In either case:

- every factual claim in the final answer must map to validated evidence;
- citation data must include available `ref_id`, locator/chunk identity, confidence, and source/access pointer where available;
- unsupported claims => ABSTAIN;
- medium/hypothesis evidence must not be promoted to verified/high language.

### R1-07 — §7 RevisionHandler is only a placeholder

Current `RevisionHandler` always returns:

`status = revision_ready`

with a note saying to delegate later.

It does not invoke:

`RevisionPublicationWorkflow`

and does not create a new KB version.

This does not implement §7.

Required integration:

```
prepared revision material
        |
        v
RevisionHandler
        |
        v
RevisionPublicationWorkflow
        |
        v
RevisionPublicationResult
        |
        v
FINALIZED / APPROVAL_REQUIRED / ... frozen status
```

For a valid same-work revision:

- prove final result reaches `FINALIZED`;
- new final version/snapshot exists;
- prior versions remain resolvable;
- no physical deletion;
- retry/replay remains idempotent.

For approval-required or conflicting material:

- preserve frozen result status;
- do not fabricate approval.

Do not add public revision MCP tools.

### R1-08 — The current tests prove file presence, not a real DSH product

Current package-loading tests mostly assert that files exist or contain strings.

Replace/add qualification that proves:

1. package can be packed with all required files;
2. package can be installed/mounted using DSH 0.2.0-rc.1 supported mechanism;
3. preset `knowledge-curator` appears in actual DSH config/runtime;
4. mounted agent can discover exactly the existing four MCP tools;
5. the §5 application path can actually commit through the internal workflow path;
6. §6 tool-call trace includes both retrieve + validate before an answered result;
7. unsupported §6 query returns ABSTAIN;
8. §7 application path actually reaches frozen revision workflow semantics.

No network is required for deterministic integration qualification; test-local provider fixtures are allowed.

### R1-09 — MCP four-tool test currently has a vacuous pass branch

Current test only compares exact names inside:

`if tool_names:`

If discovery returns an empty set, the test passes.

Remove this escape hatch.

Assert exact equality unconditionally:

```
{
  "curate_assertion_set",
  "knowledge_curator_health",
  "retrieve_evidence",
  "validate_retrieved_claims",
}
```

### R1-10 — Public MCP contract remains frozen

Do not change:

- `system/mcp_stdio.py`;
- existing four MCP tools;
- their frozen external behavior.

§5 commit and §7 revision must remain internal application-layer capabilities exposed to the DSH package through a non-public bridge supported by DSH/application runtime.

If the only way found requires adding public MCP business tools, STOP and report instead of changing the contract.

---

## 3. DSH package product shape

The final package may keep these files if they are real/consumed:

```
dsh/knowledge-curator/
  package.json
  cordis.patch.yml
  README.md
  prompt.md
  tools.yaml
  schemas/
  runtime/
  <optional supported DSH plugin/bridge files>
```

`agent.yaml` is optional.

Keep it only if the actual DSH loading path consumes it or it is explicitly documented as a portable manifest used by package code/tests.

Do not ship dead configuration.

---

## 4. Internal workflow bridge boundary

The package needs §5 commit and §7 revision while preserving exactly four public MCP tools.

Implement the smallest supported internal bridge.

Rules:

- DSH Agent / package -> internal application workflow bridge;
- bridge -> existing `CurationCommitWorkflow` / `RevisionPublicationWorkflow`;
- workflow -> frozen coordinator -> stores.

Forbidden:

- DSH package -> store directly;
- DSH package -> frozen coordinator directly when an accepted workflow exists;
- duplicated commit/revision state machine;
- new public MCP commit/revision tools.

The bridge may receive already-structured application inputs. It does not own parsing/extraction or literature research.

---

## 5. Required §5 tests

At minimum:

### publishable curation

- valid SourceIdentity + AssertionSet;
- real curation through accepted path;
- application workflow invoked;
- commit result = PUBLISHED;
- one KB version.

### replay

- identical source identity/material;
- result = IDEMPOTENT_HIT;
- still one KB version.

### blocked curation

For return_upstream / all REJECT:

- no application commit;
- explicit non-published result.

### provenance

- trace_id/provenance_id preserved through request/application result where frozen contract supports them.

---

## 6. Required §6 tests

### supported answer

Prove invocation order includes:

1. `retrieve_evidence`;
2. `validate_retrieved_claims`.

Only validated factual claims appear in answered output.

Citations must correspond to returned evidence records.

### unsupported answer

- no valid supporting evidence OR validation rejects the claim;
- final status = abstain;
- no unsupported factual answer.

### hallucination guard

At minimum prove:

- nonexistent chunk/reference cannot be presented as supported;
- guard finding causes abstain or explicit unsupported result.

Do not merely check the word "ABSTAIN" exists in prompt.md.

---

## 7. Required §7 tests

Use the already-qualified SI-2B/R1 revision application fixture/path.

Prove:

- valid PREPRINT_TO_JOURNAL or equivalent prepared RevisionPackage -> FINALIZED;
- final version != target version where frozen semantics require it;
- prior/target/final snapshots remain resolvable;
- source-version bind points to final version;
- finalized replay is idempotent;
- approval-required status is preserved when applicable;
- no historical physical deletion.

---

## 8. Package/load qualification

Add a product-level test or script that validates package contents.

At minimum:

`pnpm pack --dry-run` (or equivalent supported package manager command)

must include every required shipped file.

Also add actual DSH 0.2.0-rc.1 qualification using the already-proven isolated runtime strategy.

The test/report must distinguish:

- deterministic CI/package qualification;
- optional live model round-trip.

A live model credential must NOT be required for the mandatory suite.

---

## 9. Prompt/preset consistency

There must be one coherent behavior contract.

Current `cordis.patch.yml` persona says:

- do not generate final orchestrator-facing QA prose;

while new `prompt.md` claims full Evidence QA.

Resolve this intentionally.

For the standalone Knowledge Curator Agent package, its role is §5/§6/§7 knowledge curation, not global orchestration.

The prompt/preset must state:

- it may answer only evidence-grounded knowledge questions within §6;
- it must abstain when unsupported;
- it must not act as lit_researcher, global orchestrator, RADE, experiment agent, etc.

---

## 10. Out-of-scope detour code

The repository currently also contains earlier detour work such as:

- `system/workflow_orchestration/**`;
- `integration/system/tests/test_workflow_orchestration.py`.

These are **not part of the Knowledge Curator Agent package deliverable**.

Do not extend them in R1.

Do not make the DSH Knowledge Curator package depend on them.

Do not delete them in R1 unless removal is necessary for package correctness; cleanup can be a separate explicit housekeeping decision.

Likewise, SI-3 task-planner work is not a required dependency of this package.

---

## 11. Frozen boundaries

Do not modify:

- `knowledge_curator/**`;
- `system/composition.py`;
- `system/provider_loader.py`;
- `system/mcp_stdio.py`;
- `system/application_composition.py`;
- `system/workflows/curation_commit.py`;
- `system/workflows/revision_publication.py`;
- `planner/CONTRACT_GAPS.md`.

You MAY modify the DSH package itself because SI-4 is explicitly productizing it:

- `dsh/knowledge-curator/**`.

You MAY add the smallest new system/application bridge file if required, but it must only compose/delegate to accepted workflows and must not duplicate their logic.

If a frozen-core defect is discovered, STOP and report it.

---

## 12. Regression gates

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Pre-R1 executor-reported baseline:

- knowledge_curator: 522 passed / 0 skipped / 0 failed
- integration/system: 190 passed / 0 skipped / 0 failed
- integration/dsh: 104 passed / 0 skipped / 0 failed

Mandatory SI-4-R1 qualification:

- 0 skipped
- 0 xfailed
- no conditional pass/skip escape hatches.

---

## 13. Required report

Create:

`results/phase-si-4-r1-executor-report.md`

Report:

```
Phase SI-4-R1 implementation CODE SHA:

DSH package includes all runtime/config/schema files:
PASS / FAILED

actual DSH 0.2.0-rc.1 package mount:
PASS / FAILED

knowledge-curator preset visible:
PASS / FAILED

README/preset/prompt capability contract consistent:
PASS / FAILED

§5 publishable curation -> actual commit:
PASS / FAILED

§5 replay -> IDEMPOTENT_HIT / no duplicate version:
PASS / FAILED

§5 blocked curation -> no commit:
PASS / FAILED

§6 retrieve_evidence called:
PASS / FAILED

§6 validate_retrieved_claims called:
PASS / FAILED

§6 supported claims grounded/cited:
PASS / FAILED

§6 unsupported claim -> ABSTAIN:
PASS / FAILED

§7 RevisionPublicationWorkflow actually invoked:
PASS / FAILED

§7 valid revision -> FINALIZED:
PASS / FAILED

§7 historical versions retained:
PASS / FAILED

§7 finalized replay idempotent:
PASS / FAILED

public MCP tools exactly four:
PASS / FAILED

new public MCP commit/revision tool added:
NO

direct store access from DSH package:
NO

detour workflow_orchestration dependency:
NO

frozen upstream files changed:
NO

knowledge_curator tests:
...

integration/system tests:
...

integration/dsh tests:
...

mandatory SI-4-R1 skipped:
0

mandatory SI-4-R1 xfailed:
0

live model round-trip:
PASS / NOT_RUN_ENV

deviations:
NONE / describe
```

---

## 14. Completion protocol

1. implement SI-4-R1 closure only;
2. update package/load path so the delivered files are real;
3. prove §5/§6/§7 end-to-end semantics;
4. run all regression gates;
5. create R1 report;
6. commit and push `main`;
7. update `status.json`:
   - `phase = "SI-4-R1"`
   - `actor = "executor"`
   - `state = "executor_complete"`
   - `latest_commit = <actual R1 CODE SHA>`
   - `result_expected = "results/phase-si-4-r1-executor-report.md"`;
8. STOP;
9. do not start any generic Agent/orchestrator phase.

## 15. Acceptance principle

The acceptance question is now simple:

> Can another engineer take `dsh/knowledge-curator`, mount it in the pinned DSH runtime, and obtain a real Knowledge Curator Agent whose §5 curation can commit, §6 QA always retrieves+validates and abstains when unsupported, and §7 revision really publishes a new immutable knowledge version — without changing the frozen four-tool MCP contract?

Only when the answer is proven by committed tests is SI-4 deliverable.
