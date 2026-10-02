"""Agent execution context for Knowledge Curator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CuratorContext:
    """Task context carried through agent execution."""

    task_id: str = ""
    trace_id: str = ""
    provenance_id: str = ""
    user_query: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence_history: list[dict[str, Any]] = field(default_factory=list)

    def add_evidence(self, bundle: dict[str, Any]) -> None:
        self.evidence_history.append(bundle)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "provenance_id": self.provenance_id,
            "user_query": self.user_query,
            "metadata": self.metadata,
        }
