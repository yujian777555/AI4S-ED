# Phase SI-4-R2 Plan — Real DSH Runtime & End-to-End Curator Qualification

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Planner verdict on SI-4-R1

Reviewed implementation CODE SHA:

`144253167cfb2cf43c117ae96898ec72e2d1f1fe`

Reviewed bookkeeping HEAD:

`05cddbee7a4f600608e633e118c021d6c7bd278e`

Verdict:

**SI-4-R1 NOT ACCEPTED — R2 REQUIRED**

R1 improved the code substantially, but several PASS claims in
`results/phase-si-4-r1-executor-report.md` are not proven by the committed
implementation/tests.

R2 is qualification/closure only. Do not broaden scope.

---

## 1. Blocking finding: package.json references files that do not exist

Current `dsh/knowledge-curator/package.json` exports/lists:

- `runtime/agent.js`
- `runtime/handlers.js`
- `runtime/context.js`
- `runtime/bridge.js`

But current `dsh/knowledge-curator/runtime/` contains only:

- `__init__.py`
- `agent.py`
- `handlers.py`
- `context.py`

There are no committed `.js` runtime files.

Therefore R1-01 is not accepted.

### Required fix

Choose one real packaging design.

If DSH requires JS/TS plugin runtime:
- implement the real supported JS/TS plugin files;
- make package.json reference only files that exist;
- ensure packed artifact contains them.

If Python runtime files are only test helpers:
- do not falsely export them as JS;
- document their role accurately.

No manifest entry may point to a nonexistent file.

Add a mandatory automated test that verifies every path in package.json
`files` and local export targets exists before pack.

Also capture real package-manager dry-run output in the R2 report.

---

## 2. Blocking finding: DSH preset still does not load the internal bridge

Current authoritative DSH chain is still:

```
package.json
  -> cordis.patch.yml
    -> @deepseek-ai/dsh-agent-preset
      -> persona
      -> @deepseek-ai/dsh-mcp-client
        -> python -m system.mcp_stdio
```

`cordis.patch.yml` was unchanged in R1 and contains no path that loads:

- `runtime/agent.py`;
- `runtime/handlers.py`;
- `system/curator_agent_bridge.py`.

The MCP server intentionally exposes exactly four tools:

- curate_assertion_set
- knowledge_curator_health
- retrieve_evidence
- validate_retrieved_claims

Therefore the DSH Agent currently has no demonstrated runtime path to
`CurationCommitWorkflow` or `RevisionPublicationWorkflow`.

R1-02/R1-04/R1-07 are not accepted.

### Required fix

Inspect the pinned DeepSeek Harness source:

- version: `0.2.0-rc.1`
- source commit: `4878cdabd87d4041bdaff61d04c966883b9fd07a`

Implement the smallest **real supported DSH plugin/bridge path**.

Requirements:

```
DSH knowledge-curator preset
        |
        v
supported DSH local plugin / runtime bridge
        |
        v
internal Python application bridge
        |
        +--> CurationCommitWorkflow
        |
        +--> RevisionPublicationWorkflow
```

The bridge MUST be actually reachable from the mounted DSH Agent.

Do not add public MCP commit/revision tools.

Do not invent unsupported Cordis/DSH YAML fields.

If DSH 0.2.0-rc.1 cannot support an internal bridge without public MCP exposure,
STOP and document the blocker instead of faking integration.

---

## 3. Blocking finding: “DSH mount PASS” test is only string matching

Current R1 tests called DSH mount tests only verify text such as:

- `knowledge-curator` occurs in `cordis.patch.yml`;
- preset ID text exists.

This does NOT prove:

- package installation;
- Cordis patch loading;
- preset registration;
- Agent preset mount;
- child plugin startup;
- MCP startup/discovery.

R1-08 actual DSH qualification is not accepted.

### Required real qualification

Use the already-proven isolated DSH 0.2.0-rc.1 runtime strategy.

Mandatory qualification must actually:

1. pack/install the local `dsh/knowledge-curator` package;
2. start/load DSH configuration;
3. show preset `knowledge-curator` registered;
4. mount the preset into an Agent context;
5. start the MCP child plugin using a test provider;
6. discover exactly four MCP tools;
7. exercise the internal bridge action/path added in R2.

The mandatory path must not require a live model API key.

If needed, use a deterministic/fake model only for DSH Agent construction.

Save machine-readable/log evidence under `results/` or a qualification fixture,
and reference it from the report.

---

## 4. Blocking finding: §5 test uses MockBridge, not the real workflow

Current `test_publishable_curation_commits` uses:

