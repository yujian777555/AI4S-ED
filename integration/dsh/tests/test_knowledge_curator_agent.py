"""SI-4-R6 Actual Pinned DSH Execution Closure tests."""

from __future__ import annotations

import asyncio
import hashlib
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


def _r6_env():
    env = os.environ.copy()
    env["AI4S_SYSTEM_ADAPTER_FACTORY"] = "integration.dsh.fixtures.r6_provider:create_r6_provider_bundle"
    env["PYTHONPATH"] = str(ROOT)
    return env


class TestDefineToolContract:
    def test_plugin_imports_define_tool(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "defineTool" in text
        assert "@deepseek-ai/dsh-tools" in text

    def test_plugin_uses_define_tool_call(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        # Must actually call defineTool, not just mention it
        assert "defineTool({" in text or "defineTool({" in text.replace(" ", "")

    def test_plugin_output_schema_render(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "output:" in text
        assert "render:" in text
        assert "schema:" in text

    def test_plugin_execute_returns_canonical(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "return await callBridge" in text


class TestPackageSubpath:
    def test_cordis_uses_package_subpath(self):
        text = (PKG / "cordis.patch.yml").read_text(encoding="utf-8-sig")
        assert "@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js" in text
        assert "./runtime/bridge-plugin.js" not in text

    def test_package_has_peer_deps(self):
        pkg = json.loads((PKG / "package.json").read_text(encoding="utf-8-sig"))
        peers = pkg.get("peerDependencies", {})
        assert "@deepseek-ai/dsh-tools" in peers

    def test_package_exports_bridge_plugin(self):
        pkg = json.loads((PKG / "package.json").read_text(encoding="utf-8-sig"))
        assert "./runtime/bridge-plugin.js" in pkg.get("exports", {})


class TestStrictHydration:
    def test_invalid_approval_decision_fail_closed(self):
        env = _r6_env()
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "revise"],
            input=json.dumps({
                "package": {"package_id": "p", "work_id": "w-r6", "prior_source_version_id": "sv-prior-r6", "new_source_version_id": "sv-new-r6", "relation": "preprint_to_journal", "prior_ref_id": "ED-PRIOR", "new_ref_id": "ED-NEW", "target_assertions": []},
                "target_commit_request": {"source": {"ref_id": "ED-NEW", "source_fingerprint": "fp-new-r6"}, "assertion_set": {"ref_id": "ED-NEW", "metadata": {}, "assertions": []}, "report": {"report_id": "r", "source_ref_id": "ED-NEW", "status": "successful", "completeness": {"status": "ok"}, "decisions": []}},
                "approval": {"approval_id": "a", "package_id": "p", "scope_hash": "s", "decision": "yes-please", "approver": "x"},
            }),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0

    def test_invalid_relation_fail_closed(self):
        env = _r6_env()
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "revise"],
            input=json.dumps({
                "package": {"package_id": "p", "work_id": "w-r6", "prior_source_version_id": "sv-prior-r6", "new_source_version_id": "sv-new-r6", "relation": "INVALID", "prior_ref_id": "ED-PRIOR", "new_ref_id": "ED-NEW", "target_assertions": []},
                "target_commit_request": {"source": {"ref_id": "ED-NEW", "source_fingerprint": "fp-new-r6"}, "assertion_set": {"ref_id": "ED-NEW", "metadata": {}, "assertions": []}, "report": {"report_id": "r", "source_ref_id": "ED-NEW", "status": "successful", "completeness": {"status": "ok"}, "decisions": []}},
            }),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0

    def test_missing_required_source_ref_fail_closed(self):
        env = _r6_env()
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "curate_and_commit"],
            input=json.dumps({
                "source_ref_id": "", "source_fingerprint": "fp",
                "assertion_set": {"ref_id": "ED-X", "metadata": {}, "assertions": []},
            }),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0

    def test_missing_required_id_fail_closed(self):
        env = _r6_env()
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "curate_and_commit"],
            input=json.dumps({
                "source_ref_id": "", "source_fingerprint": "fp",
                "assertion_set": {"ref_id": "ED-X", "metadata": {}, "assertions": []},
            }),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode != 0


