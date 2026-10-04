"""Unified result protocol for agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AgentStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class AgentResult:
    """Unified result returned by AI4SAgent.run()."""

    status: AgentStatus
    workflow: str
    trace_id: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)
    knowledge_changes: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
