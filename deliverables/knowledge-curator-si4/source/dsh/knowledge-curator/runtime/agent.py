"""AI4S Knowledge Curator Agent — DSH runtime entry.

Section 5: Curation + Commit (via internal bridge -> CurationCommitWorkflow)
Section 6: Evidence-first QA (retrieve -> validate -> answer/abstain)
Section 7: Revision lifecycle (via internal bridge -> RevisionPublicationWorkflow)

Boundaries:
- Agent -> Bridge -> Workflow -> Coordinator -> Store
- No direct store/database access
- Public MCP: exactly four tools
"""

from __future__ import annotations

from typing import Any, Optional

from runtime.context import CuratorContext
from runtime.handlers import CurationHandler, EvidenceQAHandler, RevisionHandler


class KnowledgeCuratorAgent:
    """DSH Knowledge Curator Agent."""

    def __init__(
        self,
        tool_invoker: Optional[Any] = None,
        bridge: Optional[Any] = None,
    ) -> None:
        self._tool_invoker = tool_invoker
        self._bridge = bridge

    async def curate(
        self,
        assertion_set: dict[str, Any],
        context: Optional[CuratorContext] = None,
    ) -> dict[str, Any]:
        """Section 5: Curate and commit."""
        ctx = context or CuratorContext()
        return await CurationHandler.handle(assertion_set, ctx, self._tool_invoker, self._bridge)

    async def answer(
        self,
        question: str,
        context: Optional[CuratorContext] = None,
    ) -> dict[str, Any]:
        """Section 6: Evidence-first QA with mandatory validation."""
        ctx = context or CuratorContext(user_query=question)
        return await EvidenceQAHandler.handle(question, ctx, self._tool_invoker)

    async def revise(
        self,
        revision_package: Any,
        target_commit_request: Any,
        context: Optional[CuratorContext] = None,
        approval: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Section 7: Revision lifecycle."""
        ctx = context or CuratorContext()
        return await RevisionHandler.handle(revision_package, target_commit_request, ctx, self._bridge, approval)

    async def health(self) -> dict[str, Any]:
        """Health check via existing MCP tool."""
        if self._tool_invoker is None:
            return {"ok": False, "error": "tool_invoker not available"}
        return await self._tool_invoker("mcp__knowledge_curator__knowledge_curator_health", {})
