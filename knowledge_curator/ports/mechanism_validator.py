"""MechanismValidator port — L3 hard-rule / mechanism constraint boundary.

Do not implement Donnan / Nernst-Planck / CFD / limiting-current / energy-balance
models here. Real validator is owned by 04 (CG-003).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from knowledge_curator.schemas.assertions import Assertion


@dataclass
class MechanismCheckResult:
    """Result of one mechanism validation call."""

    ok: bool
    violated_assertion_ids: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class MechanismValidator(Protocol):
    """Boundary for L3 mechanism / dimensional hard-rule checks."""

    def check(self, claims: list[Assertion]) -> MechanismCheckResult:
        """Check claims against mechanism/dimensional hard rules.

        Args:
            claims: Assertions to validate.

        Returns:
            MechanismCheckResult with ok=False and violated ids on failure.
        """
        ...
