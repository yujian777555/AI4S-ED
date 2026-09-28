"""Shared test fixtures and helpers for knowledge_curator Phase 1 tests."""

from __future__ import annotations

from knowledge_curator.adapters import (
    FakeMechanismValidator,
    InMemoryKnowledgeRepository,
    SimpleOntologyService,
)
from knowledge_curator.config import CuratorConfig
from knowledge_curator.core.curator import KnowledgeCurator
from knowledge_curator.schemas.assertions import (
    Assertion,
    AssertionSet,
    ChartObjectInfo,
    ClaimType,
    Condition,
    Confidence,
    DocumentMetadata,
    ObjectValue,
    Provenance,
    QualityGrade,
    SourceClaimOrigin,
    Subject,
    ValueType,
)


def make_meta(
    *,
    title: str = "Test Paper",
    authors: list[str] | None = None,
    year: int = 2024,
    source: str = "Journal of Testing",
    doi: str | None = "10.0000/test",
    stable_id: str | None = "ST-001",
) -> DocumentMetadata:
    return DocumentMetadata(
        title=title,
        authors=authors if authors is not None else ["A. Author"],
        year=year,
        source=source,
        doi=doi,
        stable_id=stable_id,
    )


def make_assertion(
    aid: str = "AS-001",
    *,
    subject: str = "eddo:membrane:nafion117",
    property_name: str = "hasEnergyConsumption",
    value=1.42,
    unit: str | None = "kWh/m3",
    value_type: ValueType = ValueType.NUMBER,
    uncertainty: float | None = 0.05,
    conditions: list[Condition] | None = None,
    locator: str | None = "T12",
    claim_type: ClaimType = ClaimType.MEASUREMENT,
    origin: SourceClaimOrigin = SourceClaimOrigin.PRIMARY,
    confidence: Confidence = Confidence.MEDIUM,
    quality: float = 0.85,
    ref_id: str = "ED-2025-0042",
    missing_unit: bool = False,
    speculative_wording: bool = False,
) -> Assertion:
    return Assertion(
        id=aid,
        ref_id=ref_id,
        subject=Subject(
            eddo_class="Membrane",
            resolved_entity=subject,
            original_mention="Nafion 117",
        ),
        property=property_name,
        object=ObjectValue(
            value=value,
            unit=unit,
            value_type=value_type,
            uncertainty=uncertainty,
        ),
        conditions=list(conditions) if conditions is not None else [
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
            Condition(eddo_class="FeedNaCl", value=0.05, unit="mol/L"),
        ],
        provenance=Provenance(locator=locator) if locator else None,
        claim_type=claim_type,
        source_claim_origin=origin,
        confidence=confidence,
        quality=quality,
        missing_unit=missing_unit,
        speculative_wording=speculative_wording,
    )


def make_assertion_set(
    assertions: list[Assertion] | None = None,
    *,
    ref_id: str = "ED-2025-0042",
    metadata: DocumentMetadata | None = None,
    quality_grade: QualityGrade = QualityGrade.B,
    charts: list[ChartObjectInfo] | None = None,
    no_structured_data: bool = False,
    schema_valid_count: int | None = None,
    schema_total_count: int | None = None,
) -> AssertionSet:
    return AssertionSet(
        ref_id=ref_id,
        metadata=metadata or make_meta(),
        assertions=list(assertions) if assertions is not None else [make_assertion()],
        quality_grade=quality_grade,
        charts=list(charts or []),
        no_structured_data=no_structured_data,
        schema_valid_count=schema_valid_count,
        schema_total_count=schema_total_count,
    )


def make_curator(
    *,
    seed: list[Assertion] | None = None,
    mechanism: FakeMechanismValidator | None = None,
    config: CuratorConfig | None = None,
) -> KnowledgeCurator:
    return KnowledgeCurator(
        repository=InMemoryKnowledgeRepository(seed=seed),
        ontology=SimpleOntologyService(),
        mechanism_validator=mechanism or FakeMechanismValidator(),
        config=config,
    )
