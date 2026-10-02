"""Deterministic task classifier. No LLM."""

from __future__ import annotations

from typing import Union

from system.task_planner.errors import InvalidTaskError
from system.task_planner.plan_protocol import PlannedTaskType

# Deterministic keyword-based classification.
_KEYWORD_MAP: dict[PlannedTaskType, tuple[str, ...]] = {
    PlannedTaskType.RETRIEVE: (
        "retrieve", "search", "evidence", "find", "lookup",
        "检索", "搜索", "证据", "查找",
    ),
    PlannedTaskType.CURATION_COMMIT: (
        "curate", "curation", "commit", "assertion", "ingest",
        "策审", "策审", "入库", "提交", "断言",
    ),
    PlannedTaskType.REVISION_PUBLICATION: (
        "revision", "publish", "retract", "corrigendum", "preprint",
        "journal", "version", "upgrade",
        "修订", "发布", "撤稿", "更正", "预印本", "期刊", "版本", "升级",
    ),
}

# Direct type mapping for exact enum values.
_DIRECT_MAP: dict[str, PlannedTaskType] = {
    "RETRIEVE": PlannedTaskType.RETRIEVE,
    "CURATION_COMMIT": PlannedTaskType.CURATION_COMMIT,
    "REVISION_PUBLICATION": PlannedTaskType.REVISION_PUBLICATION,
}


class TaskClassifier:
    """Deterministic text -> PlannedTaskType classifier."""

    def classify(self, text: str) -> PlannedTaskType:
        """Classify a task description string."""
        if not text or not text.strip():
            raise InvalidTaskError("empty task text")

        # Direct exact match first
        upper = text.strip().upper()
        if upper in _DIRECT_MAP:
            return _DIRECT_MAP[upper]

        # Keyword scoring
        lower = text.lower()
        scores: dict[PlannedTaskType, int] = {t: 0 for t in PlannedTaskType}
        for task_type, keywords in _KEYWORD_MAP.items():
            for kw in keywords:
                if kw in lower:
                    scores[task_type] += 1

        best = max(scores.values())
        if best == 0:
            raise InvalidTaskError(f"cannot classify task: {text[:100]}")

        # Return the first matching type in priority order
        for t in (PlannedTaskType.REVISION_PUBLICATION, PlannedTaskType.CURATION_COMMIT, PlannedTaskType.RETRIEVE):
            if scores[t] == best:
                return t

        raise InvalidTaskError(f"cannot classify task: {text[:100]}")

    def classify_with_type(self, task_type: Union[str, PlannedTaskType]) -> PlannedTaskType:
        """Accept explicit type directly."""
        if isinstance(task_type, PlannedTaskType):
            return task_type
        upper = task_type.strip().upper()
        if upper in _DIRECT_MAP:
            return _DIRECT_MAP[upper]
        raise InvalidTaskError(f"unknown task type: {task_type}")
