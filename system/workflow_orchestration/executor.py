"""Workflow executor: runs ExecutionPlan steps through WorkflowRegistry."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from system.workflow_orchestration.errors import StepExecutionError
from system.workflow_orchestration.execution_plan import ExecutionPlan, PlanStep, StepStatus
from system.workflow_orchestration.state import ExecutionState, ExecutionStatus
from system.agent_runtime.workflow_registry import WorkflowRegistry


class WorkflowExecutor:
    """Executes ExecutionPlan steps in dependency order."""

    def __init__(self, registry: WorkflowRegistry) -> None:
        self._registry = registry

    async def execute(self, plan: ExecutionPlan) -> ExecutionState:
        """Execute all steps in dependency order.

        On failure: marks state FAILED and stops (no hidden retry).
        On resume: skips already-completed steps.
        """
        state = ExecutionState(plan_id=plan.plan_id)

        for step in plan.steps:
            # Skip already-completed steps (resume support)
            if step.status == StepStatus.COMPLETED:
                state.completed_step_ids.append(step.step_id)
                continue

            # Check dependencies
            for dep in step.depends_on:
                if dep not in state.completed_step_ids:
                    state.status = ExecutionStatus.FAILED
                    state.error = f"dependency not met: {dep} for {step.step_id}"
                    state.current_step_id = step.step_id
                    return state

            # Execute step
            state.current_step_id = step.step_id
            step.status = StepStatus.RUNNING

            try:
                workflow = self._registry.get(step.workflow_name)
                result = await self._run_workflow(workflow, step)
                step.status = StepStatus.COMPLETED
                state.completed_step_ids.append(step.step_id)
                state.step_results[step.step_id] = result
            except Exception as exc:
                step.status = StepStatus.FAILED
                state.status = ExecutionStatus.FAILED
                state.error = f"{step.step_id}: {exc}"
                return state

        state.status = ExecutionStatus.COMPLETED
        state.current_step_id = None
        return state

    async def _run_workflow(self, workflow: Any, step: PlanStep) -> Any:
        """Invoke workflow.run() with step parameters."""
        import inspect

        sig = inspect.signature(workflow.run)
        params = sig.parameters

        call_kwargs = dict(step.parameters)
        # Only pass kwargs the workflow accepts
        if not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            call_kwargs = {k: v for k, v in call_kwargs.items() if k in params}

        return await workflow.run(**call_kwargs)
