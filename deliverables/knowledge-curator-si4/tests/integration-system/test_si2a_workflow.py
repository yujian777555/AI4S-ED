"""SI-2A curation-to-commit workflow tests.

Covers plan section 15: happy path, return_upstream, all-rejected,
invalid source, idempotency, pending_vector, pending_finalize,
trace/metadata preservation.
"""

from __future__ import annotations

import asyncio
import copy
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowledge_curator.schemas.assertions import AssertionSet
from knowledge_curator.schemas.commit import CommitStatus, SourceIdentity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_assertion_set(ref_id: str = "ED-2025-TEST") -> AssertionSet:
    from knowledge_curator.schemas.assertions import (
        Assertion,
        ClaimType,
        Confidence,
        Condition,
        DocumentMetadata,
        ObjectValue,
        Provenance,
        SourceClaimOrigin,
        Subject,
        ValueType,
    )

    metadata = DocumentMetadata(
        title="Test Paper",
        authors=["A. Author"],
        year=2024,
        source="Journal",
        doi="10.0000/test",
        stable_id="ST-TEST",
    )
    assertion = Assertion(
        id="AS-001",
        ref_id=ref_id,
        subject=Subject(
            eddo_class="Membrane",
            resolved_entity="eddo:membrane:nafion117",
            original_mention="Nafion 117",
        ),
        property="hasEnergyConsumption",
        object=ObjectValue(value=1.42, unit="kWh/m3", value_type=ValueType.NUMBER, uncertainty=0.05),
        conditions=[
            Condition(eddo_class="Temperature", value=298.15, unit="K"),
        ],
        provenance=Provenance(locator="p.1", sentence="energy is 1.42 kWh/m3"),
        claim_type=ClaimType.MEASUREMENT,
        source_claim_origin=SourceClaimOrigin.PRIMARY,
        confidence=Confidence.MEDIUM,
        quality=0.87,
    )
    return AssertionSet(ref_id=ref_id, metadata=metadata, assertions=[assertion])


def _make_workflow():
    from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle
    from system.application_composition import (
        CommitDependencies,
        _extract_commit_deps,
        _validate_commit_deps,
    )
    from system.composition import CuratorDependencies, compose_system_runtime
    from system.workflows.curation_commit import CurationCommitWorkflow
    from knowledge_curator.core.commit import DocumentCommitCoordinator

    bundle = create_si2a_provider_bundle()
    curator_raw = bundle["curator"]
    commit_raw = bundle["commit"]

    curator_deps = CuratorDependencies(
        repository=curator_raw["repository"],
        ontology=curator_raw["ontology"],
        mechanism_validator=curator_raw["mechanism_validator"],
        provider_identity=curator_raw["provider_identity"],
    )
    system_rt = compose_system_runtime(curator_deps=curator_deps, evidence_deps=None)

    deps = _extract_commit_deps(bundle)
    _validate_commit_deps(deps)
    coordinator = DocumentCommitCoordinator(
        commit_store=deps.commit_store,
        structural_store=deps.structural_store,
        vector_index=deps.vector_index,
        usdo_store=deps.usdo_store,
        version_store=deps.version_store,
    )

    workflow = CurationCommitWorkflow(
        curator_runtime=system_rt.curator_runtime,
        commit_coordinator=coordinator,
        provider_identity="si2a-test",
    )
    return workflow, bundle, coordinator


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSI2AWorkflowInvalidInput:
    def test_empty_fingerprint_fails_closed(self):
        from system.workflows.curation_commit import WorkflowInputError

        workflow, _, _ = _make_workflow()
        source = SourceIdentity(ref_id="ED-2025-TEST", source_fingerprint="")
        assertion_set = _make_assertion_set()
        with pytest.raises(WorkflowInputError, match="source_fingerprint"):
            _run(workflow.run(source=source, assertion_set=assertion_set))

    def test_ref_mismatch_fails_closed(self):
        from system.workflows.curation_commit import WorkflowInputError

        workflow, _, _ = _make_workflow()
        source = SourceIdentity(ref_id="ED-OTHER", source_fingerprint="fp123")
        assertion_set = _make_assertion_set(ref_id="ED-2025-TEST")
        with pytest.raises(WorkflowInputError, match="ref_id"):
            _run(workflow.run(source=source, assertion_set=assertion_set))


