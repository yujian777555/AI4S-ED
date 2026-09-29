# Phase 4.0 Plan — §6 Evidence Guard Foundation

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Scope
Begin docs/03 §6, but only the deterministic evidence/anchor/Abstain/guard foundation.

This phase DOES implement:
- §6 evidence/claim-anchor compatibility models;
- confidence-driven factual-assertion gate;
- Abstain decision logic and structured missing-evidence output;
- H1/H2/H3 detector result models and local deterministic checks;
- Ports for retrieval metadata lookup and L3 validation;
- regression hardening of the already accepted DSH live round-trip.

This phase does NOT implement:
- full FAISS/BGE-M3 vector retrieval;
- BM25 index;
- EDDO query expansion;
- RRF/reranker;
- final user-facing answer generation;
- lit_researcher;
- L3 validator internals;
- Crossref/network lookup;
- §7 lifecycle.

## 1. Read first
- docs/01-总体架构与数据流设计.md
- docs/03-文献自动调研与知识入库流水线.md §6
- planner/KNOWLEDGE_CURATOR_BOUNDARY.md
- planner/phase-03-2-4-review.md
- planner/CONTRACT_GAPS.md
- status.json
- current schemas/ports/core.

Authoritative §6 rules to preserve exactly:
- evidence types = 文献 / 图谱 / 仿真 / 实验;
- anchor tuple semantics = evidence type + ref_id + locator + confidence;
- confidence enum remains verified/high/medium/hypothesis;
- verified/high may support factual assertion;
- medium must be explicitly caveated as single-source/unverified;
- hypothesis may only appear as pending hypothesis, not factual statement;
- unresolved numeric conflict must expose ranges/sources rather than silently select one;
- insufficient evidence triggers Abstain;
- H1 = unsupported/misaligned claim anchor;
- H2 = fabricated/nonexistent literature citation;
- H3 = mechanism violation;
- M1 metrics belong to 07; this module emits per-sample findings/metrics, it does not own watchdog thresholds.

## 2. First harden Phase 3.2.4 live regression
Update integration/dsh/lane324_kc_roundtrip.e2e.ts.

Required hardening:
- require tool_call_count == 1 for the deterministic fixture;
- require tool_result_count == 1 and linked to that call;
- require abc_match === true;
- structured tool-result parse failure must FAIL the live acceptance;
- delete acceptance fallbacks that infer B by copying A after keyword presence;
- optional diagnostics may keep bounded raw snippets, but they must never turn an unparsable B into PASS.

Add keyless tests protecting these rules.

Do not otherwise change DSH/MCP architecture.

## 3. New package area
Create narrowly scoped modules, recommended:

knowledge_curator/
  retrieval/
    __init__.py
    evidence_guard.py
    abstain.py
    hallucination.py
  schemas/
    evidence.py
  ports/
    evidence_store.py

Names may vary, but do not bury §6 logic inside DSH/MCP wrappers.

Core must remain runtime-independent.

## 4. Temporary compatibility evidence schemas
Create internal/temporary compatibility models. Do NOT claim public Schema Registry ownership.

Required concepts:

EvidenceType enum:
- literature
- graph
- simulation
- experiment

Choose English wire values only if docs/01 existing A.6 vocabulary already maps that way; document the mapping to 文献/图谱/仿真/实验.

EvidenceAnchor:
- evidence_type
- ref_id
- locator
- confidence
- optional quality
- optional access/reference pointer

EvidenceRecord / EvidenceHit:
- anchor
- claim/assertion id when available
- bounded evidence text/summary
- optional score
- provenance fields needed by §6.2:
  ref_id, page/object id, sentence/cell pointer, confidence, quality, access link.

Do not invent a final cross-team retrieval result schema.

## 5. Claim compatibility model
Introduce an internal Claim model for guard evaluation, not final answer generation.

Recommended fields:
- claim_id
- text
- numeric flag/value/unit where available
- anchors: list[EvidenceAnchor]
- requested subquestion id / coverage key optional.

Do not create an LLM answer generator.

## 6. Confidence gate
Implement a deterministic function/service that classifies how a claim may be surfaced.

Expected policy:
- verified/high => FACTUAL_ALLOWED
- medium => CAVEATED_ONLY
- hypothesis => PENDING_HYPOTHESIS_ONLY

If anchors disagree:
- do not elevate confidence;
- unresolved numeric conflict => CONFLICT_DISCLOSURE_REQUIRED.

The service should return policy metadata; it should not generate prose.

Do not modify the frozen Confidence enum.

## 7. Abstain decision
Implement docs/03 §6.3 conditions as deterministic inputs/decisions.

Required reasons:
- LOW_RETRIEVAL_SUPPORT
- SUBQUESTION_NOT_COVERED
- CRITICAL_NUMERIC_ONLY_HYPOTHESIS_OR_PENDING
- UNSUPPORTED_INFERENCE_NO_MECHANISM
- PRIVATE_DATA_UNAUTHORIZED