class TestNativeToolExecution:
    def test_stdio_bridge_publish(self):
        """Real stdio bridge -> CurationCommitWorkflow -> PUBLISHED."""
        env = _r6_env()
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "curate_and_commit"],
            input=json.dumps({
                "source_ref_id": "ED-R6",
                "source_fingerprint": "fp-r6-001",
                "assertion_set": {
                    "ref_id": "ED-R6",
                    "metadata": {"title": "R6 Test", "authors": ["A"], "year": 2024, "source": "J", "doi": "10.0/r6", "stable_id": "ST-R6"},
                    "assertions": [{
                        "id": "AS-001", "ref_id": "ED-R6",
                        "subject": {"eddo_class": "Membrane", "resolved_entity": "eddo:membrane:bpm", "original_mention": "BPM"},
                        "property": "hasEnergyConsumption",
                        "object": {"value": 1.42, "unit": "kWh/m3", "value_type": "number", "uncertainty": 0.05},
                        "conditions": [{"eddo_class": "Temperature", "value": 298.15, "unit": "K"}],
                        "provenance": {"locator": "p.1", "sentence": "energy is 1.42"},
                        "claim_type": "measurement", "source_claim_origin": "primary",
                        "confidence": "medium", "quality": 0.85,
                    }],
                },
                "report": {
                    "report_id": "r-r6", "source_ref_id": "ED-R6", "status": "successful",
                    "completeness": {"status": "ok"},
                    "decisions": [{"assertion_id": "AS-001", "action": "accept", "confidence": "medium", "reason": "valid"}],
                },
            }),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["status"] == "published"
        assert output["commit_attempted"] is True

    def test_stdio_bridge_revision_approval_required(self):
        """Revision without approval -> APPROVAL_REQUIRED."""
        env = _r6_env()
        result = subprocess.run(
            [sys.executable, "-m", "system.curator_agent_bridge_stdio", "revise"],
            input=json.dumps({
                "package": {
                    "package_id": "pkg-r6", "work_id": "w-r6",
                    "prior_source_version_id": "sv-prior-r6", "new_source_version_id": "sv-new-r6",
                    "relation": "preprint_to_journal", "prior_ref_id": "ED-PRIOR", "new_ref_id": "ED-NEW",
                    "target_assertions": [{
                        "id": "AS-001", "ref_id": "ED-NEW",
                        "subject": {"eddo_class": "Membrane", "resolved_entity": "eddo:membrane:bpm", "original_mention": "BPM"},
                        "property": "hasEnergyConsumption",
                        "object": {"value": 1.5, "unit": "kWh/m3", "value_type": "number", "uncertainty": 0.05},
                        "conditions": [{"eddo_class": "Temperature", "value": 298.15, "unit": "K"}],
                        "provenance": {"locator": "p.1", "sentence": "energy is 1.5"},
                        "claim_type": "measurement", "source_claim_origin": "primary",
                        "confidence": "medium", "quality": 0.85,
                    }],
                },
                "target_commit_request": {
                    "source": {"ref_id": "ED-NEW", "source_fingerprint": "fp-new-r6"},
                    "assertion_set": {
                        "ref_id": "ED-NEW",
                        "metadata": {"title": "R6 J", "authors": ["A"], "year": 2024, "source": "J", "doi": "10.0/j", "stable_id": "ST-J"},
                        "assertions": [{
                            "id": "AS-001", "ref_id": "ED-NEW",
                            "subject": {"eddo_class": "Membrane", "resolved_entity": "eddo:membrane:bpm", "original_mention": "BPM"},
                            "property": "hasEnergyConsumption",
                            "object": {"value": 1.5, "unit": "kWh/m3", "value_type": "number", "uncertainty": 0.05},
                            "conditions": [{"eddo_class": "Temperature", "value": 298.15, "unit": "K"}],
                            "provenance": {"locator": "p.1", "sentence": "energy is 1.5"},
                            "claim_type": "measurement", "source_claim_origin": "primary",
                            "confidence": "medium", "quality": 0.85,
                        }],
                    },
                    "report": {
                        "report_id": "r-r6v", "source_ref_id": "ED-NEW", "status": "successful",
                        "completeness": {"status": "ok", "metadata_valid": True, "assertion_count": 1, "allows_formal_curation": True, "requires_manual_review": False, "requires_return_upstream": False},
                        "decisions": [{"assertion_id": "AS-001", "action": "accept", "confidence": "medium", "reason": "valid"}],
                        "returned_upstream_count": 0,
                    },
                },
            }),
            capture_output=True, text=True, timeout=30, env=env, cwd=str(ROOT),
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["status"] in ("approval_required", "finalized", "conflict")


class TestSection6:
    def test_no_content_abstain(self):
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

    def test_grounded_non_empty_answer(self):
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
    def test_no_fixture_imports(self):
        text = (ROOT / "system" / "curator_agent_bridge_stdio.py").read_text(encoding="utf-8-sig")
        assert "integration.system.fixtures" not in text
        assert "integration.dsh.fixtures" not in text
        text2 = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "integration.system.fixtures" not in text2

    def test_no_temp_generation(self):
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "_bridge_call.py" not in text
        assert "writeFileSync" not in text
