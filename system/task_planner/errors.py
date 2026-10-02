"""Task Planner errors."""


class TaskPlannerError(Exception):
    """Base error for task planner."""


class InvalidTaskError(TaskPlannerError):
    """Task input is invalid or unclassifiable."""
