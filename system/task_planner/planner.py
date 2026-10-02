"""Scientific Task Planner: deterministic task understanding + workflow selection."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from system.task_planner.errors import InvalidTaskError
from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan
from system.task_planner.task_classifier import TaskClassifier

# PlannedTaskType -> workflow_name (must match WorkflowRegistry keys)
_TASK_TYPE_TO_WORKFLOW: dict[PlannedTaskType, str] = {
    PlannedTaskType.CURATION_COMMIT: "curation_commit",
    PlannedTaskType.REVISION_PUBLICATION: "revision_publication",
    # RETRIEVE has no workflow in SI-3B; it maps to a reserved name
    PlannedTaskType.RETRIEVE: "retrieve",
}


class ScientificTaskPlanner:
    """Deterministic planner producing TaskPlan from user input."""

    def __init__(self, classifier: Optional[TaskClassifier] = None) -> None:
        self._classifier = classifier or TaskClassifier()

    def plan(
        self,
        task_text: str = "",
        *,
        task_type: Optional[str] = None,
        task_id: Optional[str] = None,
        trace_id: str = "",
        provenance_id: str = "",
        parameters: Optional[dict[str, Any]] = None,
    ) -> TaskPlan:
        """Produce a TaskPlan from either text or explicit type."""
        if task_type is not None:
            planned_type = self._classifier.classify_with_type(task_type)
        elif task_text:
            planned_type = self._classifier.classify(task_text)
        else:
            raise InvalidTaskError("provide task_text or task_type")

        workflow_name = _TASK_TYPE_TO_WORKFLOW.get(planned_type)
        if workflow_name is None:
            raise InvalidTaskError(f"no workflow mapped for {planned_type}")

        return TaskPlan(
            task_id=task_id or f"plan-{uuid4().hex[:12]}",
            task_type=planned_type,
            workflow_name=workflow_name,
            parameters=dict(parameters or {}),
            trace_id=trace_id,
            provenance_id=provenance_id,
        )
