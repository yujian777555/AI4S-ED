"""AI4S Agent Runtime — unified entry point.

Agent -> TaskRouter -> WorkflowRegistry -> Workflow -> AgentResult

Agent must NOT directly access stores, coordinators, or databases.
"""

from __future__ import annotations

from typing import Any, Optional

from system.agent_runtime.errors import AgentInputError
from system.task_planner.plan_protocol import TaskPlan
from system.agent_runtime.execution_context import ExecutionContext
from system.agent_runtime.result_protocol import AgentResult, AgentStatus
from system.agent_runtime.task_router import TaskRouter, TaskType
from system.agent_runtime.workflow_registry import WorkflowRegistry


class AI4SAgent:
    """Product-level agent runtime entry point."""

    def __init__(
        self,
        *,
        router: TaskRouter,
        registry: WorkflowRegistry,
        provider_identity: str = "external",
    ) -> None:
        self._router = router
        self._registry = registry
        self._provider_identity = provider_identity

    async def run(
        self,
        task: Any,
        context: Optional[ExecutionContext] = None,
        **kwargs: Any,
    ) -> AgentResult:
        """Execute a task through the registered workflow.

        Args:
            task: TaskType enum, string value, or TaskPlan.
            context: ExecutionContext. Created automatically if omitted.
            **kwargs: Passed through to the underlying workflow.run().
        """
        # SI-3B: accept TaskPlan directly
        if isinstance(task, TaskPlan):
            if context is None:
                context = ExecutionContext.create(
                    trace_id=task.trace_id,
                    provenance_id=task.provenance_id,
                )
            workflow_name = task.workflow_name
            # Merge plan parameters into kwargs
            for k, v in task.parameters.items():
                kwargs.setdefault(k, v)
        else:
            if context is None:
                context = ExecutionContext.create()
            # 1. Route task to workflow name
            workflow_name = self._router.resolve(task)

        # 2. Get workflow from registry
        workflow = self._registry.get(workflow_name)

        # 3. Delegate to workflow (agent never touches stores directly)
        try:
            raw_result = await self._invoke_workflow(workflow, context, **kwargs)
        except Exception as exc:
            return AgentResult(
                status=AgentStatus.FAILED,
                workflow=workflow_name,
                trace_id=context.trace_id,
                error=str(exc),
            )

        # 4. Wrap into AgentResult
        return self._wrap_result(workflow_name, context, raw_result)

    async def _invoke_workflow(
        self,
        workflow: Any,
        context: ExecutionContext,
        **kwargs: Any,
    ) -> Any:
        """Invoke workflow.run() with context-aware arguments."""
        # Build trace/metadata dict for workflows that accept it
        trace = {}
        if context.trace_id:
            trace["trace_id"] = context.trace_id
        if context.provenance_id:
            trace["provenance_id"] = context.provenance_id

        metadata = dict(context.metadata)

        # Inspect the workflow signature to pass compatible arguments
        import inspect

        sig = inspect.signature(workflow.run)
        params = sig.parameters

        call_kwargs = dict(kwargs)
        if "trace" in params and trace:
            call_kwargs.setdefault("trace", trace)
        if "metadata" in params and metadata:
            call_kwargs.setdefault("metadata", metadata)

        return await workflow.run(**call_kwargs)

    def _wrap_result(
        self,
        workflow_name: str,
        context: ExecutionContext,
        raw: Any,
    ) -> AgentResult:
        """Wrap a workflow result into AgentResult."""
        status = AgentStatus.SUCCESS
        error = None
        artifacts: dict[str, Any] = {}
        knowledge_changes: list[dict[str, Any]] = []

        # Detect status from common result patterns
        raw_status = getattr(raw, "status", None)
        if raw_status is not None:
            status_str = (
                raw_status.value if hasattr(raw_status, "value") else str(raw_status)
            ).lower()
            if status_str in ("failed", "error", "conflict"):
                status = AgentStatus.FAILED
            elif status_str in ("blocked", "pending", "approval_required", "approval_rejected", "package_review_required"):
                status = AgentStatus.BLOCKED

        raw_error = getattr(raw, "last_error", None) or getattr(raw, "error", None)
        if raw_error:
            error = str(raw_error)
            if status == AgentStatus.SUCCESS:
                status = AgentStatus.FAILED

        # Extract artifacts from common result fields
        for field_name in ("report", "commit_result", "final_version_id", "target_version_id", "publication_id"):
            val = getattr(raw, field_name, None)
            if val is not None:
                artifacts[field_name] = val

        return AgentResult(
            status=status,
            workflow=workflow_name,
            trace_id=context.trace_id,
            artifacts=artifacts,
            knowledge_changes=knowledge_changes,
            error=error,
        )
