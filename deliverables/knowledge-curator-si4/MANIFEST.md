# MANIFEST — AI4S-ED Knowledge Curator SI-4 Delivery

## Runtime (required)

| File/Directory | Purpose | Required | Source |
|---|---|---|---|
| source/knowledge_curator/ | Knowledge Curator core (§5/§6/§7) | Yes | knowledge_curator/** |
| source/system/composition.py | Production composition | Yes | system/composition.py |
| source/system/provider_loader.py | Provider loading | Yes | system/provider_loader.py |
| source/system/mcp_stdio.py | MCP stdio entry | Yes | system/mcp_stdio.py |
| source/system/application_composition.py | SI-2A composition | Yes | system/application_composition.py |
| source/system/revision_application_composition.py | SI-2B composition | Yes | system/revision_application_composition.py |
| source/system/curator_agent_bridge.py | Internal bridge | Yes | system/curator_agent_bridge.py |
| source/system/curator_agent_bridge_stdio.py | Bridge stdio entry | Yes | system/curator_agent_bridge_stdio.py |
| source/system/workflows/curation_commit.py | §5 workflow | Yes | system/workflows/curation_commit.py |
| source/system/workflows/revision_publication.py | §7 workflow | Yes | system/workflows/revision_publication.py |
| source/system/agent_runtime/ | Agent runtime (SI-3A) | Yes | system/agent_runtime/** |
| source/dsh/knowledge-curator/ | DSH Agent package | Yes | dsh/knowledge-curator/** |

## DSH Package

| File | Purpose | Required | Source |
|---|---|---|---|
| packages/knowledge-curator-dsh/*.tgz | Pre-built DSH tarball | Yes | pnpm pack output |

## Tests

| File/Directory | Purpose | Required | Source |
|---|---|---|---|
| tests/knowledge_curator/ | Core unit tests (522) | Yes | knowledge_curator/tests/** |
| tests/integration-system/ | SI-2A/SI-2B tests | Yes | integration/system/tests/** |
| tests/integration-dsh/ | DSH integration tests | Yes | integration/dsh/tests/** |
| tests/integration-dsh/fixtures/ | Test providers | Yes | integration/dsh/fixtures/** |

## Documentation

| File | Purpose | Required | Source |
|---|---|---|---|
| README_DELIVERY.md | Delivery entry point | Yes | Generated |
| VERSION.txt | Version info | Yes | Generated |
| docs/architecture/ | Architecture docs | Yes | docs/*.md |
| docs/acceptance/SI4_FINAL_ACCEPTANCE.md | Final acceptance | Yes | planner/SI4_FINAL_ACCEPTANCE.md |

## Evidence

| File | Purpose | Required | Source |
|---|---|---|---|
| evidence/qualification/phase-si-4-r9-r1-*.md | R9-R1 qualification | Yes | results/ |
| evidence/qualification/phase-si-4-r9-r2-*.md | R9-R2 qualification | Yes | results/ |
| evidence/qualification/phase-si-4-r8-*.md | R8 milestone (historical) | Optional | results/ |
| evidence/qualification/*.mjs | Native harness | Yes | integration/dsh/qualification/ |
