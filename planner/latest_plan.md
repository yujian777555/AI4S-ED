# Phase SI-2B Plan — Revision Publication Application Workflow

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## 0. Goal

Integrate the already frozen revision/lifecycle publication saga into the system application layer for **same-work source-version upgrades**, such as:

- preprint -> journal;
- corrected version;
- explicit same-work revision.

Target:

```
RevisionPackage + target CommitRequest + optional RevisionApproval
                         |
                         v
              RevisionPublicationWorkflow
                         |
                         v
            RevisionPublicationCoordinator
                         |
          +--------------+---------------+
          |                              |
          v                              v
DocumentCommitCoordinator      LifecycleRevisionCoordinator
          |                              |
          v                              v
target KB version              lifecycle KB version
          \______________________________/
                         |
                         v
             SourceVersionRegistry bind
                         |
                         v
            RevisionPublicationResult
```

This phase is **application composition + transport-independent workflow only**.

Do not implement the global AI4S-ED Orchestrator.

Do not expose publication as a new public MCP tool.

Do not implement direct external retraction orchestration in SI-2B.

---

## 1. Frozen baselines

### Knowledge Curator

CODE SHA:

`42e39121af5f6120174e088a521c9ad014abdcda`

Status:

**ACCEPTED / FROZEN / DELIVERABLE**

### SI-1 production composition

CODE SHA:

`073eb3efb1bf6616f2a68b6ef4f28df6a315f8f7`

Status:

**ACCEPTED / FROZEN**

### SI-1.5 DSH production wiring

Closure SHA:

`0f014f0a3aad75a6cada18874fead10414469d6b`

Status:

**ACCEPTED / FROZEN**

### SI-2A curation -> commit application workflow

CODE SHA:

`95d55e71390a2e7266b2084243161101c5aff60a`

Planner acceptance:

`planner/phase-si-2a-final-acceptance.md`

Status:

**ACCEPTED / FROZEN**

Do not modify frozen SI-2A production files.

---

## 2. Authoritative frozen revision behavior

Do not reimplement logic already owned by:

- `knowledge_curator.core.revision_publication.RevisionPublicationCoordinator`
- `knowledge_curator.core.lifecycle.LifecycleRevisionCoordinator`
- `knowledge_curator.core.version_delta.RevisionPackageBuilder`
- `knowledge_curator.core.source_identity.IncrementalIntakeService`

The frozen `RevisionPublicationCoordinator` already owns the recoverable saga:

1. validate RevisionPackage / lineage / target CommitRequest;
2. enforce package review gate;
3. enforce explicit approval when the lifecycle draft requires manual adjudication;
4. bind approval scope to the real target CommitRequest;
5. invoke `DocumentCommitCoordinator` for target knowledge publication;
6. surface target pending states;
7. invoke `LifecycleRevisionCoordinator.apply_revision()`;
8. publish a new immutable lifecycle version;
9. bind the new source version to final KB version/snapshot;
10. journal phases and resume safely after partial failures;
11. detect request/material conflicts;
12. return authoritative `RevisionPublicationStatus` semantics.

Do not reproduce this state machine in `system/**`.

---

## 3. SI-2B scope

SI-2B covers only source-version revision publication where a frozen `RevisionPackage` already exists.

Examples:

- PREPRINT_TO_JOURNAL;
- REVISION_OF;
- CORRECTED_VERSION;
- EXPLICIT_SAME_WORK.

The application caller supplies:

- a frozen `RevisionPackage`;
- the matching target `CommitRequest`;
- optional frozen internal `RevisionApproval`.

SI-2B does **not** own PDF/XML parsing, content alignment, delta extraction, assertion extraction, or manual review UI.

The higher-level orchestrator remains future work.

---

## 4. Explicitly out of scope

Do not implement in SI-2B:

- global System Orchestrator;
- Agent Factory;
- public workflow API over HTTP;
- new MCP tools;
- DSH changes;
- parser/extractor;
- source discovery/crawling;
- automatic construction of public WorkIdentity contracts;
- automatic manual-approval UI or approval service;
- direct RETRACTION external-trigger workflow;
- direct standalone CORRIGENDUM trigger workflow outside RevisionPackage flow;
- event-bus delivery consumer;
- real database/vector/ontology adapters;
- packaging/release extraction.

