"""Unified execution context for agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4


@dataclass
class ExecutionContext:
    """Propagation context carried through workflow calls."""

    task_id: str = ""
    trace_id: str = ""
    provenance_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        task_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        provenance_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "ExecutionContext":
        return cls(
            task_id=task_id or f"task-{uuid4().hex[:12]}",
            trace_id=trace_id or "",
            provenance_id=provenance_id or "",
            metadata=dict(metadata or {}),
        )
