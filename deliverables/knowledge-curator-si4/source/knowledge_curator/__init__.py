"""knowledge_curator — AI4S-ED L4 curation agent (Phase 1 core).

Pipeline: AssertionSet -> completeness -> conflict -> quality -> decision
          -> CurationReport

Runtime-independent. Core must not import DSH / SQLite / FAISS / HTTP.
"""

from knowledge_curator.config import CuratorConfig, DEFAULT_CONFIG
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
from knowledge_curator.schemas.curation import (
    AssertionDecision,
    CompletenessResult,
    CompletenessStatus,
    ConflictFinding,
    ConflictType,
    CurationAction,
    CurationReport,
    QualityBreakdown,
)

__all__ = [
    "Assertion",
    "AssertionDecision",
    "AssertionSet",
    "ChartObjectInfo",
    "ClaimType",
    "CompletenessResult",
    "CompletenessStatus",
    "Condition",
    "Confidence",
    "ConflictFinding",
    "ConflictType",
    "CuratorConfig",
    "CurationAction",
    "CurationReport",
    "DEFAULT_CONFIG",
    "DocumentMetadata",
    "KnowledgeCurator",
    "ObjectValue",
    "Provenance",
    "QualityBreakdown",
    "QualityGrade",
    "SourceClaimOrigin",
    "Subject",
    "ValueType",
]

__version__ = "0.1.0-phase1"