Direct retraction/corrigendum trigger orchestration belongs to a later lifecycle integration phase.

---

## 5. New production application files

Recommended minimum:

```
system/revision_application_composition.py
system/workflows/revision_publication.py
```

Existing:

`system/workflows/__init__.py`

may be updated only to export the new workflow if needed.

Do not modify:

- `system/application_composition.py`;
- `system/workflows/curation_commit.py`.

Those are frozen SI-2A implementation.

---

## 6. Provider bundle contract

Reuse:

`AI4S_SYSTEM_ADAPTER_FACTORY=package.module:factory_function`

Do not create another environment variable.

The provider may now contain:

```python
{
    "curator": {...},        # existing required loader group
    "evidence": {...},       # existing optional group
    "commit": {              # accepted SI-2A group
        "commit_store": ...,
        "structural_store": ...,
        "vector_index": ...,
        "usdo_store": ...,
        "version_store": ...,
        "provider_identity": "...",
    },
    "revision": {
        "source_registry": ...,
        "lifecycle_store": ...,
        "event_outbox": ...,
        "publication_store": ...,
        "provider_identity": "...",
    },
}
```

The `revision` group MUST NOT own a second version store or a second document commit store.

SI-2B composition must reuse the exact `commit.version_store` and `commit.commit_store` instances so the target-commit and lifecycle-publication sides cannot split into different persistence universes.

If the revision group attempts to provide alternate `version_store` or `commit_store` / `document_commit_store`, fail closed rather than silently ignoring a split-brain configuration.

---

## 7. Revision dependency Ports

Validate the revision group before returning the application runtime.

Required runtime-checkable Ports:

- `SourceVersionRegistry`
- `LifecycleStore`
- `EventOutbox`
- `RevisionPublicationStore`

The version store comes from the accepted SI-2A `commit` group.

The document commit store comes from the accepted SI-2A `commit` group.

Reuse SI-2A commit dependency extraction/validation where practical without modifying SI-2A files.

---

## 8. Forbidden production adapters

SI-2B production composition must reject the known checked-in test/in-memory lifecycle adapters, including at minimum:

- `InMemoryLifecycleStore`
- `InMemoryEventOutbox`
- `InMemoryRevisionPublicationStore`
- `InMemorySourceVersionRegistry`

and objects originating from their known checked-in in-memory adapter modules.

Continue to rely on SI-2A commit validation to reject:

- InMemoryDocumentCommitStore;
- InMemoryStructuralKnowledgeStore;
- InMemoryVectorIndex;
- InMemoryUSDOStore;
- InMemoryVersionStore.

Validation must remain narrow and deterministic.

---

## 9. Application composition

Implement:

`system.revision_application_composition.compose_revision_publication_application(...)`

Suggested runtime object:

`RevisionPublicationApplicationRuntime`

containing at minimum:

- `document_commit_coordinator`;
- `lifecycle_coordinator`;
- `revision_publication_coordinator`;
- `source_registry`;
- provider identity/diagnostics.

Optional:

- `revision_package_builder`

may be exposed if built directly from the same validated `source_registry`, but SI-2B workflow tests must use a prebuilt RevisionPackage as the workflow boundary.

### Required construction

Using one loaded provider bundle:

1. extract and validate existing SI-2A commit dependencies;
2. construct/reuse a `DocumentCommitCoordinator` over those exact dependencies;
3. validate revision dependencies;
4. construct `LifecycleRevisionCoordinator` with:
   - validated lifecycle_store;
   - validated event_outbox;
   - **the exact commit.version_store instance**;
5. construct `RevisionPublicationCoordinator` with:
   - validated publication_store;
   - validated source_registry;
   - **the exact commit.version_store instance**;
   - the LifecycleRevisionCoordinator above;
   - the DocumentCommitCoordinator above;
   - **the exact commit.commit_store instance**.

