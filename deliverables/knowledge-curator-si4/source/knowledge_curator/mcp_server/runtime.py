"""Runtime factory: wire KnowledgeCurator for MCP integration tests.

Uses explicitly-labeled integration-test adapters (in-memory/fake).
Does not modify §5.1–§5.4 deterministic core logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from knowledge_curator.adapters import (
    FakeMechanismValidator,
    InMemoryKnowledgeRepository,
    SimpleOntologyService,
)
from knowledge_curator.core.curator import KnowledgeCurator
from knowledge_curator.schemas.assertions import AssertionSet
from knowledge_curator.schemas.curation import CurationReport

# Integration-test adapters. Not production L2/L3.
INTEGRATION_ADAPTER_NOTE = "integration-test adapters (in-memory/fake)"


@dataclass
class CuratorRuntime:
    curator: KnowledgeCurator
    adapter_note: str


def create_default_runtime() -> CuratorRuntime:
    """Create a runtime-independent KnowledgeCurator with integration adapters."""
    curator = KnowledgeCurator(
        repository=InMemoryKnowledgeRepository(),
        ontology=SimpleOntologyService(),
        mechanism_validator=FakeMechanismValidator(),
    )
    return CuratorRuntime(curator=curator, adapter_note=INTEGRATION_ADAPTER_NOTE)


def create_curator_runtime(
    *,
    repository: Any,
    ontology: Any,
    mechanism_validator: Any,
    adapter_note: str = "external production adapters",
) -> CuratorRuntime:
    """Create a KnowledgeCurator from externally supplied production adapters.

    This is the production injection point. The caller must supply real
    implementations of the existing ports. This function does not fall back
    to InMemory/Fake adapters.
    """
    curator = KnowledgeCurator(
        repository=repository,
        ontology=ontology,
        mechanism_validator=mechanism_validator,
    )
    return CuratorRuntime(curator=curator, adapter_note=adapter_note)


async def run_curate(runtime: CuratorRuntime, assertion_set: AssertionSet) -> CurationReport:
    """Delegate to the existing KnowledgeCurator.curate() — no logic duplication."""
    return await runtime.curator.curate(assertion_set)
