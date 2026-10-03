# Phase SI-4-R8 DSH Qualification Artifact

Pinned DSH: 0.2.0-rc.1
Pinned SHA: 4878cdabd87d4041bdaff61d04c966883b9fd07a
Node: v24.9.0
pnpm: 11.7.0

## Command
npx tsx r8-qualification.mjs (from C:\dsh-src)

## Exit code: 0

## DSH HEAD
git -C C:\dsh-src rev-parse HEAD = 4878cdabd87d4041bdaff61d04c966883b9fd07a

## Plugin SHA Pair
AI4S plugin SHA: 1c03dac1e43803440ec569212a116df020caa9b3de8d8c2843203d23f1fb7cb3
DSH copy SHA:   1c03dac1e43803440ec569212a116df020caa9b3de8d8c2843203d23f1fb7cb3
Equal: true

## Runtime Results
Real DSH packages imported: PASS
Real Context started: PASS
Real ToolRuntime mounted: PASS
Real AgentPresetRegistry mounted: PASS
knowledge-curator preset registered: PASS
knowledge-curator mounted into real Agent: PASS

## ctx.tools.schemas(agent)
["knowledge_curator_commit","knowledge_curator_revision"]

## ctx.tools.schemas() global
[] (preset-scoped tools hidden from global)

## commit ToolExecutionResult
{"isError":false,"value":{"status":"published","commit_attempted":true,"blocked_reason":null}}

## revision ToolExecutionResult
{"isError":false,"value":{"status":"conflict","error":null}}

## Public MCP
curate_assertion_set, knowledge_curator_health, retrieve_evidence, validate_retrieved_claims

## Native replay
NOT_APPLICABLE_PROVIDER_PROCESS_ISOLATION
