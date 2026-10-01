# System Integration Audit — Planner Review

Date: 2026-10-01  
Planner: ChatGPT  
Reviewed audit commit: `7ba62124ca684091f083a61c2610342f8720ca07`

## Verdict

**ACCEPTED**

The audit is consistent with the repository state and does not modify frozen Knowledge Curator implementation.

## Verified findings

### Gap A — Production Runtime Composition

Confirmed.

`knowledge_curator/mcp_server/runtime.py` constructs the curation runtime from:

- `InMemoryKnowledgeRepository`
- `SimpleOntologyService`
- `FakeMechanismValidator`

This is explicitly labelled integration-test wiring.

`knowledge_curator/mcp_server/evidence_runtime.py` correctly fails closed in the production-default path and only enables the synthetic evidence fixture under the explicit integration-fixture flag.

There is no production adapter composition/bootstrap layer.

### Gap B — System-Level Orchestrator

Confirmed.

The repository currently contains DSH presets, MCP server integration, frozen Knowledge Curator coordinators, and integration tests, but no project-level application bootstrap / workflow owner / system orchestrator.

### Gap C — Curation → Commit Wiring

Confirmed.

The public MCP curation tool performs:

`AssertionSet -> KnowledgeCurator.curate() -> CurationReport`

It does not invoke `DocumentCommitCoordinator`, `RevisionPublicationCoordinator`, or lifecycle/source-version workflow components. That separation is currently correct, but application-level wiring is absent.

## Important architecture observation

`create_mcp_server(...)` already accepts optional `CuratorRuntime` and `EvidenceRuntime` objects.

Therefore SI-1 must **reuse this existing injection point**. It must not expand the public MCP tool contract or move system orchestration into `app.py`.

## Planner phase decision

The audit's proposed direction is accepted, with a narrower implementation boundary:

### Phase SI-1 — Production Runtime Composition

SI-1 is limited to:

- production dependency composition;
- provider/bootstrap loading;
- fail-closed startup when production dependencies are absent or invalid;
- explicit separation of production vs integration/test adapters;
- system-level MCP stdio bootstrap using the existing `create_mcp_server(...)` injection point;
- tests proving the above.

SI-1 does **not** implement:

- CurationWorkflow;
- RevisionWorkflow;
- system orchestrator;
- curation→commit wiring;
- DSH preset migration to the new system bootstrap;
- real external database/vector/ontology implementations;
- new public MCP tools;
- any Knowledge Curator core/schema/port/retrieval semantic changes.

Those are later system-integration phases after SI-1 is accepted.

## Freeze constraints

Knowledge Curator remains:

**ACCEPTED / FROZEN / DELIVERABLE**

Implementation freeze SHA:

`42e39121af5f6120174e088a521c9ad014abdcda`

No Phase 5.4 is authorized.

`planner/CONTRACT_GAPS.md` must not be modified during SI-1.

## Next action

Execute `planner/latest_plan.md` as **Phase SI-1** and stop after the required executor report is pushed.
