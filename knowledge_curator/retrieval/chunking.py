"""§6.1 deterministic chunking with canonical payload prefix (Phase 4.1.1).

Fine chunk payload ALWAYS starts with [ref_id|page|section|type(类型)].
Text token budget includes prefix. Overlap only applies to body tokens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from knowledge_curator.retrieval.tokenizer import (
    TokenizerPort,
    WordTokenizer,
    build_metadata_prefix,
    stable_chunk_id,
)
from knowledge_curator.schemas.assertions import Assertion
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk


@dataclass
class ChunkingConfig:
    max_tokens: int = 512
    overlap_tokens: int = 64


@dataclass
class TableObject:
    table_id: str
    ref_id: str
    caption: str = ""
    headers: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)
    row_summary: str = ""
    page: Optional[str] = None
    section: Optional[str] = None


@dataclass
class ChartObject:
    chart_id: str
    ref_id: str
    caption: str = ""
    axes: str = ""
    units: str = ""
    digitized_summary: str = ""
    page: Optional[str] = None
    section: Optional[str] = None


def _type_label(chunk_type: ChunkType) -> str:
    return {
        ChunkType.TEXT: "text",
        ChunkType.TABLE: "table",
        ChunkType.CHART: "chart",
        ChunkType.EVIDENCE_CARD: "evidence_card",
        ChunkType.DOCUMENT_SUMMARY: "summary",
    }[chunk_type]


def chunk_text(
    text: str,
    *,
    ref_id: str,
    section: Optional[str] = None,
    page: Optional[str] = None,
    tokenizer: Optional[TokenizerPort] = None,
    config: Optional[ChunkingConfig] = None,
) -> list[KnowledgeChunk]:
    """Split text into section-aware chunks with canonical prefix embedded in payload.

    Requirements:
      * payload starts with [ref_id|page|section|type(文本)]
      * total payload token count <= max_tokens
      * body overlap = overlap_tokens (prefix not counted in overlap)
      * empty text -> no chunks
      * prefix >= max_tokens -> fail clearly
      * stable collision-free chunk_ids
    """
    tok = tokenizer or WordTokenizer()
    cfg = config or ChunkingConfig()
    if not text or not text.strip():
        return []

    prefix = build_metadata_prefix(ref_id, page, section, "text")
    prefix_tokens = tok.encode(prefix)
    if len(prefix_tokens) >= cfg.max_tokens:
        raise ValueError(
            f"metadata prefix token count ({len(prefix_tokens)}) >= max_tokens ({cfg.max_tokens})"
        )

    body_budget = cfg.max_tokens - len(prefix_tokens)
    overlap = cfg.overlap_tokens
    if overlap >= body_budget:
        overlap = max(0, body_budget - 1)

    body_tokens = tok.encode(text)
    if not body_tokens:
        return []

    chunks: list[KnowledgeChunk] = []
    start = 0
    idx = 0
    n = len(body_tokens)
    while start < n:
        end = min(start + body_budget, n)
        window = body_tokens[start:end]
        body_text = tok.decode(window)
        full_payload = f"{prefix} {body_text}"
        chunk_id = stable_chunk_id(ref_id, page, section, f"text:{idx}", tok.decode(window))
        chunks.append(
            KnowledgeChunk(
                chunk_id=chunk_id,
                ref_id=ref_id,
                level=ChunkLevel.FINE,
                chunk_type=ChunkType.TEXT,
                payload=full_payload,
                page=page,
                section=section,
                locator=section or page,
            )
        )
        idx += 1
        if end >= n:
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


def chunk_table(table: TableObject) -> list[KnowledgeChunk]:
    """One table = one chunk with canonical prefix."""
    prefix = build_metadata_prefix(table.ref_id, table.page, table.section, "table")
    parts = []
    if table.caption:
        parts.append(f"Caption: {table.caption}")
    if table.headers:
        parts.append(f"Headers: {', '.join(table.headers)}")
    if table.units:
        parts.append(f"Units: {', '.join(table.units)}")
    if table.row_summary:
        parts.append(f"Rows: {table.row_summary}")
    body = "\n".join(parts) if parts else f"Table {table.table_id}"
    payload = f"{prefix} {body}"
    return [
        KnowledgeChunk(
            chunk_id=stable_chunk_id(table.ref_id, table.page, table.section, f"table:{table.table_id}", body),
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
    """One ChartObject = one chunk with canonical prefix."""
    prefix = build_metadata_prefix(chart.ref_id, chart.page, chart.section, "chart")
    parts = []
    if chart.caption:
        parts.append(f"Caption: {chart.caption}")
    if chart.axes:
        parts.append(f"Axes: {chart.axes}")
    if chart.units:
        parts.append(f"Units: {chart.units}")
    if chart.digitized_summary:
        parts.append(f"Summary: {chart.digitized_summary}")
    body = "\n".join(parts) if parts else f"Chart {chart.chart_id}"
    payload = f"{prefix} {body}"
    return [
        KnowledgeChunk(
            chunk_id=stable_chunk_id(chart.ref_id, chart.page, chart.section, f"chart:{chart.chart_id}", body),
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
    """One Assertion = one evidence-card chunk with canonical prefix."""
    loc = assertion.provenance.locator if assertion.provenance else None
    prefix = build_metadata_prefix(assertion.ref_id, None, loc, "evidence_card")
    lines = [
        f"Subject: {assertion.subject.resolved_entity}",
        f"Property: {assertion.property}",
        f"Value: {assertion.object.value} {assertion.object.unit or ''}".strip(),
    ]
    if assertion.conditions:
        conds = "; ".join(f"{c.eddo_class}={c.value}{c.unit or ''}" for c in assertion.conditions)
        lines.append(f"Conditions: {conds}")
    lines.append(f"Ref: {assertion.ref_id}")
    lines.append(f"Locator: {loc or '-'}")
    lines.append(f"Confidence: {assertion.confidence.value}")
    body = "\n".join(lines)
    payload = f"{prefix} {body}"
    return KnowledgeChunk(
        chunk_id=stable_chunk_id(assertion.ref_id, None, loc, f"evidence:{assertion.id}", body),
        ref_id=assertion.ref_id,
        level=ChunkLevel.FINE,
        chunk_type=ChunkType.EVIDENCE_CARD,
        payload=payload,
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
    """Coarse DOCUMENT_SUMMARY wrapping upstream summary only (no LLM)."""
    return [
        KnowledgeChunk(
            chunk_id=stable_chunk_id(ref_id, page, None, "summary", summary),
            ref_id=ref_id,
            level=ChunkLevel.COARSE,
            chunk_type=ChunkType.DOCUMENT_SUMMARY,
            payload=summary,
            page=page,
        )
    ]