Return a structured AbstainDecision:
- abstain: bool
- reasons
- missing_evidence items
- optional recommended gap kinds.

Do not hard-code external database subscriptions or take over exp_designer routing.
The model may carry a recommendation category, but orchestration belongs elsewhere.

Retrieval similarity threshold must be configuration-driven and marked temporary unless 07/05 freezes it.

## 8. H1 detector
Implement the local part of H1 deterministically.

For each factual/numeric claim:
- require at least one valid anchor;
- anchor ref_id must resolve through an EvidenceMetadataPort/KB metadata lookup;
- locator must be non-empty;
- confidence policy must permit the intended claim mode;
- if an expected assertion/evidence id is supplied, check anchor alignment where current temporary data allows.

Return HallucinationFinding(type=H1, claim_id, reason, anchor ids).

Do not attempt semantic sentence entailment with an LLM in this phase.

## 9. H2 detector
Implement only the KB-existence portion in Phase 4.0.

Required:
- cited ref_id must exist in KB metadata port;
- if DOI/title metadata is locally available, compare against stored metadata;
- nonexistent ref_id => H2.

Do NOT call Crossref/web in core.
External DOI existence verification belongs to a future adapter/phase.

## 10. H3 detector
Reuse the existing MechanismValidator Port.

Do not implement electrochemical rules.

Map mechanism violations to H3 findings.
If validator unavailable, return a structured NOT_CHECKED / mechanism_unavailable state; do not claim H3 pass.

## 11. Evidence Ports
Add the minimum runtime-independent Ports required by §6 foundation.

Recommended EvidenceMetadataPort methods:
- ref_exists(ref_id) -> bool
- get_ref_metadata(ref_id) -> optional metadata
- anchor_exists(ref_id, locator) -> bool where supported

Optional retrieval contract for future phases may be a separate protocol, but do not implement full retrieval engine yet.

Do not hard-code SQLite/FAISS/HTTP.

Provide simple InMemory adapters for tests only.

## 12. Cross-source numeric conflict input
For a numeric claim, provide an internal structure that can receive the same subject+property source ranges from L2/graph later.

Phase 4.0 may implement the deterministic decision:
- intervals consistent/overlap => no forced conflict disclosure;
- disjoint unresolved intervals => conflict disclosure required;

Do not duplicate or mutate frozen §5 conflict truth adjudication.
This is answer-consumption guard behavior only.

## 13. Coverage model
Represent multi-subquestion coverage explicitly.

Given requested coverage keys and supported coverage keys:
- any uncovered required subquestion => Abstain or partial-answer-with-abstain flag for that subquestion;
- never silently omit uncovered subquestions.

Do not own orchestrator decomposition; accept subquestion/coverage ids as input.

## 14. Tests
Keep all existing tests green:
- integration/dsh current baseline: 70 tests;
- knowledge_curator current baseline: 127 tests.

Add deterministic Phase 4.0 tests for at least:
- verified anchor allows factual;
- high anchor allows factual;
- medium => caveated only;
- hypothesis => pending only;
- no anchor => H1;
- nonexistent ref_id => H2;
- empty locator => H1;
- H3 from fake MechanismValidator violation;
- validator unavailable => NOT_CHECKED, not pass;
- low support => Abstain;
- uncovered subquestion => Abstain/partial coverage;
- critical numeric hypothesis-only => Abstain;
- unsupported inference without mechanism => Abstain;
- unauthorized private data => Abstain;
- disjoint numeric source ranges => conflict disclosure required;
- overlapping ranges => no forced conflict disclosure;
- existing DSH strict live-test parser cannot infer B from A;
- live regression requires exactly one linked result and abc_match.

No real API key is needed for ordinary pytest.

## 15. No final answer generator
Important boundary:
knowledge_curator may return EvidenceGuardResult / ClaimPolicy / AbstainDecision / hallucination findings.
It must not become the final user-facing QA/orchestrator Agent.

Do not add qa_agent, trusted_rag_agent or another top-level Agent.

## 16. MCP exposure
Do NOT expose new §6 MCP tools in Phase 4.0 yet.
First stabilize deterministic core/contracts.
DSH/MCP exposure begins only after Planner review.

## 17. Deliverables
Create:
- results/phase-04-0-executor-report.md

Report:
- new schemas
- new Ports
- confidence-policy behavior
- Abstain reasons
- H1/H2/H3 behavior
- test counts
- DSH live-regression hardening
- public contracts changed? NO
- CONTRACT_GAPS changes
- implementation SHA.

## 18. status.json
On completion:
- phase = 4.0
- actor = executor
- state = executor_complete
- latest_commit = actual implementation SHA
- result_expected = results/phase-04-0-executor-report.md

Stop after Phase 4.0.
Do not implement full retrieval/chunking/reranking or §7.