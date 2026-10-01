"""Phase SI-1.5 tests: DSH production bootstrap wiring."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PRESET_PATH = ROOT / "dsh" / "knowledge-curator" / "cordis.patch.yml"


def _read_preset():
    return PRESET_PATH.read_text(encoding="utf-8")


# ---- DSH preset uses system.mcp_stdio ----

def test_dsh_preset_uses_system_mcp_stdio():
    content = _read_preset()
    assert "system.mcp_stdio" in content
    assert "knowledge_curator.mcp_server" not in content


def test_dsh_preset_keeps_env_and_failclosed():
    content = _read_preset()
    assert "AI4S_KC_PYTHON" in content
    assert "AI4S_KC_WORKSPACE" in content
    assert "failOnStartupError: true" in content
    assert "stdio" in content


def test_dsh_preset_no_hardcoded_provider():
    content = _read_preset()
    assert "AI4S_SYSTEM_ADAPTER_FACTORY" not in content  # not hardcoded in preset


# ---- provider fixture exists and is integration-only ----

def test_fixture_provider_satisfies_ports():
    from integration.system.fixtures.dsh_provider import create_provider_bundle

    bundle = create_provider_bundle()
    curator = bundle["curator"]
    from knowledge_curator.ports.knowledge_repository import KnowledgeRepository
    from knowledge_curator.ports.ontology_service import OntologyService
    from knowledge_curator.ports.mechanism_validator import MechanismValidator

    assert isinstance(curator["repository"], KnowledgeRepository)
    assert isinstance(curator["ontology"], OntologyService)
    assert isinstance(curator["mechanism_validator"], MechanismValidator)


def test_fixture_uses_no_inmemory_adapters():
    from integration.system.fixtures.dsh_provider import create_provider_bundle

    bundle = create_provider_bundle()
    for obj in (
        bundle["curator"]["repository"],
        bundle["curator"]["ontology"],
        bundle["curator"]["mechanism_validator"],
    ):
        cls = type(obj)
        assert "InMemory" not in cls.__name__
        assert "Fake" not in cls.__name__
        assert "in_memory" not in cls.__module__


# ---- system.mcp_stdio bootstrap via valid provider ----

def test_valid_provider_startup_exact_four_tools():
    pytest.importorskip("mcp", reason="mcp SDK required")
    from system.mcp_stdio import build_system_mcp_server

    server = build_system_mcp_server(
        "integration.system.fixtures.dsh_provider:create_provider_bundle"
    )

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

    server = build_system_mcp_server(
        "integration.system.fixtures.dsh_provider:create_provider_bundle"
    )

    async def _call():
        return await server.call_tool("knowledge_curator_health", {})

    import anyio

    result = anyio.run(_call)
    structured = getattr(result, "structuredContent", None) or {}
    if not structured and getattr(result, "content", None):
        text = " ".join(getattr(c, "text", "") or "" for c in result.content)
        structured = json.loads(text) if text.strip().startswith("{") else {}
    assert "integration-test-provider" in str(structured.get("adapters", ""))
    assert structured.get("retrieval_available") is True  # evidence configured in fixture


def test_curation_round_trip():
    pytest.importorskip("mcp", reason="mcp SDK required")
    from system.mcp_stdio import build_system_mcp_server

    server = build_system_mcp_server(
        "integration.system.fixtures.dsh_provider:create_provider_bundle"
    )

    assertion_set = {
        "ref_id": "R1",
        "metadata": {"title": "T", "authors": ["A"], "year": 2024, "source": "S"},
        "assertions": [
            {
                "id": "A1",
                "ref_id": "R1",
                "subject": {"eddo_class": "M", "resolved_entity": "E", "original_mention": "E"},
                "property": "P",
                "object": {"value": 1.0, "unit": "u", "value_type": "number"},
                "conditions": [],
                "provenance": {"locator": "p.1"},
                "claim_type": "measurement",
                "source_claim_origin": "primary",
                "confidence": "high",
                "quality": 0.9,
            }
        ],
        "quality_grade": "B",
    }

    async def _call():
        return await server.call_tool("curate_assertion_set", {"assertion_set": assertion_set})

    import anyio

    result = anyio.run(_call)
    structured = getattr(result, "structuredContent", None) or {}
    if not structured and getattr(result, "content", None):
        text = " ".join(getattr(c, "text", "") or "" for c in result.content)
        structured = json.loads(text) if text.strip().startswith("{") else {}
    assert structured.get("ok") is True
    assert "report" in structured


def test_evidence_unavailable_when_omitted():
    pytest.importorskip("mcp", reason="mcp SDK required")
    from system.mcp_stdio import build_system_mcp_server

    server = build_system_mcp_server(
        "integration.system.fixtures.dsh_provider:create_provider_bundle_no_evidence"
    )

    async def _call():
        return await server.call_tool("retrieve_evidence", {"request": {"query": "test"}})

    import anyio

    result = anyio.run(_call)
    structured = getattr(result, "structuredContent", None) or {}
    if not structured and getattr(result, "content", None):
        text = " ".join(getattr(c, "text", "") or "" for c in result.content)
        structured = json.loads(text) if text.strip().startswith("{") else {}
    assert structured.get("ok") is False
    assert structured.get("error") == "retrieval_unavailable"


# ---- fail-closed startup ----

def test_missing_provider_fail_closed():
    from system.provider_loader import ProviderLoadError, load_provider_bundle

    with pytest.raises(ProviderLoadError, match="missing production provider"):
        load_provider_bundle(environ={})


def test_invalid_provider_fail_closed():
    from system.provider_loader import ProviderLoadError, load_provider_bundle

    with pytest.raises(ProviderLoadError):
        load_provider_bundle("nonexistent.module:factory")


def test_kc_evidence_fixture_cannot_bypass_production():
    """KC_EVIDENCE_INTEGRATION_FIXTURE=1 does not create production evidence."""
    from system.mcp_stdio import build_system_mcp_server

    os.environ["KC_EVIDENCE_INTEGRATION_FIXTURE"] = "1"
    try:
        server = build_system_mcp_server(
            "integration.system.fixtures.dsh_provider:create_provider_bundle_no_evidence"
        )

        async def _call():
            return await server.call_tool("retrieve_evidence", {"request": {"query": "test"}})

        import anyio

        result = anyio.run(_call)
        structured = getattr(result, "structuredContent", None) or {}
        if not structured and getattr(result, "content", None):
            text = " ".join(getattr(c, "text", "") or "" for c in result.content)
            structured = json.loads(text) if text.strip().startswith("{") else {}
        # Evidence remains unavailable despite the fixture env var
        assert structured.get("ok") is False
        assert structured.get("error") == "retrieval_unavailable"
    finally:
        os.environ.pop("KC_EVIDENCE_INTEGRATION_FIXTURE", None)


# ---- evidence configured round-trip ----

def test_evidence_configured_round_trip():
    pytest.importorskip("mcp", reason="mcp SDK required")
    from system.mcp_stdio import build_system_mcp_server

    server = build_system_mcp_server(
        "integration.system.fixtures.dsh_provider:create_provider_bundle"
    )

    async def _call():
        return await server.call_tool(
            "retrieve_evidence", {"request": {"query": "test", "top_k": 3}}
        )

    import anyio

    result = anyio.run(_call)
    structured = getattr(result, "structuredContent", None) or {}
    if not structured and getattr(result, "content", None):
        text = " ".join(getattr(c, "text", "") or "" for c in result.content)
        structured = json.loads(text) if text.strip().startswith("{") else {}
    # Stub backends return empty results but the call succeeds
    assert structured.get("ok") is True
    assert "evidence_bundle" in structured


# ---- frozen tree verification (structural) ----

def test_no_orchestrator_in_system_fixtures():
    import re

    fixture = ROOT / "integration" / "system" / "fixtures" / "dsh_provider.py"
    src = fixture.read_text(encoding="utf-8")
    for kw in ("DocumentCommitCoordinator", "RevisionPublicationCoordinator", "LifecycleRevisionCoordinator"):
        if re.search(rf"from\s+\S+\s+import\s+.*{kw}|\b{kw}\s*\(", src):
            pytest.fail(f"fixture uses {kw}")
