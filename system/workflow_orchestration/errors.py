"""Workflow orchestration errors."""


class OrchestrationError(Exception):
    """Base error for workflow orchestration."""


class InvalidPlanError(OrchestrationError):
    """Execution plan is invalid."""


class StepExecutionError(OrchestrationError):
    """A workflow step failed during execution."""


class PlanStateError(OrchestrationError):
    """Invalid plan state transition."""
