"""In-memory / fake adapters for Phase 1 testing and local development."""

from __future__ import annotations

from typing import Optional

from knowledge_curator.ports.mechanism_validator import MechanismCheckResult
from knowledge_curator.schemas.assertions import Assertion, Condition


class InMemoryKnowledgeRepository:
    """In-memory KnowledgeRepository adapter (no SQLite/FAISS/HTTP)."""

    def __init__(self, seed: Optional[list[Assertion]] = None) -> None:
        self._store: list[Assertion] = list(seed or [])
        self._commit_counter = 0

    def find_assertions(
        self,
        subject: str,
        property_name: str,
        ref_id_exclude: Optional[str] = None,
    ) -> list[Assertion]:
        """Return stored assertions matching subject+property."""
        results: list[Assertion] = []
        for item in self._store:
            if item.subject.resolved_entity != subject:
                continue
            if item.property != property_name:
                continue
            if ref_id_exclude is not None and item.ref_id == ref_id_exclude:
                continue
            results.append(item)
        return results

    def commit_assertions(self, assertions: list[Assertion]) -> str:
        """Append assertions to the in-memory store; return snapshot id."""
        self._store.extend(assertions)
        self._commit_counter += 1
        return f"mem-snapshot-{self._commit_counter:04d}"

    def all_assertions(self) -> list[Assertion]:
        """Return a copy of every stored assertion."""
        return list(self._store)


class FakeMechanismValidator:
    """Fake MechanismValidator used in unit tests (not real L3)."""

    def __init__(
        self,
        violated_ids: Optional[list[str]] = None,
        ok: bool = True,
        messages: Optional[list[str]] = None,
    ) -> None:
        self._violated_ids = list(violated_ids or [])
        self._ok = ok
        self._messages = list(messages or [])
        self.calls: list[list[str]] = []

    def check(self, claims: list[Assertion]) -> MechanismCheckResult:
        """Return a preconfigured mechanism check result."""
        self.calls.append([c.id for c in claims])
        if self._ok and not self._violated_ids:
            return MechanismCheckResult(ok=True)
        violated = [c.id for c in claims if c.id in self._violated_ids] or [
            c.id for c in claims
        ]
        return MechanismCheckResult(
            ok=False,
            violated_assertion_ids=violated,
            messages=self._messages or ["mechanism violation (fake)"],
        )


class SimpleOntologyService:
    """Deterministic OntologyService stub for Phase 1.

    Full EDDO normalization belongs to 02; this stub only implements the
    condition-compatibility rule required by §5.2 (different conditions are
    not numeric conflicts).
    """

    def normalize_entity(self, mention: str, eddo_class: str) -> Optional[str]:
        """Return a naive stable id; real resolution is out of scope."""
        if not mention:
            return None
        return f"eddo:{eddo_class.lower()}:{mention.strip().lower().replace(' ', '_')}"

    def normalize_condition(self, condition: Condition) -> Optional[Condition]:
        """Pass conditions through unchanged (no unit conversion in Phase 1)."""
        return condition

    def are_conditions_compatible(
        self,
        left: list[Condition],
        right: list[Condition],
    ) -> bool:
        """True only when condition bindings match on class and value.

        Different temperature / concentration / membrane-type values mean
        different operating domains (docs/03 §5.2 condition_difference).
        """
        left_map = {c.eddo_class.lower(): c for c in left}
        right_map = {c.eddo_class.lower(): c for c in right}
        if set(left_map) != set(right_map):
            return False
        for key, lc in left_map.items():
            rc = right_map[key]
            if not self._values_compatible(lc.value, rc.value, lc.unit, rc.unit):
                return False
        return True

    @staticmethod
    def _values_compatible(v1: object, v2: object, u1: Optional[str], u2: Optional[str]) -> bool:
        if u1 != u2:
            # Phase 1: treat differing units as incompatible domains (no blind convert).
            return False
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            return abs(float(v1) - float(v2)) <= 1e-9
        return str(v1).strip().lower() == str(v2).strip().lower()
