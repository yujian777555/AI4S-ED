# Phase SI-3B Plan — Scientific Task Planner

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## Goal

Extend the accepted SI-3A Agent Runtime with a deterministic Scientific Task Planner layer.

SI-3B adds task understanding and workflow selection only. Do not redesign Agent Runtime, workflows, MCP, or DSH.

## Architecture

```
User Task
    |
    v
ScientificTaskPlanner
    |
    v
TaskPlan
    |
    v
AI4SAgent Runtime
    |
    v
WorkflowRegistry
    |
    +----------------+
    |                |
    v                v
CurationCommit   RevisionPublication
Workflow         Workflow
```

## Scope

Create:

```
system/task_planner/
    __init__.py
    planner.py
    task_classifier.py
    plan_protocol.py
    errors.py
```

## Required capabilities

### TaskClassifier

First version deterministic only.

Support:

- RETRIEVE
- CURATION_COMMIT
- REVISION_PUBLICATION

No LLM planner.

### TaskPlan Protocol

Must contain:

- task_id
- task_type
- workflow_name
- parameters
- trace_id
- provenance_id

### Runtime integration

Extend flow:

```
AI4SAgent
    |
ScientificTaskPlanner
    |
TaskRouter
    |
WorkflowRegistry
    |
Workflow
```

## Forbidden

Do not modify:

- knowledge_curator/**
- system/workflows/curation_commit.py
- system/workflows/revision_publication.py
- dsh/knowledge-curator/**

Do not add:

- new MCP tools
- DSH changes
- multi-agent system
- autonomous research loop

## Tests

Add:

```
integration/system/tests/test_task_planner.py
```

Verify:

- retrieve classification
- curation classification
- revision classification
- invalid task fail closed
- provenance preservation
- Agent Runtime consumes TaskPlan
- WorkflowRegistry boundary preserved
- MCP unchanged
- DSH unchanged

## Regression

Run:

```
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```

## Completion

Update status.json:

```
phase: SI-3B
actor: executor
state: executor_complete
```

Create:

```
results/phase-si-3b-executor-report.md
```

STOP after completion. Do not start SI-4 without Planner review.
