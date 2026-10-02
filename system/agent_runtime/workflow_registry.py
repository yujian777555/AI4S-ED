"""Workflow registry: maps workflow names to instantiated workflow objects."""

from __future__ import annotations

from typing import Any

from system.agent_runtime.errors import WorkflowNotRegisteredError


class WorkflowRegistry:
    """Registry of workflow instances accessible to the agent."""

    def __init__(self) -> None:
        self._workflows: dict[str, Any] = {}

    def register(self, name: str, workflow: Any) -> None:
        self._workflows[name] = workflow

    def get(self, name: str) -> Any:
        wf = self._workflows.get(name)
        if wf is None:
            raise WorkflowNotRegisteredError(f"workflow not registered: {name}")
        return wf

    def has(self, name: str) -> bool:
        return name in self._workflows

    @property
    def names(self) -> list[str]:
        return list(self._workflows.keys())
