"""Agent Runtime errors."""


class AgentRuntimeError(Exception):
    """Base error for agent runtime."""


class ProviderNotConfiguredError(AgentRuntimeError):
    """Provider missing or invalid. Fail closed."""


class UnknownTaskTypeError(AgentRuntimeError):
    """TaskType not registered in the router."""


class WorkflowNotRegisteredError(AgentRuntimeError):
    """Workflow name not found in the registry."""


class AgentInputError(AgentRuntimeError):
    """Invalid agent input (missing task, context, etc.)."""
