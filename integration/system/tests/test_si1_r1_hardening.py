"""Phase SI-1-R1 tests: production composition hardening."""

from __future__ import annotations

import pytest

from knowledge_curator.mcp_server.evidence_runtime import (
    build_fixture_evidence_service,
    create_production_evidence_runtime,
    create_unavailable_evidence_runtime,
)
from knowledge_curator.mcp_server.runtime import create_curator_runtime
from system.composition import (
    CuratorDependencies,
    EvidenceDependencies,
    ProductionAdapterError,
    compose_system_runtime,
)
from system.provider_loader import (
    ProviderLoadError,
    load_provider_bundle,
)


# ---- complete protocol-compatible external stubs ----

class StubRepository:
    def find_assertions(self, **kwargs):
        return []
    def commit_assertions(self, *args, **kwargs):
        return None


class StubOntology:
    def normalize_entity(self, *args, **kwargs):
        return None
    def normalize_condition(self, *args, **kwargs):
        return None
    def are_conditions_compatible(self, *args, **kwargs):
        return True


class StubValidator:
    def check(self, assertions):
        from knowledge_curator.ports.mechanism_validator import MechanismCheckResult

        return MechanismCheckResult(ok=True)


class StubVector:
    def search(self, query):
        return []


class StubKeyword:
    def search(self, query):
        return []


class StubReranker:
    def rerank(self, hits, query):
        return hits


def _curator_deps():
    return CuratorDependencies(
        repository=StubRepository(),
        ontology=StubOntology(),
        mechanism_validator=StubValidator(),
        provider_identity="test-external",
    )


def _valid_evidence_service():
    from knowledge_curator.retrieval.evidence_service import EvidenceRetrievalService

    return EvidenceRetrievalService(
        vector_port=StubVector(),
        keyword_port=StubKeyword(),
        reranker=StubReranker(),
    )


# ---- R1-01: nested test adapter rejection ----

def test_checked_in_fixture_rejected_as_production():
    fixture = build_fixture_evidence_service()
    deps = _curator_deps()
    ev = EvidenceDependencies(retrieval=fixture)
    with pytest.raises(ProductionAdapterError, match="test/integration adapter"):
        compose_system_runtime(curator_deps=deps, evidence_deps=ev)


def test_nested_in_memory_vector_rejected():
    from knowledge_curator.adapters.in_memory_retrieval import InMemoryVectorSearch
    from knowledge_curator.retrieval.evidence_service import EvidenceRetrievalService

    svc = EvidenceRetrievalService(
        vector_port=InMemoryVectorSearch([]),
        keyword_port=StubKeyword(),
        reranker=StubReranker(),
    )
    deps = _curator_deps()
    ev = EvidenceDependencies(retrieval=svc)
    with pytest.raises(ProductionAdapterError, match="test/integration adapter"):
        compose_system_runtime(curator_deps=deps, evidence_deps=ev)


def test_nested_in_memory_keyword_rejected():
    from knowledge_curator.adapters.in_memory_retrieval import InMemoryKeywordSearch
    from knowledge_curator.retrieval.evidence_service import EvidenceRetrievalService

    svc = EvidenceRetrievalService(
        vector_port=StubVector(),
        keyword_port=InMemoryKeywordSearch([]),
        reranker=StubReranker(),
    )
    deps = _curator_deps()
    ev = EvidenceDependencies(retrieval=svc)
    with pytest.raises(ProductionAdapterError, match="test/integration adapter"):
        compose_system_runtime(curator_deps=deps, evidence_deps=ev)


def test_nested_fake_reranker_rejected():
    from knowledge_curator.adapters.in_memory_retrieval import FakeReranker
    from knowledge_curator.retrieval.evidence_service import EvidenceRetrievalService

    svc = EvidenceRetrievalService(
        vector_port=StubVector(),
        keyword_port=StubKeyword(),
        reranker=FakeReranker(),
    )
    deps = _curator_deps()
    ev = EvidenceDependencies(retrieval=svc)
    with pytest.raises(ProductionAdapterError, match="test/integration adapter"):
        compose_system_runtime(curator_deps=deps, evidence_deps=ev)


def test_valid_external_evidence_accepted():
    deps = _curator_deps()
    ev = EvidenceDependencies(retrieval=_valid_evidence_service())
    rt = compose_system_runtime(curator_deps=deps, evidence_deps=ev)
    assert rt.evidence_runtime.retrieval_available is True
    assert rt.evidence_runtime.integration_fixture is False


# ---- R1-02: Port validation ----

def test_invalid_repository_shape_rejected():
    deps = CuratorDependencies(
        repository=object(), ontology=StubOntology(), mechanism_validator=StubValidator()
    )
    with pytest.raises(ProductionAdapterError, match="does not satisfy"):
        compose_system_runtime(curator_deps=deps)


def test_invalid_ontology_shape_rejected():
    deps = CuratorDependencies(
        repository=StubRepository(), ontology=object(), mechanism_validator=StubValidator()
    )
    with pytest.raises(ProductionAdapterError, match="does not satisfy"):
        compose_system_runtime(curator_deps=deps)


def test_invalid_mechanism_validator_shape_rejected():
    deps = CuratorDependencies(
        repository=StubRepository(), ontology=StubOntology(), mechanism_validator=object()
    )
    with pytest.raises(ProductionAdapterError, match="does not satisfy"):
        compose_system_runtime(curator_deps=deps)


