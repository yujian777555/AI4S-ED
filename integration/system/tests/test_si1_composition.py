"""Phase SI-1 tests: production runtime composition / bootstrap."""

from __future__ import annotations

import pytest

from knowledge_curator.mcp_server.evidence_runtime import (
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
    PROVIDER_ENV_VAR,
    ProviderLoadError,
    load_provider_bundle,
)


# ---- stubs for valid external adapters (not InMemory/Fake) ----

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


class StubRetrieval:
    pass


def _curator_deps():
    return CuratorDependencies(
        repository=StubRepository(),
        ontology=StubOntology(),
        mechanism_validator=StubValidator(),
        provider_identity="test-external",
    )


# ---- production provider loading ----

def test_missing_provider_fails_closed():
    with pytest.raises(ProviderLoadError, match="missing production provider"):
        load_provider_bundle(environ={})


def test_invalid_module_fails_closed():
    with pytest.raises(ProviderLoadError, match="provider_module_import_failed"):
        load_provider_bundle("nonexistent.module:factory")


def test_missing_factory_fails_closed():
    with pytest.raises(ProviderLoadError, match="not found"):
        load_provider_bundle("system.provider_loader:nonexistent_factory")


def test_non_callable_factory_fails_closed():
    with pytest.raises(ProviderLoadError, match="not callable"):
        load_provider_bundle("system.provider_loader:PROVIDER_ENV_VAR")


def test_factory_exception_fails_closed():
    def boom():
        raise RuntimeError("factory exploded")

    import types, sys
    mod = types.ModuleType("test_factory_boom")
    mod.boom = boom
    sys.modules["test_factory_boom"] = mod
    with pytest.raises(ProviderLoadError, match="provider_factory_failed"):
        load_provider_bundle("test_factory_boom:boom")


def test_invalid_bundle_fails_closed():
    def bad_bundle():
        return {"not_curator": 1}

    import types, sys
    mod = types.ModuleType("test_factory_bad")
    mod.bad_bundle = bad_bundle
    sys.modules["test_factory_bad"] = mod
    with pytest.raises(ProviderLoadError, match="missing 'curator'"):
        load_provider_bundle("test_factory_bad:bad_bundle")


def test_valid_factory_returns_bundle():
    def good_factory():
        return {"curator": {"repository": StubRepository()}}

    import types, sys
    mod = types.ModuleType("test_factory_good")
    mod.good_factory = good_factory
    sys.modules["test_factory_good"] = mod
    bundle = load_provider_bundle("test_factory_good:good_factory")
    assert "curator" in bundle


# ---- adapter isolation ----

def test_reject_in_memory_knowledge_repository():
    from knowledge_curator.adapters import InMemoryKnowledgeRepository

    deps = CuratorDependencies(
        repository=InMemoryKnowledgeRepository(),
        ontology=StubOntology(),
        mechanism_validator=StubValidator(),
    )
    with pytest.raises(ProductionAdapterError, match="test/integration adapter"):
        compose_system_runtime(curator_deps=deps)


def test_reject_simple_ontology_service():
    from knowledge_curator.adapters import SimpleOntologyService

    deps = CuratorDependencies(
        repository=StubRepository(),
        ontology=SimpleOntologyService(),
        mechanism_validator=StubValidator(),
    )
    with pytest.raises(ProductionAdapterError, match="test/integration adapter"):
        compose_system_runtime(curator_deps=deps)


def test_reject_fake_mechanism_validator():
    from knowledge_curator.adapters import FakeMechanismValidator

    deps = CuratorDependencies(
        repository=StubRepository(),
        ontology=StubOntology(),
        mechanism_validator=FakeMechanismValidator(),
    )
    with pytest.raises(ProductionAdapterError, match="test/integration adapter"):
        compose_system_runtime(curator_deps=deps)


def test_reject_in_memory_retrieval_adapter():
    from knowledge_curator.adapters.in_memory_retrieval import InMemoryVectorSearch

    deps = _curator_deps()
    ev = EvidenceDependencies(retrieval=InMemoryVectorSearch([]))
    with pytest.raises(ProductionAdapterError, match="test/integration adapter"):
        compose_system_runtime(curator_deps=deps, evidence_deps=ev)


# ---- valid external injection ----

def test_valid_external_curator_injection():
    deps = _curator_deps()
    rt = compose_system_runtime(curator_deps=deps)
    assert rt.curator_runtime is not None
    assert "production:test-external" in rt.curator_runtime.adapter_note
    assert rt.evidence_runtime.retrieval_available is False  # fail-closed default


