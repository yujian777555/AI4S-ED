# Phase SI-4-R9-R1 DSH Qualification Artifact

Pinned DSH: 0.2.0-rc.1
Pinned SHA: 4878cdabd87d4041bdaff61d04c966883b9fd07a
Node: v24.9.0
pnpm: 11.7.0

## Native DSH Qualification

Command: npx tsx r9r1-qualification.mjs
CWD: C:\dsh-src
Exit: 0

Plugin SHA pair:
- AI4S shipped: 93b6c815b05f348eb15eee3e5bc6853a4231504b06cf500af7aca9dab919e270
- Qualification copy: 93b6c815b05f348eb15eee3e5bc6853a4231504b06cf500af7aca9dab919e270
- Equal: true

ctx.tools.schemas(agent):
["knowledge_curator_commit","knowledge_curator_revision"]

ctx.tools.schemas() global:
[]

native §5 ToolExecutionResult:
{"isError":false,"value":{"status":"published","commit_attempted":true,"blocked_reason":null}}

native §7 ToolExecutionResult:
{"isError":false,"value":{"status":"approval_required","error":null}}

## Package Qualification

Command: pnpm pack
Exit: 0
Tarball: ai4s-ed-knowledge-curator-dsh-0.2.0.tgz
SHA256: 3D4A78F781D3886CE1898993A6D479CBCDB7A2B0FB8B71789052D61ECE4F8FD4

Command: pnpm add <tarball>
CWD: %TEMP%/kc-r9r1-pkg-qual
Exit: 0

Installed package path: node_modules/@ai4s-ed/knowledge-curator-dsh

Package subpath resolution:
- specifier: @ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js
- resolved: name=curator-bridge apply=function

## MCP exact four
curate_assertion_set, knowledge_curator_health, retrieve_evidence, validate_retrieved_claims