Do not load the provider factory twice during one composition call.

A provider factory is allowed to create stateful adapters; double loading could create split state and is forbidden.

---

## 10. Workflow API

Implement:

`system.workflows.revision_publication.RevisionPublicationWorkflow`

Recommended API:

```python
result = await workflow.run(
    package=revision_package,
    target_commit_request=commit_request,
    approval=revision_approval_or_none,
)
```

The workflow should be deliberately thin.

It MUST delegate authoritative semantics to:

`RevisionPublicationCoordinator.publish(...)`

exactly once per workflow invocation.

Return the frozen `RevisionPublicationResult` directly unless a wrapper is absolutely necessary.

Do not invent another publication-status enum.

---

## 11. No automatic approval

The workflow MUST NOT:

- synthesize a `RevisionApproval`;
- mark manual adjudication as passed;
- generate a fake approver;
- rewrite the package to bypass review;
- mutate approval scope hashes.

If the frozen coordinator returns:

- `APPROVAL_REQUIRED`;
- `APPROVAL_REJECTED`;
- `PACKAGE_REVIEW_REQUIRED`;

return that result immediately.

CG-021 remains an external/public contract gap.

SI-2B uses the existing internal frozen `RevisionApproval` model only for application integration tests and internal callers.

Do not present it as a newly frozen cross-team public approval API.

---

## 12. No hidden retries

The workflow MUST NOT internally retry:

- `TARGET_PENDING`;
- `LIFECYCLE_PENDING`;
- `FAILED`;
- `CONFLICT`.

Return immediately.

Recovery occurs when the caller invokes the workflow again with materially identical:

- RevisionPackage;
- target CommitRequest;
- RevisionApproval, if required.

The frozen publication journal/coordinators own resume/idempotency.

---

## 13. Authoritative publication statuses

SI-2B must preserve the frozen statuses without translation:

- `APPROVAL_REQUIRED`
- `APPROVAL_REJECTED`
- `PACKAGE_REVIEW_REQUIRED`
- `TARGET_PENDING`
- `LIFECYCLE_PENDING`
- `CONFLICT`
- `FAILED`
- `FINALIZED`

Do not collapse them into generic success/failure booleans.

---

## 14. Approval scope behavior

The approval scope is bound to the actual:

- RevisionPackage;
- target CommitRequest.

Use the frozen:

`compute_publication_scope_hash(...)`

when integration tests need to construct a valid `RevisionApproval`.

The workflow itself should not silently recalculate and overwrite an approval's scope.

A changed package/request with an old approval must surface `CONFLICT`.

---

## 15. Integration-only SI-2B provider fixture

Add:

`integration/system/fixtures/si2b_provider.py`

It may reuse/import the accepted SI-2A **test-local fixture** to obtain the five test-local commit dependencies.

Add test-local protocol-compatible implementations for:

- SourceVersionRegistry;
- LifecycleStore;
- EventOutbox;
- RevisionPublicationStore.

It MUST NOT import/instantiate/subclass/wrap/delegate to:

- `knowledge_curator.adapters.in_memory_lifecycle.*`;
- `knowledge_curator.adapters.in_memory_revision_publication.*`;
- `knowledge_curator.adapters.in_memory_source_versions.*`.

Production `system/**` must never import this fixture.

Failure injection is encouraged for:

- target commit;
- lifecycle publication;
- publication journal finalization.

---

## 16. Required composition tests

Add:

`integration/system/tests/test_si2b_composition.py`

At minimum prove:

1. missing `revision` group fails closed;
2. missing source_registry fails;
3. missing lifecycle_store fails;
4. missing event_outbox fails;
5. missing publication_store fails;
6. malformed source_registry fails Port validation;
7. malformed lifecycle_store fails;
8. malformed event_outbox fails;
9. malformed publication_store fails;
10. known checked-in InMemory lifecycle/source/publication adapters are rejected;
11. valid test-local dependency set composes;
12. resulting runtime contains existing `DocumentCommitCoordinator`;
13. resulting runtime contains existing `LifecycleRevisionCoordinator`;
14. resulting runtime contains existing `RevisionPublicationCoordinator`;
15. lifecycle coordinator and publication coordinator use the **same VersionStore instance** as the commit group;
16. publication coordinator uses the **same DocumentCommitStore instance** as the commit group;
17. provider factory is invoked once per composition;
18. an extra `revision` group does not change the existing MCP surface;
19. public Knowledge Curator MCP tools remain exactly four.

