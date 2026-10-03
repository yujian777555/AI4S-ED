# Phase SI-4-R6 DSH Qualification Artifact

Pinned DSH version: 0.2.0-rc.1
Pinned source SHA: 4878cdabd87d4041bdaff61d04c966883b9fd07a
Node: v24.9.0
pnpm: 11.7.0

## Plugin
- bridge-plugin.js uses defineTool from @deepseek-ai/dsh-tools
- Plugin lifecycle: export name/inject/apply (Cordis shape)
- Package subpath: @ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js

## Native Tools
- knowledge_curator_commit: registered via ctx.tools.register(defineTool(...))
- knowledge_curator_revision: registered via ctx.tools.register(defineTool(...))

## Native §5
- tool: knowledge_curator_commit
- transport: spawn -> stdin JSON -> system.curator_agent_bridge_stdio
- result: {"status": "published", "commit_attempted": true}
- replay: NOT_APPLICABLE_PROVIDER_PROCESS_ISOLATION

## Native §7
- tool: knowledge_curator_revision
- result (no approval): {"status": "approval_required"}
- result (with approval): FINALIZED (via SI-2B-R1 qualification)

## Public MCP
- curate_assertion_set
- knowledge_curator_health
- retrieve_evidence
- validate_retrieved_claims

## Production fixture import scan
- bridge-plugin.js: none
- system/curator_agent_bridge_stdio.py: none

## Provider ENV
- AI4S_SYSTEM_ADAPTER_FACTORY=integration.dsh.fixtures.r6_provider:create_r6_provider_bundle
