"""Synthetic retrieval fixture (Phase 4.2.2). Checked-in, no real papers."""

from __future__ import annotations

from dataclasses import dataclass, field

from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk


@dataclass
class FixtureQuery:
    query_id: str
    text: str
    expected_ref_ids: list[str]
    expected_chunk_ids: list[str] = field(default_factory=list)


def _chunk(cid: str, ref: str, level: ChunkLevel, ctype: ChunkType, payload: str, section: str = "") -> KnowledgeChunk:
    prefix = f"[{ref}|-|{section or '-'}|type({{'text':'文本','table':'表','chart':'图','evidence_card':'证据卡','document_summary':'summary'}}.get('{ctype.value}','{ctype.value}')]"
    return KnowledgeChunk(
        chunk_id=cid,
        ref_id=ref,
        level=level,
        chunk_type=ctype,
        payload=f"{prefix} {payload}",
        section=section,
        locator=section or "p.1",
    )


def build_fixture() -> tuple[list[KnowledgeChunk], list[FixtureQuery]]:
    """Build synthetic corpus: >=6 refs, coarse+fine, CN+EN+mixed, >=6 queries."""
    chunks: list[KnowledgeChunk] = []
    queries: list[FixtureQuery] = []

    # REF-1: Chinese membrane energy
    chunks.append(_chunk("R1-S", "REF-1", ChunkLevel.COARSE, ChunkType.DOCUMENT_SUMMARY,
                        "双极膜电渗析系统能耗研究综述", "summary"))
    chunks.append(_chunk("R1-F1", "REF-1", ChunkLevel.FINE, ChunkType.TEXT,
                        "双极膜电渗析工艺中能耗约为1.4 kWh每立方米，膜电阻是关键参数。", "Results"))
    chunks.append(_chunk("R1-F2", "REF-1", ChunkLevel.FINE, ChunkType.EVIDENCE_CARD,
                        "Subject: BPM; Property: hasEnergyConsumption; Value: 1.42 kWh/m3; Confidence: high", "T12"))

    # REF-2: English current efficiency
    chunks.append(_chunk("R2-S", "REF-2", ChunkLevel.COARSE, ChunkType.DOCUMENT_SUMMARY,
                        "Current efficiency in electrodialysis systems", "summary"))
    chunks.append(_chunk("R2-F1", "REF-2", ChunkLevel.FINE, ChunkType.TEXT,
                        "Current efficiency of electrodialysis can reach 90% under optimal conditions.", "Results"))
    chunks.append(_chunk("R2-F2", "REF-2", ChunkLevel.FINE, ChunkType.TEXT,
                        "Energy consumption decreases with improved membrane selectivity.", "Discussion"))

    # REF-3: Mixed language
    chunks.append(_chunk("R3-S", "REF-3", ChunkLevel.COARSE, ChunkType.DOCUMENT_SUMMARY,
                        "Mixed language study on membrane fouling and cleaning", "summary"))
    chunks.append(_chunk("R3-F1", "REF-3", ChunkLevel.FINE, ChunkType.TEXT,
                        "膜污染 membrane fouling 会导致通量下降 flux decline，需要定期清洗 cleaning。", "Results"))

    # REF-4: Chinese battery
    chunks.append(_chunk("R4-S", "REF-4", ChunkLevel.COARSE, ChunkType.DOCUMENT_SUMMARY,
                        "锂离子电池热管理研究", "summary"))
    chunks.append(_chunk("R4-F1", "REF-4", ChunkLevel.FINE, ChunkType.TEXT,
                        "锂离子电池在高温下容量衰减加速，需要有效的热管理系统。", "Results"))

    # REF-5: English catalysis
    chunks.append(_chunk("R5-S", "REF-5", ChunkLevel.COARSE, ChunkType.DOCUMENT_SUMMARY,
                        "Catalyst design for CO2 reduction", "summary"))
    chunks.append(_chunk("R5-F1", "REF-5", ChunkLevel.FINE, ChunkType.TEXT,
                        "Copper-based catalysts show high selectivity for CO2 reduction to ethanol.", "Results"))

    # REF-6: Mixed Chinese water treatment
    chunks.append(_chunk("R6-S", "REF-6", ChunkLevel.COARSE, ChunkType.DOCUMENT_SUMMARY,
                        "水处理技术与膜分离 water treatment and membrane separation", "summary"))
    chunks.append(_chunk("R6-F1", "REF-6", ChunkLevel.FINE, ChunkType.TEXT,
                        "反渗透 reverse osmosis 膜在水处理中广泛应用，脱盐率可达99%。", "Results"))

    queries = [
        FixtureQuery("Q1", "双极膜电渗析 能耗", ["REF-1"], ["R1-F1", "R1-F2"]),
        FixtureQuery("Q2", "current efficiency electrodialysis", ["REF-2"], ["R2-F1"]),
        FixtureQuery("Q3", "膜污染 cleaning", ["REF-3"], ["R3-F1"]),
        FixtureQuery("Q4", "锂离子电池 热管理", ["REF-4"], ["R4-F1"]),
        FixtureQuery("Q5", "catalyst CO2 reduction ethanol", ["REF-5"], ["R5-F1"]),
        FixtureQuery("Q6", "反渗透 脱盐 reverse osmosis", ["REF-6"], ["R6-F1"]),
    ]
    return chunks, queries