```python
class MockBridge:
    async def curate_and_commit(...):
        return CurateAndCommitResult(status="published", commit_attempted=True)
```

This proves only handler plumbing.

It does not prove:

- `CuratorAgentBridge`;
- `CurationCommitWorkflow`;
- `DocumentCommitCoordinator`;
- PUBLISHED;
- IDEMPOTENT_HIT;
- one-version invariant.

R1-04 is not accepted.

### Required §5 end-to-end tests

Use the already-qualified SI-2A provider/workflow fixtures.

At least:

#### §5-E2E-A publish

```
real CuratorAgentBridge
  -> real CurationCommitWorkflow
  -> qualified coordinator/store fixtures
```

Assert:

- commit attempted;
- status == PUBLISHED;
- exactly one finalized/published KB version.

#### §5-E2E-B replay

Run identical source identity + fingerprint + material again.

Assert:

- status == IDEMPOTENT_HIT (or exact frozen enum value);
- version count remains exactly one.

#### §5-E2E-C blocked

Use actual curation terminal result, or a faithful public-tool fixture matching
frozen semantics, and prove bridge/workflow is not called.

No MockBridge is sufficient for acceptance of publish/replay semantics.

Handler unit tests may keep mocks in addition to the E2E tests.

---

## 5. Blocking finding: §7 test uses MockBridge, not RevisionPublicationWorkflow

Current `test_revision_delegates_to_workflow` uses a MockBridge that simply
returns `finalized`.

It does not prove:

- real `CuratorAgentBridge.revise`;
- real `RevisionPublicationWorkflow`;
- FINALIZED;
- historical version preservation;
- bind to final version;
- replay idempotency;
- APPROVAL_REQUIRED preservation.

R1-07 is not accepted.

### Required §7 end-to-end tests

Reuse the already-qualified SI-2B/R1 fixtures and real workflow.

Prove at least:

1. valid same-work revision -> exact FINALIZED;
2. final version differs from target where frozen semantics require it;
3. prior/target/final versions remain resolvable;
4. source-version binding points to final version;
5. finalized replay is idempotent;
6. approval-required result is preserved exactly;
7. no physical historical deletion.

No MockBridge-only test may satisfy these acceptance items.

---

## 6. §6 still does not produce a meaningful evidence-derived answer

R1 correctly added:

```
retrieve_evidence
  -> validate_retrieved_claims
```

But current candidate claim text is:

```
"Based on <chunk_id>: <original question>"
```

This is not a scientific claim derived from evidence.

The final answer is only:

```
"Based on N validated claims from M evidence records."
```

This does not actually answer the user's scientific question.

R1-05 call ordering is improved, but R1-06 “supported claims grounded/cited” is
not fully accepted as product behavior.

### Required §6 design

Do NOT fabricate scientific prose in deterministic Python.

Implement one coherent supported path:

### Preferred

Use the DSH model layer to synthesize candidate claims from EvidenceBundle,
then call `validate_retrieved_claims`, then allow only validated claims into
the final DSH response.

Mandatory no-live-key tests may use a deterministic fake model whose output is
derived from fixture evidence.

OR

### Deterministic structured mode

Return a structured evidence answer containing evidence-derived statement/value
fields already present in evidence records, then validate those exact claims.

In either mode:

- candidate claim text must be evidence-derived, not question-derived;
- validation must occur before final supported response;
- each returned factual claim maps to resolved anchors;
- fake/nonexistent anchor fails closed;
- unsupported validation -> ABSTAIN;
- final response contains actual claim content, not just counts.

---

## 7. Prompt/preset/runtime must describe one real execution model

Current `prompt.md`, README, Python runtime, and `cordis.patch.yml` still
describe partly different execution models.

After R2 there must be one authoritative model:

```
DSH Agent
  -> public evidence/curation MCP tools
  -> supported internal bridge for commit/revision
  -> frozen application workflows
```

Update persona/prompt only as needed so they accurately describe what the
mounted DSH Agent can actually invoke.

Do not claim a capability in README/prompt unless the DSH runtime path can
actually execute it.

---

## 8. Public MCP remains exactly four tools

This remains frozen:

```
curate_assertion_set
knowledge_curator_health
retrieve_evidence
validate_retrieved_claims
```

Keep the unconditional exact-equality test.

Do NOT solve R2 by adding:

- commit_document;
- publish;
- revise;
- revision_publication;

to the public MCP server.

---

## 9. Frozen boundaries

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
- `system/curator_agent_bridge.py`;
- smallest additional DSH-local bridge/plugin file required by supported API;
- integration fixtures/tests/results.

