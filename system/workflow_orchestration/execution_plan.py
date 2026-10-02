"""Execution plan definition."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class PlanStep:
    """One step in an execution plan."""

    step_id: str
    workflow_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING


@dataclass
class ExecutionPlan:
    """Multi-step scientific workflow plan."""

    plan_id: str
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    current_step: int = 0
    status: str = "PENDING"
    trace_id: str = ""
    provenance_id: str = ""

    @classmethod
    def create(
        cls,
        goal: str,
        steps: list[PlanStep],
        *,
        plan_id: Optional[str] = None,
        trace_id: str = "",
        provenance_id: str = "",
    ) -> "ExecutionPlan":
        return cls(
            plan_id=plan_id or f"plan-{uuid4().hex[:12]}",
            goal=goal,
            steps=steps,
            trace_id=trace_id,
            provenance_id=provenance_id,
        )
