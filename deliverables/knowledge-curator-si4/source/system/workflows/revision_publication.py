"""SI-2B revision publication application workflow (thin delegate).

Delegates authoritative semantics to the frozen RevisionPublicationCoordinator.
Does NOT synthesize approvals. Does NOT auto-retry. Does NOT invent statuses.
"""

from __future__ import annotations

from typing import Any, Optional

from knowledge_curator.schemas.commit import CommitRequest
from knowledge_curator.schemas.revision_publication import (
    RevisionApproval,
    RevisionPublicationResult,
)
from knowledge_curator.schemas.version_delta import RevisionPackage


class RevisionWorkflowInputError(ValueError):
    """Raised when workflow input is structurally invalid. Fail closed."""


class RevisionPublicationWorkflow:
    """Transport-independent revision publication workflow."""

    def __init__(
        self,
        *,
        revision_publication_coordinator: Any,
        provider_identity: str = "external",
    ) -> None:
        self._coordinator = revision_publication_coordinator
        self._provider_identity = provider_identity

    async def run(
        self,
        *,
        package: RevisionPackage,
        target_commit_request: CommitRequest,
        approval: Optional[RevisionApproval] = None,
    ) -> RevisionPublicationResult:
        """Delegate exactly once to RevisionPublicationCoordinator.publish()."""
        # Minimal structural input check (fail closed before coordinator).
        if package is None:
            raise RevisionWorkflowInputError("package is required")
        if target_commit_request is None:
            raise RevisionWorkflowInputError("target_commit_request is required")

        # Single delegation — no retry loop.
        return await self._coordinator.publish(
            package=package,
            target_commit_request=target_commit_request,
            approval=approval,
        )
