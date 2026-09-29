"""Chunk compatibility models for §6.1 (temporary compatibility model).

Phase 4.1.1: payload itself carries the canonical metadata prefix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from knowledge_curator.schemas.assertions import Confidence


class ChunkLevel(str, Enum):
    COARSE = "coarse"
    FINE = "fine"


class ChunkType(str, Enum):
    DOCUMENT_SUMMARY = "document_summary"
    TEXT = "text"
    TABLE = "table"
    CHART = "chart"
    EVIDENCE_CARD = "evidence_card"


@dataclass
class KnowledgeChunk:
    """One retrieval chunk with provenance (temporary compatibility model).

    payload must start with canonical prefix for fine chunks:
    [ref_id|page|section|type(类型)]
    """

    chunk_id: str
    ref_id: str
    level: ChunkLevel
    chunk_type: ChunkType
    payload: str
    page: Optional[str] = None
    section: Optional[str] = None
    object_id: Optional[str] = None
    locator: Optional[str] = None
    assertion_id: Optional[str] = None
    confidence: Optional[Confidence] = None
    quality: Optional[float] = None
    provenance: dict[str, Any] = field(default_factory=dict)
