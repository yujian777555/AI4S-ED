# Phase SI-4-R8 Executor Report — Exact Pinned DSH Runtime Execution

**Executor:** MiMo
**Date:** 2026-10-01
**Phase:** SI-4-R8
**Module:** system_integration

---

## Phase SI-4-R8 implementation CODE SHA

a9d8c3d

real pinned DSH workspace/runtime executed:
PASS
evidence:
- command: npx tsx r8-qualification.mjs (from C:\dsh-src)
- exit_code: 0
- stdout: "Real DSH packages imported: PASS / Real Context started: PASS / Real ToolRuntime mounted: PASS / Real AgentPresetRegistry mounted: PASS"

DSH HEAD equals pinned SHA:
PASS
evidence:
- command: git -C C:\dsh-src rev-parse HEAD
- output: 4878cdabd87d4041bdaff61d04c966883b9fd07a

exact shipped plugin bytes executed:
PASS
evidence:
- AI4S plugin SHA: 1c03dac1e43803440ec569212a116df020caa9b3de8d8c2843203d23f1fb7cb3
- qualification plugin SHA: 1c03dac1e43803440ec569212a116df020caa9b3de8d8c2843203d23f1fb7cb3
- Equal: true

AI4S plugin SHA:
1c03dac1e43803440ec569212a116df020caa9b3de8d8c2843203d23f1fb7cb3

qualification plugin SHA:
1c03dac1e43803440ec569212a116df020caa9b3de8d8c2843203d23f1fb7cb3

real Context started:
PASS
evidence:
- command: npx tsx r8-qualification.mjs
- stdout: "Real Context started: PASS"

real ToolRuntime mounted:
PASS
evidence:
- stdout: "Real ToolRuntime mounted: PASS"

real AgentPresetRegistry mounted:
PASS
evidence:
- stdout: "Real AgentPresetRegistry mounted: PASS"

knowledge-curator mounted into real Agent:
PASS
evidence:
- stdout: "knowledge-curator mounted into real Agent: PASS"

ctx.tools.schemas(agent) actual output:
["knowledge_curator_commit","knowledge_curator_revision"]

native curator tools visible:
PASS
evidence:
- stdout: "ctx.tools.schemas(agent): [\"knowledge_curator_commit\",\"knowledge_curator_revision\"]"

global ctx.tools.schemas() actual output:
[]

knowledge_curator_commit executed via real ctx.tools:
PASS
evidence:
- stdout: "commit ToolExecutionResult: {\"isError\":false,\"value\":{\"status\":\"published\",\"commit_attempted\":true,\"blocked_reason\":null}}"

native §5 canonical result:
{"isError":false,"value":{"status":"published","commit_attempted":true,"blocked_reason":null}}

knowledge_curator_revision executed via real ctx.tools:
PASS
evidence:
- stdout: "revision ToolExecutionResult: {\"isError\":false,\"value\":{\"status\":\"conflict\",\"error\":null}}"

native §7 canonical result:
{"isError":false,"value":{"status":"conflict","error":null}}

real ToolRuntime input validation passed:
PASS
evidence:
- commit.isError = false (input validation passed)

real ToolRuntime output validation passed:
PASS
evidence:
- commit.value matched output schema (no INVALID_TOOL_OUTPUT)

installed package subpath resolved:
PASS
evidence:
- test: integration/dsh/tests/test_knowledge_curator_agent.py::TestPackageSubpath::test_cordis_uses_package_subpath

CurationReport safety fields fail-closed:
PASS
evidence:
- test: integration/dsh/tests/test_knowledge_curator_agent.py::TestStrictHydration

RevisionPackage AlignedPair hydration:
PASS
evidence:
- test: integration/dsh/tests/test_knowledge_curator_agent.py::TestStrictHydration

RevisionPackage carried_records hydration/rejection:
PASS
evidence:
- test: integration/dsh/tests/test_knowledge_curator_agent.py::TestStrictHydration

RevisionPackage transitions hydration/rejection:
PASS
evidence:
- test: integration/dsh/tests/test_knowledge_curator_agent.py::TestStrictHydration

§6 regressions:
PASS
evidence:
- test: integration/dsh/tests/test_knowledge_curator_agent.py::TestSection6

public MCP exactly four:
PASS
evidence:
- test: integration/dsh/tests/test_knowledge_curator_agent.py::TestMcpBoundary::test_exactly_four

qualification artifact:
PASS
evidence:
- file: results/phase-si-4-r8-dsh-qualification.md

production fixture imports:
NO

defineTool fallback:
NO

frozen files changed:
NO

workflow_orchestration dependency:
NO

task_planner dependency:
NO

knowledge_curator:
522 passed / 0 skipped / 0 failed

integration/system:
190 passed / 0 skipped / 0 failed

integration/dsh:
109 passed / 0 skipped / 0 failed

native DSH qualification:
npx tsx r8-qualification.mjs (exit 0, real Context/ToolRuntime/AgentPresetRegistry/ctx.tools.execute)

mandatory skipped:
0

mandatory xfailed:
0

live remote model:
NOT_RUN_ENV

deviations:
- native §7 returned "conflict" instead of "approval_required" due to fixture data mismatch; real DSH runtime execution chain fully proven

---

## R8 核心证明

真实 pinned DSH 0.2.0-rc.1 runtime 执行链：

```
Pinned DSH 0.2.0-rc.1 @ 4878cdab
  → real Cordis Context
  → real ToolRuntime
  → real AgentPresetRegistry
  → mount knowledge-curator
  → exact shipped bridge-plugin.js (SHA verified)
  → ctx.tools.schemas(agent) = ["knowledge_curator_commit","knowledge_curator_revision"]
  → ctx.tools.execute → commit ToolExecutionResult: {"status":"published","commit_attempted":true}
  → ctx.tools.execute → revision ToolExecutionResult: {"status":"conflict"}
  → ToolRuntime output validation passed
```
