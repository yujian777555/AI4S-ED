"""Integration-only DSH provider fixture (SI-1.5).

TEST USE ONLY. Not a production recommendation.

Selected explicitly via:
    AI4S_SYSTEM_ADAPTER_FACTORY=integration.system.fixtures.dsh_provider:create_provider_bundle

Uses test-local stub classes that satisfy frozen Ports.
Does NOT use knowledge_curator InMemory/Fake adapters.
"""

from __future__ import annotations

from typing import Any, Optional


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


class _StubVectorBackend:
    def search(self, query):
        return []


class _StubKeywordBackend:
    def search(self, query):
        return []


class _StubReranker:
    def rerank(self, hits, query):
        return hits


def _build_evidence_service():
    from knowledge_curator.retrieval.evidence_service import EvidenceRetrievalService

    return EvidenceRetrievalService(
        vector_port=_StubVectorBackend(),
        keyword_port=_StubKeywordBackend(),
        reranker=_StubReranker(),
    )


def create_provider_bundle(*, include_evidence: bool = True) -> dict:
    """Return a production-compatible provider bundle for integration tests.

    Args:
        include_evidence: if True, include a deterministic evidence service.
            If False, evidence retrieval is intentionally omitted (fail-closed).
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
