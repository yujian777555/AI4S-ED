# Phase SI-3A Plan — Agent Runtime Skeleton

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## Goal

Build the first product-level Agent Runtime layer on top of the accepted AI4S-ED system.

Current accepted capabilities:

- Knowledge Curator MCP tools
- CurationCommitWorkflow
- RevisionPublicationWorkflow
- Production composition boundaries

SI-3A does not redesign frozen components. It only creates the runtime entry layer.

## Scope

Create:

```
system/agent_runtime/
    __init__.py
    agent.py
    task_router.py
    workflow_registry.py
    execution_context.py
    result_protocol.py
    errors.py
```

## Required capabilities

### 1. Execution Context

Provide unified propagation:

- task_id
- trace_id
- provenance_id
- metadata

### 2. Workflow Registry

Register existing workflows:

- curation_commit
- revision_publication

Agent must access workflows through registry.

### 3. Task Router

Initial version uses explicit task types only.

Required:

- CURATION_COMMIT
- REVISION_PUBLICATION

No LLM planner in SI-3A.

### 4. AI4S Agent Runtime

Expose:

```python
agent.run(task, context)
```

Flow:

Agent
 -> Router
 -> Registry
 -> Workflow
 -> Result Protocol

Agent must not directly access stores or coordinators.

### 5. Result Protocol

Provide unified AgentResult containing:

- status
- workflow
- trace_id
- artifacts
- knowledge_changes
- error

## Tests

Add integration/system tests proving:

- valid runtime bootstrap
- missing provider fail closed
- invalid provider fail closed
- curation task dispatch
- revision task dispatch
- no direct store access
- existing MCP contract unchanged
- DSH preset unchanged

## Frozen boundaries

Do not modify:

- knowledge_curator/**
- system/composition.py
- system/provider_loader.py
- system/mcp_stdio.py
- system/application_composition.py
- system/workflows/curation_commit.py
- system/workflows/revision_publication.py
- dsh/knowledge-curator/**
- planner/CONTRACT_GAPS.md

## Regression gates

Run:

```
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

## Completion report

Executor must report:

```
Phase SI-3A implementation CODE SHA:

Agent Runtime created:
PASS
Workflow Registry:
PASS
Task Router:
PASS
Execution Context:
PASS
Agent API:
PASS
CurationCommit integration:
PASS
RevisionPublication integration:
PASS
Provider fail-closed:
PASS
No direct store access:
PASS
MCP changed:
NO
DSH changed:
NO
Frozen files changed:
NO

knowledge_curator:
...
integration/system:
...
integration/dsh:
...

deviations:
NONE / describe
```

STOP after completion. Do not start SI-3B.
