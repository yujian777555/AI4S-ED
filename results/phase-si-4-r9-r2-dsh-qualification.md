# Phase SI-4-R9-R2 DSH Qualification Artifact

Pinned DSH version: 0.2.0-rc.1
Pinned DSH SHA: 4878cdabd87d4041bdaff61d04c966883b9fd07a
Node: v24.9.0
pnpm: 11.7.0

## Native DSH Qualification

Command: npx tsx r9r2-qualification.mjs
CWD: C:\dsh-src
Exit: 0

ctx.tools.schemas(agent):
["knowledge_curator_commit","knowledge_curator_revision"]

ctx.tools.schemas():
[]

global isolation assertion: PASS
(hard assert: !global.includes('knowledge_curator_commit') && !global.includes('knowledge_curator_revision'))

native §5:
{"isError":false,"value":{"status":"published","commit_attempted":true,"blocked_reason":null}}

native §7:
{"isError":false,"value":{"status":"approval_required","error":null}}

## Package Qualification

pnpm pack command: pnpm pack
exit: 0
tarball: ai4s-ed-knowledge-curator-dsh-0.2.0.tgz
sha256: 3D4A78F781D3886CE1898993A6D479CBCDB7A2B0FB8B71789052D61ECE4F8FD4

install dir: D:\temp\kc-r9r2-installed-product
command: pnpm add <tarball>
exit: 0

installed package: D:\temp\kc-r9r2-installed-product\node_modules\@ai4s-ed\knowledge-curator-dsh

## Installed Patch Activation

AI4S source patch: C:\Users\于舰\XiaomiMiMoProjects\AI4S-ED\dsh\knowledge-curator\cordis.patch.yml
Installed patch: D:\temp\kc-r9r2-installed-product\node_modules\@ai4s-ed\knowledge-curator-dsh\cordis.patch.yml
Using installed patch: true

activation command: node apps/cli/lib/bin.js --profile sdk-minimal --patch <installed-patch> --dump-config
cwd: C:\dsh-src
exit: 0

knowledge-curator declared: true
installed preset broken: NO (no broken/error diagnostics)

Output confirms:
- preset-knowledge-curator from installed patch path
- id: knowledge-curator
- curator-bridge with package subpath @ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js
- mcp-knowledge-curator configured

## MCP exact four
curate_assertion_set, knowledge_curator_health, retrieve_evidence, validate_retrieved_claims
