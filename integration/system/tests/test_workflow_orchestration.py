"""SI-4 Workflow Orchestration tests."""

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
# Test 1: Single workflow plan
# ---------------------------------------------------------------------------


class TestSingleWorkflowPlan:
    def test_retrieve_plan_one_step(self):
        from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan
        from system.workflow_orchestration.planner import WorkflowPlanner

        task = TaskPlan(
            task_id="t1",
            task_type=PlannedTaskType.RETRIEVE,
            workflow_name="retrieve",
            trace_id="tr-1",
        )
        plan = WorkflowPlanner().plan_from_task(task)
        assert len(plan.steps) == 1
        assert plan.steps[0].workflow_name == "retrieve"
        assert plan.trace_id == "tr-1"


# ---------------------------------------------------------------------------
# Test 2: Multi-step plan
# ---------------------------------------------------------------------------


class TestMultiStepPlan:
    def test_curation_plan_three_steps(self):
        from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan
        from system.workflow_orchestration.planner import WorkflowPlanner

        task = TaskPlan(
            task_id="t2",
            task_type=PlannedTaskType.CURATION_COMMIT,
            workflow_name="curation_commit",
        )
        plan = WorkflowPlanner().plan_from_task(task)
        assert len(plan.steps) == 3
        names = [s.workflow_name for s in plan.steps]
        assert names == ["retrieve", "curation", "commit"]

    def test_revision_plan_one_step(self):
        from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan
        from system.workflow_orchestration.planner import WorkflowPlanner

        task = TaskPlan(
            task_id="t3",
            task_type=PlannedTaskType.REVISION_PUBLICATION,
            workflow_name="revision_publication",
        )
        plan = WorkflowPlanner().plan_from_task(task)
        assert len(plan.steps) == 1
        assert plan.steps[0].workflow_name == "revision"


# ---------------------------------------------------------------------------
# Test 3: Execution order
# ---------------------------------------------------------------------------


class TestExecutionOrder:
    def test_steps_execute_in_dependency_order(self):
        from system.agent_runtime.workflow_registry import WorkflowRegistry
        from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan
        from system.workflow_orchestration.executor import WorkflowExecutor
        from system.workflow_orchestration.planner import WorkflowPlanner

        execution_log = []

        class TrackingWorkflow:
            def __init__(self, name):
                self._name = name

            async def run(self, **kwargs):
                execution_log.append(self._name)
                return {"status": "ok", "name": self._name}

        registry = WorkflowRegistry()
        registry.register("retrieve", TrackingWorkflow("retrieve"))
        registry.register("curation", TrackingWorkflow("curation"))
        registry.register("commit", TrackingWorkflow("commit"))

        task = TaskPlan(task_id="t", task_type=PlannedTaskType.CURATION_COMMIT, workflow_name="curation_commit")
        plan = WorkflowPlanner().plan_from_task(task)

        state = _run(WorkflowExecutor(registry).execute(plan))
        assert state.status.value == "COMPLETED"
        assert execution_log == ["retrieve", "curation", "commit"]


# ---------------------------------------------------------------------------
# Test 4: Failure handling
# ---------------------------------------------------------------------------


class TestFailureHandling:
    def test_mid_failure_stops(self):
        from system.agent_runtime.workflow_registry import WorkflowRegistry
        from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan
        from system.workflow_orchestration.execution_plan import StepStatus
        from system.workflow_orchestration.executor import WorkflowExecutor
        from system.workflow_orchestration.planner import WorkflowPlanner
        from system.workflow_orchestration.state import ExecutionStatus

        execution_log = []

        class FailingWorkflow:
            def __init__(self, name, fail=False):
                self._name = name
                self._fail = fail

            async def run(self, **kwargs):
                execution_log.append(self._name)
                if self._fail:
                    raise RuntimeError("injected failure")
                return {"ok": True}

        registry = WorkflowRegistry()
        registry.register("retrieve", FailingWorkflow("retrieve"))
        registry.register("curation", FailingWorkflow("curation", fail=True))
        registry.register("commit", FailingWorkflow("commit"))

        task = TaskPlan(task_id="t", task_type=PlannedTaskType.CURATION_COMMIT, workflow_name="curation_commit")
        plan = WorkflowPlanner().plan_from_task(task)

        state = _run(WorkflowExecutor(registry).execute(plan))
        assert state.status == ExecutionStatus.FAILED
        assert "curation" in (state.error or "")
        # commit should NOT have executed
        assert "commit" not in execution_log


# ---------------------------------------------------------------------------
# Test 5: Resume
# ---------------------------------------------------------------------------


