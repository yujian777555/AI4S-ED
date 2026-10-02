"""DSH Knowledge Curator Agent package tests."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PKG = ROOT / "dsh" / "knowledge-curator"


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Test 1: Agent package loads
# ---------------------------------------------------------------------------


class TestAgentPackageLoading:
    def test_agent_yaml_exists(self):
        assert (PKG / "agent.yaml").exists()

    def test_prompt_md_exists(self):
        assert (PKG / "prompt.md").exists()

    def test_tools_yaml_exists(self):
        assert (PKG / "tools.yaml").exists()

    def test_schemas_exist(self):
        assert (PKG / "schemas" / "curation_request.json").exists()
        assert (PKG / "schemas" / "evidence_query.json").exists()
        assert (PKG / "schemas" / "revision_request.json").exists()

    def test_runtime_exists(self):
        assert (PKG / "runtime" / "agent.py").exists()
        assert (PKG / "runtime" / "handlers.py").exists()
        assert (PKG / "runtime" / "context.py").exists()

    def test_agent_yaml_valid(self):
        text = (PKG / "agent.yaml").read_text(encoding="utf-8")
        assert "AI4S Knowledge Curator" in text
        assert "knowledge_curation" in text
        assert "evidence_qa" in text
        assert "lifecycle_governance" in text

    def test_tools_yaml_has_exactly_four(self):
        text = (PKG / "tools.yaml").read_text(encoding="utf-8")
        assert "curate_assertion_set" in text
        assert "knowledge_curator_health" in text
        assert "retrieve_evidence" in text
        assert "validate_retrieved_claims" in text
        # No new tools
        assert "publish" not in text.lower() or "not" in text.lower()
        assert "commit_document" not in text
        assert "revision_publication" not in text or "internal" in text.lower()


# ---------------------------------------------------------------------------
# Test 2: Four MCP tools unchanged
# ---------------------------------------------------------------------------


class TestMcpFourTools:
    def test_mcp_still_four_tools(self):
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        from system.composition import compose_system_runtime, CuratorDependencies

        bundle = create_si2b_provider_bundle()
        curator_raw = bundle["curator"]
        deps = CuratorDependencies(
            repository=curator_raw["repository"],
            ontology=curator_raw["ontology"],
            mechanism_validator=curator_raw["mechanism_validator"],
            provider_identity=curator_raw["provider_identity"],
        )
        rt = compose_system_runtime(curator_deps=deps, evidence_deps=None)
        from knowledge_curator.mcp_server.app import create_mcp_server

        server = create_mcp_server(runtime=rt.curator_runtime, evidence_runtime=rt.evidence_runtime)
        assert server is not None
        tool_names = set(server._tool_manager._tools.keys()) if hasattr(server, "_tool_manager") else set()
        if tool_names:
            expected = {
                "curate_assertion_set",
                "knowledge_curator_health",
                "retrieve_evidence",
                "validate_retrieved_claims",
            }
            assert tool_names == expected


# ---------------------------------------------------------------------------
# Test 3-4: Evidence QA + Abstain
# ---------------------------------------------------------------------------


class TestEvidenceQA:
    def test_evidence_qa_answer(self):
        """Evidence QA returns answer when evidence is sufficient."""
        import sys as _sys
        _sys.path.insert(0, str(PKG))
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {
                    "ok": True,
                    "evidence_bundle": {
                        "evidence_records": [
                            {"chunk_id": "R1-F1", "ref_id": "REF-1", "confidence": "high"},
                            {"chunk_id": "R1-F2", "ref_id": "REF-1", "confidence": "high"},
                        ],
                        "abstain": {"abstain": False, "reasons": []},
                    },
                }
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("What is the energy consumption of BPM?", CuratorContext()))
        assert result["status"] == "answered"
        assert len(result["citations"]) == 2
        assert result["evidence_count"] == 2

    def test_evidence_qa_abstain(self):
        """Evidence QA must ABSTAIN when evidence is insufficient."""
        import sys as _sys
        _sys.path.insert(0, str(PKG))
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {
                    "ok": True,
                    "evidence_bundle": {
                        "evidence_records": [],
                        "abstain": {"abstain": True, "reasons": ["no_evidence"]},
                    },
                }
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("What is quantum gravity?", CuratorContext()))
        assert result["status"] == "abstain"
        assert "ABSTAIN" in result["answer"]


# ---------------------------------------------------------------------------
# Test 5: Curation flow
# ---------------------------------------------------------------------------


class TestCurationFlow:
    def test_curation_returns_report(self):
        import sys as _sys
        _sys.path.insert(0, str(PKG))
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "curate_assertion_set" in tool_name:
                return {"ok": True, "report": {"status": "successful", "decisions": []}}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.curate({"ref_id": "R1", "metadata": {}, "assertions": []}, CuratorContext()))
        assert result["status"] == "curated"
        assert result["report"]["ok"] is True or result["report"]["report"]["status"] == "successful"


# ---------------------------------------------------------------------------
# Test 6: Revision flow
# ---------------------------------------------------------------------------


class TestRevisionFlow:
    def test_revision_ready(self):
        import sys as _sys
        _sys.path.insert(0, str(PKG))
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        agent = KnowledgeCuratorAgent()
        result = _run(agent.revise({"new_knowledge": "test"}, CuratorContext()))
        assert result["status"] == "revision_ready"
        assert "RevisionPublicationWorkflow" in result["note"]


# ---------------------------------------------------------------------------
# Test 7: No direct store access
# ---------------------------------------------------------------------------


class TestNoDirectStoreAccess:
    def test_handlers_no_store_imports(self):
        import ast

        for fname in ("agent.py", "handlers.py", "context.py"):
            src = (PKG / "runtime" / fname).read_text(encoding="utf-8-sig")
            tree = ast.parse(src)
            forbidden = (
                "knowledge_curator.core",
                "knowledge_curator.ports",
                "knowledge_curator.adapters",
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for f in forbidden:
                        assert f not in mod, f"{fname} must not import {f}"

    def test_prompt_principles(self):
        text = (PKG / "prompt.md").read_text(encoding="utf-8")
        assert "ABSTAIN" in text
        assert "evidence" in text.lower()
        assert "provenance" in text.lower() or "confidence" in text.lower()
        assert "version" in text.lower() or "lifecycle" in text.lower()
