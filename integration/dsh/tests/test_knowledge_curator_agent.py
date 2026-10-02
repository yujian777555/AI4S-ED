"""SI-4-R4 Production DSH Bridge Closure tests."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "dsh" / "knowledge-curator"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))


def _run(coro):
    return asyncio.run(coro)


class TestProductionBridgeBoundary:
    def test_no_integration_fixture_in_shipped_runtime(self):
        """Production runtime must not import integration test fixtures."""
        import ast
        for fname in ["bridge-plugin.js"]:
            text = (PKG / "runtime" / fname).read_text(encoding="utf-8-sig")
            assert "integration.system.fixtures" not in text
            assert "create_si2a_provider_bundle" not in text
            assert "create_si2b_provider_bundle" not in text

        # Check Python stdio entrypoint
        text = (ROOT / "system" / "curator_agent_bridge_stdio.py").read_text(encoding="utf-8-sig")
        assert "integration.system.fixtures" not in text
        assert "create_si2a_provider_bundle" not in text

    def test_no_temp_bridge_call_generation(self):
        """No _bridge_call.py temporary file generation."""
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "_bridge_call.py" not in text
        assert "writeFileSync" not in text or "unlinkSync" not in text

    def test_uses_ai4s_system_adapter_factory(self):
        """Bridge reads AI4S_SYSTEM_ADAPTER_FACTORY."""
        text = (ROOT / "system" / "curator_agent_bridge_stdio.py").read_text(encoding="utf-8-sig")
        assert "load_provider_bundle" in text
        assert "AI4S_SYSTEM_ADAPTER_FACTORY" in text or "load_provider_bundle()" in text

    def test_both_workflows_configured(self):
        """Production bridge configures both curation and revision workflows."""
        text = (ROOT / "system" / "curator_agent_bridge_stdio.py").read_text(encoding="utf-8-sig")
        assert "CurationCommitWorkflow" in text
        assert "RevisionPublicationWorkflow" in text

    def test_typed_hydration_present(self):
        """Bridge hydrates JSON into typed domain objects."""
        text = (ROOT / "system" / "curator_agent_bridge_stdio.py").read_text(encoding="utf-8-sig")
        assert "AssertionSet" in text
        assert "RevisionPackage" in text
        assert "CommitRequest" in text
        assert "RevisionApproval" in text


class TestBridgeStdio:
    def test_stdio_entrypoint_exists(self):
        assert (ROOT / "system" / "curator_agent_bridge_stdio.py").exists()

    def test_stdio_missing_provider_fail_closed(self):
        """Missing AI4S_SYSTEM_ADAPTER_FACTORY -> fail closed."""
        env = os.environ.copy()
        env.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)
        env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "curate_and_commit"],
            input=json.dumps({"source_ref_id": "R1", "source_fingerprint": "fp", "assertion_set": {}}),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0
        output = json.loads(result.stdout)
        assert "error" in output

    def test_stdio_unknown_action_fail_closed(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "unknown_action"],
            input="{}",
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0

    def test_stdio_invalid_json_fail_closed(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "curate_and_commit"],
            input="not json",
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0


class TestBridgePlugin:
    def test_plugin_uses_stdio_entrypoint(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "curator_agent_bridge_stdio" in text

    def test_plugin_registers_preset_scoped_tools(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "knowledge_curator_commit" in text
        assert "knowledge_curator_revision" in text

    def test_plugin_no_fixture_dependency(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "integration.system.fixtures" not in text


class TestSection6FailClosed:
    def test_no_evidence_content_abstain(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {"ok": True, "evidence_bundle": {"evidence_records": [{
                    "chunk_id": "R1-F1", "ref_id": "REF-1", "confidence": "high",
                }], "abstain": {"abstain": False}}}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("test", CuratorContext()))
        assert result["status"] == "abstain"

    def test_evidence_content_answer(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {"ok": True, "evidence_bundle": {"evidence_records": [{
                    "chunk_id": "R1-F1", "ref_id": "REF-1",
                    "payload_excerpt": "Energy consumption was 1.42 kWh/m3.",
                }], "abstain": {"abstain": False}}}
            if "validate_retrieved_claims" in tool_name:
                return {"ok": True, "claim_results": [{
                    "claim_id": "C1",
                    "claim_text": "Energy consumption was 1.42 kWh/m3.",
                    "policy": {"policy": "factual_allowed", "effective_confidence": "high"},
                    "abstain": {"abstain": False},
                    "resolved_anchors": [{"ref_id": "REF-1", "locator": "p.1"}],
                }]}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("test", CuratorContext()))
        assert result["status"] == "answered"
        assert "1.42" in result.get("answer", "")

    def test_fake_anchor_abstain(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {"ok": True, "evidence_bundle": {"evidence_records": [{
                    "chunk_id": "R1-F1", "ref_id": "REF-1",
                    "payload_excerpt": "test content",
                }], "abstain": {"abstain": False}}}
            if "validate_retrieved_claims" in tool_name:
                return {"ok": True, "claim_results": [{
                    "claim_id": "C1",
                    "policy": {"policy": "factual_allowed"},
                    "abstain": {"abstain": False},
                    "resolved_anchors": [{"ref_id": "FAKE-REF", "locator": "FAKE"}],
                }]}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("test", CuratorContext()))
        assert result["status"] == "abstain"


class TestDirectWorkflowRegressions:
    def test_mcp_exactly_four(self):
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        from system.composition import compose_system_runtime, CuratorDependencies

        bundle = create_si2b_provider_bundle()
        curator_raw = bundle["curator"]
        deps = CuratorDependencies(
            repository=curator_raw["repository"], ontology=curator_raw["ontology"],
            mechanism_validator=curator_raw["mechanism_validator"], provider_identity=curator_raw["provider_identity"],
        )
        rt = compose_system_runtime(curator_deps=deps, evidence_deps=None)
        from knowledge_curator.mcp_server.app import create_mcp_server

        server = create_mcp_server(runtime=rt.curator_runtime, evidence_runtime=rt.evidence_runtime)
        tool_names = set(server._tool_manager._tools.keys()) if hasattr(server, "_tool_manager") else set()
        assert tool_names == {"curate_assertion_set", "knowledge_curator_health", "retrieve_evidence", "validate_retrieved_claims"}

    def test_bridge_stdio_with_fixture_env(self):
        """Test bridge stdio with test fixture supplied via env (not hardcoded)."""
        env = os.environ.copy()
        env["AI4S_SYSTEM_ADAPTER_FACTORY"] = "integration.system.fixtures.si2a_provider:create_si2a_provider_bundle"
        env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "curate_and_commit"],
            input=json.dumps({
                "source_ref_id": "ED-TEST",
                "source_fingerprint": "fp-stdio-001",
                "assertion_set": {
                    "ref_id": "ED-TEST",
                    "metadata": {"title": "Test", "authors": ["A"], "year": 2024, "source": "J", "doi": "10.0/t", "stable_id": "ST"},
                    "assertions": [{
                        "id": "AS-001", "ref_id": "ED-TEST",
                        "subject": {"eddo_class": "Membrane", "resolved_entity": "eddo:membrane:bpm", "original_mention": "BPM"},
                        "property": "hasEnergyConsumption",
                        "object": {"value": 1.42, "unit": "kWh/m3", "value_type": "number", "uncertainty": 0.05},
                        "conditions": [{"eddo_class": "Temperature", "value": 298.15, "unit": "K"}],
                        "provenance": {"locator": "p.1", "sentence": "energy is 1.42"},
                        "claim_type": "measurement", "source_claim_origin": "primary",
                        "confidence": "medium", "quality": 0.85,
                    }],
                },
            }),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["status"] == "published"
        assert output["commit_attempted"] is True
