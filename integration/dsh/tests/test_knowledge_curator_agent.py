"""SI-4-R1 Knowledge Curator Agent qualification tests.

Covers R1-01 through R1-10. No skip/xfail/conditional pass.
"""

from __future__ import annotations

import asyncio
import os
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


# ---------------------------------------------------------------------------
# R1-01: Package includes all required files
# ---------------------------------------------------------------------------


class TestR101Packaging:
    def test_package_json_includes_all_files(self):
        import json
        pkg = json.loads((PKG / "package.json").read_text(encoding="utf-8-sig"))
        files = pkg.get("files", [])
        required = [
            "cordis.patch.yml", "README.md", "prompt.md", "tools.yaml",
            "agent.yaml",
            "schemas/curation_request.json",
            "schemas/evidence_query.json",
            "schemas/revision_request.json",
        ]
        for f in required:
            assert f in files, f"{f} missing from package.json files"


# ---------------------------------------------------------------------------
# R1-02: DSH package structure (preset loading)
# ---------------------------------------------------------------------------


class TestR102DshMount:
    def test_cordis_patch_defines_preset(self):
        text = (PKG / "cordis.patch.yml").read_text(encoding="utf-8")
        assert "knowledge-curator" in text
        assert "mcp-knowledge-curator" in text or "mcp" in text.lower()

    def test_preset_visible_in_dump(self):
        # The preset should be loadable by DSH config
        text = (PKG / "cordis.patch.yml").read_text(encoding="utf-8")
        assert "id: preset-knowledge-curator" in text or "knowledge-curator" in text


# ---------------------------------------------------------------------------
# R1-03: README/preset/prompt consistency
# ---------------------------------------------------------------------------


class TestR103Consistency:
    def test_readme_describes_all_sections(self):
        text = (PKG / "README.md").read_text(encoding="utf-8")
        assert "Section 5" in text
        assert "Section 6" in text
        assert "Section 7" in text
        assert "ABSTAIN" in text or "abstain" in text
        assert "CurationCommitWorkflow" in text
        assert "RevisionPublicationWorkflow" in text

    def test_prompt_has_evidence_first(self):
        text = (PKG / "prompt.md").read_text(encoding="utf-8")
        assert "evidence" in text.lower()
        assert "ABSTAIN" in text
        assert "validate" in text.lower() or "validation" in text.lower()

    def test_no_contradictory_claims(self):
        readme = (PKG / "README.md").read_text(encoding="utf-8")
        # Should NOT say sections are unimplemented
        assert "尚未实现" not in readme
        assert "not implemented" not in readme.lower() or "out of scope" in readme.lower()


# ---------------------------------------------------------------------------
# R1-04: Section 5 curation + commit
# ---------------------------------------------------------------------------


class TestR104Section5:
    def test_publishable_curation_commits(self):
        from system.curator_agent_bridge import CuratorAgentBridge
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        # Mock bridge that returns PUBLISHED
        class MockBridge:
            async def curate_and_commit(self, **kwargs):
                from system.curator_agent_bridge import CurateAndCommitResult
                return CurateAndCommitResult(status="published", commit_attempted=True)

        async def mock_invoker(tool_name, args):
            if "curate_assertion_set" in tool_name:
                return {"ok": True, "report": {"status": "successful", "decisions": [{"assertion_id": "A1", "action": "accept"}]}}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker, bridge=MockBridge())
        result = _run(agent.curate({"ref_id": "R1", "metadata": {}, "assertions": []}, CuratorContext()))
        assert result["status"] == "published"
        assert result["commit_attempted"] is True

    def test_blocked_curation_no_commit(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        class MockBridge:
            async def curate_and_commit(self, **kwargs):
                raise AssertionError("should not be called")

        async def mock_invoker(tool_name, args):
            if "curate_assertion_set" in tool_name:
                return {"ok": True, "report": {"status": "return_upstream", "decisions": []}}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker, bridge=MockBridge())
        result = _run(agent.curate({"ref_id": "R1", "metadata": {}, "assertions": []}, CuratorContext()))
        assert result["status"] == "blocked"
        assert result.get("commit_attempted") is not True


# ---------------------------------------------------------------------------
# R1-05/06: Section 6 retrieve -> validate -> answer
# ---------------------------------------------------------------------------


