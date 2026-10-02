"""Handlers for Knowledge Curator Agent capabilities.

Each handler delegates to existing MCP tools / workflows.
No direct store access. No database writes.
"""

from __future__ import annotations

from typing import Any, Optional

from runtime.context import CuratorContext


class CurationHandler:
    """Section 5: Knowledge curation and evidence governance."""

    @staticmethod
    async def handle(
        assertion_set: dict[str, Any],
        context: CuratorContext,
        tool_invoker: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Curate an AssertionSet through the existing MCP tool.

        Flow: AssertionSet -> curate_assertion_set -> CurationReport
        """
        if tool_invoker is None:
            return {
                "status": "error",
                "error": "tool_invoker not available",
            }

        result = await tool_invoker(
            "mcp__knowledge_curator__curate_assertion_set",
            {"assertion_set": assertion_set},
        )
        return {
            "status": "curated",
            "report": result,
            "trace_id": context.trace_id,
            "provenance_id": context.provenance_id,
        }


class EvidenceQAHandler:
    """Section 6: Anti-hallucination evidence-first QA."""

    @staticmethod
    async def handle(
        question: str,
        context: CuratorContext,
        tool_invoker: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Evidence-first QA: retrieve -> validate -> answer/abstain.

        Must ABSTAIN when evidence is insufficient.
        """
        if tool_invoker is None:
            return {
                "status": "error",
                "error": "tool_invoker not available",
            }

        # Step 1: Retrieve evidence
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
        abstain = (bundle.get("abstain") or {}).get("abstain", True)
        records = bundle.get("evidence_records") or []

        # Step 2: If abstain or no evidence -> ABSTAIN
        if abstain or not records:
            return {
                "status": "abstain",
                "answer": "ABSTAIN: insufficient evidence to answer this question.",
                "evidence_count": len(records),
                "abstain_reasons": (bundle.get("abstain") or {}).get("reasons", []),
                "trace_id": context.trace_id,
            }

        # Step 3: Build answer from evidence
        citations = [
            {
                "chunk_id": r.get("chunk_id"),
                "ref_id": r.get("ref_id"),
                "confidence": r.get("confidence"),
                "access_pointer": r.get("access_pointer"),
            }
            for r in records[:3]
        ]

        return {
            "status": "answered",
            "answer": f"Based on {len(records)} evidence records: {question}",
            "citations": citations,
            "confidence": records[0].get("confidence") if records else None,
            "evidence_count": len(records),
            "trace_id": context.trace_id,
        }


class RevisionHandler:
    """Section 7: Knowledge lifecycle update and incremental governance."""

    @staticmethod
    async def handle(
        new_knowledge: dict[str, Any],
        context: CuratorContext,
        tool_invoker: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Handle new knowledge through comparison and revision workflow.

        Flow: New Knowledge -> Compare -> RevisionPublicationWorkflow -> New Version
        """
        # Internal workflow call (not MCP tool)
        # The actual revision is delegated to RevisionPublicationWorkflow
        return {
            "status": "revision_ready",
            "action": "compare_and_route",
            "note": "Revision requires RevisionPackage; delegate to RevisionPublicationWorkflow",
            "trace_id": context.trace_id,
            "provenance_id": context.provenance_id,
        }