No skipped SI-2B composition tests.

---

## 17. Required workflow tests

Add:

`integration/system/tests/test_si2b_workflow.py`

Use a realistic same-work revision fixture, preferably PREPRINT_TO_JOURNAL because the frozen core already has explicit lineage semantics for it.

### A. approval required

For a draft requiring manual adjudication:

- call workflow without approval;
- result = `APPROVAL_REQUIRED`;
- document commit coordinator not called;
- no new KB version.

### B. rejected approval

- valid scope, decision REJECTED;
- result = `APPROVAL_REJECTED`;
- no target commit.

### C. package review required

- `package.requires_manual_review=True`;
- result = `PACKAGE_REVIEW_REQUIRED`;
- no target commit.

### D. full publication

With valid package/request/approval where required:

- result = `FINALIZED`;
- target commit publishes a target version;
- lifecycle publishes the final lifecycle version;
- final version is distinct from target version;
- final version prior points to target version as required by frozen semantics;
- new source version is bound to final version/snapshot;
- publication journal phase = FINALIZED.

### E. final replay

Run the same material again:

- result = `FINALIZED`;
- `idempotent=True`;
- `resumed=True`;
- no additional target/final versions;
- no duplicate lifecycle records/events.

### F. target pending

Inject a transient target commit failure that yields:

- `PENDING_VECTOR` or `PENDING_FINALIZE` at the commit layer;
- application result = `TARGET_PENDING`;
- workflow invokes publication coordinator once only;
- no hidden retry.

Clear the failure and invoke workflow again:

- publication resumes;
- result = `FINALIZED`;
- no duplicate target/final publication.

### G. lifecycle pending

Inject lifecycle failure after target publication:

- first result = `LIFECYCLE_PENDING` (or frozen documented failure form where appropriate);
- no hidden retry;
- target publication is not duplicated.

Clear failure and invoke again:

- result = `FINALIZED`;
- saga resumes from journal state.

### H. post-bind journal recovery

Inject failure after source-version bind but before journal FINALIZED acknowledgement.

First invocation may return FAILED.

Second identical invocation must:

- detect already-correct source binding;
- finalize journal idempotently;
- return `FINALIZED`;
- not create additional versions.

### I. material/scope conflict

Change target assertion material or CommitRequest material while reusing an existing publication/package identity.

Expected:

- `CONFLICT` or frozen fail-closed result;
- no silent overwrite.

Use an approval with stale/wrong scope hash:

- expected `CONFLICT`;
- no side effects beyond already-existing safe state.

### J. curation gate integrity

A target CommitRequest containing non-publishable curation decisions must not be promoted by the application workflow.

The frozen coordinator must reject/fail closed.

### K. trace/provenance

For a valid flow, verify the existing trace/provenance fields survive into publication/lifecycle records/events where frozen core semantics provide them.

---

## 18. Historical/version safety

SI-2B must prove at integration level that publication:

- creates new immutable versions;
- does not physically delete prior versions;
- keeps prior snapshots resolvable;
- binds the new source version only to the final lifecycle version;
- does not rebind an already-bound source version to conflicting material.

Do not introduce destructive update semantics.

---

## 19. MCP / DSH boundary

Do not add:

- `publish_revision`;
- `apply_revision`;
- `retract_document`;
- `approve_revision`;

or any other public MCP tool.

Existing public Knowledge Curator tools remain exactly:

- `curate_assertion_set`
- `knowledge_curator_health`
- `retrieve_evidence`
- `validate_retrieved_claims`

Do not modify the DSH preset.

