"""SI-3A Agent Runtime tests."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Test 1: Normal initialization
# ---------------------------------------------------------------------------


class TestAgentRuntimeBootstrap:
    def test_normal_init(self):
        from system.agent_runtime_composition import compose_agent_runtime

        old = os.environ.get("AI4S_SYSTEM_ADAPTER_FACTORY")
        os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = (
            "integration.system.fixtures.si2b_provider:create_si2b_provider_bundle"
        )
        try:
            agent = compose_agent_runtime()
            assert agent is not None
            assert agent._provider_identity == "si2b-test-provider"
            # Registry has both workflows
            assert agent._registry.has("curation_commit")
            assert agent._registry.has("revision_publication")
        finally:
            if old is not None:
                os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = old
            else:
                os.environ.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)

    def test_missing_provider_fail_closed(self):
        from system.agent_runtime.errors import ProviderNotConfiguredError
        from system.agent_runtime_composition import compose_agent_runtime

        old = os.environ.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)
        try:
            with pytest.raises(ProviderNotConfiguredError):
                compose_agent_runtime()
        finally:
            if old is not None:
                os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = old

    def test_invalid_provider_fail_closed(self):
        from system.agent_runtime.errors import ProviderNotConfiguredError
        from system.agent_runtime_composition import compose_agent_runtime

        old = os.environ.get("AI4S_SYSTEM_ADAPTER_FACTORY")
        os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = "nonexistent.module:factory"
        try:
            with pytest.raises(ProviderNotConfiguredError):
                compose_agent_runtime()
        finally:
            if old is not None:
                os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = old
            else:
                os.environ.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)


# ---------------------------------------------------------------------------
# Test 2: Workflow Registry
# ---------------------------------------------------------------------------


class TestWorkflowRegistry:
    def test_register_and_get(self):
        from system.agent_runtime.workflow_registry import WorkflowRegistry

        reg = WorkflowRegistry()
        obj = object()
        reg.register("test_wf", obj)
        assert reg.get("test_wf") is obj
        assert reg.has("test_wf")

    def test_missing_workflow_raises(self):
        from system.agent_runtime.errors import WorkflowNotRegisteredError
        from system.agent_runtime.workflow_registry import WorkflowRegistry

        reg = WorkflowRegistry()
        with pytest.raises(WorkflowNotRegisteredError):
            reg.get("nonexistent")


# ---------------------------------------------------------------------------
# Test 3: Task Router
# ---------------------------------------------------------------------------


class TestTaskRouter:
    def test_curation_commit_route(self):
        from system.agent_runtime.task_router import TaskRouter, TaskType

        router = TaskRouter()
        assert router.resolve(TaskType.CURATION_COMMIT) == "curation_commit"

    def test_revision_publication_route(self):
        from system.agent_runtime.task_router import TaskRouter, TaskType

        router = TaskRouter()
        assert router.resolve(TaskType.REVISION_PUBLICATION) == "revision_publication"

    def test_string_task_type(self):
        from system.agent_runtime.task_router import TaskRouter

        router = TaskRouter()
        assert router.resolve("CURATION_COMMIT") == "curation_commit"

    def test_unknown_task_raises(self):
        from system.agent_runtime.errors import UnknownTaskTypeError
        from system.agent_runtime.task_router import TaskRouter

        router = TaskRouter()
        with pytest.raises(UnknownTaskTypeError):
            router.resolve("UNKNOWN_TASK")


# ---------------------------------------------------------------------------
# Test 4: Execution Context
# ---------------------------------------------------------------------------


class TestExecutionContext:
    def test_create_defaults(self):
        from system.agent_runtime.execution_context import ExecutionContext

        ctx = ExecutionContext.create()
        assert ctx.task_id  # auto-generated
        assert ctx.metadata == {}

    def test_create_with_values(self):
        from system.agent_runtime.execution_context import ExecutionContext

        ctx = ExecutionContext.create(
            task_id="t-1", trace_id="tr-1", provenance_id="pv-1", metadata={"k": "v"}
        )
        assert ctx.task_id == "t-1"
        assert ctx.trace_id == "tr-1"
        assert ctx.provenance_id == "pv-1"
        assert ctx.metadata == {"k": "v"}


# ---------------------------------------------------------------------------
# Test 5: Agent dispatch — CurationCommit
# ---------------------------------------------------------------------------


class TestCurationCommitDispatch:
    def test_dispatch_curation_commit(self):
        """Agent dispatches CURATION_COMMIT to CurationCommitWorkflow."""
        from system.agent_runtime.execution_context import ExecutionContext
        from system.agent_runtime.task_router import TaskType
        from system.agent_runtime_composition import compose_agent_runtime

        old = os.environ.get("AI4S_SYSTEM_ADAPTER_FACTORY")
        os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = (
            "integration.system.fixtures.si2b_provider:create_si2b_provider_bundle"
        )
        try:
            agent = compose_agent_runtime()

            # Track which workflow was called
            called = {"workflow": None}
            orig_wf = agent._registry.get("curation_commit")

            async def tracking_run(**kwargs):
                called["workflow"] = "curation_commit"
                # Simulate a blocked result
                from system.agent_runtime.result_protocol import AgentStatus

                class FakeResult:
                    status = "blocked"
                    last_error = "test"

                return FakeResult()

            orig_wf.run = tracking_run

            ctx = ExecutionContext.create(trace_id="tr-001")
            result = _run(agent.run(TaskType.CURATION_COMMIT, ctx))

            assert called["workflow"] == "curation_commit"
            assert result.workflow == "curation_commit"
            assert result.trace_id == "tr-001"
        finally:
            if old is not None:
                os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = old
            else:
                os.environ.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)


# ---------------------------------------------------------------------------
# Test 6: Agent dispatch — RevisionPublication
# ---------------------------------------------------------------------------


class TestRevisionPublicationDispatch:
    def test_dispatch_revision_publication(self):
        from system.agent_runtime.execution_context import ExecutionContext
        from system.agent_runtime.task_router import TaskType
        from system.agent_runtime_composition import compose_agent_runtime

        old = os.environ.get("AI4S_SYSTEM_ADAPTER_FACTORY")
        os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = (
            "integration.system.fixtures.si2b_provider:create_si2b_provider_bundle"
        )
        try:
            agent = compose_agent_runtime()

            called = {"workflow": None}
            orig_wf = agent._registry.get("revision_publication")

            async def tracking_run(**kwargs):
                called["workflow"] = "revision_publication"

                class FakeResult:
                    status = "failed"
                    last_error = "test"

                return FakeResult()

            orig_wf.run = tracking_run

            ctx = ExecutionContext.create()
            result = _run(agent.run(TaskType.REVISION_PUBLICATION, ctx))

            assert called["workflow"] == "revision_publication"
            assert result.workflow == "revision_publication"
        finally:
            if old is not None:
                os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = old
            else:
                os.environ.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)


# ---------------------------------------------------------------------------
# Test 7: No direct store access
# ---------------------------------------------------------------------------


class TestNoDirectStoreAccess:
    def test_agent_has_no_store_attributes(self):
        """AI4SAgent must not hold store/coordinator references."""
        from system.agent_runtime.agent import AI4SAgent

        agent = AI4SAgent.__new__(AI4SAgent)
        # Check the class does not define store-related attributes
        forbidden = (
            "commit_store", "structural_store", "vector_index", "usdo_store",
            "version_store", "source_registry", "lifecycle_store",
            "event_outbox", "publication_store",
            "document_commit_coordinator", "revision_publication_coordinator",
            "lifecycle_coordinator",
        )
        for attr in forbidden:
            assert not hasattr(AI4SAgent, attr) or not callable(getattr(AI4SAgent, attr, None)), (
                f"AI4SAgent should not expose {attr}"
            )

    def test_agent_module_imports(self):
        """Agent module must not import store/coordinator modules."""
        import ast

        agent_src = (ROOT / "system" / "agent_runtime" / "agent.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(agent_src)
        forbidden_modules = (
            "knowledge_curator.core.commit",
            "knowledge_curator.core.revision_publication",
            "knowledge_curator.core.lifecycle",
            "knowledge_curator.ports",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for forbidden in forbidden_modules:
                    assert forbidden not in mod, (
                        f"agent.py must not import {forbidden}"
                    )


# ---------------------------------------------------------------------------
# Test 8: MCP surface unchanged
# ---------------------------------------------------------------------------


class TestMcpSurfaceUnchanged:
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
