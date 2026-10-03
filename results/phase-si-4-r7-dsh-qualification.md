# Phase SI-4-R7 DSH Qualification Artifact

Pinned DSH version: 0.2.0-rc.1
Pinned source SHA: 4878cdabd87d4041bdaff61d04c966883b9fd07a
Node: v24.9.0
pnpm: 11.7.0

## Command
node integration/dsh/qualification/knowledge-curator-r7.mjs

## Exit code: 0

## Results
- Shipped plugin SHA256: 1c03dac1e43803440ec569212a116df020caa9b3de8d8c2843203d23f1fb7cb3
- Static defineTool import: PASS
- Revision output schema oneOf: PASS
- Spawn/stdin transport: PASS
- Package subpath in cordis.patch.yml: PASS
- No fixture imports in shipped runtime: PASS
- Strict hydration markers: PASS
- No identity fallback: PASS

## Native tools
- knowledge_curator_commit (preset-scoped)
- knowledge_curator_revision (preset-scoped)

## Native §5 result
{"status": "published", "commit_attempted": true}

## Native §7 result
{"status": "approval_required"}

## Public MCP
curate_assertion_set, knowledge_curator_health, retrieve_evidence, validate_retrieved_claims

## Native replay
NOT_APPLICABLE_PROVIDER_PROCESS_ISOLATION
SI-2A direct workflow replay cited for IDEMPOTENT_HIT semantics.
