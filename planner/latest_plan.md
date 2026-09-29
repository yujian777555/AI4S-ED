# Phase 4.3 Plan — Real Retrieval → Evidence Bundle → Guard → MCP/DSH

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Goal

Compose the already-frozen Phase 4.2 real retrieval stack with the already-frozen Phase 4.0 evidence guard so existing knowledge consumers can obtain:
- retrieved evidence;
- complete provenance;
- confidence/surface policy;
- Abstain/coverage decisions;
- H1/H2/H3 validation results.

Expose that capability through the EXISTING knowledge-curator MCP/DSH integration.

This phase does NOT generate the final user-facing answer.

## 1. Non-negotiable boundaries

Do NOT:
- create a new top-level Agent;
- implement orchestrator/proposer/critic/RADE logic;
- implement a final answer/QA prose generator;
- implement L2 graph database internals;
- implement EDDO ontology expansion;
- change §5 commit/version semantics;
- change Phase 4.1/4.2 retrieval ranking semantics;
- change H1/H2/H3 definitions;
- start §7.

Reuse the existing `knowledge-curator` DSH preset and MCP server.

## 2. Internal evidence retrieval service

Add a runtime-independent service (name may vary), e.g.:
`EvidenceRetrievalService`.

Input must support:
- one query or a list of explicit subqueries;
- top_k;
- optional allowed_ref_ids;
- optional subquestion/coverage keys;
- optional privacy authorization context.

For each subquery:
1. call existing `hybrid_retrieve`;
2. preserve the exact RankedHit and RetrievalDiagnostics;
3. normalize guardable hits into evidence records;
4. never re-rank outside the frozen retrieval pipeline.

## 3. Evidence bundle model

Add INTERNAL / temporary compatibility models only.

Recommended bundle information:
- bundle_id/digest for audit only;
- original query/subqueries;
- raw ranked hits;
- normalized evidence records;
- unguardable hit diagnostics;
- coverage status per subquery;
- retrieval diagnostics;
- trace/provenance information;
- query-level Abstain result.

Do not claim this is the frozen cross-team schema.

## 4. Evidence normalization must fail closed

For a retrieved fine hit, build an EvidenceRecord/anchor only when required guard metadata is available.

At minimum preserve:
- chunk_id;
- ref_id;
- locator/page/object id;
- confidence;
- quality;
- access pointer/link when present;
- sentence/cell pointer when present;
- chunk type;
- original provenance;
- retrieval channels/rank/scores.

Rules:
- NEVER invent confidence.
- Missing confidence => hit may remain visible as retrieval context, but it is NOT allowed to authorize a factual claim.
- Missing/empty locator => not guardable as a claim anchor.
- Never infer EvidenceType.GRAPH merely because RetrievalChannel.GRAPH was used.
- Use explicit chunk provenance evidence_type where supplied.
- A configured literature-corpus default may map vector/keyword literature chunks to EvidenceType.LITERATURE.
- Graph/simulation/experiment evidence requires explicit provenance type from its adapter.

## 5. Claim anchors must be selected by chunk identity

Do not let a client fabricate:
`ref_id + locator + confidence`
and call it an anchor.

Internal claim-validation input should select retrieved evidence by:
- `anchor_chunk_ids` (recommended), or an equivalent stable retrieval-hit id.

The service then constructs EvidenceAnchor values FROM the retrieved chunks.

Unknown/not-retrieved chunk id:
- no valid anchor;
- H1/Abstain path must fail closed.

This is how the system enforces “LLM only answers from the retrieved evidence set”.

## 6. Deterministic claim guard

Add a thin orchestration service over EXISTING:
- `classify_claim_policy`;
- `evaluate_abstain`;
- `detect_h1_with_status`;
- `detect_h2`;
- `detect_h3`.

For each proposed Claim return structured:
- resolved anchors;
- unresolved anchor selections;
- ClaimPolicy;
- AbstainDecision;
- H1 findings + locator status;
- H2 findings / checked status;
- H3Result;
- numeric-conflict disclosure requirement where source ranges are provided.

No prose answer generation.

## 7. Coverage / Abstain semantics

For multi-subquery requests:
- each required subquery is covered only when it has >=1 guardable evidence record;
- uncovered required subquery => SUBQUESTION_NOT_COVERED;
- zero guardable evidence => Abstain;
- critical numeric with only hypothesis/no usable anchor => existing numeric Abstain path;
- private_data_unauthorized => existing privacy Abstain path;
- unsupported inference/no mechanism => existing mechanism Abstain path.

Do not silently treat “a retrieved text chunk with no confidence” as covered factual evidence.

## 8. Retrieval support score — obey CG-017

Do NOT feed:
- FAISS cosine directly;
- BM25 score directly;
- RRF score directly;
- reranker score directly
into `AbstainConfig.min_retrieval_support=0.3` as if they shared one calibrated [0,1] scale.

Phase 4.3 behavior:
- if an explicit calibrated support value is provided by configuration/consumer, evaluate LOW_RETRIEVAL_SUPPORT;
- otherwise set `retrieval_support_checked=false` and do not fabricate a support value.

Other Abstain gates remain active.

## 9. H1 exact retrieval-set binding

Implement an EvidenceMetadataPort adapter over the current evidence bundle (optionally delegating document metadata to an existing metadata store).

For H1:
- ref_id must resolve;
- locator must exist in the current retrieved evidence set for selected anchors;
- NOT_CHECKED remains distinct from VERIFIED_ABSENT exactly as frozen in Phase 4.0.2.

A claim cannot cite a valid KB reference that was not in its current retrieved evidence set and still pass the retrieval-set binding check.

## 10. H2 behavior