The current DSH 0.2.0-rc.1 Web runtime validation is independent of SI-2B.

---

## 20. Frozen files/directories

Do not modify:

- `knowledge_curator/**`
- `system/composition.py`
- `system/provider_loader.py`
- `system/mcp_stdio.py`
- `system/application_composition.py`
- `system/workflows/curation_commit.py`
- `dsh/knowledge-curator/**`
- `planner/CONTRACT_GAPS.md`

If a confirmed defect in frozen code blocks SI-2B:

**STOP and report it.**

Do not patch frozen code inside this phase.

---

## 21. Architectural dependency direction

Allowed:

```
system/workflows/revision_publication
       |
       v
system/revision_application_composition
       |
       +--> system/application_composition internal validation helpers
       |
       +--> frozen knowledge_curator coordinators / schemas / Ports
```

Forbidden:

```
knowledge_curator -> system
knowledge_curator -> DSH
system/workflows -> DSH
system/workflows -> MCP transport
```

The workflow remains transport-independent.

---

## 22. Regression gates

Run:

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

Accepted baseline before SI-2B:

- knowledge_curator: **522 passed / 0 skipped / 0 failed**
- integration/system: **107 passed / 0 skipped / 0 failed**
- integration/dsh: **90 passed / 0 skipped / 0 failed**

All new SI-2B mandatory tests:

**0 skipped**

No network dependency.

Do not weaken/delete/skip earlier tests.

---

## 23. Freeze verification

Compare final tree against the SI-2B Planner handoff commit.

Explicitly verify no changes under the frozen boundaries listed in §20.

Also verify:

- exactly four public MCP tools;
- DSH bundle unchanged;
- SI-2A files unchanged.

---

## 24. Required executor report

Create:

`results/phase-si-2b-executor-report.md`

Report at minimum:

```
Phase SI-2B implementation CODE SHA:

revision application composition:
PASS / FAILED

revision provider group fail-closed:
PASS / FAILED

four revision Ports validated:
PASS / FAILED

known InMemory lifecycle/revision/source adapters rejected:
PASS / FAILED

single provider load / no split-brain:
PASS / FAILED

shared commit/version store identity:
PASS / FAILED

RevisionPublicationWorkflow delegates exactly once:
PASS / FAILED

approval required:
PASS / FAILED

approval rejected:
PASS / FAILED

package review required:
PASS / FAILED

full revision publication FINALIZED:
PASS / FAILED

target pending surfaced without hidden retry:
PASS / FAILED

target retry recovery:
PASS / FAILED

lifecycle pending surfaced without hidden retry:
PASS / FAILED

lifecycle retry recovery:
PASS / FAILED

post-bind journal recovery:
PASS / FAILED

idempotent finalized replay:
PASS / FAILED

material/scope conflict fail-closed:
PASS / FAILED

historical versions remain resolvable:
PASS / FAILED

new public MCP tool added:
NO

DSH preset changed:
NO

SI-2A frozen production files changed:
NO

Knowledge Curator / SI-1 / SI-1.5 frozen tree changed:
NO

knowledge_curator tests:
...

integration/system tests:
...

integration/dsh tests:
...

deviations:
NONE / describe
```

---

## 25. Executor completion protocol

When implementation and tests are complete:

1. commit all SI-2B implementation/test/report changes;
2. push `main`;
3. update `status.json`:
   - `phase = "SI-2B"`
   - `actor = "executor"`
   - `state = "executor_complete"`
   - `latest_commit = <actual SI-2B CODE SHA>`
   - `result_expected = "results/phase-si-2b-executor-report.md"`;
4. STOP;
5. do not start the next phase;
6. wait for Planner review.

## 26. Acceptance principle

The point of SI-2B is not to invent another revision engine.

The point is to prove that the already frozen revision/publication/lifecycle machinery can be safely composed with production-style injected dependencies at the system application layer, while preserving:

- approval boundaries;
- atomic target commit semantics;
- lifecycle version evolution;
- resumability;
- idempotency;
- lineage binding;
- historical safety;
- existing DSH/MCP contracts.
