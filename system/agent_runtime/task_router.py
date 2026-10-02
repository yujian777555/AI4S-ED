"""Task router: explicit TaskType -> workflow name mapping."""

from __future__ import annotations

from enum import Enum

from system.agent_runtime.errors import UnknownTaskTypeError


class TaskType(str, Enum):
    CURATION_COMMIT = "CURATION_COMMIT"
    REVISION_PUBLICATION = "REVISION_PUBLICATION"


# Explicit mapping. No LLM planner in SI-3A.
_TASK_TO_WORKFLOW: dict[TaskType, str] = {
    TaskType.CURATION_COMMIT: "curation_commit",
    TaskType.REVISION_PUBLICATION: "revision_publication",
}


class TaskRouter:
    """Routes a TaskType to the canonical workflow name."""

    def resolve(self, task: TaskType | str) -> str:
        if isinstance(task, str):
            try:
                task = TaskType(task)
            except ValueError:
                raise UnknownTaskTypeError(f"unknown task type: {task}") from None
        workflow_name = _TASK_TO_WORKFLOW.get(task)
        if workflow_name is None:
            raise UnknownTaskTypeError(f"no workflow mapped for task: {task}")
        return workflow_name
