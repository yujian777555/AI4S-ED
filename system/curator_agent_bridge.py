"""Internal application bridge for Knowledge Curator Agent.

Composes existing workflows for DSH package use. Does NOT reimplement
commit/revision logic. Does NOT create new MCP tools.

Boundary: DSH Agent -> Bridge -> Workflow -> Coordinator -> Store
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CurateAndCommitResult:
    """Result of curation + commit."""
    status: str
    report: Optional[dict] = None
    commit_result: Optional[Any] = None
    commit_attempted: bool = False
    blocked_reason: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RevisionResult:
    """Result of revision publication."""
    status: str
    publication_result: Optional[Any] = None
    error: Optional[str] = None


class CuratorAgentBridge:
    """Minimal bridge: compose + delegate to existing workflows."""

    def __init__(
        self,
        *,
        curation_workflow: Optional[Any] = None,
        revision_workflow: Optional[Any] = None,
    ) -> None:
        self._curation_workflow = curation_workflow
        self._revision_workflow = revision_workflow

    async def curate_and_commit(
        self,
        *,
        source_ref_id: str,
        source_fingerprint: str,
        assertion_set: Any,
        metadata: Optional[dict] = None,
        trace: Optional[dict] = None,
    ) -> CurateAndCommitResult:
        """Section 5: CurationReport -> CurationCommitWorkflow -> CommitResult."""
        if self._curation_workflow is None:
            return CurateAndCommitResult(
                status="error",
                error="curation workflow not configured",
            )

        from knowledge_curator.schemas.commit import SourceIdentity

        source = SourceIdentity(
            ref_id=source_ref_id,
            source_fingerprint=source_fingerprint,
        )

        try:
            result = await self._curation_workflow.run(
                source=source,
                assertion_set=assertion_set,
                metadata=metadata or {},
                trace=trace or {},
            )
        except Exception as exc:
            return CurateAndCommitResult(status="error", error=str(exc))

        # Extract report as dict if possible
        report = result.report
        report_dict = None
        if report is not None:
            report_dict = {
                "status": getattr(report, "status", None),
                "source_ref_id": getattr(report, "source_ref_id", None),
                "decisions_count": len(getattr(report, "decisions", []) or []),
            }

        commit_status = None
        if result.commit_result is not None:
            commit_status = getattr(result.commit_result, "status", None)
            commit_status = commit_status.value if hasattr(commit_status, "value") else str(commit_status)

        return CurateAndCommitResult(
            status=commit_status or ("blocked" if not result.commit_attempted else "unknown"),
            report=report_dict,
            commit_result=result.commit_result,
            commit_attempted=result.commit_attempted,
            blocked_reason=result.blocked_reason,
        )

    async def revise(
        self,
        *,
        package: Any,
        target_commit_request: Any,
        approval: Optional[Any] = None,
    ) -> RevisionResult:
        """Section 7: RevisionPublicationWorkflow -> FINALIZED."""
        if self._revision_workflow is None:
            return RevisionResult(
                status="error",
                error="revision workflow not configured",
            )

        try:
            result = await self._revision_workflow.run(
                package=package,
                target_commit_request=target_commit_request,
                approval=approval,
            )
        except Exception as exc:
            return RevisionResult(status="error", error=str(exc))

        status = getattr(result, "status", None)
        status_str = status.value if hasattr(status, "value") else str(status)

        return RevisionResult(status=status_str, publication_result=result)
