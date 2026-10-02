"""SI-4-R5 Executable DSH Plugin & Strict Bridge Validation tests."""

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


def _bridge_env():
    env = os.environ.copy()
    env["AI4S_SYSTEM_ADAPTER_FACTORY"] = "integration.system.fixtures.si2b_provider:create_si2b_provider_bundle"
    env["PYTHONPATH"] = str(ROOT)
    return env


class TestAsyncTransport:
    def test_plugin_uses_spawn_not_execfile(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "spawn" in text
        assert "execFileAsync" not in text
        assert "child.stdin.write" in text
        assert "child.stdin.end" in text

    def test_stdin_payload_reaches_python(self):
        """Real spawn transport: payload reaches Python via stdin."""
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "curate_and_commit"],
            input=json.dumps({
                "source_ref_id": "ED-TRANSPORT",
                "source_fingerprint": "fp-transport-001",
                "assertion_set": {
                    "ref_id": "ED-TRANSPORT",
                    "metadata": {"title": "T", "authors": ["A"], "year": 2024, "source": "J", "doi": "10.0/t", "stable_id": "ST"},
                    "assertions": [{
                        "id": "AS-001", "ref_id": "ED-TRANSPORT",
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
            capture_output=True, text=True, timeout=30, env=_bridge_env(), cwd=str(ROOT),
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["status"] == "published"


class TestPinnedDefineToolContract:
    def test_plugin_uses_output_schema_and_render(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "output:" in text
        assert "render:" in text
        assert "schema:" in text

    def test_plugin_export_shape(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "export const name" in text or "export function apply" in text

    def test_execute_returns_canonical_value(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        # execute should return result object, not content block
        assert "return await callBridge" in text


class TestStrictHydration:
    def test_invalid_approval_decision_fail_closed(self):
        env = _bridge_env()
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "revise"],
            input=json.dumps({
                "package": {"package_id": "p", "work_id": "w", "prior_source_version_id": "a", "new_source_version_id": "b", "relation": "preprint_to_journal", "prior_ref_id": "R1", "new_ref_id": "R2", "target_assertions": []},
                "target_commit_request": {"source": {"ref_id": "R2", "source_fingerprint": "fp"}, "assertion_set": {"ref_id": "R2", "metadata": {}, "assertions": []}, "report": {"source_ref_id": "R2", "decisions": []}},
                "approval": {"approval_id": "a", "package_id": "p", "scope_hash": "s", "decision": "yes-please", "approver": "x"},
            }),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0
        output = json.loads(result.stdout)
        assert "error" in output

    def test_invalid_relation_fail_closed(self):
        env = _bridge_env()
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "revise"],
            input=json.dumps({
                "package": {"package_id": "p", "work_id": "w", "prior_source_version_id": "a", "new_source_version_id": "b", "relation": "INVALID_RELATION", "prior_ref_id": "R1", "new_ref_id": "R2", "target_assertions": []},
                "target_commit_request": {"source": {"ref_id": "R2", "source_fingerprint": "fp"}, "assertion_set": {"ref_id": "R2", "metadata": {}, "assertions": []}, "report": {"source_ref_id": "R2", "decisions": []}},
            }),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0

    def test_invalid_confidence_fail_closed(self):
        env = _bridge_env()
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "curate_and_commit"],
            input=json.dumps({
                "source_ref_id": "ED-X", "source_fingerprint": "fp",
                "assertion_set": {
                    "ref_id": "ED-X", "metadata": {"title": "T", "authors": [], "year": 2024, "source": "J"},
                    "assertions": [{
                        "id": "AS-001", "ref_id": "ED-X",
                        "subject": {"eddo_class": "M", "resolved_entity": "e", "original_mention": "m"},
                        "property": "p", "object": {"value": 1, "unit": "u", "value_type": "number"},
                        "claim_type": "measurement", "source_claim_origin": "primary",
                        "confidence": "INVALID_CONF", "quality": 0.5,
                    }],
                },
            }),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0

    def test_missing_required_field_fail_closed(self):
        env = _bridge_env()
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "curate_and_commit"],
            input=json.dumps({
                "source_ref_id": "ED-X", "source_fingerprint": "fp",
                "assertion_set": {
                    "ref_id": "ED-X", "metadata": {"title": "T"},
                    "assertions": [{"id": "AS-001", "ref_id": "ED-X"}],  # missing required fields
                },
            }),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0

    def test_missing_revision_provider_fail_closed(self):
        """No revision deps in provider -> fail closed."""
        env = os.environ.copy()
        env["AI4S_SYSTEM_ADAPTER_FACTORY"] = "integration.system.fixtures.si2b_provider:create_si2b_provider_bundle"
        env["PYTHONPATH"] = str(ROOT)
        # si2a_provider has no revision group
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "revise"],
            input=json.dumps({"package": {}, "target_commit_request": {}}),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0
        output = json.loads(result.stdout)
        assert "error" in output


class TestSection6FailClosed:
    def test_no_evidence_content_abstain(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {"ok": True, "evidence_bundle": {"evidence_records": [{"chunk_id": "R1-F1", "ref_id": "REF-1"}], "abstain": {"abstain": False}}}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("test", CuratorContext()))
        assert result["status"] == "abstain"

    def test_fake_anchor_abstain(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {"ok": True, "evidence_bundle": {"evidence_records": [{"chunk_id": "R1-F1", "ref_id": "REF-1", "payload_excerpt": "test"}], "abstain": {"abstain": False}}}
            if "validate_retrieved_claims" in tool_name:
                return {"ok": True, "claim_results": [{"claim_id": "C1", "policy": {"policy": "factual_allowed"}, "abstain": {"abstain": False}, "resolved_anchors": [{"ref_id": "FAKE", "locator": "FAKE"}]}]}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("test", CuratorContext()))
        assert result["status"] == "abstain"

    def test_supported_answer_non_empty(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {"ok": True, "evidence_bundle": {"evidence_records": [{"chunk_id": "R1-F1", "ref_id": "REF-1", "payload_excerpt": "Energy consumption was 1.42 kWh/m3."}], "abstain": {"abstain": False}}}
            if "validate_retrieved_claims" in tool_name:
                return {"ok": True, "claim_results": [{"claim_id": "C1", "claim_text": "Energy consumption was 1.42 kWh/m3.", "policy": {"policy": "factual_allowed", "effective_confidence": "high"}, "abstain": {"abstain": False}, "resolved_anchors": [{"ref_id": "REF-1", "locator": "p.1"}]}]}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("test", CuratorContext()))
        assert result["status"] == "answered"
        assert result.get("answer", "") != ""
        assert "1.42" in result["answer"]


class TestMcpBoundary:
    def test_exactly_four(self):
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        from system.composition import compose_system_runtime, CuratorDependencies

        bundle = create_si2b_provider_bundle()
        curator_raw = bundle["curator"]
        deps = CuratorDependencies(repository=curator_raw["repository"], ontology=curator_raw["ontology"], mechanism_validator=curator_raw["mechanism_validator"], provider_identity=curator_raw["provider_identity"])
        rt = compose_system_runtime(curator_deps=deps, evidence_deps=None)
        from knowledge_curator.mcp_server.app import create_mcp_server
        server = create_mcp_server(runtime=rt.curator_runtime, evidence_runtime=rt.evidence_runtime)
        tool_names = set(server._tool_manager._tools.keys()) if hasattr(server, "_tool_manager") else set()
        assert tool_names == {"curate_assertion_set", "knowledge_curator_health", "retrieve_evidence", "validate_retrieved_claims"}


class TestProductionBoundary:
    def test_no_fixture_imports_in_shipped_runtime(self):
        text = (ROOT / "system" / "curator_agent_bridge_stdio.py").read_text(encoding="utf-8-sig")
        assert "integration.system.fixtures" not in text
        text2 = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "integration.system.fixtures" not in text2

    def test_no_temp_source_generation(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "_bridge_call.py" not in text
        assert "writeFileSync" not in text
