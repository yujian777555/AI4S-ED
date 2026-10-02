"""Deterministic workflow planner. No LLM."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from system.workflow_orchestration.errors import InvalidPlanError
from system.workflow_orchestration.execution_plan import ExecutionPlan, PlanStep
from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan


# Deterministic mapping: PlannedTaskType -> ordered workflow steps
_TASK_TO_STEPS: dict[PlannedTaskType, list[str]] = {
    PlannedTaskType.RETRIEVE: ["retrieve"],
    PlannedTaskType.CURATION_COMMIT: ["retrieve", "curation", "commit"],
    PlannedTaskType.REVISION_PUBLICATION: ["revision"],
}


class WorkflowPlanner:
    """Deterministic planner producing ExecutionPlan from TaskPlan."""

    def plan_from_task(
        self,
        task_plan: TaskPlan,
        *,
        goal: Optional[str] = None,
    ) -> ExecutionPlan:
        """Generate an ExecutionPlan from a TaskPlan."""
        step_names = _TASK_TO_STEPS.get(task_plan.task_type)
        if not step_names:
            raise InvalidPlanError(f"no step template for {task_plan.task_type}")

        steps: list[PlanStep] = []
        for i, name in enumerate(step_names):
            step_id = f"step-{i + 1}-{name}"
            depends_on = [f"step-{i}-{step_names[i - 1]}"] if i > 0 else []
            steps.append(
                PlanStep(
                    step_id=step_id,
                    workflow_name=name,
                    parameters=dict(task_plan.parameters),
                    depends_on=depends_on,
                )
            )

        return ExecutionPlan.create(
            goal=goal or task_plan.task_type.value,
            steps=steps,
            trace_id=task_plan.trace_id,
            provenance_id=task_plan.provenance_id,
        )
