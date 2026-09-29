"""§6.1 chunking with full-payload token budget validation (Phase 4.1.2)."""

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


def _build_chunk(
    *,
    chunk_id: str,
    ref_id: str,
    level: ChunkLevel,
    chunk_type: ChunkType,
    prefix: str,
    body: str,
    page: Optional[str],
    section: Optional[str],
    locator: Optional[str],
    object_id: Optional[str] = None,
    assertion_id: Optional[str] = None,
    confidence: Optional[Confidence] = None,
    quality: Optional[float] = None,
) -> KnowledgeChunk:
    payload = f"{prefix} {body}" if body else prefix
    return KnowledgeChunk(
        chunk_id=chunk_id,
        ref_id=ref_id,
        level=level,
        chunk_type=chunk_type,
        payload=payload,
        page=page,
        section=section,
        object_id=object_id,
        locator=locator,
        assertion_id=assertion_id,
        confidence=confidence,
        quality=quality,
    )


def chunk_text(
    text: str,
    *,
    ref_id: str,
    section: Optional[str] = None,
    page: Optional[str] = None,
    tokenizer: Optional[TokenizerPort] = None,
    config: Optional[ChunkingConfig] = None,
) -> list[KnowledgeChunk]:
    """Split text into chunks with full-payload token budget validation.

    Phase 4.1.2: validate tokenizer.count(full_payload) <= max_tokens,
    shrink body deterministically if boundary-sensitive tokenizer overflows.
    """
    tok = tokenizer or WordTokenizer()
    cfg = config or ChunkingConfig()
    if not text or not text.strip():
        return []

    prefix = build_metadata_prefix(ref_id, page, section, "text")
    if tok.count(prefix) >= cfg.max_tokens:
        raise ValueError(
            f"metadata prefix token count ({tok.count(prefix)}) >= max_tokens ({cfg.max_tokens})"
        )

    body_budget = cfg.max_tokens - tok.count(prefix) - 1  # -1 for separator
    overlap = cfg.overlap_tokens
    if overlap >= body_budget:
        overlap = max(0, body_budget - 1)

    # Encode full text losslessly, then window on non-whitespace tokens
    all_tokens = tok.encode(text)
    # Build body as string, then split into word tokens for windowing
    body_words = text.split()
    if not body_words:
        return []

    chunks: list[KnowledgeChunk] = []
    start = 0
    idx = 0
    n = len(body_words)
    while start < n:
        end = min(start + body_budget, n)
        body_text = " ".join(body_words[start:end])
        # Validate full payload token budget; shrink if needed
        full_payload = f"{prefix} {body_text}"
        while tok.count(full_payload) > cfg.max_tokens and end > start + 1:
            end -= 1
            body_text = " ".join(body_words[start:end])
            full_payload = f"{prefix} {body_text}"
        if tok.count(full_payload) > cfg.max_tokens and end == start + 1:
            raise ValueError(
                f"single body word with prefix exceeds max_tokens ({cfg.max_tokens})"
            )

        chunk_id = stable_chunk_id(ref_id, page, section, f"text:{idx}", body_text)
        chunks.append(
            _build_chunk(
                chunk_id=chunk_id,
                ref_id=ref_id,
                level=ChunkLevel.FINE,
                chunk_type=ChunkType.TEXT,
                prefix=prefix,
                body=body_text,
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
    return [
        _build_chunk(
            chunk_id=stable_chunk_id(table.ref_id, table.page, table.section, f"table:{table.table_id}", body),
            ref_id=table.ref_id,
            level=ChunkLevel.FINE,
            chunk_type=ChunkType.TABLE,
            prefix=prefix,
            body=body,
            page=table.page,
            section=table.section,
            locator=table.table_id,
            object_id=table.table_id,
        )
    ]


def chunk_chart(chart: ChartObject) -> list[KnowledgeChunk]:
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
    return [
        _build_chunk(
            chunk_id=stable_chunk_id(chart.ref_id, chart.page, chart.section, f"chart:{chart.chart_id}", body),
            ref_id=chart.ref_id,
            level=ChunkLevel.FINE,
            chunk_type=ChunkType.CHART,
            prefix=prefix,
            body=body,
            page=chart.page,
            section=chart.section,
            locator=chart.chart_id,
            object_id=chart.chart_id,
        )
    ]


def chunk_evidence_card(assertion: Assertion) -> KnowledgeChunk:
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
    return _build_chunk(
        chunk_id=stable_chunk_id(assertion.ref_id, None, loc, f"evidence:{assertion.id}", body),
        ref_id=assertion.ref_id,
        level=ChunkLevel.FINE,
        chunk_type=ChunkType.EVIDENCE_CARD,
        prefix=prefix,
        body=body,
        page=None,
        section=loc,
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
