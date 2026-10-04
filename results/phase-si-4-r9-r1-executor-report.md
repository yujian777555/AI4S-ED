# Phase SI-4-R9-R1 Executor Report — Final Evidence Closure

**Executor:** MiMo
**Date:** 2026-10-04
**Phase:** SI-4-R9-R1

---

## Phase SI-4-R9-R1 CODE SHA

9591cd3

real pinned native chain preserved:
PASS
evidence: npx tsx r9r1-qualification.mjs (exit 0)

DSH HEAD pinned:
PASS
evidence: 4878cdabd87d4041bdaff61d04c966883b9fd07a

exact shipped plugin SHA:
PASS
evidence: 93b6c815b05f348eb15eee3e5bc6853a4231504b06cf500af7aca9dab919e270 (shipped == copy)

ctx.tools.schemas(agent):
["knowledge_curator_commit","knowledge_curator_revision"]

global ctx.tools.schemas():
[]

native §5 exact PUBLISHED:
PASS
evidence: {"isError":false,"value":{"status":"published","commit_attempted":true,"blocked_reason":null}}

native §7 exact APPROVAL_REQUIRED:
PASS
evidence: {"isError":false,"value":{"status":"approval_required","error":null}}

native harness wrong §7 status exits nonzero:
PASS
evidence: assert() throws on status !== 'approval_required'

global scope isolation hard-asserted:
PASS
evidence: assert(!global.includes('knowledge_curator_commit'))

pnpm pack:
PASS
evidence: exit 0, tarball generated

tarball SHA256:
3D4A78F781D3886CE1898993A6D479CBCDB7A2B0FB8B71789052D61ECE4F8FD4

tarball actually installed:
PASS
evidence: pnpm add exit 0, node_modules/@ai4s-ed/knowledge-curator-dsh exists

package subpath actually resolved:
PASS
evidence: import('@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js') -> name=curator-bridge apply=function

installed bridge module imported:
PASS
evidence: mod.name === 'curator-bridge', typeof mod.apply === 'function'

qualification artifact committed:
PASS
evidence: results/phase-si-4-r9-r1-dsh-qualification.md

R9 typed/fail-closed hydration preserved:
PASS

§6 regressions:
PASS

public MCP exactly four:
PASS

frozen files changed:
NO

knowledge_curator: 522 passed / 0 skipped / 0 failed
integration/system: 190 passed / 0 skipped / 0 failed
integration/dsh: 109 passed / 0 skipped / 0 failed

native DSH qualification: PASS
installed package qualification: PASS

mandatory skipped: 0
mandatory xfailed: 0

live remote model: NOT_RUN_ENV

deviations: NONE
