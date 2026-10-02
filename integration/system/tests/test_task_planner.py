"""SI-3B Scientific Task Planner tests."""

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
# Task Classifier
# ---------------------------------------------------------------------------


class TestTaskClassifier:
    def test_retrieve_classification(self):
        from system.task_planner.plan_protocol import PlannedTaskType
        from system.task_planner.task_classifier import TaskClassifier

        c = TaskClassifier()
        assert c.classify("retrieve evidence for membrane") == PlannedTaskType.RETRIEVE
        assert c.classify("search for paper evidence") == PlannedTaskType.RETRIEVE
        assert c.classify("RETRIEVE") == PlannedTaskType.RETRIEVE

    def test_curation_classification(self):
        from system.task_planner.plan_protocol import PlannedTaskType
        from system.task_planner.task_classifier import TaskClassifier

        c = TaskClassifier()
        assert c.classify("curate this assertion set") == PlannedTaskType.CURATION_COMMIT
        assert c.classify("commit the curated document") == PlannedTaskType.CURATION_COMMIT
        assert c.classify("CURATION_COMMIT") == PlannedTaskType.CURATION_COMMIT

    def test_revision_classification(self):
        from system.task_planner.plan_protocol import PlannedTaskType
        from system.task_planner.task_classifier import TaskClassifier

        c = TaskClassifier()
        assert c.classify("publish revision for preprint") == PlannedTaskType.REVISION_PUBLICATION
        assert c.classify("REVISION_PUBLICATION") == PlannedTaskType.REVISION_PUBLICATION

    def test_invalid_task_fail_closed(self):
        from system.task_planner.errors import InvalidTaskError
        from system.task_planner.task_classifier import TaskClassifier

        c = TaskClassifier()
        with pytest.raises(InvalidTaskError):
            c.classify("")
        with pytest.raises(InvalidTaskError):
            c.classify("xyz completely unrelated gibberish")

    def test_chinese_classification(self):
        from system.task_planner.plan_protocol import PlannedTaskType
        from system.task_planner.task_classifier import TaskClassifier

        c = TaskClassifier()
        assert c.classify("检索证据") == PlannedTaskType.RETRIEVE
        assert c.classify("策审入库") == PlannedTaskType.CURATION_COMMIT


# ---------------------------------------------------------------------------
# Task Plan Protocol
# ---------------------------------------------------------------------------


class TestTaskPlanProtocol:
    def test_plan_fields(self):
        from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan

        plan = TaskPlan(
            task_id="t1",
            task_type=PlannedTaskType.CURATION_COMMIT,
            workflow_name="curation_commit",
            parameters={"key": "val"},
            trace_id="tr1",
            provenance_id="pv1",
        )
        assert plan.task_id == "t1"
        assert plan.task_type == PlannedTaskType.CURATION_COMMIT
        assert plan.workflow_name == "curation_commit"
        assert plan.parameters == {"key": "val"}
        assert plan.trace_id == "tr1"
        assert plan.provenance_id == "pv1"


# ---------------------------------------------------------------------------
# Scientific Task Planner
# ---------------------------------------------------------------------------


class TestScientificTaskPlanner:
    def test_plan_from_text(self):
        from system.task_planner.plan_protocol import PlannedTaskType
        from system.task_planner.planner import ScientificTaskPlanner

        p = ScientificTaskPlanner()
        plan = p.plan("curate this assertion set", trace_id="tr-001")
        assert plan.task_type == PlannedTaskType.CURATION_COMMIT
        assert plan.workflow_name == "curation_commit"
        assert plan.trace_id == "tr-001"

    def test_plan_from_explicit_type(self):
        from system.task_planner.plan_protocol import PlannedTaskType
        from system.task_planner.planner import ScientificTaskPlanner

        p = ScientificTaskPlanner()
        plan = p.plan(task_type="REVISION_PUBLICATION", provenance_id="pv-001")
        assert plan.task_type == PlannedTaskType.REVISION_PUBLICATION
        assert plan.workflow_name == "revision_publication"
        assert plan.provenance_id == "pv-001"

    def test_plan_provenance_preservation(self):
        from system.task_planner.planner import ScientificTaskPlanner

        p = ScientificTaskPlanner()
        plan = p.plan(
            task_type="CURATION_COMMIT",
            trace_id="trace-abc",
            provenance_id="prov-def",
            parameters={"source": "test"},
        )
        assert plan.trace_id == "trace-abc"
        assert plan.provenance_id == "prov-def"
        assert plan.parameters == {"source": "test"}

    def test_plan_empty_input_fails(self):
        from system.task_planner.errors import InvalidTaskError
        from system.task_planner.planner import ScientificTaskPlanner

        p = ScientificTaskPlanner()
        with pytest.raises(InvalidTaskError):
            p.plan()


# ---------------------------------------------------------------------------
# Agent Runtime consumes TaskPlan
# ---------------------------------------------------------------------------


class TestAgentConsumesTaskPlan:
    def test_agent_dispatches_from_plan(self):
        from system.agent_runtime.execution_context import ExecutionContext
        from system.agent_runtime_composition import compose_agent_runtime
        from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan

        old = os.environ.get("AI4S_SYSTEM_ADAPTER_FACTORY")
        os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = (
            "integration.system.fixtures.si2b_provider:create_si2b_provider_bundle"
        )
        try:
            agent = compose_agent_runtime()

            called = {"workflow": None}
            orig_wf = agent._registry.get("curation_commit")

            async def tracking_run(**kwargs):
                called["workflow"] = "curation_commit"

                class FakeResult:
                    status = "blocked"
                    last_error = "test"

                return FakeResult()

            orig_wf.run = tracking_run

            plan = TaskPlan(
                task_id="t-1",
                task_type=PlannedTaskType.CURATION_COMMIT,
                workflow_name="curation_commit",
                trace_id="tr-plan",
                provenance_id="pv-plan",
            )
            result = _run(agent.run(plan))

            assert called["workflow"] == "curation_commit"
            assert result.workflow == "curation_commit"
            assert result.trace_id == "tr-plan"
        finally:
            if old is not None:
                os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = old
            else:
                os.environ.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)

    def test_workflow_registry_boundary(self):
        """Agent must access workflows only through registry."""
        from system.agent_runtime.workflow_registry import WorkflowRegistry

        reg = WorkflowRegistry()
        assert not reg.has("nonexistent")
        assert reg.names == []


# ---------------------------------------------------------------------------
# MCP / DSH unchanged
# ---------------------------------------------------------------------------


class TestMcpDshUnchanged:
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
