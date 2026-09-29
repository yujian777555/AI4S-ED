# Phase 4.3 Planner Review — MOSTLY PASS, Final Evidence/DSH Semantics Closure Required

Implementation code SHA: 3150f33382507d375b149ac6032f18babb1d9f8b
origin/main bookkeeping tip: 3eb15ebc366353f98bf6f54988e21375567fa6c4
Verdict: MOSTLY PASS.

## Accepted

- EvidenceRetrievalService composes the frozen hybrid_retrieve path rather than implementing a second ranking pipeline.
- EvidenceBundle / ClaimGuardResult remain internal temporary models.
- Claims bind via anchor_chunk_ids to the current retrieval set; a client-supplied forged bundle is ignored by validate_retrieved_claims.
- Missing confidence / locator cannot authorize a factual claim.
- Confidence policy, numeric conflict policy, coverage Abstain, privacy Abstain and critical-numeric rules reuse the frozen guard functions.
- CG-017 is respected: raw FAISS/BM25/RRF/reranker scores are not fed into the uncalibrated 0.3 threshold.
- Production-default MCP runtime returns retrieval_unavailable instead of leaking the synthetic fixture.
- Existing MCP server is extended; no new top-level Agent was created.
- Real retrieval->guard smoke uses the real Phase 4.2 retrieval stack.
- Reported baselines are 290 knowledge_curator tests / 78 integration-dsh tests with zero failures.

## P4.3.1-01 — guardable_as_anchor and coverage can disagree with actual anchor construction

normalize_hit_to_record currently sets guardable_as_anchor from missing locator/confidence only.
But build_evidence_anchor additionally requires evidence_type != None.

Therefore a hit with an invalid/absent evidence_type and no configured default can be counted as:
- guardable_count >= 1;
- coverage = COVERED;

while build_evidence_anchor later returns None and the claim has no valid anchor.

Fix the invariant:
guardable_as_anchor == (build_evidence_anchor can succeed).

At minimum, missing/invalid evidence_type must be an unguardable reason when no valid default applies.
Coverage must count only records that can actually produce an EvidenceAnchor.

## P4.3.1-02 — H2 checked semantics are too optimistic

When no explicit EvidenceMetadataPort is supplied, ClaimGuardService constructs RetrievalSetMetadata.
That adapter proves only that a ref/locator is in the CURRENT retrieval set.
Its get_ref_metadata() may return RefMetadata(ref_id=...) with no DOI/title.

Current code sets h2_checked=True for any non-empty bundle.
If the proposed citation contains DOI/title but authoritative local citation metadata is unavailable, DOI/title was NOT actually checked.

Required semantics:
- H2 ref existence in the current retrieval set may be checked.
- If no citation DOI/title was supplied, local-ref H2 may be considered checked at that level.
- If cited DOI and/or title is supplied, h2_checked=true only when the required KB metadata fields were actually available and compared.
- Otherwise h2_checked=false (or explicit PARTIAL status) with h2_unavailable_reason.
- Never report H2 PASS merely because the retrieved ref exists.

No Crossref/web in this phase.

## P4.3.1-03 — DSH PASS evidence is MCP-only, not mounted Agent evidence

results/phase-04-3-mcp-dsh-smoke.json explicitly says:
"keyless stdio MCP discovery + direct-vs-tool identity/policy match; live DeepSeek model not required".

The new integration tests create/call MCPServer or stdio MCP directly.
They do NOT mount the existing knowledge-curator DSH preset through:
ctx.agents.create(...)
ctx.agentPresets.mount(...)

Therefore:
- MCP tool discovery = PASS;
- MCP roundtrip = PASS;
- mounted DSH Agent discovery/roundtrip is NOT YET PROVEN for the new tools.

Reuse the already accepted Phase 3.2.4 lane324 pattern. Do not create a new Agent.

## P4.3.1-04 — repair MCP source mojibake

knowledge_curator/mcp_server/app.py contains garbled strings such as the §5 tool description / em dash text.
Repair these as UTF-8 source strings. Do not alter business semantics.

## Next

Proceed to Phase 4.3.1 only.

After these four closures pass:
- freeze docs/03 §6 knowledge_curator capability;
- then proceed to docs/03 §7 curator-owned revision/retraction lifecycle work.
