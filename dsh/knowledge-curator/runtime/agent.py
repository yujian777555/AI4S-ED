"""AI4S Knowledge Curator Agent — DSH runtime entry.

Provides unified agent interface for:
1. Knowledge Curation (Section 5)
2. Evidence QA (Section 6)
3. Lifecycle Governance (Section 7)

Boundaries:
- Agent -> Workflow -> Coordinator -> Store
- No direct store/database access
- Delegates to existing MCP tools and workflows
"""

from __future__ import annotations

from typing import Any, Optional

from runtime.context import CuratorContext
from runtime.handlers import CurationHandler, EvidenceQAHandler, RevisionHandler


class KnowledgeCuratorAgent:
    """DSH Knowledge Curator Agent."""

    def __init__(self, tool_invoker: Optional[Any] = None) -> None:
        self._tool_invoker = tool_invoker

    async def curate(
        self,
        assertion_set: dict[str, Any],
        context: Optional[CuratorContext] = None,
    ) -> dict[str, Any]:
        """Section 5: Curate an AssertionSet."""
        ctx = context or CuratorContext()
        return await CurationHandler.handle(assertion_set, ctx, self._tool_invoker)

    async def answer(
        self,
        question: str,
        context: Optional[CuratorContext] = None,
    ) -> dict[str, Any]:
        """Section 6: Evidence-first QA with abstain."""
        ctx = context or CuratorContext(user_query=question)
        return await EvidenceQAHandler.handle(question, ctx, self._tool_invoker)

    async def revise(
        self,
        new_knowledge: dict[str, Any],
        context: Optional[CuratorContext] = None,
    ) -> dict[str, Any]:
        """Section 7: Knowledge revision and lifecycle governance."""
        ctx = context or CuratorContext()
        return await RevisionHandler.handle(new_knowledge, ctx, self._tool_invoker)

    async def health(self) -> dict[str, Any]:
        """Health check via existing MCP tool."""
        if self._tool_invoker is None:
            return {"ok": False, "error": "tool_invoker not available"}
        return await self._tool_invoker("mcp__knowledge_curator__knowledge_curator_health", {})
