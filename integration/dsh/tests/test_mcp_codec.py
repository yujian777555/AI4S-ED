"""Codec tests for AssertionSet/CurationReport JSON translation."""

from __future__ import annotations

import pytest

from knowledge_curator.mcp_server.codec import (
    CodecError,
    parse_assertion_set,
    serialize_curation_report,
)
from knowledge_curator.tests.conftest import make_assertion, make_assertion_set


def _sample_payload() -> dict:
    return {
        "ref_id": "ED-2025-0042",
        "metadata": {
            "title": "Test Paper",
            "authors": ["A. Author"],
            "year": 2024,
            "source": "Journal",
            "doi": "10.0000/test",
            "stable_id": "ST-001",
        },
        "quality_grade": "B",
        "assertions": [
            {
                "id": "AS-001",
                "ref_id": "ED-2025-0042",
                "subject": {
                    "eddo_class": "Membrane",
                    "resolved_entity": "eddo:membrane:nafion117",
                    "original_mention": "Nafion 117",
                },
                "property": "hasEnergyConsumption",
                "object": {
                    "value": 1.42,
                    "unit": "kWh/m3",
                    "value_type": "number",
                    "uncertainty": 0.05,
                },
                "conditions": [
                    {"eddo_class": "Temperature", "value": 298.15, "unit": "K"}
                ],
                "provenance": {"locator": "T12", "sentence": "Table 3 row2"},
                "claim_type": "measurement",
                "source_claim_origin": "primary",
                "confidence": "medium",
                "quality": 0.87,
            }
        ],
    }


def test_parse_valid_assertion_set():
    aset = parse_assertion_set(_sample_payload())
    assert aset.ref_id == "ED-2025-0042"
    assert aset.assertions[0].id == "AS-001"
    assert aset.assertions[0].object.unit == "kWh/m3"
    assert aset.assertions[0].provenance.locator == "T12"


def test_reject_malformed_not_object():
    with pytest.raises(CodecError):
        parse_assertion_set(["not-an-object"])  # type: ignore[arg-type]


def test_reject_missing_ref_id():
    payload = _sample_payload()
    del payload["ref_id"]
    with pytest.raises(CodecError):
        parse_assertion_set(payload)


def test_reject_invalid_confidence_enum():
    payload = _sample_payload()
    payload["assertions"][0]["confidence"] = "certainty-1000"
    with pytest.raises(CodecError):
        parse_assertion_set(payload)


def test_reject_invalid_value_type():
    payload = _sample_payload()
    payload["assertions"][0]["object"]["value_type"] = "quantum"
    with pytest.raises(CodecError):
        parse_assertion_set(payload)


def test_reject_invalid_claim_type():
    payload = _sample_payload()
    payload["assertions"][0]["claim_type"] = "gossip"
    with pytest.raises(CodecError):
        parse_assertion_set(payload)


def test_missing_locator_kept_absent_not_filled():
    payload = _sample_payload()
    payload["assertions"][0]["provenance"] = {"sentence": "no locator"}
    aset = parse_assertion_set(payload)
    assert aset.assertions[0].provenance is None


def test_serialize_report_has_business_fields():
    from knowledge_curator.adapters import FakeMechanismValidator, InMemoryKnowledgeRepository, SimpleOntologyService
    from knowledge_curator.core.curator import KnowledgeCurator
    import asyncio

    aset = make_assertion_set([make_assertion("AS-1")])
    report = asyncio.run(
        KnowledgeCurator(
            repository=InMemoryKnowledgeRepository(),
            ontology=SimpleOntologyService(),
            mechanism_validator=FakeMechanismValidator(),
        ).curate(aset)
    )
    payload = serialize_curation_report(report)
    for key in (
        "status",
        "completeness",
        "conflicts",
        "decisions",
        "quality",
        "warnings",
    ):
        assert key in payload
    assert payload["decisions"][0]["action"] in {
        "accept",
        "downgrade",
        "pending_review",
        "supersede",
        "reject",
        "return_upstream",
    }
    assert payload["decisions"][0]["confidence"] in {
        "verified",
        "high",
        "medium",
        "hypothesis",
    }
