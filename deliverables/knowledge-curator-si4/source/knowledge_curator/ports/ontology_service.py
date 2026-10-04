"""OntologyService port — EDDO normalization query boundary.

Only the queries needed by knowledge_curator Phase 1 are defined here.
Do not implement full EDDO (CG / 02 ownership).
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.assertions import Condition


@runtime_checkable
class OntologyService(Protocol):
    """Entity/condition normalization queries used by curation."""

    def normalize_entity(self, mention: str, eddo_class: str) -> Optional[str]:
        """Resolve an original mention to a canonical entity id.

        Returns None when the concept is unresolved (do not guess/merge).
        """
        ...

    def normalize_condition(self, condition: Condition) -> Optional[Condition]:
        """Normalize a condition binding (class/value/unit) when possible."""
        ...

    def are_conditions_compatible(
        self,
        left: list[Condition],
        right: list[Condition],
    ) -> bool:
        """Return True when two condition sets describe the same operating domain.

        Different temperature/concentration/membrane type means NOT the same
        domain — those cases must be treated as condition_difference, not
        numeric_conflict.
        """
        ...