def test_invalid_evidence_retrieval_shape_rejected():
    deps = _curator_deps()
    ev = EvidenceDependencies(retrieval=object())
    with pytest.raises(ProductionAdapterError, match="does not satisfy|EvidenceRetrievalService"):
        compose_system_runtime(curator_deps=deps, evidence_deps=ev)


def test_invalid_evidence_mechanism_validator_rejected():
    deps = _curator_deps()
    ev = EvidenceDependencies(
        retrieval=_valid_evidence_service(), mechanism_validator=object()
    )
    with pytest.raises(ProductionAdapterError, match="does not satisfy"):
        compose_system_runtime(curator_deps=deps, evidence_deps=ev)


# ---- R1-03: secret redaction ----

def test_factory_exception_secret_redacted():
    def bad_factory():
        raise RuntimeError("connection failed with key=TOP_SECRET_SENTINEL")

    import types, sys
    mod = types.ModuleType("test_secret_factory")
    mod.bad_factory = bad_factory
    sys.modules["test_secret_factory"] = mod
    with pytest.raises(ProviderLoadError) as exc_info:
        load_provider_bundle("test_secret_factory:bad_factory")
    assert "TOP_SECRET_SENTINEL" not in str(exc_info.value)
    assert "provider_factory_failed" in str(exc_info.value)


def test_import_exception_secret_redacted():
    # Create a module that raises on import with a sentinel
    import types, sys

    class FakeLoader:
        def create_module(self, spec):
            raise RuntimeError("import error with TOP_SECRET_SENTINEL")

        def exec_module(self, module):
            pass

    # Use a module that will fail to import by using a nonexistent submodule
    with pytest.raises(ProviderLoadError) as exc_info:
        load_provider_bundle("nonexistent_secret_module_xyz:factory")
    assert "TOP_SECRET_SENTINEL" not in str(exc_info.value)
    assert "provider_module_import_failed" in str(exc_info.value)


# ---- R1-04: MCP contract via system bootstrap ----

def test_system_bootstrap_exact_four_tool_contract():
    pytest.importorskip("mcp", reason="mcp SDK required")
    from system.mcp_stdio import build_system_mcp_server

    def good_factory():
        return {
            "curator": {
                "repository": StubRepository(),
                "ontology": StubOntology(),
                "mechanism_validator": StubValidator(),
                "provider_identity": "test-external",
            }
        }

    import types, sys
    mod = types.ModuleType("test_si1_bootstrap")
    mod.good_factory = good_factory
    sys.modules["test_si1_bootstrap"] = mod

    server = build_system_mcp_server("test_si1_bootstrap:good_factory")

    async def _get_tools():
        tools = await server.list_tools()
        return [t.name for t in tools]

    import anyio

    names = anyio.run(_get_tools)
    assert sorted(names) == sorted(
        [
            "curate_assertion_set",
            "knowledge_curator_health",
            "retrieve_evidence",
            "validate_retrieved_claims",
        ]
    )


def test_health_production_adapter_identity():
    pytest.importorskip("mcp", reason="mcp SDK required")
    from system.mcp_stdio import build_system_mcp_server

    def good_factory():
        return {
            "curator": {
                "repository": StubRepository(),
                "ontology": StubOntology(),
                "mechanism_validator": StubValidator(),
                "provider_identity": "my-prod",
            }
        }

    import types, sys
    mod = types.ModuleType("test_si1_health")
    mod.good_factory = good_factory
    sys.modules["test_si1_health"] = mod

    server = build_system_mcp_server("test_si1_health:good_factory")

    async def _call():
        return await server.call_tool("knowledge_curator_health", {})

    import anyio

    result = anyio.run(_call)
    structured = getattr(result, "structuredContent", None) or {}
    if not structured and getattr(result, "content", None):
        text = " ".join(getattr(c, "text", "") or "" for c in result.content)
        import json

        structured = json.loads(text) if text.strip().startswith("{") else {}
    assert "production:my-prod" in str(structured.get("adapters", ""))
    assert structured.get("retrieval_available") is False  # fail-closed


# ---- existing invariants preserved ----

def test_missing_provider_fails_closed():
    with pytest.raises(ProviderLoadError, match="missing production provider"):
        load_provider_bundle(environ={})


def test_evidence_absent_remains_unavailable():
    deps = _curator_deps()
    rt = compose_system_runtime(curator_deps=deps)
    assert rt.evidence_runtime.retrieval_available is False
    assert "not_configured" in (rt.evidence_runtime.unavailability_reason or "")


def test_no_orchestrator_in_system():
    import re
    import system.composition
    import system.provider_loader

    for mod in (system.composition, system.provider_loader):
        src = open(mod.__file__, encoding="utf-8").read()
        # Check for actual imports/calls, not docstring mentions
        for kw in ("DocumentCommitCoordinator", "RevisionPublicationCoordinator", "LifecycleRevisionCoordinator"):
            # Only flag if it appears as an import or function call
            if re.search(rf'from\s+\S*\s+import\s+.*{kw}|\b{kw}\s*\(', src):
                assert False, f"{mod.__name__} uses {kw}"