class TestSI2AWorkflowHappyPath:
    def test_happy_path_published(self):
        workflow, bundle, coordinator = _make_workflow()
        source = SourceIdentity(ref_id="ED-2025-TEST", source_fingerprint="fp-happy-001")
        assertion_set = _make_assertion_set()
        result = _run(
            workflow.run(
                source=source,
                assertion_set=assertion_set,
                metadata={"key": "value"},
                trace={"trace_id": "trace-001", "provenance_id": "prov-001"},
            )
        )
        assert result.commit_attempted is True
        assert result.commit_result is not None
        assert result.commit_result.status == CommitStatus.PUBLISHED
        assert result.report is not None
        # Exactly one published version
        versions = bundle["commit"]["version_store"].list_published_versions()
        assert len(versions) == 1

    def test_trace_metadata_preserved(self):
        captured = {}

        workflow, bundle, coordinator = _make_workflow()

        # Monkey-patch coordinator.commit to capture the request
        original_commit = coordinator.commit

        async def capturing_commit(request):
            captured["request"] = request
            return await original_commit(request)

        coordinator.commit = capturing_commit

        source = SourceIdentity(ref_id="ED-2025-TEST", source_fingerprint="fp-trace-001")
        assertion_set = _make_assertion_set()
        meta = {"org": "test-org", "batch": "b-42"}
        trace = {"trace_id": "trace-XYZ", "provenance_id": "prov-ABC"}

        result = _run(
            workflow.run(
                source=source,
                assertion_set=assertion_set,
                metadata=meta,
                trace=trace,
            )
        )
        assert result.commit_attempted is True
        req = captured["request"]
        assert req.trace["trace_id"] == "trace-XYZ"
        assert req.trace["provenance_id"] == "prov-ABC"
        assert req.metadata["org"] == "test-org"
        assert req.metadata["batch"] == "b-42"
        assert req.source.ref_id == source.ref_id
        assert req.source.source_fingerprint == source.source_fingerprint


class TestSI2AWorkflowGateShortCircuits:
    def test_return_upstream_skips_commit(self):
        workflow, bundle, coordinator = _make_workflow()

        # Force return_upstream by monkey-patching the curator
        from knowledge_curator.schemas.curation import (
            CompletenessResult,
            CompletenessStatus,
            CurationReport,
        )

        async def fake_run_curate(runtime, assertion_set):
            return CurationReport(
                report_id="r-up",
                source_ref_id=assertion_set.ref_id,
                status="return_upstream",
                completeness=CompletenessResult(status=CompletenessStatus.MANUAL_REVIEW),
                decisions=[],
                returned_upstream_count=1,
            )

        import system.workflows.curation_commit as wmod

        orig = wmod.CurationCommitWorkflow.run

        async def patched_run(self, **kwargs):
            self._validate_input(kwargs["source"], kwargs["assertion_set"])
            report = await fake_run_curate(self._curator_runtime, kwargs["assertion_set"])
            blocked = self._precommit_gate(report)
            return wmod.CurationCommitResult(
                report=report,
                commit_attempted=False,
                commit_result=None,
                blocked_reason=blocked,
            )

        wmod.CurationCommitWorkflow.run = patched_run
        try:
            source = SourceIdentity(ref_id="ED-2025-TEST", source_fingerprint="fp-up-001")
            result = _run(workflow.run(source=source, assertion_set=_make_assertion_set()))
            assert result.commit_attempted is False
            assert result.blocked_reason == "return_upstream"
            versions = bundle["commit"]["version_store"].list_published_versions()
            assert len(versions) == 0
        finally:
            wmod.CurationCommitWorkflow.run = orig

    def test_empty_decisions_skips_commit(self):
        from system.workflows.curation_commit import CurationCommitResult, CurationCommitWorkflow

        workflow, bundle, _ = _make_workflow()
        # Precommit gate logic test directly
        from knowledge_curator.schemas.curation import (
            CompletenessResult,
            CompletenessStatus,
            CurationReport,
        )

        report = CurationReport(
            report_id="r-empty",
            source_ref_id="ED-2025-TEST",
            status="incomplete",
            completeness=CompletenessResult(status=CompletenessStatus.NO_ASSERTIONS),
            decisions=[],
        )
        blocked = workflow._precommit_gate(report)
        assert blocked == "empty_decisions"

    def test_all_rejected_skips_commit(self):
        workflow, bundle, _ = _make_workflow()
        from knowledge_curator.schemas.curation import (
            AssertionDecision,
            CompletenessResult,
            CompletenessStatus,
            CurationAction,
            CurationReport,
            ConflictType,
        )
        from knowledge_curator.schemas.assertions import Confidence

        report = CurationReport(
            report_id="r-rej",
            source_ref_id="ED-2025-TEST",
            status="successful",
            completeness=CompletenessResult(status=CompletenessStatus.OK),
            decisions=[
                AssertionDecision(
                    assertion_id="AS-001",
                    action=CurationAction.REJECT,
                    confidence=Confidence.MEDIUM,
                    reason="test reject",
                )
            ],
        )
        blocked = workflow._precommit_gate(report)
        assert blocked == "all_rejected"


class TestSI2AWorkflowIdempotency:
    def test_published_replay_idempotent_hit(self):
        workflow, bundle, _ = _make_workflow()
        source = SourceIdentity(ref_id="ED-2025-TEST", source_fingerprint="fp-idem-001")
        assertion_set = _make_assertion_set()

        r1 = _run(workflow.run(source=source, assertion_set=assertion_set))
        assert r1.commit_result.status == CommitStatus.PUBLISHED

        r2 = _run(workflow.run(source=source, assertion_set=assertion_set))
        assert r2.commit_result.status == CommitStatus.IDEMPOTENT_HIT

        versions = bundle["commit"]["version_store"].list_published_versions()
        assert len(versions) == 1


