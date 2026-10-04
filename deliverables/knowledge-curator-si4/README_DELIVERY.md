# AI4S-ED Knowledge Curator — SI-4 Delivery

## 1. Delivery Status

Status: **ACCEPTED / FROZEN / DELIVERABLE**

Final implementation CODE SHA: `322e53e3ac8319082188049e5e61e0ee13666540`

Final acceptance: `docs/acceptance/SI4_FINAL_ACCEPTANCE.md`

## 2. Module Purpose

The Knowledge Curator is the AI4S-ED scientific knowledge curation agent implementing document 03 (文献自动调研与知识入库流水线):

- **Section 5 — Evidence Curation**: completeness check, conflict detection, quality scoring, decision-making
- **Section 5.4 — Atomic Commit**: CurationCommitWorkflow → DocumentCommitCoordinator → KB version
- **Section 6 — Anti-hallucination Retrieval QA**: evidence-first answering with mandatory validation and ABSTAIN discipline
- **Section 7 — Lifecycle / Revision / Publication**: RevisionPublicationWorkflow → immutable new KB versions

## 3. Architecture

```
DSH Agent Preset (knowledge-curator)
        ↓
    Knowledge Curator
        ↓
    Native DSH tools (knowledge_curator_commit, knowledge_curator_revision)
        ↓
    Python application bridge (system.curator_agent_bridge_stdio)
        ↓
    AI4S_SYSTEM_ADAPTER_FACTORY → provider bundle
        ↓
    CuratorAgentBridge
        ↓
    CurationCommitWorkflow / RevisionPublicationWorkflow
        ↓
    Frozen Coordinators → Stores
```

## 4. Public MCP Tools (exactly four)

- `curate_assertion_set`
- `knowledge_curator_health`
- `retrieve_evidence`
- `validate_retrieved_claims`

## 5. DSH Native Tools (preset-scoped, NOT public MCP)

- `knowledge_curator_commit` — curate and commit via CurationCommitWorkflow
- `knowledge_curator_revision` — publish revision via RevisionPublicationWorkflow

## 6. DSH Pinned Baseline

- DeepSeek Harness: **0.2.0-rc.1**
- Pinned SHA: `4878cdabd87d4041bdaff61d04c966883b9fd07a`

## 7. Environment Variables

| Variable | Purpose |
|---|---|
| `AI4S_KC_PYTHON` | Python executable for MCP server |
| `AI4S_KC_WORKSPACE` | Workspace root path |
| `AI4S_SYSTEM_ADAPTER_FACTORY` | Provider factory (`package.module:factory_function`) |

## 8. DSH Package Installation

```bash
cd <AI4S_ED_ROOT>/dsh/knowledge-curator
pnpm pack
# Then install into DSH profile:
dsh plugin --profile web add file:$(pwd)
```

Or install the pre-built tarball from `packages/knowledge-curator-dsh/`:

```bash
pnpm add <path-to-tarball>.tgz
```

The product preset is defined in `cordis.patch.yml` and loaded by DSH's AgentPresetRegistry.

## 9. Python Runtime

```bash
export AI4S_KC_PYTHON=<python-executable>
export AI4S_KC_WORKSPACE=<AI4S_ED_ROOT>
export AI4S_SYSTEM_ADAPTER_FACTORY=<provider-factory>
python -m system.mcp_stdio
```

## 10. DSH Usage

The `knowledge-curator` preset is loaded via `cordis.patch.yml` which declares:
- `@deepseek-ai/dsh-persona` — agent persona
- `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js` — native bridge tools
- `@deepseek-ai/dsh-mcp-client` — MCP stdio connection

## 11. Verification

Accepted executor-reported regression baselines:

```
pytest knowledge_curator/tests        → 522 passed
pytest integration/system/tests       → 190 passed
pytest integration/dsh/tests          → 109 passed
```

## 12. Native Qualification

Verified through real pinned DSH runtime:

- `ctx.tools.schemas(agent)` = `["knowledge_curator_commit", "knowledge_curator_revision"]`
- `ctx.tools.schemas()` = `[]` (global isolation)
- §5 → `PUBLISHED`
- §7 → `APPROVAL_REQUIRED`

## 13. Package Qualification

Verified: `pnpm pack` → clean install → package subpath import → installed `cordis.patch.yml` → pinned DSH Loader → `knowledge-curator` declared → preset not broken.

## 14. Frozen Boundary

**This delivery is frozen.** Do not modify core code unless:
1. A confirmed bug is found; or
2. A new explicitly approved contract is required.

## 15. Known Scope

This delivery covers **Knowledge Curator / SI-4** only. It does not represent the entire AI4S-ED project.
