"""Centralized configuration for knowledge_curator Phase 1.

All thresholds, weights and tolerances live here. Core modules must not
embed magic numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QualityWeights:
    """Weights for docs/03 §5.3 quality formula.

    Q(doc) = w1*P_parse + w2*S_schema + w3*E_evidence + w4*N_novelty + w5*penalty
    Defaults follow docs/03 ≈ 0.25 / 0.25 / 0.30 / 0.10 / 0.10.
    """

    w1_p_parse: float = 0.25
    w2_s_schema: float = 0.25
    w3_e_evidence: float = 0.30
    w4_n_novelty: float = 0.10
    w5_penalty: float = 0.10

    def as_tuple(self) -> tuple[float, float, float, float, float]:
        return (
            self.w1_p_parse,
            self.w2_s_schema,
            self.w3_e_evidence,
            self.w4_n_novelty,
            self.w5_penalty,
        )


@dataclass(frozen=True)
class QualityConfig:
    """Component scoring rules for §5.3."""

    weights: QualityWeights = field(default_factory=QualityWeights)
    # P_parse: grade B deducts 20% relative to grade A
    p_parse_a: float = 1.0
    p_parse_b: float = 0.8
    p_parse_c: float = 0.4
    p_parse_d_e: float = 0.0
    # penalty component starts at 1.0; each issue deducts below
    penalty_start: float = 1.0
    penalty_conflict_hang: float = 0.3
    penalty_mechanism_review: float = 0.3
    penalty_chart_low: float = 0.2
    # Low-quality document threshold (docs/03 §5.3: Q < threshold → demote)
    low_quality_threshold: float = 0.5


@dataclass(frozen=True)
class ConflictConfig:
    """Numeric comparison tolerance for §5.2 conflict detection."""

    # Relative tolerance when comparing point values / interval endpoints
    relative_tolerance: float = 0.05
    # Absolute floor so near-zero values still compare sensibly
    absolute_tolerance: float = 1e-9


@dataclass(frozen=True)
class CompletenessConfig:
    """Thresholds for §5.1 completeness checks."""

    require_metadata_fields: tuple[str, ...] = ("title", "authors", "year", "source")
    require_doi_or_stable_id: bool = True
    formal_quality_grades: tuple[str, ...] = ("A", "B")
    manual_quality_grades: tuple[str, ...] = ("C",)
    excluded_quality_grades: tuple[str, ...] = ("D", "E")


@dataclass(frozen=True)
class CuratorConfig:
    """Top-level configuration bundle for KnowledgeCurator."""

    quality: QualityConfig = field(default_factory=QualityConfig)
    conflict: ConflictConfig = field(default_factory=ConflictConfig)
    completeness: CompletenessConfig = field(default_factory=CompletenessConfig)
    # Whether to call MechanismValidator port during conflict detection
    enable_mechanism_check: bool = True


DEFAULT_CONFIG = CuratorConfig()