Do not depend on:

- `system/workflow_orchestration/**`;
- `system/task_planner/**`.

---

## 10. Required tests

Mandatory R2 tests must include real behavior, not just file/string assertions.

### Packaging

- every `package.json files` entry exists;
- every local export target exists;
- real `npm/pnpm pack --dry-run` succeeds;
- packed file list contains required runtime/plugin/config/schema files.

### DSH runtime

- real DSH 0.2.0-rc.1 package install/load;
- real preset registration;
- real preset mount;
- child plugins start;
- exactly four public MCP tools discovered;
- real internal bridge path callable from mounted agent/plugin context.

### §5

- real bridge + real workflow publish;
- real replay/idempotency;
- blocked -> no commit.

### §6

- retrieve -> validate invocation order;
- evidence-derived candidate claim;
- actual grounded claim returned;
- citations resolved;
- fake anchor blocked;
- validation reject -> ABSTAIN.

### §7

- real bridge + real RevisionPublicationWorkflow;
- FINALIZED;
- history retained;
- final binding correct;
- replay idempotent;
- approval-required preserved.

Mocks may exist only for isolated unit tests, not for the acceptance E2E claims.

---

## 11. Regression

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

R1 reported baseline:

- knowledge_curator: 522 passed
- integration/system: 190 passed
- integration/dsh: 106 passed

Required:

- 0 failed;
- 0 skipped;
- 0 xfailed;
- no conditional acceptance branches.

Also run actual DSH/package qualification command(s) and record exact commands
and exit codes.

---

## 12. R2 report

Create:

`results/phase-si-4-r2-executor-report.md`

Required fields:

```
Phase SI-4-R2 implementation CODE SHA:

package manifest references only existing files:
PASS / FAILED

real package dry-run:
PASS / FAILED
command:
exit code:
packed file evidence:

real DSH 0.2.0-rc.1 load:
PASS / FAILED
command:
exit code:

knowledge-curator preset actually registered:
PASS / FAILED

knowledge-curator preset actually mounted:
PASS / FAILED

exactly four public MCP tools discovered:
PASS / FAILED

internal commit/revision bridge reachable from mounted DSH path:
PASS / FAILED

§5 real CurationCommitWorkflow invoked:
PASS / FAILED

§5 publish -> PUBLISHED:
PASS / FAILED

§5 replay -> IDEMPOTENT_HIT:
PASS / FAILED

§5 version count remains one after replay:
PASS / FAILED

§5 blocked -> no commit:
PASS / FAILED

§6 retrieve before validate:
PASS / FAILED

§6 candidate claim derived from evidence:
PASS / FAILED

§6 final answer contains validated claim content:
PASS / FAILED

§6 citations resolve to retrieved evidence:
PASS / FAILED

§6 fake anchor blocked:
PASS / FAILED

§6 rejected/unsupported -> ABSTAIN:
PASS / FAILED

§7 real RevisionPublicationWorkflow invoked:
PASS / FAILED

§7 valid revision -> FINALIZED:
PASS / FAILED

§7 historical versions retained:
PASS / FAILED

§7 final source-version binding correct:
PASS / FAILED

§7 finalized replay idempotent:
PASS / FAILED

§7 approval-required preserved:
PASS / FAILED

new public MCP tools:
NO

direct store access:
NO

workflow_orchestration dependency:
NO

task_planner dependency:
NO

frozen files changed:
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

live model round-trip:
PASS / NOT_RUN_ENV

deviations:
NONE / describe
```

---

## 13. Completion protocol

1. implement only SI-4-R2 closure;
2. run all real qualifications;
3. commit implementation;
4. push main;
5. create/update R2 report;
6. update status.json:
   - phase = SI-4-R2
   - actor = executor
   - state = executor_complete
   - latest_commit = <R2 CODE SHA>
   - result_expected = results/phase-si-4-r2-executor-report.md
7. verify working tree clean and origin/main matches bookkeeping HEAD;
8. STOP.

Do not start another phase.

---

## 14. Final R2 acceptance question

R2 passes only if this is demonstrably true:

> A mounted DSH 0.2.0-rc.1 `knowledge-curator` Agent can actually reach the
> frozen §5 commit workflow and §7 revision workflow through a supported
> internal path, can answer §6 questions with real evidence-derived validated
> claims or ABSTAIN, and the package manifest contains only real shippable
> runtime files — while the public MCP surface remains exactly four tools.

String-presence tests and MockBridge-only tests are insufficient.
