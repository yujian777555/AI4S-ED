"""Runtime factory for evidence retrieval + claim guard (Phase 4.3).

Production default: retrieval_unavailable / not_configured unless a real or
explicitly-labelled integration retrieval stack is injected. Never silently
serve the synthetic fixture as production data (CG-004).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from knowledge_curator.ports.mechanism_validator import MechanismValidator
from knowledge_curator.retrieval.evidence_service import EvidenceRetrievalService
from knowledge_curator.retrieval.guard_service import ClaimGuardService


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