class TestResume:
    def test_resume_skips_completed(self):
        from system.agent_runtime.workflow_registry import WorkflowRegistry
        from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan
        from system.workflow_orchestration.execution_plan import StepStatus
        from system.workflow_orchestration.executor import WorkflowExecutor
        from system.workflow_orchestration.planner import WorkflowPlanner
        from system.workflow_orchestration.state import ExecutionStatus

        execution_log = []

        class TrackingWorkflow:
            def __init__(self, name):
                self._name = name

            async def run(self, **kwargs):
                execution_log.append(self._name)
                return {"ok": True}

        registry = WorkflowRegistry()
        registry.register("retrieve", TrackingWorkflow("retrieve"))
        registry.register("curation", TrackingWorkflow("curation"))
        registry.register("commit", TrackingWorkflow("commit"))

        task = TaskPlan(task_id="t", task_type=PlannedTaskType.CURATION_COMMIT, workflow_name="curation_commit")
        plan = WorkflowPlanner().plan_from_task(task)

        # Mark first two as completed (simulating prior partial run)
        plan.steps[0].status = StepStatus.COMPLETED
        plan.steps[1].status = StepStatus.COMPLETED

        state = _run(WorkflowExecutor(registry).execute(plan))
        assert state.status == ExecutionStatus.COMPLETED
        # Only commit executed (retrieve and curation were skipped)
        assert execution_log == ["commit"]


# ---------------------------------------------------------------------------
# Test 6: State persistence
# ---------------------------------------------------------------------------


class TestStatePersistence:
    def test_state_tracks_progress(self):
        from system.agent_runtime.workflow_registry import WorkflowRegistry
        from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan
        from system.workflow_orchestration.executor import WorkflowExecutor
        from system.workflow_orchestration.planner import WorkflowPlanner
        from system.workflow_orchestration.state import ExecutionState, ExecutionStatus

        class OKWorkflow:
            async def run(self, **kwargs):
                return {"ok": True}

        registry = WorkflowRegistry()
        registry.register("retrieve", OKWorkflow())
        registry.register("curation", OKWorkflow())
        registry.register("commit", OKWorkflow())

        task = TaskPlan(task_id="t", task_type=PlannedTaskType.CURATION_COMMIT, workflow_name="curation_commit")
        plan = WorkflowPlanner().plan_from_task(task)

        state = _run(WorkflowExecutor(registry).execute(plan))
        assert isinstance(state, ExecutionState)
        assert state.status == ExecutionStatus.COMPLETED
        assert len(state.completed_step_ids) == 3
        assert state.error is None
        assert len(state.step_results) == 3

    def test_state_persists_error(self):
        from system.agent_runtime.workflow_registry import WorkflowRegistry
        from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan
        from system.workflow_orchestration.executor import WorkflowExecutor
        from system.workflow_orchestration.planner import WorkflowPlanner
        from system.workflow_orchestration.state import ExecutionStatus

        class FailWorkflow:
            async def run(self, **kwargs):
                raise ValueError("boom")

        registry = WorkflowRegistry()
        registry.register("retrieve", FailWorkflow())

        task = TaskPlan(task_id="t", task_type=PlannedTaskType.RETRIEVE, workflow_name="retrieve")
        plan = WorkflowPlanner().plan_from_task(task)

        state = _run(WorkflowExecutor(registry).execute(plan))
        assert state.status == ExecutionStatus.FAILED
        assert "boom" in (state.error or "")


# ---------------------------------------------------------------------------
# Test 7: No bypass
# ---------------------------------------------------------------------------


class TestNoBypass:
    def test_orchestrator_no_direct_store_access(self):
        """AST: orchestrator modules must not import store/coordinator modules."""
        import ast

        for fname in ("executor.py", "planner.py"):
            src = (ROOT / "system" / "workflow_orchestration" / fname).read_text(encoding="utf-8-sig")
            tree = ast.parse(src)
            forbidden = (
                "knowledge_curator.core.commit",
                "knowledge_curator.core.revision_publication",
                "knowledge_curator.core.lifecycle",
                "knowledge_curator.ports",
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for f in forbidden:
                        assert f not in mod, f"{fname} must not import {f}"

    def test_executor_only_uses_registry(self):
        """Executor must access workflows through WorkflowRegistry only."""
        import ast

        src = (ROOT / "system" / "workflow_orchestration" / "executor.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "knowledge_curator" not in mod, "executor must not import knowledge_curator"


# ---------------------------------------------------------------------------
# Test 8: MCP boundary
# ---------------------------------------------------------------------------


class TestMcpBoundary:
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
# Agent Runtime integration
# ---------------------------------------------------------------------------


class TestAgentIntegration:
    def test_agent_run_orchestrated(self):
        from system.agent_runtime.execution_context import ExecutionContext
        from system.agent_runtime.workflow_registry import WorkflowRegistry
        from system.agent_runtime.agent import AI4SAgent
        from system.agent_runtime.task_router import TaskRouter
        from system.task_planner.plan_protocol import PlannedTaskType, TaskPlan

        class OKWorkflow:
            async def run(self, **kwargs):
                return {"status": "ok"}

        registry = WorkflowRegistry()
        registry.register("retrieve", OKWorkflow())
        registry.register("curation", OKWorkflow())
        registry.register("commit", OKWorkflow())

        agent = AI4SAgent(router=TaskRouter(), registry=registry)

        task_plan = TaskPlan(
            task_id="t-1",
            task_type=PlannedTaskType.CURATION_COMMIT,
            workflow_name="curation_commit",
            trace_id="tr-integ",
        )
        result = _run(agent.run_orchestrated(task_plan))
        assert result.status.value == "success"
        assert "orchestrated" in result.workflow
        assert result.trace_id == "tr-integ"
        assert len(result.artifacts.get("completed_steps", [])) == 3
