# SI-4 FINAL ACCEPTANCE — Knowledge Curator DSH Delivery

Planner: ChatGPT  
Final reviewed implementation CODE SHA: `322e53e3ac8319082188049e5e61e0ee13666540`  
Executor bookkeeping HEAD: `d8227baf09e523a066f564a1843fd3cae8801acd`  
Pinned DeepSeek Harness: `0.2.0-rc.1`  
Pinned DSH SHA: `4878cdabd87d4041bdaff61d04c966883b9fd07a`

## Final Verdict

**ACCEPTED / FROZEN / DELIVERABLE**

Phase SI-4 is complete.

No further SI-4 implementation round is required.

---

## Accepted delivery

The Knowledge Curator is accepted as a DSH-deliverable agent package for the
AI4S-ED system, with the accepted frozen Knowledge Curator domain/runtime core
and the completed DeepSeek Harness product integration.

The delivery covers:

- §5 curation and commit application path;
- §6 evidence-grounded fail-closed QA behavior;
- §7 revision/publication application path;
- DSH preset packaging;
- preset-scoped native application tools;
- public MCP surface of exactly four tools;
- real pinned DSH runtime qualification;
- installed package/subpath qualification;
- installed product patch/preset activation qualification.

---

## Final native DSH qualification

Accepted real runtime chain:

```
DeepSeek Harness 0.2.0-rc.1
@ 4878cdabd87d4041bdaff61d04c966883b9fd07a
        ↓
real Cordis Context
        ↓
real ToolRuntime
        ↓
real AgentPresetRegistry
        ↓
real Agent scope
        ↓
knowledge-curator preset
        ↓
exact shipped curator bridge plugin
        ↓
defineTool
        ↓
ctx.tools.schemas(agent)
        ↓
ctx.tools.execute(..., agent)
        ↓
JS spawn/stdin bridge
        ↓
Python application bridge
        ↓
deployment provider factory
        ↓
accepted §5 / §7 application workflows
        ↓
real ToolRuntime output validation
```

Observed scoped native tools:

```json
[
  "knowledge_curator_commit",
  "knowledge_curator_revision"
]
```

Observed global tool view:

```json
[]
```

Global isolation is hard-asserted by the qualification harness.

---

## §5 native application acceptance

Observed real ToolRuntime result:

```json
{
  "isError": false,
  "value": {
    "status": "published",
    "commit_attempted": true,
    "blocked_reason": null
  }
}
```

**ACCEPTED**

---

## §7 native application acceptance

Observed real ToolRuntime result:

```json
{
  "isError": false,
  "value": {
    "status": "approval_required",
    "error": null
  }
}
```

The qualification harness requires exact `approval_required`; wrong status is
a hard failure.

**ACCEPTED**

---

## Installed package qualification

Accepted evidence includes:

- `pnpm pack` succeeded;
- tarball created and hashed;
- tarball installed into a clean environment;
- installed package exists under
  `node_modules/@ai4s-ed/knowledge-curator-dsh`;
- installed bridge subpath resolves/imports:
  `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`;
- imported bridge exposes:
  - `name = curator-bridge`;
  - `apply = function`;
- the installed tarball's own `cordis.patch.yml` was resolved from the clean
  installed package path;
- pinned DSH consumed the installed patch through its real Loader/app-boot
  configuration path;
- `knowledge-curator` preset was declared;
- no broken/error diagnostic was reported for the installed preset.

**ACCEPTED**

---

## Transport safety acceptance

Accepted transport boundary behavior includes:

- AssertionSet required identifiers validated;
- enum fields validated fail-closed;
- CurationReport safety-relevant fields explicitly required;
- no permissive silent defaults for accepted safety gates;
- `AlignedPair` hydrated as typed frozen model;
- `CarriedAssertionRecord` hydrated as typed frozen model;
- `AssertionTransition` hydrated as typed frozen model;
- invalid nested enums/identifiers fail closed;
- RevisionPackage semantics are not silently rewritten to an invented safe
  default.

**ACCEPTED**

---

## Public MCP boundary

The public MCP surface remains exactly:

1. `curate_assertion_set`
2. `knowledge_curator_health`
3. `retrieve_evidence`
4. `validate_retrieved_claims`

The DSH-native application tools:

- `knowledge_curator_commit`
- `knowledge_curator_revision`

remain preset-scoped native tools and are not added to the public MCP surface.

**ACCEPTED**

---

## Regression evidence

Executor-reported accepted regression baselines:

- `knowledge_curator`: 522 passed / 0 skipped / 0 failed
- `integration/system`: 190 passed / 0 skipped / 0 failed
- `integration/dsh`: 109 passed / 0 skipped / 0 failed

R9-R2 was evidence-only and reran the relevant DSH qualification/integration
regression without modifying frozen implementation code.

Planner did not independently rerun these pytest suites; acceptance is based on
the committed executor evidence plus independent source/diff inspection.

---

## Frozen boundaries

The following remain frozen unless a confirmed bug or new explicit contract is
approved:

- `knowledge_curator/**`
- accepted system composition/provider/MCP integration
- accepted §5 curation/commit workflow
- accepted §7 revision/publication workflow
- public four-tool MCP contract
- DSH preset/native tool boundary
- transport safety semantics closed in R9

Do not extend through:

- `system/workflow_orchestration/**`
- `system/task_planner/**`

as part of this accepted Knowledge Curator delivery.

---

## Final evidence artifacts

Accepted final artifacts include:

- `results/phase-si-4-r9-r1-dsh-qualification.md`
- `results/phase-si-4-r9-r1-executor-report.md`
- `results/phase-si-4-r9-r2-dsh-qualification.md`
- `results/phase-si-4-r9-r2-executor-report.md`

Historical Planner reviews remain as audit history for rejected/partial rounds.

---

## Freeze declaration

**Phase:** SI-4  
**Status:** ACCEPTED  
**Lifecycle:** FROZEN  
**Delivery:** DELIVERABLE  
**Final implementation CODE SHA:** `322e53e3ac8319082188049e5e61e0ee13666540`

Further work must start from a new explicitly approved phase/contract.

Do not silently reopen SI-4.
