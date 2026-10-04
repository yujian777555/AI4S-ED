"""Integration-only DSH provider fixture (SI-1.5-R2).

TEST USE ONLY. Not a production recommendation.

Selected explicitly via:
    AI4S_SYSTEM_ADAPTER_FACTORY=integration.system.fixtures.dsh_provider:create_provider_bundle

Uses test-local protocol-compatible adapter classes over the checked-in
deterministic evidence fixture corpus. Does NOT import, instantiate, wrap,
or delegate to knowledge_curator InMemory/Fake retrieval adapters.
"""

from __future__ import annotations

from typing import Any, Optional

from knowledge_curator.ports.retrieval import (
    RankedHit,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
)
from knowledge_curator.schemas.chunk import KnowledgeChunk


# ---------------------------------------------------------------------------
# Test-local protocol-compatible retrieval adapters (SI-1.5-R2 / R2-02)
# ---------------------------------------------------------------------------


def _filter_and_rank(
    chunks: list[KnowledgeChunk],
    query: RetrievalQuery,
    channel: RetrievalChannel,
) -> list[RetrievalCandidate]:
    """Deterministic filter-by-level then rank. Parity with direct reference."""
    filtered = []
    for c in chunks:
        if c.level != query.level:
            continue
        if query.allowed_ref_ids is not None and c.ref_id not in query.allowed_ref_ids:
            continue
        filtered.append(c)
    limited = filtered[: query.top_k]
    return [
        RetrievalCandidate(chunk=c, channel=channel, rank=i + 1, raw_score=1.0 / (i + 1))
        for i, c in enumerate(limited)
    ]


class _FixtureVectorSearch:
    """Test-local vector adapter over the checked-in fixture chunks."""

    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self._chunks = list(chunks)

    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        return _filter_and_rank(self._chunks, query, RetrievalChannel.VECTOR)


class _FixtureKeywordSearch:
    """Test-local keyword adapter over the checked-in fixture chunks."""

    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self._chunks = list(chunks)

    def search(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        return _filter_and_rank(self._chunks, query, RetrievalChannel.KEYWORD)


class _FixtureReranker:
    """Test-local deterministic reranker: stable sort by rrf_score desc, chunk_id."""

    def rerank(self, hits: list[RankedHit], query: RetrievalQuery) -> list[RankedHit]:
        return sorted(hits, key=lambda h: (-h.rrf_score, h.chunk.chunk_id))


def _build_evidence_service():
    """EvidenceRetrievalService over test-local adapters + frozen fixture corpus."""
    from knowledge_curator.retrieval.evidence_service import EvidenceRetrievalService
    from knowledge_curator.retrieval.fixture import build_fixture
    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    chunks, _queries = build_fixture()
    return EvidenceRetrievalService(
        vector_port=_FixtureVectorSearch(chunks),
        keyword_port=_FixtureKeywordSearch(chunks),
        reranker=_FixtureReranker(),
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=False),
        default_evidence_type=None,  # force explicit/default handling from provenance
    )


# ---------------------------------------------------------------------------
# Curator stubs (unchanged from R1)
# ---------------------------------------------------------------------------


class _StubRepository:
    """Protocol-compatible KnowledgeRepository stub."""

    def find_assertions(self, **kwargs):
        return []

    def commit_assertions(self, *args, **kwargs):
        return None


class _StubOntology:
    """Protocol-compatible OntologyService stub."""

    def normalize_entity(self, *args, **kwargs):
        return None

    def normalize_condition(self, *args, **kwargs):
        return None

    def are_conditions_compatible(self, *args, **kwargs):
        return True


class _StubValidator:
    """Protocol-compatible MechanismValidator stub."""

    def check(self, assertions):
        from knowledge_curator.ports.mechanism_validator import MechanismCheckResult

        return MechanismCheckResult(ok=True)


def create_provider_bundle(*, include_evidence: bool = True) -> dict:
    """Return a production-compatible provider bundle for integration tests.

    Args:
        include_evidence: if True, include a deterministic evidence service
            over the checked-in fixture corpus. If False, evidence retrieval
            is intentionally omitted (fail-closed).
    """
    bundle: dict[str, Any] = {
        "curator": {
            "repository": _StubRepository(),
            "ontology": _StubOntology(),
            "mechanism_validator": _StubValidator(),
            "provider_identity": "integration-test-provider",
        }
    }
    if include_evidence:
        bundle["evidence"] = {
            "retrieval": _build_evidence_service(),
            "mechanism_validator": _StubValidator(),
            "provider_identity": "integration-test-provider",
        }
    return bundle


def create_provider_bundle_no_evidence() -> dict:
    """Provider bundle with evidence intentionally omitted."""
    return create_provider_bundle(include_evidence=False)
