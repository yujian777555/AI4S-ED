# Phase SI-2B-R1 Plan — Revision Publication Qualification Closure

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Why R1 is required

SI-2B implementation CODE SHA:

`d2d69f63550d2ece3d74d3b02be41614ba78250f`

Executor merge HEAD reviewed:

`f61a5e05804e1967f4e6c3b8a452318478eca751`

The production design is directionally correct, but Planner review found the committed qualification does **not** yet prove several mandatory SI-2B acceptance claims.

Therefore SI-2B is **NOT YET ACCEPTED/FROZEN**.

R1 is a narrow closure phase. Do not redesign the architecture.

---

## 1. Findings to close

### R1-01 — Mandatory workflow scenarios are missing

`integration/system/tests/test_si2b_workflow.py` currently contains only 8 test functions.

Missing mandatory SI-2B workflow qualification includes:

- lifecycle pending surfaced without hidden retry;
- lifecycle retry recovery;
- post-bind / pre-journal-finalization recovery;
- material conflict fail-closed;
- stale/wrong approval scope conflict;
- historical version/snapshot resolvability;
- curation gate integrity;
- trace/provenance propagation into lifecycle/publication artifacts where frozen semantics support it.

Executor report claimed these items PASS, but committed tests do not prove them.

Add explicit tests.

### R1-02 — Approval tests are too permissive

Current approval tests accept broad status sets such as:

```
("approval_required", "finalized", "failed", "conflict")
```

and:

```
("approval_rejected", "finalized", "failed", "conflict")
```

This does not prove approval behavior.

Build deterministic fixtures that require manual adjudication and assert exactly:

- no approval -> `PublicationStatus.APPROVAL_REQUIRED`;
- rejected approval -> `PublicationStatus.APPROVAL_REJECTED`;
- no target commit/version side effect.

### R1-03 — Mandatory tests contain skip escape hatches

Current full-publication/replay tests contain conditional `pytest.skip(...)`.

Remove these escape hatches from mandatory SI-2B tests.

Required behavior must be asserted exactly:

- full publication -> `FINALIZED`;
- replay -> `FINALIZED`, `idempotent=True`, `resumed=True`.

A regression must fail, not skip.

### R1-04 — Target pending test does not prove status or recovery

Strengthen the target pending test.

First invocation with injected commit pending failure must assert:

- result.status == `PublicationStatus.TARGET_PENDING`;
- publication coordinator invoked exactly once;
- workflow has no hidden retry.

After clearing failure, second identical invocation must assert:

- result.status == `PublicationStatus.FINALIZED`;
- saga resumes rather than restarts destructively;
- no duplicate target/final versions.

### R1-05 — Lifecycle pending / recovery must be proven

Inject a deterministic lifecycle failure after target publication.

First invocation must assert:

- `LIFECYCLE_PENDING` (or the exact frozen documented status if the frozen coordinator uses another specific fail-closed status for that injected failure);
- one workflow->publication delegation;
- target publication remains persisted;
- no hidden retry.

After clearing the failure:

- second invocation reaches `FINALIZED`;
- target version is reused, not duplicated;
- final lifecycle version is created once.

Do not modify frozen lifecycle/revision coordinators.

### R1-06 — Post-bind journal recovery must be proven

Inject failure after source-version bind succeeds but before publication journal acknowledges `FINALIZED`.

Verify:

- first call returns the frozen failure result;
- source version is already bound to the expected final version/snapshot;
- second materially identical call detects the already-correct binding;
- journal reaches `FINALIZED`;
- result = `FINALIZED`, `idempotent=True`, `resumed=True`;
- no extra KB versions.

### R1-07 — Conflict qualification must be explicit

Add tests for at least:

1. changed target assertion / CommitRequest material under same publication identity;
2. stale/wrong `RevisionApproval.scope_hash`.

Expected:

- `PublicationStatus.CONFLICT` or the exact frozen fail-closed status required by the coordinator;
- never silently overwrite prior material;
- no unauthorized publication.

Prefer exact `CONFLICT` where frozen coordinator explicitly returns it.