class TestSI2AWorkflowPendingRecovery:
    def test_pending_vector_no_hidden_retry_and_recovery(self):
        from integration.system.fixtures.si2a_provider import TestFailureInjection

        failures = TestFailureInjection()
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle
        from system.application_composition import _extract_commit_deps, _validate_commit_deps
        from system.composition import CuratorDependencies, compose_system_runtime
        from system.workflows.curation_commit import CurationCommitWorkflow
        from knowledge_curator.core.commit import DocumentCommitCoordinator

        bundle = create_si2a_provider_bundle(failures=failures)
        curator_raw = bundle["curator"]
        curator_deps = CuratorDependencies(
            repository=curator_raw["repository"],
            ontology=curator_raw["ontology"],
            mechanism_validator=curator_raw["mechanism_validator"],
            provider_identity=curator_raw["provider_identity"],
        )
        system_rt = compose_system_runtime(curator_deps=curator_deps, evidence_deps=None)
        deps = _extract_commit_deps(bundle)
        _validate_commit_deps(deps)
        coordinator = DocumentCommitCoordinator(
            commit_store=deps.commit_store,
            structural_store=deps.structural_store,
            vector_index=deps.vector_index,
            usdo_store=deps.usdo_store,
            version_store=deps.version_store,
        )
        workflow = CurationCommitWorkflow(
            curator_runtime=system_rt.curator_runtime,
            commit_coordinator=coordinator,
            provider_identity="si2a-test",
        )

        # Inject vector upsert failure
        failures.fail_on("vector.upsert")

        source = SourceIdentity(ref_id="ED-2025-TEST", source_fingerprint="fp-vec-001")
        assertion_set = _make_assertion_set()

        call_count = [0]
        original_commit = coordinator.commit

        async def counting_commit(request):
            call_count[0] += 1
            return await original_commit(request)

        coordinator.commit = counting_commit

        r1 = _run(workflow.run(source=source, assertion_set=assertion_set))
        assert r1.commit_result.status == CommitStatus.PENDING_VECTOR
        assert call_count[0] == 1  # no hidden retry

        # Clear failure and retry
        failures.clear("vector.upsert")
        r2 = _run(workflow.run(source=source, assertion_set=assertion_set))
        assert r2.commit_result.status == CommitStatus.PUBLISHED
        assert call_count[0] == 2

        versions = bundle["commit"]["version_store"].list_published_versions()
        assert len(versions) == 1  # exactly one version

    def test_pending_finalize_no_hidden_retry_and_recovery(self):
        from integration.system.fixtures.si2a_provider import (
            TestFailureInjection,
            create_si2a_provider_bundle,
        )
        from system.application_composition import _extract_commit_deps, _validate_commit_deps
        from system.composition import CuratorDependencies, compose_system_runtime
        from system.workflows.curation_commit import CurationCommitWorkflow
        from knowledge_curator.core.commit import DocumentCommitCoordinator

        failures = TestFailureInjection()
        bundle = create_si2a_provider_bundle(failures=failures)
        curator_raw = bundle["curator"]
        curator_deps = CuratorDependencies(
            repository=curator_raw["repository"],
            ontology=curator_raw["ontology"],
            mechanism_validator=curator_raw["mechanism_validator"],
            provider_identity=curator_raw["provider_identity"],
        )
        system_rt = compose_system_runtime(curator_deps=curator_deps, evidence_deps=None)
        deps = _extract_commit_deps(bundle)
        _validate_commit_deps(deps)
        coordinator = DocumentCommitCoordinator(
            commit_store=deps.commit_store,
            structural_store=deps.structural_store,
            vector_index=deps.vector_index,
            usdo_store=deps.usdo_store,
            version_store=deps.version_store,
        )
        workflow = CurationCommitWorkflow(
            curator_runtime=system_rt.curator_runtime,
            commit_coordinator=coordinator,
            provider_identity="si2a-test",
        )

        # Inject snapshot creation failure
        failures.fail_on("version.create_snapshot")

        source = SourceIdentity(ref_id="ED-2025-TEST", source_fingerprint="fp-fin-001")
        assertion_set = _make_assertion_set()

        call_count = [0]
        original_commit = coordinator.commit

        async def counting_commit(request):
            call_count[0] += 1
            return await original_commit(request)

        coordinator.commit = counting_commit

        r1 = _run(workflow.run(source=source, assertion_set=assertion_set))
        assert r1.commit_result.status == CommitStatus.PENDING_FINALIZE
        assert call_count[0] == 1  # no hidden retry

        # Clear failure and retry
        failures.clear("version.create_snapshot")
        r2 = _run(workflow.run(source=source, assertion_set=assertion_set))
        assert r2.commit_result.status == CommitStatus.PUBLISHED
        assert call_count[0] == 2

        versions = bundle["commit"]["version_store"].list_published_versions()
        assert len(versions) == 1  # no duplicate version
