"""SI-2A curation-to-commit application workflow.

Delegates curation to the existing CuratorRuntime and commit to the frozen
DocumentCommitCoordinator. Does NOT duplicate commit logic. Does NOT
auto-retry PENDING_VECTOR / PENDING_FINALIZE / FAILED.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Optional

from knowledge_curator.core.commit import DocumentCommitCoordinator
from knowledge_curator.schemas.assertions import AssertionSet
from knowledge_curator.schemas.commit import (
    CommitRequest,
    CommitResult,
    CommitStatus,
    SourceIdentity,
)
from knowledge_curator.schemas.curation import CurationAction, CurationReport


class WorkflowInputError(ValueError):
    """Raised when workflow input is invalid. Fail closed before commit."""


@dataclass
class CurationCommitResult:
    """Application-level result of one workflow invocation."""

    report: Optional[CurationReport]
    commit_attempted: bool = False
    commit_result: Optional[CommitResult] = None
    blocked_reason: Optional[str] = None


class CurationCommitWorkflow:
    """Transport-independent curation -> commit application workflow."""

    def __init__(
        self,
        *,
        curator_runtime: Any,
        commit_coordinator: DocumentCommitCoordinator,
        provider_identity: str = "external",
    ) -> None:
        self._curator_runtime = curator_runtime
        self._coordinator = commit_coordinator
        self._provider_identity = provider_identity

    async def run(
        self,
        *,
        source: SourceIdentity,
        assertion_set: AssertionSet,
        metadata: Optional[dict[str, Any]] = None,
        trace: Optional[dict[str, Any]] = None,
    ) -> CurationCommitResult:
        # Step 1: validate application input (fail closed before scientific work).
        self._validate_input(source, assertion_set)

        # Step 2: curate via existing delegation path.
        from knowledge_curator.mcp_server.runtime import run_curate

        report = await run_curate(self._curator_runtime, assertion_set)

        # Step 3: conservative precommit gate.
        blocked = self._precommit_gate(report)
        if blocked is not None:
            return CurationCommitResult(
                report=report,
                commit_attempted=False,
                commit_result=None,
                blocked_reason=blocked,
            )

        # Step 4: build CommitRequest (copy metadata/trace, do not mutate caller).
        request = CommitRequest(
            source=source,
            assertion_set=assertion_set,
            report=report,
            metadata=copy.deepcopy(metadata) if metadata else {},
            trace=copy.deepcopy(trace) if trace else {},
        )

        # Step 5: commit exactly once. No hidden retry.
        commit_result = await self._coordinator.commit(request)

        # Step 6: return application result.
        return CurationCommitResult(
            report=report,
            commit_attempted=True,
            commit_result=commit_result,
            blocked_reason=None,
        )

    def _validate_input(
        self, source: SourceIdentity, assertion_set: AssertionSet
    ) -> None:
        if not source.source_fingerprint or not str(source.source_fingerprint).strip():
            raise WorkflowInputError(
                "source_fingerprint must be non-empty; caller must supply it explicitly"
            )
        if not source.ref_id or not str(source.ref_id).strip():
            raise WorkflowInputError("source.ref_id must be non-empty")
        if source.ref_id != assertion_set.ref_id:
            raise WorkflowInputError(
                f"source.ref_id ({source.ref_id}) != assertion_set.ref_id ({assertion_set.ref_id})"
            )

    def _precommit_gate(self, report: CurationReport) -> Optional[str]:
        """Conservative short-circuit for clearly terminal curation outcomes."""
        if report.status == "return_upstream" or report.returned_upstream_count > 0:
            return "return_upstream"
        if not report.decisions:
            return "empty_decisions"
        actions = [d.action for d in report.decisions]
        if all(a == CurationAction.REJECT for a in actions):
            return "all_rejected"
        return None