### R1-08 — Historical safety must be asserted

For a successful PREPRINT_TO_JOURNAL publication:

- capture prior KB version/snapshot;
- capture target commit version/snapshot;
- capture final lifecycle version/snapshot;
- assert all historical versions/snapshots remain resolvable;
- assert final version is distinct from target;
- assert final version's `prior_version_id == target_version_id`;
- assert the new source version binds only to final version/snapshot.

No destructive update/delete semantics.

### R1-09 — Curation gate integrity must be asserted

Create a target `CommitRequest` whose curation report contains a non-publishable decision (for example REJECT).

Invoke the SI-2B workflow.

Assert the frozen coordinator fails closed and no final publication is produced.

The workflow must not mutate decisions or promote them.

### R1-10 — Trace/provenance qualification

Use non-empty package/request/approval trace/provenance IDs.

After successful publication, inspect the frozen artifacts available through the test-local stores and prove trace/provenance are preserved wherever frozen core semantics specify them, including lifecycle records/events and publication journal fields when applicable.

Do not invent new trace semantics.

### R1-11 — MCP/DSH boundary regression tests are missing

The SI-2B plan required proof that adding a `revision` provider group does not alter the existing MCP surface.

Add integration/system or integration/dsh qualification that constructs the existing MCP server with a provider bundle containing `commit` + `revision` and asserts the public Knowledge Curator tool names remain exactly:

- `curate_assertion_set`
- `knowledge_curator_health`
- `retrieve_evidence`
- `validate_retrieved_claims`

No new publication/lifecycle tool.

DSH preset must remain unchanged.

### R1-12 — Object-shaped revision split-brain bypass

`system/revision_application_composition._extract_revision_deps()` accepts dict-shaped and object-shaped revision groups.

However current `_reject_split_brain()` only checks forbidden store keys for a dict-shaped revision group.

Close this asymmetry.

For object-shaped revision groups, if any non-None attribute exists for:

- `version_store`
- `commit_store`
- `document_commit_store`

composition must fail closed exactly as for dict-shaped groups.

Add regression tests for object-shaped split-brain attempts.

Do not broaden the blacklist beyond the specified store ownership boundary.

### R1-13 — Test-local LifecycleStore is not fully Port-compatible

Fix only the SI-2B integration fixture.

Current mismatches include:

- `append_assertion_records(...)` should return the appended record list as the Port specifies;
- `latest_document_state(ref_id, at_version_id=None)` must accept the Port argument shape;
- `latest_assertion_state(assertion_id, ref_id, at_version_id=None)` must use the Port argument order/signature.

Also ensure test-local append semantics are sufficiently idempotent to validate retry behavior:

- lifecycle document records: deterministic identity must not silently create duplicates;
- lifecycle assertion records: replay must not duplicate the same lifecycle/assertion identity;
- EventOutbox: append must be idempotent by `event_id`.

Do not import or delegate to frozen checked-in InMemory adapters.

### R1-14 — Test-local append-only registry safety

The SI-2B fixture is described as protocol-compatible and append-only.

Harden same-ID replay behavior for test-local `SourceVersionRegistry` / publication journal sufficiently so tests cannot silently overwrite contradictory material and still pass.

Do not build a second production state machine; this is test-fixture integrity only.

---

## 2. Production code allowed to change

Only if needed for the confirmed R1 finding:

- `system/revision_application_composition.py`

Specifically the object-shaped split-brain check.

`system/workflows/revision_publication.py` should remain unchanged unless a concrete defect is discovered and reported.

---

## 3. Integration code allowed to change

- `integration/system/fixtures/si2b_provider.py`
- `integration/system/tests/test_si2b_composition.py`
- `integration/system/tests/test_si2b_workflow.py`

Optional additive test file is allowed if it keeps tests clearer.

Do not weaken or delete existing tests.

---

## 4. Frozen boundaries — MUST remain unchanged

Do not modify:

- `knowledge_curator/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `system/application_composition.py`
- `system/workflows/curation_commit.py`
- `dsh/knowledge-curator/**`
- `planner/CONTRACT_GAPS.md`

Knowledge Curator freeze:

`42e39121af5f6120174e088a521c9ad014abdcda`

SI-1 freeze:

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

SI-1.5 freeze:

`0f014f0a3aad75a6cada18874fead10414469d6b`

SI-2A freeze:

`95d55e71390a2e7266b2084243161101c5aff60a`

If closing R1 appears to require changing frozen code, STOP and report the blocker.

---

## 5. Test-quality rules

Mandatory R1 acceptance tests:

- MUST use exact expected statuses where the frozen coordinator defines them;
- MUST NOT use broad "one of success/failure/conflict" assertions merely to keep tests green;
- MUST NOT contain `pytest.skip`, `xfail`, conditional early return, or equivalent escape hatches;
- MUST prove side-effect counts/state, not only returned status;
- MUST prove no hidden workflow retry;
- MUST prove retry/resume does not duplicate versions/lifecycle/events.

---

## 6. Regression gates

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Pre-R1 reported baseline:

- knowledge_curator: 522 passed / 0 skipped / 0 failed
- integration/system: 134 passed / 0 skipped / 0 failed
- integration/dsh: 90 passed / 0 skipped / 0 failed

All new and existing SI-2B/R1 mandatory tests:

**0 skipped / 0 xfailed**

Do not weaken previous suites.

---

## 7. Freeze comparison

Use SI-2B-R1 Planner handoff HEAD as comparison base.

Before completion prove zero changes under all frozen boundaries in §4.

Also report whether `system/workflows/revision_publication.py` changed. Expected: NO unless a confirmed defect is discovered.

---

## 8. Required R1 report

Create:

`results/phase-si-2b-r1-executor-report.md`

Report:

```
Phase SI-2B-R1 implementation CODE SHA:

approval_required exact assertion:
PASS / FAILED

approval_rejected exact assertion:
PASS / FAILED

mandatory pytest.skip/xfail removed:
PASS / FAILED

target pending exact status:
PASS / FAILED

target recovery to FINALIZED:
PASS / FAILED

lifecycle pending exact status:
PASS / FAILED

lifecycle recovery to FINALIZED:
PASS / FAILED

post-bind journal recovery:
PASS / FAILED

material conflict:
PASS / FAILED

approval scope conflict:
PASS / FAILED

historical versions/snapshots resolvable:
PASS / FAILED

curation gate integrity:
PASS / FAILED

trace/provenance preservation:
PASS / FAILED

MCP surface remains exactly four:
PASS / FAILED

object-shaped split-brain rejected:
PASS / FAILED

SI-2B test fixture Port signatures corrected:
PASS / FAILED

lifecycle/outbox replay idempotency in fixture:
PASS / FAILED

source/publication fixture contradictory overwrite prevented:
PASS / FAILED

new public MCP tool added:
NO

DSH preset changed:
NO

system/workflows/revision_publication.py changed:
NO / YES + reason

frozen upstream files changed:
NO

knowledge_curator:
...

integration/system:
...

integration/dsh:
...

mandatory SI-2B/R1 skips:
0

mandatory SI-2B/R1 xfails:
0

deviations:
NONE / describe
```

---

## 9. Completion protocol

1. implement R1 closure only;
2. run all regression gates;
3. create R1 report;
4. commit and push main;
5. update `status.json`:
   - `phase = "SI-2B-R1"`
   - `actor = "executor"`
   - `state = "executor_complete"`
   - `latest_commit = <actual R1 CODE SHA>`
   - `result_expected = "results/phase-si-2b-r1-executor-report.md"`;
6. STOP;
7. do not start any next phase.

## 10. Acceptance principle

SI-2B-R1 is a qualification closure, not a redesign.

The goal is to make the committed evidence match the claims:

- exact approval boundaries;
- exact pending/recovery semantics;
- recoverable publication saga;
- no split-brain;
- historical safety;
- real idempotency;
- exact four-tool MCP boundary.

Only after this evidence is committed will Planner consider SI-2B for ACCEPTED / FROZEN status.