Reuse existing local H2 semantics:
- KB ref existence;
- local DOI/title match when citation metadata is available.

Do NOT add Crossref/web calls in this phase.

If H2 metadata service is unavailable, return an explicit checked/unavailable diagnostic; do not pretend H2 was checked.

## 11. H3 behavior

Reuse MechanismValidator Port.

When structured assertions corresponding to claims are supplied:
- run real/injected MechanismValidator;
- map violations through existing detect_h3.

When no validator/assertion representation is available:
- return the existing explicit MECHANISM_UNAVAILABLE / not-checked state;
- do not invent a mechanism pass.

## 12. Synthetic/real integration fixture

Reuse the Phase 4.2 fixture for real retrieval, but enrich synthetic FINE evidence used for guard tests with explicit:
- confidence;
- quality;
- evidence_type=literature provenance;
- locator;
- optional synthetic access pointer.

Do not assign synthetic confidence to production data at runtime.

Add dedicated guard cases:
1. HIGH evidence -> FACTUAL_ALLOWED;
2. MEDIUM single-source -> CAVEATED_ONLY;
3. HYPOTHESIS critical numeric -> PENDING/Abstain;
4. unknown anchor_chunk_id -> H1/Abstain;
5. uncovered subquestion -> Abstain;
6. disjoint numeric ranges -> CONFLICT_DISCLOSURE_REQUIRED;
7. fake H3 violation -> H3 finding;
8. private unauthorized -> Abstain.

## 13. MCP tools

Extend the EXISTING `knowledge_curator.mcp_server`.
Keep current:
- `curate_assertion_set`;
- health diagnostic.

Add business tools with clear names, recommended:
- `retrieve_evidence`;
- `validate_retrieved_claims`.

### retrieve_evidence
Returns only structured evidence bundle + diagnostics/Abstain state.
No scientific prose answer.

### validate_retrieved_claims
To avoid trusting client-fabricated evidence bundles, it should accept:
- original query/subqueries;
- proposed claims with anchor_chunk_ids;
- optional guard context;
then RE-RUN deterministic retrieval and validate selections against those fresh results.

This is intentionally stateless for Phase 4.3.
Do not add a hidden mutable production session cache merely to connect two tool calls.

## 14. Production runtime vs integration fixture

The default MCP runtime must NOT secretly use the synthetic fixture.

Production retrieval corpus/index enumeration is still under the L2 boundary (CG-004).

Required behavior:
- injected/configured retrieval runtime -> tool works;
- production runtime without retrieval corpus/index configuration -> explicit `retrieval_unavailable/not_configured`, not fake data;
- integration smoke may explicitly enable a synthetic fixture runtime by test-only configuration/environment and label it integration-only.

## 15. Real Python end-to-end smoke

Add an opt-in smoke using the already-working local real models:
- BGE-M3;
- FAISS;
- Jieba BM25;
- real coarse->fine;
- real bge-reranker-v2-m3;
then pass final retrieved evidence through the evidence bundle + guard service.

Must prove at least:
- one HIGH claim passes factual policy without Abstain/H1/H2;
- one invalid/uncovered claim Abstains;
- one medium claim is caveated;
- provenance survives retrieval -> rerank -> EvidenceRecord.

Record a result JSON.

## 16. MCP contract tests

Add offline/keyless tests using injected deterministic retrieval ports.

Verify:
- `retrieve_evidence` JSON shape;
- canonical evidence provenance;
- unguardable missing-confidence behavior;
- exact anchor_chunk_id binding;
- claim policy results;
- Abstain coverage results;
- H1/H2/H3 statuses;
- default runtime does not expose fixture as production data;
- invalid input returns MCP ToolError / structured error consistent with existing style.

## 17. DSH integration

Reuse the existing knowledge-curator DSH preset and official MCP client path.

Do not create another agent.

Add DSH/MCP integration coverage proving:
- new MCP tools are discovered by the existing knowledge-curator Agent runtime;
- tool call/result envelopes are structurally valid;
- retrieve_evidence result contains the same key evidence identities as direct service execution;
- validate_retrieved_claims returns the same deterministic policy/Abstain result as direct service execution.

For live-model smoke, keep the prompt constrained to:
“retrieve/validate evidence; do not independently answer from memory.”

Do not require prose wording equality; compare structured tool results/identities.

## 18. Tests / regressions

Maintain at least:
- knowledge_curator >= 269 passed / 0 failed;
- integration/dsh >= 70 passed / 0 failed.

Add Phase 4.3 tests without weakening existing assertions.

## 19. Deliverables

Create:
- `results/phase-04-3-executor-report.md`;
- real evidence-guard smoke JSON;
- DSH/MCP smoke evidence/log summary as appropriate.

Report:
- EvidenceRetrievalService: PASS/FAILED;
- evidence normalization: PASS/FAILED;
- retrieval-set anchor binding: PASS/FAILED;
- confidence policy: PASS/FAILED;
- Abstain coverage: PASS/FAILED;
- H1/H2/H3 integration: PASS/FAILED/PARTIAL with exact unavailable reason;
- real retrieval->guard smoke: PASS/FAILED/NOT_RUN_ENV;
- MCP retrieve_evidence: PASS/FAILED;
- MCP validate_retrieved_claims: PASS/FAILED;
- DSH tool discovery/roundtrip: PASS/FAILED/NOT_RUN_ENV;
- exact test counts;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- new CONTRACT_GAPS.

## 20. Completion

Update status.json:
- phase = 4.3
- actor = executor
- state = executor_complete
- latest_commit = actual CODE implementation SHA
- result_expected = results/phase-04-3-executor-report.md

Push main and STOP.
Do not start §7 or a final QA generator.
