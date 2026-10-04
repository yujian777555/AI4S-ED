# Phase SI-4-R9-R2 Executor Report — Installed Product Preset Activation Evidence

**Executor:** MiMo
**Date:** 2026-10-04
**Phase:** SI-4-R9-R2

---

## Phase SI-4-R9-R2 CODE SHA

（见 commit）

R9-R1 native baseline preserved:
PASS

DSH HEAD pinned:
PASS
evidence: 4878cdabd87d4041bdaff61d04c966883b9fd07a

global isolation hard-asserted:
PASS
evidence: assert(!global.includes('knowledge_curator_commit')) && assert(!global.includes('knowledge_curator_revision'))

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

clean tarball install preserved:
PASS

tarball SHA256:
3D4A78F781D3886CE1898993A6D479CBCDB7A2B0FB8B71789052D61ECE4F8FD4

installed package path:
D:\temp\kc-r9r2-installed-product\node_modules\@ai4s-ed\knowledge-curator-dsh

installed cordis.patch.yml resolved:
PASS

installed cordis.patch.yml path:
D:\temp\kc-r9r2-installed-product\node_modules\@ai4s-ed\knowledge-curator-dsh\cordis.patch.yml

pinned DSH consumed installed patch:
PASS
evidence: --dump-config output shows installed patch path in header

activation command:
node apps/cli/lib/bin.js --profile sdk-minimal --patch <installed-patch> --dump-config

activation exit: 0

knowledge-curator preset declared:
PASS

installed preset broken: NO

installed preset mount: NOT_RUN (dump-config activation sufficient per Planner minimum gate)

installed preset native tools: N/A (mount not run)

public MCP exactly four:
PASS

qualification artifact committed:
PASS
evidence: results/phase-si-4-r9-r2-dsh-qualification.md

frozen implementation changed: NO

workflow_orchestration dependency: NO

task_planner dependency: NO

integration/dsh: 109 passed / 0 skipped / 0 failed

knowledge_curator: NOT_RERUN_NO_IMPLEMENTATION_CHANGE
integration/system: NOT_RERUN_NO_IMPLEMENTATION_CHANGE

native qualification: PASS
installed product qualification: PASS

mandatory skipped: 0
mandatory xfailed: 0

deviations: NONE
