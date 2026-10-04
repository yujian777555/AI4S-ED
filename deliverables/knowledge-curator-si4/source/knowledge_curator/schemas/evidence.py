"""Evidence / anchor compatibility models for §6 (temporary compatibility model).

Not the frozen cross-team public schema. Maps to docs/03 §6 evidence types:
  literature=文献, graph=图谱, simulation=仿真, experiment=实验
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from knowledge_curator.schemas.assertions import Confidence


class EvidenceType(str, Enum):
    """docs/03 §6 evidence types (English wire values)."""

    LITERATURE = "literature"  # 文献
    GRAPH = "graph"  # 图谱
    SIMULATION = "simulation"  # 仿真
    EXPERIMENT = "experiment"  # 实验


@dataclass
class EvidenceAnchor:
    """Anchor tuple: evidence type + ref_id + locator + confidence."""

    evidence_type: EvidenceType
    ref_id: str
    locator: str
    confidence: Confidence
    quality: Optional[float] = None
    access_pointer: Optional[str] = None


@dataclass
class EvidenceRecord:
    """Evidence hit with bounded summary and §6.2 provenance fields."""

    anchor: EvidenceAnchor
    claim_id: Optional[str] = None
    summary: str = ""
    score: Optional[float] = None
    page_or_object_id: Optional[str] = None
    sentence_or_cell: Optional[str] = None


@dataclass
class Claim:
    """Internal claim for guard evaluation (not a final answer)."""

    claim_id: str
    text: str
    anchors: list[EvidenceAnchor] = field(default_factory=list)
    is_numeric: bool = False
    numeric_value: Optional[float] = None
    numeric_unit: Optional[str] = None
    coverage_key: Optional[str] = None


class SurfacePolicy(str, Enum):
    """How a claim may be surfaced based on confidence gate."""

    FACTUAL_ALLOWED = "factual_allowed"
    CAVEATED_ONLY = "caveated_only"
    PENDING_HYPOTHESIS_ONLY = "pending_hypothesis_only"
    CONFLICT_DISCLOSURE_REQUIRED = "conflict_disclosure_required"
    ABSTAIN = "abstain"


@dataclass
class ClaimPolicy:
    """Deterministic confidence-gate policy for one claim."""

    claim_id: str
    policy: SurfacePolicy
    effective_confidence: Optional[Confidence]
    reasons: list[str] = field(default_factory=list)
