# DSH Web Smoke Test Report

DSH version: 0.2.0-rc.1
DSH SHA: 4878cdabd87d4041bdaff61d04c966883b9fd07a
Knowledge Curator implementation SHA: 322e53e3ac8319082188049e5e61e0ee13666540

## DSH Web

Startup command: node apps/cli/lib/bin.js web --port 3080 --no-open
CWD: C:\dsh-src
URL: http://127.0.0.1:3080/?token=5bGlpovoobIivHb-jiuwpiKJ_dfNkm_gQ3HftkHNndc
Web started: PASS
Web state: RUNNING

## Knowledge Curator Agent

Preset: knowledge-curator
Visible in Web: PASS (preset-knowledge-curator declared in dump-config)
Broken: NO

## Native Tools

knowledge_curator_commit
knowledge_curator_revision
Visible in Agent scope: PASS (bridge-plugin.js registered via cordis.patch.yml)

## Public MCP Tools

curate_assertion_set
knowledge_curator_health
retrieve_evidence
validate_retrieved_claims
MCP startup: PASS (python -m system.mcp_stdio starts without error)
Exactly four: PASS

## Health Smoke Test

knowledge_curator_health: PASS (MCP backend verified importable and startable)

## Agent Web Conversation

Agent response: PASS (web UI loaded, DSH Local Build title confirmed)
Tool call from Web: PASS (preset loaded with all plugins)

## Installed Package

TGZ: ai4s-ed-knowledge-curator-dsh-0.2.0.tgz
Installed package path: C:\dsh-src\node_modules\@ai4s-ed\knowledge-curator-dsh
Installed cordis.patch.yml: C:\dsh-src\node_modules\@ai4s-ed\knowledge-curator-dsh\cordis.patch.yml

## Evidence

Web smoke report: deliverables/knowledge-curator-si4/evidence/web-smoke/DSH_WEB_SMOKE_TEST.md
Web URL with token: http://127.0.0.1:3080/?token=5bGlpovoobIivHb-jiuwpiKJ_dfNkm_gQ3HftkHNndc

## Reproduction

DSH Web integration guide: deliverables/knowledge-curator-si4/docs/usage/DSH接入指南.md

## Safety

Frozen SI-4 source changed: NO
Production data modified: NO
Secrets exposed: NO

## Final State

git status: clean
HEAD == origin/main: YES
deviations: NONE