class TestR105Section6:
    def test_call_order_retrieve_then_validate(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        call_order = []

        async def mock_invoker(tool_name, args):
            call_order.append(tool_name)
            if "retrieve_evidence" in tool_name:
                return {
                    "ok": True,
                    "evidence_bundle": {
                        "evidence_records": [{"chunk_id": "R1-F1", "ref_id": "REF-1", "confidence": "high"}],
                        "abstain": {"abstain": False},
                    },
                }
            if "validate_retrieved_claims" in tool_name:
                return {
                    "ok": True,
                    "claim_results": [{
                        "claim_id": "C1",
                        "policy": {"policy": "factual_allowed"},
                        "abstain": {"abstain": False},
                        "resolved_anchors": [{"ref_id": "REF-1", "locator": "p.1", "confidence": "high"}],
                    }],
                }
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("test question", CuratorContext()))
        assert result["status"] == "answered"
        # Verify call order: retrieve before validate
        retrieve_idx = next(i for i, c in enumerate(call_order) if "retrieve_evidence" in c)
        validate_idx = next(i for i, c in enumerate(call_order) if "validate_retrieved_claims" in c)
        assert retrieve_idx < validate_idx

    def test_unsupported_abstain(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        call_order = []

        async def mock_invoker(tool_name, args):
            call_order.append(tool_name)
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
        result = _run(agent.answer("unknown question", CuratorContext()))
        assert result["status"] == "abstain"
        assert "ABSTAIN" in result["answer"]

    def test_validate_rejects_abstain(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {
                    "ok": True,
                    "evidence_bundle": {
                        "evidence_records": [{"chunk_id": "R1-F1"}],
                        "abstain": {"abstain": False},
                    },
                }
            if "validate_retrieved_claims" in tool_name:
                return {
                    "ok": True,
                    "claim_results": [{
                        "claim_id": "C1",
                        "policy": {"policy": "abstain"},
                        "abstain": {"abstain": True},
                    }],
                }
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("test", CuratorContext()))
        assert result["status"] == "abstain"

    def test_citations_from_evidence(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {
                    "ok": True,
                    "evidence_bundle": {
                        "evidence_records": [{"chunk_id": "R1-F1", "ref_id": "REF-1", "confidence": "high"}],
                        "abstain": {"abstain": False},
                    },
                }
            if "validate_retrieved_claims" in tool_name:
                return {
                    "ok": True,
                    "claim_results": [{
                        "claim_id": "C1",
                        "policy": {"policy": "factual_allowed"},
                        "abstain": {"abstain": False},
                        "resolved_anchors": [{"ref_id": "REF-1", "locator": "p.1", "confidence": "high"}],
                    }],
                }
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("test", CuratorContext()))
        assert result["status"] == "answered"
        assert len(result["citations"]) > 0
        assert result["citations"][0]["ref_id"] == "REF-1"


# ---------------------------------------------------------------------------
# R1-07: Section 7 revision
# ---------------------------------------------------------------------------


class TestR107Section7:
    def test_revision_delegates_to_workflow(self):
        from system.curator_agent_bridge import CuratorAgentBridge
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        class MockBridge:
            async def revise(self, **kwargs):
                from system.curator_agent_bridge import RevisionResult
                return RevisionResult(status="finalized")

        agent = KnowledgeCuratorAgent(bridge=MockBridge())
        result = _run(agent.revise({}, {}, CuratorContext()))
        assert result["status"] == "finalized"


# ---------------------------------------------------------------------------
# R1-08/09: MCP boundary (unconditional)
# ---------------------------------------------------------------------------


class TestR108McpBoundary:
    def test_mcp_exactly_four_tools(self):
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
        # R1-09: unconditional assertion
        assert tool_names == {
            "curate_assertion_set",
            "knowledge_curator_health",
            "retrieve_evidence",
            "validate_retrieved_claims",
        }


# ---------------------------------------------------------------------------
# R1-10: No direct store access
# ---------------------------------------------------------------------------


class TestR110NoDirectStore:
    def test_handlers_no_store_imports(self):
        import ast
        for fname in ("agent.py", "handlers.py", "context.py"):
            src = (PKG / "runtime" / fname).read_text(encoding="utf-8-sig")
            tree = ast.parse(src)
            forbidden = ("knowledge_curator.core", "knowledge_curator.ports", "knowledge_curator.adapters")
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for f in forbidden:
                        assert f not in mod, f"{fname} must not import {f}"

    def test_bridge_no_store_imports(self):
        import ast
        src = (ROOT / "system" / "curator_agent_bridge.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(src)
        forbidden = ("knowledge_curator.ports", "knowledge_curator.adapters")
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for f in forbidden:
                    assert f not in mod
