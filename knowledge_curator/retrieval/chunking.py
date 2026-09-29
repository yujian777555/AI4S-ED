"""§6.1 deterministic chunking (temporary compatibility).

Text: max_tokens=512, overlap=64, section-aware.
Table/Chart: always one chunk per object.
Evidence card: one chunk per Assertion.
Coarse: DOCUMENT_SUMMARY wraps upstream-provided summary only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

from knowledge_curator.schemas.assertions import Assertion
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk


@runtime_checkable
class Tokenizer(Protocol):
    """Injectable tokenizer abstraction (no binding to a specific model)."""

    def count(self, text: str) -> int:
        """Return token count for text."""
        ...

    def split(self, text: str) -> list[str]:
        """Split text into token units (words for deterministic tests)."""
        ...


class WordTokenizer:
    """Deterministic whitespace tokenizer for tests (not a model tokenizer)."""

    def count(self, text: str) -> int:
        return len(text.split()) if text.strip() else 0

    def split(self, text: str) -> list[str]:
        return text.split() if text.strip() else []


@dataclass
class ChunkingConfig:
    max_tokens: int = 512
    overlap_tokens: int = 64


@dataclass
class TableObject:
    """Upstream-parsed table compatibility object (no PDF parsing here)."""

    table_id: str
    ref_id: str
    caption: str = ""
    headers: list[str] = None  # type: ignore[assignment]
    units: list[str] = None  # type: ignore[assignment]
    row_summary: str = ""
    page: Optional[str] = None
    section: Optional[str] = None

    def __post_init__(self) -> None:
        if self.headers is None:
            self.headers = []
        if self.units is None:
            self.units = []


@dataclass
class ChartObject:
    """Upstream ChartObject compatibility (no digitization here)."""

    chart_id: str
    ref_id: str
    caption: str = ""
    axes: str = ""
    units: str = ""
    digitized_summary: str = ""
    page: Optional[str] = None
    section: Optional[str] = None


def chunk_text(
    text: str,
    *,
    ref_id: str,
    section: Optional[str] = None,
    page: Optional[str] = None,
    tokenizer: Optional[Tokenizer] = None,
    config: Optional[ChunkingConfig] = None,
) -> list[KnowledgeChunk]:
    """Split text into section-aware chunks with overlap.

    Requirements:
      * each chunk token count <= max_tokens
      * adjacent chunks in same section overlap by overlap_tokens
      * do not cross section boundaries (caller provides section per call)
      * empty text produces no chunks
      * no infinite loop when overlap >= content length
    """
    tok = tokenizer or WordTokenizer()
    cfg = config or ChunkingConfig()
    if not text or not text.strip():
        return []

    tokens = tok.split(text)
    if not tokens:
        return []

    max_tok = cfg.max_tokens
    overlap = cfg.overlap_tokens
    if overlap >= max_tok:
        overlap = max_tok - 1  # prevent infinite loop

    chunks: list[KnowledgeChunk] = []
    start = 0
    idx = 0
    n = len(tokens)
    while start < n:
        end = min(start + max_tok, n)
        chunk_tokens = tokens[start:end]
        chunk_text_str = " ".join(chunk_tokens)
        chunk_id = f"{ref_id}:text:{idx}"
        chunks.append(
            KnowledgeChunk(
                chunk_id=chunk_id,
                ref_id=ref_id,
                level=ChunkLevel.FINE,
                chunk_type=ChunkType.TEXT,
                payload=chunk_text_str,
                page=page,
                section=section,
                locator=section or page,
            )
        )
        idx += 1
        if end >= n:
            break
        # Advance with overlap
        next_start = end - overlap
        if next_start <= start:
            # Prevent infinite loop when overlap >= content
            next_start = end
        start = next_start

    return chunks


def chunk_table(table: TableObject) -> list[KnowledgeChunk]:
    """One table = one chunk (docs/03 §6.1). Never split by text rules."""
    parts = []
    if table.caption:
        parts.append(f"Caption: {table.caption}")
    if table.headers:
        parts.append(f"Headers: {', '.join(table.headers)}")
    if table.units:
        parts.append(f"Units: {', '.join(table.units)}")
    if table.row_summary:
        parts.append(f"Rows: {table.row_summary}")
    payload = "\n".join(parts) if parts else f"Table {table.table_id}"
    return [
        KnowledgeChunk(
            chunk_id=f"{table.ref_id}:table:{table.table_id}",
            ref_id=table.ref_id,
            level=ChunkLevel.FINE,
            chunk_type=ChunkType.TABLE,
            payload=payload,
            page=table.page,
            section=table.section,
            object_id=table.table_id,
            locator=table.table_id,
        )
    ]


def chunk_chart(chart: ChartObject) -> list[KnowledgeChunk]:
    """One ChartObject = one chunk. No digitization."""
    parts = []
    if chart.caption:
        parts.append(f"Caption: {chart.caption}")
    if chart.axes:
        parts.append(f"Axes: {chart.axes}")
    if chart.units:
        parts.append(f"Units: {chart.units}")
    if chart.digitized_summary:
        parts.append(f"Summary: {chart.digitized_summary}")
    payload = "\n".join(parts) if parts else f"Chart {chart.chart_id}"
    return [
        KnowledgeChunk(
            chunk_id=f"{chart.ref_id}:chart:{chart.chart_id}",
            ref_id=chart.ref_id,
            level=ChunkLevel.FINE,
            chunk_type=ChunkType.CHART,
            payload=payload,
            page=chart.page,
            section=chart.section,
            object_id=chart.chart_id,
            locator=chart.chart_id,
        )
    ]


def chunk_evidence_card(assertion: Assertion) -> KnowledgeChunk:
    """One Assertion = one evidence-card chunk (suitable for claim-level citation)."""
    lines = [
        f"Subject: {assertion.subject.resolved_entity}",
        f"Property: {assertion.property}",
        f"Value: {assertion.object.value} {assertion.object.unit or ''}".strip(),
    ]
    if assertion.conditions:
        conds = "; ".join(f"{c.eddo_class}={c.value}{c.unit or ''}" for c in assertion.conditions)
        lines.append(f"Conditions: {conds}")
    lines.append(f"Ref: {assertion.ref_id}")
    loc = assertion.provenance.locator if assertion.provenance else None
    lines.append(f"Locator: {loc or '-'}")
    lines.append(f"Confidence: {assertion.confidence.value}")
    return KnowledgeChunk(
        chunk_id=f"{assertion.ref_id}:evidence:{assertion.id}",
        ref_id=assertion.ref_id,
        level=ChunkLevel.FINE,
        chunk_type=ChunkType.EVIDENCE_CARD,
        payload="\n".join(lines),
        locator=loc,
        assertion_id=assertion.id,
        confidence=assertion.confidence,
        quality=assertion.quality,
    )


def chunk_document_summary(
    ref_id: str,
    summary: str,
    *,
    page: Optional[str] = None,
) -> list[KnowledgeChunk]:
    """Coarse DOCUMENT_SUMMARY wrapping upstream-provided summary only.

    No LLM call in core.
    """
    return [
        KnowledgeChunk(
            chunk_id=f"{ref_id}:summary",
            ref_id=ref_id,
            level=ChunkLevel.COARSE,
            chunk_type=ChunkType.DOCUMENT_SUMMARY,
            payload=summary,
            page=page,
        )
    ]
