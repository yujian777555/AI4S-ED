"""Runtime factory for evidence retrieval + claim guard (Phase 4.3/4.3.1).

Production default: retrieval_unavailable / not_configured unless a real or
explicitly-labelled integration retrieval stack is injected. Never silently
serve the synthetic fixture as production data (CG-004).

Integration fixture mode is opt-in ONLY via env:
    KC_EVIDENCE_INTEGRATION_FIXTURE=1
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from knowledge_curator.ports.mechanism_validator import MechanismValidator
from knowledge_curator.retrieval.evidence_service import EvidenceRetrievalService
from knowledge_curator.retrieval.guard_service import ClaimGuardService

INTEGRATION_FIXTURE_ENV = "KC_EVIDENCE_INTEGRATION_FIXTURE"


@dataclass
class EvidenceRuntime:
    """Holds optional retrieval/guard services for MCP tools."""

    retrieval: Optional[EvidenceRetrievalService]
    guard: ClaimGuardService
    adapter_note: str
    integration_fixture: bool = False
    retrieval_available: bool = False
    unavailability_reason: Optional[str] = None


def create_unavailable_evidence_runtime(
    mechanism_validator: Optional[MechanismValidator] = None,
) -> EvidenceRuntime:
    """Production default: explicit retrieval_unavailable / not_configured."""
    return EvidenceRuntime(
        retrieval=None,
        guard=ClaimGuardService(mechanism_validator=mechanism_validator),
        adapter_note="production-default: retrieval corpus not configured (CG-004)",
        integration_fixture=False,
        retrieval_available=False,
        unavailability_reason="retrieval_unavailable: not_configured",
    )


def create_integration_evidence_runtime(
    retrieval: EvidenceRetrievalService,
    *,
    mechanism_validator: Optional[MechanismValidator] = None,
) -> EvidenceRuntime:
    """Explicit integration fixture mode. Clearly labelled, not production."""
    return EvidenceRuntime(
        retrieval=retrieval,
        guard=ClaimGuardService(mechanism_validator=mechanism_validator),
        adapter_note="integration fixture mode (explicit, not production corpus)",
        integration_fixture=True,
        retrieval_available=True,
        unavailability_reason=None,
    )


def create_production_evidence_runtime(
    retrieval: EvidenceRetrievalService,
    *,
    mechanism_validator: Optional[MechanismValidator] = None,
    adapter_note: str = "external production evidence adapters",
) -> EvidenceRuntime:
    """Create a production evidence runtime from an injected real retrieval service.

    Properties:
    - integration_fixture=False (never a synthetic fixture)
    - retrieval_available=True
    - no fallback to build_fixture_evidence_service()
    """
    return EvidenceRuntime(
        retrieval=retrieval,
        guard=ClaimGuardService(mechanism_validator=mechanism_validator),
        adapter_note=adapter_note,
        integration_fixture=False,
        retrieval_available=True,
        unavailability_reason=None,
    )


def build_fixture_evidence_service() -> EvidenceRetrievalService:
    """Build an in-memory evidence service over the checked-in synthetic fixture.

    Only for integration tests / DSH smoke. Production never calls this unless
    KC_EVIDENCE_INTEGRATION_FIXTURE=1 is explicitly set.
    """
    from knowledge_curator.adapters.in_memory_retrieval import (
        FakeReranker,
        InMemoryKeywordSearch,
        InMemoryVectorSearch,
    )
    from knowledge_curator.retrieval.fixture import build_fixture
    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    chunks, _queries = build_fixture()
    return EvidenceRetrievalService(
        vector_port=InMemoryVectorSearch(chunks),
        keyword_port=InMemoryKeywordSearch(chunks),
        reranker=FakeReranker(),
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=False),
        default_evidence_type=None,  # force explicit/default handling from provenance
    )


def create_evidence_runtime_from_env(
    *,
    environ: Optional[dict[str, str]] = None,
    mechanism_validator: Optional[MechanismValidator] = None,
) -> EvidenceRuntime:
    """Resolve evidence runtime from the environment.

    - KC_EVIDENCE_INTEGRATION_FIXTURE=1 -> labelled synthetic fixture runtime.
    - unset/any other value -> production default (retrieval_unavailable).
    """
    env = environ if environ is not None else os.environ
    flag = str(env.get(INTEGRATION_FIXTURE_ENV, "")).strip()
    if flag != "1":
        return create_unavailable_evidence_runtime(mechanism_validator=mechanism_validator)

    retrieval = build_fixture_evidence_service()
    return create_integration_evidence_runtime(
        retrieval,
        mechanism_validator=mechanism_validator,
    )
