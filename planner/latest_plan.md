# Phase 4.3.1 Plan — Guardable/H2 Semantics + True Mounted-DSH Evidence Roundtrip

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Scope

Close only the remaining Phase 4.3 semantic/integration gaps:
1. guardable_as_anchor / evidence_type consistency;
2. H2 checked/unavailable correctness;
3. real existing DSH Agent preset discovery + roundtrip for the new evidence tools;
4. MCP UTF-8 description cleanup.

Do NOT:
- change Phase 4.0 guard definitions;
- change Phase 4.1/4.2 retrieval ranking;
- add a final QA generator;
- add a new top-level Agent;
- implement L2 graph DB / EDDO;
- start §7.

## 1. Make guardability a single invariant

A RetrievalEvidenceRecord is guardable_as_anchor only if build_evidence_anchor(record) can succeed.

Required components:
- non-empty ref_id;
- non-empty locator;
- confidence present;
- valid evidence_type present.

If evidence_type is absent/invalid and no valid configured default applies:
- add unguardable reason such as missing_evidence_type / invalid_evidence_type;
- guardable_as_anchor=false;
- do not count it toward coverage.

Do not silently turn an explicitly invalid evidence_type into GRAPH or another type.

A configured literature default may still be used for the literature corpus exactly as Phase 4.3 intended.

## 2. Coverage must use actual anchorability

EvidenceRetrievalService coverage guardable_count must count only records for which a valid EvidenceAnchor can be built.

Recommended implementation:
- centralize an is_guardable/build helper;
- avoid duplicating subtly different conditions.

Add tests:
- confidence+locator but evidence_type=None/default=None => NOT_COVERED;
- invalid explicit evidence_type => unguardable;
- valid configured literature default => covered;
- build_evidence_anchor success iff guardable_as_anchor=true.

## 3. Correct H2 checked semantics

Keep detect_h2 frozen.
Fix only orchestration/status reporting.

Define an INTERNAL H2 status if helpful, e.g.:
- CHECKED;
- PARTIAL;
- METADATA_UNAVAILABLE.

At minimum keep h2_checked + h2_unavailable_reason truthful.

Rules:

### 3a. No citation DOI/title supplied
- retrieval-set ref existence can be checked through RetrievalSetMetadata;
- h2_checked may be true for the scope that was actually requested.

### 3b. cited DOI supplied
h2_checked=true only when authoritative/local KB metadata for that ref contains DOI and comparison actually occurred.

If KB DOI unavailable:
- h2_checked=false or PARTIAL;
- reason states DOI metadata unavailable.

### 3c. cited title supplied
Same rule for title.

### 3d. DOI/title both supplied
Both required fields must be available for full checked=true.

Mismatch remains an H2 finding through existing detect_h2.
Unavailable metadata is NOT an H2 hallucination finding by itself; it is a not-checked/partial status.

## 4. Tests for H2 truthfulness

Add:
- retrieved ref + no citation metadata -> ref-existence H2 checked;
- cited DOI + KB DOI same -> checked, no finding;
- cited DOI + KB DOI mismatch -> checked, H2 finding;
- cited DOI + KB DOI unavailable -> not fully checked / unavailable reason;
- cited title + KB title unavailable -> not fully checked;
- DOI available but title unavailable when both cited -> partial/not fully checked;
- empty retrieval set remains unavailable.

Do not call Crossref/web.

## 5. Explicit integration fixture mode for mounted DSH Agent

The existing preset launches:
python -m knowledge_curator.mcp_server

Add an explicit TEST/INTEGRATION-ONLY environment switch, name may be:
KC_EVIDENCE_INTEGRATION_FIXTURE=1

When unset:
- production default remains retrieval_unavailable;
- fixture MUST NOT leak.

When explicitly set in integration environment:
- stdio MCP server may build the labelled synthetic evidence fixture and deterministic/in-memory evidence runtime needed for DSH tests;
- mark integration_fixture=true in returned bundles;
- never enable this implicitly.

Prefer a small runtime factory resolver rather than putting fixture-building business logic into app.py.

## 6. Update existing DSH preset persona, not Agent identity

Keep preset id:
knowledge-curator

Do not create a second preset/Agent.

