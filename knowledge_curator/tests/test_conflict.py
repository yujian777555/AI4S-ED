"""Conflict detection tests (docs/03 §5.2)."""

from __future__ import annotations

from knowledge_curator.adapters import (
    FakeMechanismValidator,
    InMemoryKnowledgeRepository,
    SimpleOntologyService,
)
from knowledge_curator.core.conflict import detect_conflicts
from knowledge_curator.schemas.assertions import Condition, ValueType
from knowledge_curator.schemas.curation import ConflictType
from knowledge_curator.tests.conftest import make_assertion


def _repo_with(*items):
    return InMemoryKnowledgeRepository(seed=list(items))


def test_t06_same_conditions_overlapping_intervals_is_consistent():
    """T06: same conditions, overlapping numeric intervals -> consistent."""
    existing = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=1.40,
        uncertainty=0.10,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
    )
    new = make_assertion(
        "AS-NEW",
        value=1.45,
        uncertainty=0.10,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
    )
    findings = detect_conflicts(
        [new],
        repository=_repo_with(existing),
        ontology=SimpleOntologyService(),
        mechanism_validator=FakeMechanismValidator(),
        run_mechanism_check=False,
    )
    types = [f.conflict_type for f in findings]
    assert ConflictType.CONSISTENT in types
    assert ConflictType.NUMERIC_CONFLICT not in types


def test_t07_different_conditions_is_condition_difference_not_numeric_conflict():
    """T07: different temperature -> condition_difference, NOT numeric_conflict."""
    existing = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=1.40,
        uncertainty=0.0,
        conditions=[Condition(eddo_class="Temperature", value=298.15, unit="K")],
    )
    new = make_assertion(
        "AS-NEW",
        value=3.20,
        uncertainty=0.0,
        conditions=[Condition(eddo_class="Temperature", value=333.15, unit="K")],
    )
    findings = detect_conflicts(
        [new],
        repository=_repo_with(existing),
        ontology=SimpleOntologyService(),
        mechanism_validator=FakeMechanismValidator(),
        run_mechanism_check=False,
    )
    types = [f.conflict_type for f in findings]
    assert ConflictType.CONDITION_DIFFERENCE in types
    assert ConflictType.NUMERIC_CONFLICT not in types


def test_t08_same_conditions_non_overlapping_is_numeric_conflict():
    """T08: same conditions, intervals completely disjoint -> numeric_conflict."""
    existing = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=0.4,
        uncertainty=0.05,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
    )
    new = make_assertion(
        "AS-NEW",
        value=3.0,
        uncertainty=0.05,
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
    )
    findings = detect_conflicts(
        [new],
        repository=_repo_with(existing),
        ontology=SimpleOntologyService(),
        mechanism_validator=FakeMechanismValidator(),
        run_mechanism_check=False,
    )
    types = [f.conflict_type for f in findings]
    assert ConflictType.NUMERIC_CONFLICT in types
    assert ConflictType.CONDITION_DIFFERENCE not in types


def test_t09_mechanism_violation_via_port():
    """T09: FakeMechanismValidator reports violation -> mechanism_violation."""
    new = make_assertion("AS-M1")
    fake = FakeMechanismValidator(violated_ids=["AS-M1"], ok=False, messages=["efficiency > 100%"])
    findings = detect_conflicts(
        [new],
        repository=InMemoryKnowledgeRepository(),
        ontology=SimpleOntologyService(),
        mechanism_validator=fake,
        run_mechanism_check=True,
    )
    types = [f.conflict_type for f in findings]
    assert ConflictType.MECHANISM_VIOLATION in types
    assert any(f.new_assertion_id == "AS-M1" for f in findings)
    assert fake.calls and fake.calls[0] == ["AS-M1"]


def test_relation_conflict_on_opposite_bool_enum():
    existing = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value="yes",
        unit=None,
        value_type=ValueType.ENUM,
        uncertainty=None,
    )
    new = make_assertion(
        "AS-NEW",
        value="no",
        unit=None,
        value_type=ValueType.ENUM,
        uncertainty=None,
    )
    findings = detect_conflicts(
        [new],
        repository=_repo_with(existing),
        ontology=SimpleOntologyService(),
        mechanism_validator=FakeMechanismValidator(),
        run_mechanism_check=False,
    )
    types = [f.conflict_type for f in findings]
    assert ConflictType.RELATION_CONFLICT in types


def test_no_existing_assertions_yields_none_or_empty():
    new = make_assertion("AS-SOLO")
    findings = detect_conflicts(
        [new],
        repository=InMemoryKnowledgeRepository(),
        ontology=SimpleOntologyService(),
        mechanism_validator=FakeMechanismValidator(),
        run_mechanism_check=False,
    )
    assert findings == [] or all(f.conflict_type == ConflictType.NONE for f in findings)
