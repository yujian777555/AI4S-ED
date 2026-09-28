"""Assertion / AssertionSet temporary compatibility models.

temporary compatibility model
This module is NOT the frozen cross-team public schema.
Field names and semantics follow docs/03 §4.1 / §4.2 until Schema Registry (02/08)
freezes the official AssertionSet contract. See planner/CONTRACT_GAPS.md (CG-002).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Confidence(str, Enum):
    """Unified project-wide confidence ladder. Do not extend."""

    VERIFIED = "verified"
    HIGH = "high"
    MEDIUM = "medium"
    HYPOTHESIS = "hypothesis"


class ValueType(str, Enum):
    NUMBER = "number"
    RANGE = "range"
    ENUM = "enum"
    TEXT = "text"
    FORMULA = "formula"


class ClaimType(str, Enum):
    MEASUREMENT = "measurement"
    RELATION = "relation"
    METHOD = "method"
    RULE = "rule"
    MECHANISM = "mechanism"


class SourceClaimOrigin(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class QualityGrade(str, Enum):
    """ParsedDoc processing quality grade from docs/03 §3.7."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


@dataclass
class Subject:
    """EDDO-resolved assertion subject."""

    eddo_class: str
    resolved_entity: str
    original_mention: str


@dataclass
class ObjectValue:
    """Assertion object payload (value/unit/value_type)."""

    value: Any
    unit: Optional[str]
    value_type: ValueType
    uncertainty: Optional[float] = None


@dataclass
class Condition:
    """Operating-condition binding (temperature, concentration, ...)."""

    eddo_class: str
    value: Any
    unit: Optional[str] = None


@dataclass
class Provenance:
    """Source locator for an assertion (page / table / chart id)."""

    locator: str
    sentence: Optional[str] = None


@dataclass
class Assertion:
    """One extracted scientific claim (temporary compatibility model)."""

    id: str
    ref_id: str
    subject: Subject
    property: str
    object: ObjectValue
    conditions: list[Condition] = field(default_factory=list)
    provenance: Optional[Provenance] = None
    claim_type: ClaimType = ClaimType.MEASUREMENT
    source_claim_origin: SourceClaimOrigin = SourceClaimOrigin.PRIMARY
    confidence: Confidence = Confidence.MEDIUM
    quality: float = 0.5
    # Upstream quality flags (optional, compatibility with §4.2 downgrade table)
    missing_unit: bool = False
    speculative_wording: bool = False
    chart_quality_low: bool = False

    @property
    def is_numeric(self) -> bool:
        """True when the object carries a numeric or range payload."""
        return self.object.value_type in (ValueType.NUMBER, ValueType.RANGE)

    @property
    def has_locator(self) -> bool:
        """True when provenance locator is present and non-empty."""
        return self.provenance is not None and bool(self.provenance.locator)

    def numeric_interval(self) -> Optional[tuple[float, float]]:
        """Return (low, high) numeric interval, or None if not numeric."""
        if self.object.value_type == ValueType.NUMBER:
            try:
                v = float(self.object.value)
            except (TypeError, ValueError):
                return None
            unc = self.object.uncertainty or 0.0
            return (v - abs(unc), v + abs(unc))
        if self.object.value_type == ValueType.RANGE:
            raw = self.object.value
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                try:
                    lo, hi = float(raw[0]), float(raw[1])
                except (TypeError, ValueError):
                    return None
                return (min(lo, hi), max(lo, hi))
        return None


@dataclass
class ChartObjectInfo:
    """Minimal ChartObject compatibility fields used by completeness checks."""

    id: str
    caption_complete: bool = True
    axes_complete: bool = True
    units_complete: bool = True
    not_digitizable: bool = False
    quality_low: bool = False


@dataclass
class DocumentMetadata:
    """Document-level metadata required by docs/03 §5.1 completeness gate."""

    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    source: str = ""
    doi: Optional[str] = None
    stable_id: Optional[str] = None


@dataclass
class AssertionSet:
    """Batch of assertions extracted from one document.

    temporary compatibility model — not the frozen public schema.
    """

    ref_id: str
    metadata: DocumentMetadata
    assertions: list[Assertion] = field(default_factory=list)
    quality_grade: QualityGrade = QualityGrade.B
    charts: list[ChartObjectInfo] = field(default_factory=list)
    # Explicit declaration that the source has no structured extractable data
    no_structured_data: bool = False
    # Schema validation: how many assertions passed first-pass JSON schema check
    schema_valid_count: Optional[int] = None
    schema_total_count: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)
