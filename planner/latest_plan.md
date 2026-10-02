# Phase SI-4 Plan — DSH Knowledge Curator Agent Package

Planner: ChatGPT  
Executor: MiMo / Kimi / Codex  
State: READY_FOR_EXECUTOR

## Goal

Complete the original delivery target:

Build a deployable DSH Agent package for AI4S-ED Knowledge Curator.

Scope is the curator part of the literature knowledge pipeline:

- Section 5: knowledge curation and evidence governance
- Section 6: evidence-grounded anti-hallucination retrieval QA
- Section 7: knowledge lifecycle update and incremental governance

Do not redesign the whole AI4S-ED architecture.

## Target Package

Create or complete:

```
dsh/knowledge-curator/
    agent.yaml
    prompt.md
    tools.yaml
    schemas/
    runtime/
    README.md
```

The package must be loadable by DSH as an Agent.

## Agent Responsibilities

### 1. Knowledge Curation Agent

Input:

```
AssertionSet
```

Process:

```
Completeness Check
        |
Conflict Detection
        |
Quality Scoring
        |
Decision
        |
Atomic Commit
```

Output:

```
CurationReport
```

Must preserve:

- provenance_id
- trace_id
- evidence reference
- confidence

### 2. Evidence QA Agent

Implement evidence-first answering:

```
Question
   |
Evidence Retrieval
   |
EvidenceBundle
   |
Validation
   |
Answer / Abstain
```

Requirements:

- No unsupported claims
- Confidence propagation
- Evidence citation required
- Abstain when evidence is insufficient

### 3. Knowledge Lifecycle Governance

Support:

```
New Assertion
      |
Compare Existing Knowledge
      |
Revision / Conflict / Merge
      |
New Version Snapshot
```

Reuse existing revision workflow where possible.

## Integration Boundary

Reuse existing:

- knowledge_curator core
- EvidenceBundle
- MCP tools
- CurationCommitWorkflow
- RevisionPublicationWorkflow
- Agent Runtime

Do not:

- replace existing runtime
- create unrelated autonomous research agents
- modify lit_researcher implementation

## Tests

Add DSH-level verification:

```
integration/dsh/tests/test_knowledge_curator_agent.py
```

Verify:

- Agent loading
- Tool registration
- Curation flow
- Evidence QA flow
- Abstain behavior
- Revision flow
- Existing regression tests remain passing

## Deliverables

Required:

```
dsh/knowledge-curator/
results/phase-si-4-curator-agent-report.md
```

Update status.json:

```
phase: SI-4
actor: executor
state: executor_complete
```

STOP after implementation. Wait for Planner review before further expansion.
