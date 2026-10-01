# Knowledge Curator — Final Acceptance / Freeze

Date: 2026-10-01  
Planner: ChatGPT  
Module: knowledge_curator  
Repository: yujian777555/AI4S-ED

## Final status

ACCEPTED  
FROZEN  
DELIVERABLE

Final implementation CODE SHA:

`42e39121af5f6120174e088a521c9ad014abdcda`

Executor bookkeeping HEAD at final R3 handoff:

`c540497bbae059c45a50b7ad9771ceaddc010ff2`

Final executor-reported test evidence:

- knowledge_curator: **522 passed / 0 skipped / 0 failed**
- integration/dsh: **90 passed / 0 failed**

No public contracts changed in Phase 5.3-R3.  
`planner/CONTRACT_GAPS.md` was not modified.

## Phase 5.3-R3 final closure

Phase 5.3-R3 closes the authoritative commit-store / manifest-integrity boundary for revision publication.

The final implementation requires:

- a configured `DocumentCommitStore` before publication;
- fail-closed behavior for missing/unreadable authoritative store state;
- frozen Phase-2 assertion-hash agreement;
- frozen Phase-2 decision-hash agreement;
- exact request/admitted scientific-material agreement;
- metadata-hash agreement;
- mandatory manifest on PUBLISHED records;
- exact manifest assertion/decision hashes;
- exact commit-result version/snapshot agreement;
- resolved VersionStore snapshot presence;
- commit-store manifest content-hash and stable identity agreement with the resolved snapshot;
- successful shared validation before `TARGET_PUBLISHED`.

The final publication saga remains:

approval  
→ target `DocumentCommitCoordinator` commit  
→ authoritative store/material verification  
→ lifecycle revision  
→ final SourceVersion bind

## Final publication invariant

For a source-version upgrade:

prior source version  
→ historical prior KB version remains immutable

new source content  
→ V_target via real DocumentCommitCoordinator

authoritative commit-store record  
→ must agree with request + V_target snapshot before lifecycle

prior lifecycle transition  
→ V_final derived from V_target

new SourceVersion  
→ bound to V_final, never V_target

This preserves current visibility, historical rollback/auditability, and prevents a successful-looking commit result from bypassing authoritative persisted material.

## Frozen capability set

### §5 — curation and atomic knowledge commit

- completeness / conflict / quality evaluation;
- confidence policy;
- mechanism-validation boundary;
- deterministic curation decisions;
- document commit staging;
- structural / vector / USDO persistence coordination;
- pending-vector compensation and exact retry idempotency;
- immutable snapshots and version publication;
- version-scoped knowledge view and rollback-safe historical resolution;
- authoritative commit-store/manifest integrity enforcement.

### §6 — retrieval / evidence / hallucination control

- deterministic text/table/chart/evidence chunking;
- coarse-to-fine hybrid retrieval;
- BM25 + dense FAISS/BGE-M3 path;
- reranking;
- provenance-bearing evidence results;
- calibrated-support boundary rather than raw heterogeneous-score misuse;
- confidence/coverage/Abstain policy;
- H1/H2/H3 evidence hallucination guards;
- strict DSH/MCP evidence harness;
- pinned DSH 0.2.0-rc.1 integration baseline.

### §7 — lifecycle / source-version evolution

- append-only document/assertion lifecycle;
- retraction / corrigendum / supersede semantics;
- retrieval/training eligibility filtering;
- current/historical version-scoped visibility;
- deterministic Work / SourceVersion lineage;
- exact replay and same-work new-version classification;
- PREPRINT_TO_JOURNAL lineage;
- exact content-unit delta planning;
- DELTA_SAFE and FULL_REEXTRACT_REQUIRED fail-safe modes;
- deterministic assertion carry-forward / transition planning;
- material-sensitive RevisionPackage;
- prior-ref lifecycle direction;
- explicit auditable manual approval boundary;
- recoverable publication saga;
- crash/retry recovery;
- stale-base fail-closed;
- exact publication material lock for assertion / decision / metadata identity;
- post-target authoritative store verification before lifecycle progression.

## Frozen boundaries

knowledge_curator does NOT own:

- PDF/XML/OCR parsing;
- literature crawling;
- fuzzy/LLM paragraph alignment;
- global orchestration;
- proposer/critic/validator ownership;
- external event-bus technology;
- public cross-team approval schema;
- public WorkIdentity/content-unit schemas owned by upstream teams.

## Remaining CONTRACT_GAPS

The open CG items are integration/public-contract dependencies, not blockers for the delivered module:

- CG-016: real EDDO query-expansion adapter;
- CG-017: calibrated common retrieval-support score/threshold;
- CG-018: external lifecycle event-bus consumer contract;
- CG-019: public WorkIdentity/SourceVersion lineage contract;
- CG-020: public stable cross-version content-unit/alignment contract;
- CG-021: public manual revision approval/auditor contract.

The `CONTRACT_GAPS.md` blob remained unchanged across the R3 closure.

## Verification note

Planner reviewed the committed R3 implementation, regression sources, commit boundary, and executor report.

The final reported test counts above are executor-run evidence; a separate Planner-local test execution was not available in the current environment and is therefore not claimed as an independent second run.

The intermediate editor messages reporting failed text replacements do not alter this acceptance: the required R3 logic is present in the final committed source.

## Change policy after freeze

No new Phase 5.4 is authorized.

Future changes to knowledge_curator should be accepted only as one of:

1. integration adapter work required by a frozen external contract;
2. confirmed bug fix with regression test;
3. explicitly approved new product/research requirement.

Do not reopen frozen algorithms merely for refactoring or speculative generalization.

## Delivery decision

knowledge_curator is ready for **AI4S-ED system-level integration and downstream consumption**.

The authoritative R3 review is:

`planner/phase-05-3-r3-review.md`
