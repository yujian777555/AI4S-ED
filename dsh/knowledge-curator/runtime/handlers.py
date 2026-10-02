"""Handlers for Knowledge Curator Agent capabilities.

Section 5: Curation + Commit (via internal bridge)
Section 6: Evidence-first QA (retrieve -> validate -> answer/abstain)
Section 7: Revision lifecycle (via internal bridge)

No direct store access. Delegates to existing workflows.
"""

from __future__ import annotations

from typing import Any, Optional

from runtime.context import CuratorContext


class CurationHandler:
    """Section 5: Knowledge curation and atomic commit."""

    @staticmethod
    async def handle(
        assertion_set: dict[str, Any],
        context: CuratorContext,
        tool_invoker: Optional[Any] = None,
        bridge: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Curate and commit through internal bridge.

        Flow: AssertionSet -> curate -> CurationReport -> CurationCommitWorkflow -> CommitResult
        """
        if tool_invoker is None:
            return {"status": "error", "error": "tool_invoker not available"}

        # Step 1: Curate via MCP tool
        curate_result = await tool_invoker(
            "mcp__knowledge_curator__curate_assertion_set",
            {"assertion_set": assertion_set},
        )

        report = (curate_result or {}).get("report") or {}
        report_status = report.get("status", "")

        # Step 2: If not publishable, return blocked
        if report_status in ("return_upstream", "rejected"):
            return {
                "status": "blocked",
                "reason": f"curation status: {report_status}",
                "report": report,
                "trace_id": context.trace_id,
            }

        decisions = report.get("decisions") or []
        if not decisions:
            return {
                "status": "blocked",
                "reason": "empty decisions",
                "report": report,
                "trace_id": context.trace_id,
            }

        # Step 3: Commit via internal bridge
        if bridge is not None:
            commit_result = await bridge.curate_and_commit(
                source_ref_id=assertion_set.get("ref_id", ""),
                source_fingerprint=context.metadata.get("source_fingerprint", ""),
                assertion_set=assertion_set,
                metadata=context.metadata,
                trace={"trace_id": context.trace_id, "provenance_id": context.provenance_id},
            )
            return {
                "status": commit_result.status,
                "report": report,
                "commit_attempted": commit_result.commit_attempted,
                "commit_result": str(commit_result.commit_result)[:200] if commit_result.commit_result else None,
                "blocked_reason": commit_result.blocked_reason,
                "trace_id": context.trace_id,
                "provenance_id": context.provenance_id,
            }

        return {
            "status": "curated_only",
            "report": report,
            "note": "bridge not configured; commit not attempted",
            "trace_id": context.trace_id,
        }


class EvidenceQAHandler:
    """Section 6: Anti-hallucination evidence-first QA.

    Required path: retrieve_evidence -> validate_retrieved_claims -> answer/abstain
    """

    @staticmethod
    async def handle(
        question: str,
        context: CuratorContext,
        tool_invoker: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Evidence-first QA with mandatory validation."""
        if tool_invoker is None:
            return {"status": "error", "error": "tool_invoker not available"}

        call_order: list[str] = []

        # Step 1: Retrieve evidence
        call_order.append("retrieve_evidence")
        retrieve_result = await tool_invoker(
            "mcp__knowledge_curator__retrieve_evidence",
            {
                "request": {
                    "query": question,
                    "top_k": 5,
                    "coverage_keys": ["sq1"],
                    "required_coverage_keys": ["sq1"],
                }
            },
        )

        bundle = (retrieve_result or {}).get("evidence_bundle") or {}
        abstain_info = bundle.get("abstain") or {}
        records = bundle.get("evidence_records") or []

        # If no evidence or abstain -> ABSTAIN
        if abstain_info.get("abstain") or not records:
            return {
                "status": "abstain",
                "answer": "ABSTAIN: insufficient evidence to answer this question.",
                "evidence_count": len(records),
                "abstain_reasons": abstain_info.get("reasons", []),
                "call_order": call_order,
                "trace_id": context.trace_id,
            }

        # Step 2: Build candidate claims from EVIDENCE CONTENT (not question)
        candidate_claims = []
        for r in records[:3]:
            # Derive claim text from actual evidence record content
            claim_text = r.get("payload_excerpt") or r.get("sentence_or_cell") or r.get("text") or ""
            if not claim_text:
                # Use structured evidence fields if available
                ref = r.get("ref_id", "")
                conf = r.get("confidence", "")
                claim_text = f"Evidence from {ref} (confidence: {conf})"
            candidate_claims.append({
                "claim_id": f"C{len(candidate_claims) + 1}",
                "text": claim_text,
                "anchor_chunk_ids": [r.get("chunk_id")],
            })

        # Step 3: Validate claims (MANDATORY before any answer)
        call_order.append("validate_retrieved_claims")
        validate_result = await tool_invoker(
            "mcp__knowledge_curator__validate_retrieved_claims",
            {
                "payload": {
                    "query": question,
                    "claims": candidate_claims,
                }
            },
        )

        claim_results = (validate_result or {}).get("claim_results") or []

        # Step 4: Check validation outcomes
        validated_claims = []
        for cr in claim_results:
            policy = (cr.get("policy") or {}).get("policy", "")
            abstain = (cr.get("abstain") or {}).get("abstain", True)
            if policy == "factual_allowed" and not abstain:
                validated_claims.append(cr)

        # If no claims passed validation -> ABSTAIN
        if not validated_claims:
            return {
                "status": "abstain",
                "answer": "ABSTAIN: claims not supported by evidence after validation.",
                "evidence_count": len(records),
                "validation_results": [
                    {"claim_id": cr.get("claim_id"), "policy": (cr.get("policy") or {}).get("policy")}
                    for cr in claim_results
                ],
                "call_order": call_order,
                "trace_id": context.trace_id,
            }

        # Step 5: Build grounded answer from validated claims only
        citations = []
        claim_contents = []
        for cr in validated_claims:
            anchors = cr.get("resolved_anchors") or []
            for a in anchors:
                citations.append({
                    "ref_id": a.get("ref_id"),
                    "locator": a.get("locator"),
                    "confidence": a.get("confidence"),
                    "access_pointer": a.get("access_pointer"),
                })
            # Include actual claim text from validation
            claim_contents.append({
                "claim_id": cr.get("claim_id"),
                "text": cr.get("claim_text") or cr.get("text") or "",
                "confidence": (cr.get("policy") or {}).get("effective_confidence"),
                "citations": [
                    {"ref_id": a.get("ref_id"), "locator": a.get("locator")}
                    for a in anchors
                ],
            })

        return {
            "status": "answered",
            "answer": claim_contents[0]["text"] if claim_contents else "",
            "claims": claim_contents,
            "citations": citations,
            "call_order": call_order,
            "trace_id": context.trace_id,
        }


class RevisionHandler:
    """Section 7: Knowledge lifecycle update and incremental governance."""

    @staticmethod
    async def handle(
        revision_package: Any,
        target_commit_request: Any,
        context: CuratorContext,
        bridge: Optional[Any] = None,
        approval: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Revision through internal bridge to RevisionPublicationWorkflow."""
        if bridge is None:
            return {
                "status": "error",
                "error": "bridge not configured",
                "trace_id": context.trace_id,
            }

        result = await bridge.revise(
            package=revision_package,
            target_commit_request=target_commit_request,
            approval=approval,
        )

        return {
            "status": result.status,
            "publication_result": str(result.publication_result)[:300] if result.publication_result else None,
            "error": result.error,
            "trace_id": context.trace_id,
            "provenance_id": context.provenance_id,
        }