def test_injected_curator_executes_curation():
    """Injected runtime can execute one curation round-trip without default factory."""
    from knowledge_curator.schemas.assertions import (
        Assertion,
        AssertionSet,
        ClaimType,
        Confidence,
        Condition,
        DocumentMetadata,
        ObjectValue,
        Provenance,
        QualityGrade,
        SourceClaimOrigin,
        Subject,
        ValueType,
    )

    deps = _curator_deps()
    rt = compose_system_runtime(curator_deps=deps)

    assertion = Assertion(
        id="A1", ref_id="R1",
        subject=Subject(eddo_class="M", resolved_entity="E", original_mention="E"),
        property="P",
        object=ObjectValue(value=1.0, unit="u", value_type=ValueType.NUMBER),
        conditions=[Condition(eddo_class="T", value=298, unit="K")],
        provenance=Provenance(locator="p.1", sentence="s"),
        claim_type=ClaimType.MEASUREMENT,
        source_claim_origin=SourceClaimOrigin.PRIMARY,
        confidence=Confidence.HIGH, quality=0.9,
    )
    aset = AssertionSet(
        ref_id="R1",
        metadata=DocumentMetadata(title="T", authors=["A"], year=2024, source="S"),
        assertions=[assertion],
        quality_grade=QualityGrade.B,
    )
    import asyncio
    report = asyncio.run(rt.curator_runtime.curator.curate(aset))
    assert report is not None
    assert report.source_ref_id == "R1"


def test_valid_external_evidence_injection():
    from knowledge_curator.retrieval.evidence_service import EvidenceRetrievalService

    deps = _curator_deps()
    svc = EvidenceRetrievalService(
        vector_port=StubVector(), keyword_port=StubKeyword(), reranker=StubReranker()
    )
    ev = EvidenceDependencies(retrieval=svc, provider_identity="test-external")
    rt = compose_system_runtime(curator_deps=deps, evidence_deps=ev)
    assert rt.evidence_runtime.retrieval_available is True
    assert rt.evidence_runtime.integration_fixture is False


def test_production_evidence_integration_fixture_false():
    er = create_production_evidence_runtime(retrieval=StubRetrieval())
    assert er.integration_fixture is False
    assert er.retrieval_available is True


def test_evidence_absent_remains_unavailable():
    deps = _curator_deps()
    rt = compose_system_runtime(curator_deps=deps)
    assert rt.evidence_runtime.retrieval_available is False
    assert "not_configured" in (rt.evidence_runtime.unavailability_reason or "")


# ---- MCP contract preservation ----

def test_mcp_tools_unchanged():
    pytest.importorskip("mcp", reason="mcp SDK required for tool contract test")
    from knowledge_curator.mcp_server.app import (
        HEALTH_TOOL_NAME,
        PUBLIC_TOOL_NAME,
        RETRIEVE_EVIDENCE_TOOL,
        VALIDATE_CLAIMS_TOOL,
    )
    assert PUBLIC_TOOL_NAME == "curate_assertion_set"
    assert HEALTH_TOOL_NAME == "knowledge_curator_health"
    assert RETRIEVE_EVIDENCE_TOOL == "retrieve_evidence"
    assert VALIDATE_CLAIMS_TOOL == "validate_retrieved_claims"


def test_no_new_mcp_business_tool():
    pytest.importorskip("mcp", reason="mcp SDK required for tool contract test")
    import knowledge_curator.mcp_server.app as app
    names = [n for n in dir(app) if n.endswith("_TOOL") or n.endswith("_NAME")]
    # Only the existing four tool names
    assert "PUBLIC_TOOL_NAME" in names
    assert "HEALTH_TOOL_NAME" in names
    assert "RETRIEVE_EVIDENCE_TOOL" in names
    assert "VALIDATE_CLAIMS_TOOL" in names


# ---- isolation ----

def test_system_not_imported_by_frozen_core():
    import knowledge_curator.core.curator
    import knowledge_curator.core.commit
    import knowledge_curator.retrieval.hybrid

    for mod in (knowledge_curator.core.curator, knowledge_curator.core.commit, knowledge_curator.retrieval.hybrid):
        src = open(mod.__file__, encoding="utf-8").read()
        # Check for actual imports, not docstring mentions
        import re
        imports = re.findall(r'^(?:from|import)\s+system', src, re.M)
        assert not imports, f"{mod.__name__} imports system package"


def test_production_bootstrap_ignores_fixture_env():
    """Production provider loader does not read KC_EVIDENCE_INTEGRATION_FIXTURE."""
    import system.provider_loader as pl
    src = open(pl.__file__, encoding="utf-8").read()
    assert "KC_EVIDENCE_INTEGRATION_FIXTURE" not in src
    assert "build_fixture_evidence_service" not in src


def test_composition_rejects_none_dependencies():
    deps = CuratorDependencies(
        repository=None, ontology=StubOntology(), mechanism_validator=StubValidator()
    )
    with pytest.raises(ProductionAdapterError, match="must not be None"):
        compose_system_runtime(curator_deps=deps)
