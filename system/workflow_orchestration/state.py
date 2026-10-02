"""Execution state tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ExecutionStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


@dataclass
class ExecutionState:
    """Tracks progress of an execution plan."""

    plan_id: str
    status: ExecutionStatus = ExecutionStatus.RUNNING
    current_step_id: Optional[str] = None
    completed_step_ids: list[str] = field(default_factory=list)
    error: Optional[str] = None
    step_results: dict[str, Any] = field(default_factory=dict)
