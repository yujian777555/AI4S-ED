# AI4S-ED Knowledge Curator — DSH Agent Package

AI4S-ED Knowledge Curator Agent for DeepSeek Harness (DSH 0.2.0-rc.1).

## Capabilities

Implements document 03 (文献自动调研与知识入库流水线):

- **Section 5**: Knowledge curation and atomic commit (策审与入库)
- **Section 6**: Evidence-grounded anti-hallucination QA (反幻觉检索问答)
- **Section 7**: Knowledge lifecycle update and incremental governance (更新与增量治理)

## Architecture

```
DSH Agent
  -> Internal Bridge (system/curator_agent_bridge.py)
    -> Existing Workflows (CurationCommitWorkflow / RevisionPublicationWorkflow)
      -> Frozen Coordinators (DocumentCommitCoordinator / RevisionPublicationCoordinator)
        -> Stores
```

## DSH Version

```
deepseek-harness 0.2.0-rc.1
commit 4878cdabd87d4041bdaff61d04c966883b9fd07a
```

## Installation

```bash
cd dsh/knowledge-curator
# Via DSH plugin manager
dsh plugin --profile web add file:$(pwd)
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `AI4S_KC_PYTHON` | Yes | Python executable for MCP server |
| `AI4S_KC_WORKSPACE` | Yes | Workspace root |
| `AI4S_SYSTEM_ADAPTER_FACTORY` | Yes | Provider factory (`package.module:factory_function`) |

Example (integration testing only):
```bash
export AI4S_SYSTEM_ADAPTER_FACTORY=integration.system.fixtures.dsh_provider:create_provider_bundle
```

## Public MCP Tools

Exactly four:

- `mcp__knowledge_curator__curate_assertion_set`
- `mcp__knowledge_curator__knowledge_curator_health`
- `mcp__knowledge_curator__retrieve_evidence`
- `mcp__knowledge_curator__validate_retrieved_claims`

## Internal Workflow Bridge

Commit and revision are **internal capabilities**, not MCP tools:

- `system/curator_agent_bridge.py` composes `CurationCommitWorkflow` and `RevisionPublicationWorkflow`
- Bridge delegates to frozen workflows; does not reimplement state machines

## Section 5: Curation + Commit

```
AssertionSet -> curate_assertion_set -> CurationReport
  -> CurationCommitWorkflow -> CommitResult -> KB Version
```

For publishable curation: `PUBLISHED`, exactly one KB version.
For blocked curation: no commit attempted.

## Section 6: Evidence QA

```
Question -> retrieve_evidence -> EvidenceBundle
  -> validate_retrieved_claims -> Answer / ABSTAIN
```

- Every supported answer requires BOTH `retrieve_evidence` AND `validate_retrieved_claims`
- Unsupported claims -> `ABSTAIN`
- Citations must map to actual evidence records

## Section 7: Revision

```
RevisionPackage -> RevisionPublicationWorkflow -> New KB Version
```

- Immutable version history preserved
- Replay is idempotent (`IDEMPOTENT_HIT`)
- Approval-required status respected

## Boundaries

This bundle declares only one Agent Preset. It does NOT contain:
- @deepseek-ai/dsh-agent-preset-registry (global registry is system-level)
- Other Agent presets

## Out of Scope

- lit_researcher (document 02)
- parser/extractor stages (document 03 §3/§4)
- Generic scientific orchestration
- Experiment planning/execution
- RADE
- Global system orchestrator

## Testing

```bash
pytest knowledge_curator/tests
pytest integration/system/tests
pytest integration/dsh/tests
```