The persona may be minimally expanded to say:
- use retrieve_evidence for structured retrieval;
- use validate_retrieved_claims to validate claim evidence;
- do not answer scientific questions from memory;
- do not generate final orchestrator-facing QA prose.

Preserve its §5 curation responsibilities.

## 7. Mounted DSH tool discovery test

Reuse the proven Phase 3.2.4 pattern:
- official pinned DSH runtime;
- launchWebScaffold;
- existing dsh/knowledge-curator package;
- ctx.agents.create(... agentPreset=knowledge-curator ...);
- ctx.agentPresets.mount(agentCtx, 'knowledge-curator');
- ctx.tools.schemas(handle.agent).

Prove mounted Agent schemas contain:
- mcp__knowledge_curator__curate_assertion_set;
- mcp__knowledge_curator__retrieve_evidence;
- mcp__knowledge_curator__validate_retrieved_claims.

This is different from raw MCP session.list_tools().

## 8. Mounted DSH live roundtrip

Add a live-model E2E lane analogous to lane324.

Use the already accepted DSH baseline/pinned runtime.
If valid DeepSeek credentials/model route are available, actually run it.

Set integration-only env:
KC_EVIDENCE_INTEGRATION_FIXTURE=1

Prompt the mounted Agent explicitly to call the exact evidence tool.
Do NOT ask it to independently answer from memory.

Recommended first live turn:
- call mcp__knowledge_curator__retrieve_evidence for a synthetic fixture query;
- final response may be a tiny structured summary only.

Required evidence:
- exact tool visible in mounted Agent schema;
- >=1 matching tool/call;
- linked tool/result;
- result parses structurally;
- evidence chunk identities equal direct EvidenceRetrievalService execution for the same fixture query.

Then validate claims either:
A. in a second live turn using mcp__knowledge_curator__validate_retrieved_claims, or
B. a second E2E test.

For validate:
- compare policy / Abstain / unresolved-anchor identities to direct service execution.
- Do not require prose text equality.

## 9. DSH status semantics

Report separately:
- raw MCP stdio discovery/roundtrip;
- mounted DSH Agent tool discovery;
- mounted DSH live model roundtrip.

Allowed live status:
- PASS;
- NOT_RUN_ENV only if credential/model/runtime prerequisite is absent before the run;
- FAILED for execution/semantic failure after prerequisites are available.

Do not label keyless raw MCP testing as "DSH live roundtrip PASS".

## 10. MCP UTF-8 cleanup

Repair mojibake in knowledge_curator/mcp_server/app.py descriptions/comments:
- §5.1–§5.3;
- em dash / punctuation;
- any other clearly corrupted source strings.

Keep file UTF-8, no BOM if repository convention is no BOM.

## 11. Regression

Maintain at least:
- knowledge_curator >= 290 passed / 0 failed;
- integration/dsh >= 78 passed / 0 failed.

Add tests rather than weakening existing ones.

## 12. Deliverables

Create:
- results/phase-04-3-1-executor-report.md
- results/phase-04-3-1-dsh-evidence-smoke.json (or equivalent)

Report:
- guardability/evidence_type invariant: PASS/FAILED;
- coverage-anchor consistency: PASS/FAILED;
- H2 checked semantics: PASS/FAILED;
- MCP UTF-8 cleanup: PASS/FAILED;
- raw MCP tools: PASS/FAILED;
- mounted DSH tool discovery: PASS/FAILED;
- mounted DSH retrieve_evidence live roundtrip: PASS/NOT_RUN_ENV/FAILED;
- mounted DSH validate_retrieved_claims live roundtrip: PASS/NOT_RUN_ENV/FAILED;
- direct-vs-DSH evidence identity match: PASS/NOT_RUN_ENV/FAILED;
- direct-vs-DSH policy match: PASS/NOT_RUN_ENV/FAILED;
- exact test counts;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- new CONTRACT_GAPS.

## 13. Completion

Update status.json:
- phase = 4.3.1
- actor = executor
- state = executor_complete
- latest_commit = actual CODE implementation SHA
- result_expected = results/phase-04-3-1-executor-report.md

Push main and STOP.
Do not start §7 until Planner review.
