# Phase 4.0.1 Plan — H1 Anchor Reality + H2 Local Citation Metadata Closure

Planner: ChatGPT
Executor: MiMo
State: READY_FOR_EXECUTOR

## 0. Scope
This is a narrow closure round for the Phase 4.0 evidence guard.

Do not add FAISS/BM25/RRF/reranker.
Do not expose §6 MCP tools.
Do not start §7.
Do not modify frozen §5 or DSH/MCP integration.

## 1. H1 must validate real locator support
Update EvidenceMetadataPort so locator validation can represent three states:
- TRUE: the KB can verify this ref_id + locator exists;
- FALSE: the KB can verify it does not exist;
- UNKNOWN/UNSUPPORTED: this adapter cannot validate locator existence.

Recommended signature:
anchor_exists(ref_id, locator) -> Optional[bool]

Semantics:
- True => aligned locator check passes;
- False => emit H1 finding for unresolvable/misaligned anchor locator;
- None => do not claim alignment PASS; preserve a structured NOT_CHECKED/validation-unavailable signal.

Do not treat unsupported validation as False unless the adapter explicitly knows the locator is absent.

## 2. Improve InMemoryEvidenceStore
Allow tests to register known locators per ref_id.

Example internal shape:
REF-1 -> metadata + {'p.1','T12','Fig.3'}

anchor_exists must:
- return False for nonexistent ref_id;
- return True for registered locator;
- return False for an unregistered locator when locator checking is configured for that ref;
- return None when the fixture/ref has no locator index capability.

Keep this adapter test-only.

## 3. H1 result must expose unavailable alignment checks
Do not overload HallucinationFinding to mean both violation and not-checked if avoidable.

Recommended:
add a small H1CheckResult containing:
- findings
- locator_validation_checked: bool or per-anchor status.

If changing detect_h1 return type would cause unnecessary churn, add a parallel detect_h1_with_status and keep detect_h1 compatibility wrapper.

Acceptance behavior:
- no anchor => H1;
- missing ref => H1;
- empty locator => H1;
- real ref + fabricated known-checkable locator => H1;
- real ref + valid locator => no H1;
- real ref + locator validator unavailable => no fabricated PASS claim; status explicitly NOT_CHECKED/PARTIAL.

## 4. Add internal citation metadata input for H2
Do not mutate the docs/03 anchor tuple semantics.

Add a separate internal temporary model, e.g. CitationMetadata or CitedReference:
- ref_id
- optional cited_title
- optional cited_doi.

Claim may carry zero or more citation metadata records, or detector may receive them as an explicit argument.
Prefer the least invasive option.

This is temporary compatibility data only; mark it clearly.

## 5. H2 local metadata checks
For literature citations:
- cited ref_id absent in KB => H2;
- cited DOI present and KB DOI present but normalized values differ => H2;
- cited title present and KB title present but normalized exact/casefold-whitespace comparison differs materially => H2 in Phase 4.0.1;
- when cited DOI/title is absent, do not invent it;
- when KB metadata lacks DOI/title, return only what can be checked.

Do not perform fuzzy semantic title matching yet.
Do not call Crossref or web.

Normalize DOI conservatively:
- strip whitespace;
- casefold;
- remove optional https://doi.org/ or http://doi.org/ prefix;
- do not rewrite the DOI path.

Normalize title conservatively:
- Unicode-safe casefold;
- collapse whitespace;
- trim.

## 6. Avoid duplicate H1/H2 semantics
Missing literature ref_id may legitimately produce both:
- H1 because the claim anchor is not resolvable;
- H2 because the literature citation is fabricated/nonexistent.

That is acceptable because docs/03 defines distinct hallucination classes.

Do not deduplicate away one class.

## 7. Regression tests
Keep:
- knowledge_curator baseline 151 tests green;
- integration/dsh baseline 70 tests green.

Add tests for at least:
- H1 valid registered locator => no finding;
- H1 fabricated locator on existing ref => finding;
- H1 locator validation unavailable => explicit not-checked/partial status;
- H2 DOI exact normalized match => no finding;
- H2 DOI mismatch => finding;
- H2 title normalized match => no finding;
- H2 title mismatch => finding;
- H2 absent cited metadata does not fabricate mismatch;
- non-literature evidence does not trigger literature H2 metadata checks.

Also keep DSH strict regression hardening unchanged.

## 8. No public contract change
Do not edit docs/01 public schemas.
Do not claim EvidenceMetadataPort/CitationMetadata is a frozen cross-team contract.

If a future public answer/citation schema is needed from another team, note it in existing temporary-compatibility comments rather than inventing a cross-team API now.

## 9. Report
Create results/phase-04-0-1-executor-report.md.

Report:
- H1 locator validation behavior;
- unavailable-validation semantics;
- H2 local DOI/title behavior;
- exact test counts;
- public contracts changed? NO;
- CONTRACT_GAPS changes;
- implementation SHA.

## 10. status.json
On completion:
- phase = 4.0.1
- actor = executor
- state = executor_complete
- latest_commit = actual implementation SHA
- result_expected = results/phase-04-0-1-executor-report.md

Push main and stop.
Do not begin Phase 4.1.