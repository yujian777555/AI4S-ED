"""Task plan protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class PlannedTaskType(str, Enum):
    RETRIEVE = "RETRIEVE"
    CURATION_COMMIT = "CURATION_COMMIT"
    REVISION_PUBLICATION = "REVISION_PUBLICATION"


@dataclass
class TaskPlan:
    """Deterministic plan produced by ScientificTaskPlanner."""

    task_id: str
    task_type: PlannedTaskType
    workflow_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    provenance_id: str = ""
