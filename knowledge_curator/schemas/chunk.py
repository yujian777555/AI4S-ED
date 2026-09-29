"""Chunk compatibility models for §6.1 (temporary compatibility model).

Not the frozen cross-team public schema. Maps to docs/03 §6.1 chunk types.
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
    DOCUMENT_SUMMARY = "document_summary"  # coarse
    TEXT = "text"  # 文本
    TABLE = "table"  # 表
    CHART = "chart"  # 图
    EVIDENCE_CARD = "evidence_card"  # 证据卡


@dataclass
class KnowledgeChunk:
    """One retrieval chunk with provenance (temporary compatibility model)."""

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

    def metadata_prefix(self) -> str:
        """docs/03 §6.1 metadata prefix: [ref_id|page|section|type(...)]"""
        type_label = {
            ChunkType.TEXT: "text",
            ChunkType.TABLE: "table",
            ChunkType.CHART: "chart",
            ChunkType.EVIDENCE_CARD: "evidence_card",
            ChunkType.DOCUMENT_SUMMARY: "summary",
        }[self.chunk_type]
        return f"[{self.ref_id}|{self.page or '-'}|{self.section or '-'}|{type_label}]"

    def prefixed_payload(self) -> str:
        """Fine chunk payload must include the metadata prefix."""
        return f"{self.metadata_prefix()} {self.payload}"
