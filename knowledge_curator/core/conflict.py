"""Conflict detection (docs/03 §5.2). Deterministic rules + MechanismValidator port."""

from __future__ import annotations

from typing import Optional

from knowledge_curator.config import ConflictConfig, DEFAULT_CONFIG
from knowledge_curator.ports.knowledge_repository import KnowledgeRepository
from knowledge_curator.ports.mechanism_validator import MechanismValidator
from knowledge_curator.ports.ontology_service import OntologyService
from knowledge_curator.schemas.assertions import Assertion, ValueType
from knowledge_curator.schemas.curation import ConflictFinding, ConflictType


def detect_conflicts(
    assertion_set_assertions: list[Assertion],
    repository: KnowledgeRepository,
    ontology: OntologyService,
    mechanism_validator: Optional[MechanismValidator] = None,
    config: ConflictConfig | None = None,
    *,
    run_mechanism_check: bool = True,
) -> list[ConflictFinding]:
    """Compare new assertions against existing graph assertions.

    Rules (docs/03 §5.2):
      * Same subject+property → look up existing assertions.
      * Different conditions → condition_difference (never numeric_conflict).
      * Same conditions + overlapping intervals/tolerance → consistent.
      * Same conditions + non-overlapping intervals → numeric_conflict.
      * Opposite bool/enum values → relation_conflict.
      * L3 hard-rule violation via MechanismValidator port.

    Args:
        assertion_set_assertions: New assertions from the current document.
        repository: Port for querying existing graph assertions.
        ontology: Port for condition-domain compatibility.
        mechanism_validator: Optional L3 mechanism validator port.
        config: Numeric comparison tolerance configuration.
        run_mechanism_check: Whether to invoke the mechanism validator.

    Returns:
        List of ConflictFinding records (may be empty).
    """
    cfg = config or DEFAULT_CONFIG.conflict
    findings: list[ConflictFinding] = []

    for assertion in assertion_set_assertions:
        existing = repository.find_assertions(
            subject=assertion.subject.resolved_entity,
            property_name=assertion.property,
            ref_id_exclude=assertion.ref_id,
        )
        for other in existing:
            finding = compare_pair(assertion, other, ontology, cfg)
            if finding is not None and finding.conflict_type != ConflictType.NONE:
                findings.append(finding)

    if run_mechanism_check and mechanism_validator is not None and assertion_set_assertions:
        result = mechanism_validator.check(assertion_set_assertions)
        if not result.ok:
            violated = set(result.violated_assertion_ids) or {
                a.id for a in assertion_set_assertions
            }
            for aid in violated:
                findings.append(
                    ConflictFinding(
                        conflict_type=ConflictType.MECHANISM_VIOLATION,
                        new_assertion_id=aid,
                        message="; ".join(result.messages) or "mechanism violation",
                        detail=dict(result.detail),
                    )
                )

    return findings


def compare_pair(
    new: Assertion,
    existing: Assertion,
    ontology: OntologyService,
    config: ConflictConfig,
) -> Optional[ConflictFinding]:
    """Compare one new assertion with one existing assertion.

    Returns a ConflictFinding, or None when the pair is unopposed
    (including empty/none comparisons).
    """
    # Relation / enum / bool opposite → relation_conflict
    if new.object.value_type in (ValueType.ENUM, ValueType.TEXT) or existing.object.value_type in (
        ValueType.ENUM,
        ValueType.TEXT,
    ):
        return _compare_relation(new, existing)

    if new.object.value_type == ValueType.FORMULA or existing.object.value_type == ValueType.FORMULA:
        return None

    # Numeric / range comparison
    # Critical rule: different operating conditions are NOT numeric conflicts.
    if not ontology.are_conditions_compatible(new.conditions, existing.conditions):
        return ConflictFinding(
            conflict_type=ConflictType.CONDITION_DIFFERENCE,
            new_assertion_id=new.id,
            existing_assertion_id=existing.id,
            message="values differ under different operating conditions",
            detail={
                "new_conditions": _conditions_repr(new.conditions),
                "existing_conditions": _conditions_repr(existing.conditions),
            },
        )

    new_interval = new.numeric_interval()
    existing_interval = existing.numeric_interval()
    if new_interval is None or existing_interval is None:
        return ConflictFinding(
            conflict_type=ConflictType.NONE,
            new_assertion_id=new.id,
            existing_assertion_id=existing.id,
            message="non-comparable numeric payloads",
        )

    if _intervals_compatible(new_interval, existing_interval, config):
        return ConflictFinding(
            conflict_type=ConflictType.CONSISTENT,
            new_assertion_id=new.id,
            existing_assertion_id=existing.id,
            message="numeric values overlap within tolerance",
            detail={
                "new_interval": list(new_interval),
                "existing_interval": list(existing_interval),
            },
        )

    return ConflictFinding(
        conflict_type=ConflictType.NUMERIC_CONFLICT,
        new_assertion_id=new.id,
        existing_assertion_id=existing.id,
        message="same operating domain but numeric intervals do not overlap",
        detail={
            "new_interval": list(new_interval),
            "existing_interval": list(existing_interval),
        },
    )


def _compare_relation(new: Assertion, existing: Assertion) -> Optional[ConflictFinding]:
    same = _scalar_equal(new.object.value, existing.object.value)
    if same:
        return ConflictFinding(
            conflict_type=ConflictType.CONSISTENT,
            new_assertion_id=new.id,
            existing_assertion_id=existing.id,
            message="relation/enum values agree",
        )
    return ConflictFinding(
        conflict_type=ConflictType.RELATION_CONFLICT,
        new_assertion_id=new.id,
        existing_assertion_id=existing.id,
        message="relation/enum values contradict",
        detail={"new_value": new.object.value, "existing_value": existing.object.value},
    )


def _scalar_equal(v1: object, v2: object) -> bool:
    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
        return abs(float(v1) - float(v2)) <= 1e-12
    return str(v1).strip().lower() == str(v2).strip().lower()


def _intervals_compatible(
    left: tuple[float, float],
    right: tuple[float, float],
    config: ConflictConfig,
) -> bool:
    """True when intervals overlap or endpoints are within tolerance."""
    l_lo, l_hi = left
    r_lo, r_hi = right
    # Expand both intervals by relative/absolute tolerance
    def expand(lo: float, hi: float) -> tuple[float, float]:
        span = max(abs(lo), abs(hi), 1.0)
        pad = max(config.relative_tolerance * span, config.absolute_tolerance)
        return (lo - pad, hi + pad)

    el_lo, el_hi = expand(l_lo, l_hi)
    er_lo, er_hi = expand(r_lo, r_hi)
    return el_lo <= er_hi and er_lo <= el_hi


def _conditions_repr(conditions: list) -> list[dict]:
    return [
        {"eddo_class": c.eddo_class, "value": c.value, "unit": c.unit}
        for c in conditions
    ]
