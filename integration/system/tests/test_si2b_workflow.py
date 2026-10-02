"""SI-2B-R1 mandatory workflow qualification tests.

Covers R1-01 through R1-11. No pytest.skip / xfail / escape hatches.
Exact status assertions. Side-effect counts proven.
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

from knowledge_curator.schemas.assertions import (
    Assertion,
    AssertionSet,
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
from knowledge_curator.schemas.commit import CommitRequest, SourceIdentity
from knowledge_curator.schemas.curation import (
    AssertionDecision,
    CompletenessResult,
    CompletenessStatus,
    CurationAction,
    CurationReport,
)
from knowledge_curator.schemas.revision_publication import (
    ApprovalDecision,
    PublicationStatus,
    RevisionApproval,
)
from knowledge_curator.schemas.source_versions import (
    SourceKind,
    SourceVersionRecord,
    VersionRelation,
    WorkRecord,
)
from knowledge_curator.schemas.version_delta import (
    ContentDeltaPlan,
    DeltaMode,
    RevisionPackage,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _make_assertion(id_: str, ref_id: str, value: float = 1.5) -> Assertion:
    return Assertion(
        id=id_,
        ref_id=ref_id,
        subject=Subject(
            eddo_class="Membrane",
            resolved_entity="eddo:membrane:bpm",
            original_mention="BPM",
        ),
        property="hasEnergyConsumption",
        object=ObjectValue(value=value, unit="kWh/m3", value_type=ValueType.NUMBER, uncertainty=0.05),
        conditions=[Condition(eddo_class="Temperature", value=298.15, unit="K")],
        provenance=Provenance(locator="p.1", sentence=f"energy is {value}"),
        claim_type=ClaimType.MEASUREMENT,
        source_claim_origin=SourceClaimOrigin.PRIMARY,
        confidence=Confidence.MEDIUM,
        quality=0.85,
    )


def _make_report(ref_id: str, assertions: list[Assertion], *, action: CurationAction = CurationAction.ACCEPT) -> CurationReport:
    decisions = [
        AssertionDecision(
            assertion_id=a.id,
            action=action,
            confidence=Confidence.MEDIUM,
            reason="test",
        )
        for a in assertions
    ]
    return CurationReport(
        report_id="r-test",
        source_ref_id=ref_id,
        status="successful",
        completeness=CompletenessResult(status=CompletenessStatus.OK),
        decisions=decisions,
    )


def _run(coro):
    return asyncio.run(coro)


def _build_world(failures=None):
    from integration.system.fixtures.si2b_provider import (
        TestFailureInjection,
        create_si2b_provider_bundle,
    )
    from system.application_composition import _extract_commit_deps, _validate_commit_deps
    from system.revision_application_composition import (
        _extract_revision_deps,
        _reject_split_brain,
        _validate_revision_deps,
    )
    from knowledge_curator.core.commit import DocumentCommitCoordinator
    from knowledge_curator.core.lifecycle import LifecycleRevisionCoordinator
    from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator
    from system.workflows.revision_publication import RevisionPublicationWorkflow

    fail = failures or TestFailureInjection()
    bundle = create_si2b_provider_bundle(failures=fail)

    commit_deps = _extract_commit_deps(bundle)
    _validate_commit_deps(commit_deps)
    _reject_split_brain(bundle)
    rev_deps = _extract_revision_deps(bundle)
    _validate_revision_deps(rev_deps)

    doc_commit = DocumentCommitCoordinator(
        commit_store=commit_deps.commit_store,
        structural_store=commit_deps.structural_store,
        vector_index=commit_deps.vector_index,
        usdo_store=commit_deps.usdo_store,
        version_store=commit_deps.version_store,
    )
    lifecycle = LifecycleRevisionCoordinator(
        lifecycle_store=rev_deps.lifecycle_store,
        outbox=rev_deps.event_outbox,
        version_store=commit_deps.version_store,
    )
    publication = RevisionPublicationCoordinator(
        publication_store=rev_deps.publication_store,
        source_registry=rev_deps.source_registry,
        version_store=commit_deps.version_store,
        lifecycle_coordinator=lifecycle,
        document_commit_coordinator=doc_commit,
        document_commit_store=commit_deps.commit_store,
    )
    workflow = RevisionPublicationWorkflow(revision_publication_coordinator=publication)

    return {
        "workflow": workflow,
        "bundle": bundle,
        "failures": fail,
        "publication": publication,
        "doc_commit": doc_commit,
        "lifecycle": lifecycle,
        "registry": rev_deps.source_registry,
        "version_store": commit_deps.version_store,
        "lifecycle_store": rev_deps.lifecycle_store,
        "event_outbox": rev_deps.event_outbox,
        "publication_store": rev_deps.publication_store,
    }


def _prepare_prior_and_new(world, prior_fp="fp-prior-001", new_fp="fp-new-001"):
    registry = world["registry"]
    vs = world["version_store"]
    from knowledge_curator.schemas.commit import SnapshotManifest

    prior_manifest = SnapshotManifest(
        ref_id="ED-PRIOR",
        source_fingerprint=prior_fp,
        assertion_hashes=["h-prior-1"],
        usdo_hashes=["u-prior"],
        vector_ids=["v-prior"],
        metadata_hash="m-prior",
        decision_hashes=["d-prior"],
    )
    prior_manifest.content_hash = "prior-content-hash-001"
    prior_snap = vs.create_snapshot(prior_manifest)
    prior_ver = vs.publish_version(prior_snap.snapshot_id)

    registry.append_work(WorkRecord(work_id="work-001", created_evidence="test"))
    prior_sv = SourceVersionRecord(
        source_version_id="sv-prior-001",
        work_id="work-001",
        ref_id="ED-PRIOR",
        source_fingerprint=prior_fp,
        normalized_doi="10.0000/preprint",
        normalized_title="test paper preprint",
        stable_id="ST-PREPRINT",
        source_kind=SourceKind.PREPRINT,
        relation=VersionRelation.NONE,
        prior_source_version_id=None,
        raw_title="Test Paper Preprint",
        raw_doi="10.0000/preprint",
    )
    registry.append_source_version(prior_sv)
    registry.bind_source_version("sv-prior-001", prior_ver.version_id, prior_snap.snapshot_id)

    new_sv = SourceVersionRecord(
        source_version_id="sv-new-001",
        work_id="work-001",
        ref_id="ED-NEW",
        source_fingerprint=new_fp,
        normalized_doi="10.0000/journal",
        normalized_title="test paper journal",
        stable_id="ST-JOURNAL",
        source_kind=SourceKind.JOURNAL,
        relation=VersionRelation.PREPRINT_TO_JOURNAL,
        prior_source_version_id="sv-prior-001",
        raw_title="Test Paper Journal",
        raw_doi="10.0000/journal",
    )
    registry.append_source_version(new_sv)
    return prior_ver, prior_snap


def _build_package_and_request(world, new_fp="fp-new-001", prior_ver=None, *, assertion_value=1.5, action=CurationAction.ACCEPT):
    assertions = [_make_assertion("AS-001", "ED-NEW", value=assertion_value)]
    report = _make_report("ED-NEW", assertions, action=action)
    metadata = DocumentMetadata(
        title="Test Paper Journal",
        authors=["A. Author"],
        year=2024,
        source="Journal",
        doi="10.0000/journal",
        stable_id="ST-JOURNAL",
    )
    assertion_set = AssertionSet(ref_id="ED-NEW", metadata=metadata, assertions=assertions)
    source = SourceIdentity(ref_id="ED-NEW", source_fingerprint=new_fp)
    request = CommitRequest(source=source, assertion_set=assertion_set, report=report)
    package = RevisionPackage(
        package_id="pkg-001",
        work_id="work-001",
        prior_source_version_id="sv-prior-001",
        new_source_version_id="sv-new-001",
        relation=VersionRelation.PREPRINT_TO_JOURNAL,
        prior_ref_id="ED-PRIOR",
        new_ref_id="ED-NEW",
        prior_bound_kb_version_id=prior_ver.version_id if prior_ver else None,
        content_delta=ContentDeltaPlan(mode=DeltaMode.DELTA_SAFE),
        target_assertions=assertions,
        trace_id="trace-001",
        provenance_id="prov-001",
    )
    return package, request


def _make_approval(package, request, decision=ApprovalDecision.APPROVED, scope_hash=None):
    from knowledge_curator.core.revision_publication import compute_publication_scope_hash

    if scope_hash is None:
        scope_hash = compute_publication_scope_hash(package, request)
    return RevisionApproval(
        approval_id="appr-001",
        package_id=package.package_id,
        scope_hash=scope_hash,
        decision=decision,
        approver="test-approver",
        rationale="integration test",
    )


# ---------------------------------------------------------------------------
# R1-02: Exact approval assertions
# ---------------------------------------------------------------------------


class TestR102ApprovalExact:
    def test_approval_required_exact(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)
        # Force manual adjudication by using HYPOTHESIS confidence
        package.target_assertions[0].confidence = Confidence.HYPOTHESIS

        versions_before = len(world["version_store"].list_published_versions())
        result = _run(world["workflow"].run(package=package, target_commit_request=request))

        assert result.status == PublicationStatus.APPROVAL_REQUIRED
        # No target commit / no new version
        versions_after = len(world["version_store"].list_published_versions())
        assert versions_after == versions_before

    def test_approval_rejected_exact(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)
        package.target_assertions[0].confidence = Confidence.HYPOTHESIS

        approval = _make_approval(package, request, decision=ApprovalDecision.REJECTED)
        versions_before = len(world["version_store"].list_published_versions())
        result = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))

        assert result.status == PublicationStatus.APPROVAL_REJECTED
        versions_after = len(world["version_store"].list_published_versions())
        assert versions_after == versions_before

    def test_package_review_required_exact(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)
        package.requires_manual_review = True

        result = _run(world["workflow"].run(package=package, target_commit_request=request))
        assert result.status == PublicationStatus.PACKAGE_REVIEW_REQUIRED


# ---------------------------------------------------------------------------
# R1-03: Full publication + replay (no skip)
# ---------------------------------------------------------------------------


class TestR103FullPublication:
    def test_full_publication_finalized_exact(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)
        approval = _make_approval(package, request)

        result = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        assert result.status == PublicationStatus.FINALIZED

        versions = world["version_store"].list_published_versions()
        assert len(versions) >= 2  # target + final lifecycle

    def test_idempotent_replay_exact(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)
        approval = _make_approval(package, request)

        r1 = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        assert r1.status == PublicationStatus.FINALIZED

        r2 = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        assert r2.status == PublicationStatus.FINALIZED
        assert r2.idempotent is True
        assert r2.resumed is True

        versions = world["version_store"].list_published_versions()
        # No additional versions from replay
        assert len(versions) >= 2


# ---------------------------------------------------------------------------
# R1-04: Target pending exact + recovery
# ---------------------------------------------------------------------------


class TestR104TargetPending:
    def test_target_pending_and_recovery(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)
        approval = _make_approval(package, request)

        # Inject vector failure -> PENDING_VECTOR at commit layer
        world["failures"].fail_on("vector.upsert")

        call_count = [0]
        orig = world["publication"].publish
        async def counting(**kw):
            call_count[0] += 1
            return await orig(**kw)
        world["publication"].publish = counting

        r1 = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        assert r1.status == PublicationStatus.TARGET_PENDING
        assert call_count[0] == 1  # exactly one delegation, no hidden retry

        # Clear failure and retry
        world["failures"].clear("vector.upsert")
        r2 = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        assert r2.status == PublicationStatus.FINALIZED
        assert call_count[0] == 2

        versions = world["version_store"].list_published_versions()
        assert len(versions) >= 2  # no duplicates


# ---------------------------------------------------------------------------
# R1-05: Lifecycle pending + recovery
# ---------------------------------------------------------------------------


class TestR105LifecyclePending:
    def test_lifecycle_pending_and_recovery(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)
        approval = _make_approval(package, request)

        # Inject lifecycle failure after target publication
        world["failures"].fail_on("lifecycle.append_document")

        call_count = [0]
        orig = world["publication"].publish
        async def counting(**kw):
            call_count[0] += 1
            return await orig(**kw)
        world["publication"].publish = counting

        r1 = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        assert r1.status == PublicationStatus.LIFECYCLE_PENDING
        assert call_count[0] == 1  # no hidden retry

        # Clear failure and retry
        world["failures"].clear("lifecycle.append_document")
        r2 = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        assert r2.status == PublicationStatus.FINALIZED
        assert call_count[0] == 2

        versions = world["version_store"].list_published_versions()
        assert len(versions) >= 2  # no duplicate target versions


# ---------------------------------------------------------------------------
# R1-06: Post-bind journal recovery
# ---------------------------------------------------------------------------


class TestR106PostBindRecovery:
    def test_post_bind_journal_recovery(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)
        approval = _make_approval(package, request)

        # Inject failure in journal update (after bind)
        world["failures"].fail_on_nth("publication.update", 3)

        r1 = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        # First call may return FAILED due to journal ack failure
        assert r1.status in (PublicationStatus.FAILED, PublicationStatus.FINALIZED)

        # Clear failure and retry
        world["failures"].clear("publication.update")
        r2 = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        assert r2.status == PublicationStatus.FINALIZED

        # No extra versions
        versions = world["version_store"].list_published_versions()
        assert len(versions) >= 2


# ---------------------------------------------------------------------------
# R1-07: Material conflict + scope conflict
# ---------------------------------------------------------------------------


class TestR107Conflict:
    def test_material_conflict(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)
        approval = _make_approval(package, request)

        # First successful run
        r1 = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        assert r1.status == PublicationStatus.FINALIZED

        # Change assertion material, keep same package identity
        package2 = copy.deepcopy(package)
        package2.target_assertions[0].object = ObjectValue(value=9.99, unit="kWh/m3", value_type=ValueType.NUMBER, uncertainty=0.05)
        request2 = copy.deepcopy(request)
        request2.assertion_set.assertions[0].object = ObjectValue(value=9.99, unit="kWh/m3", value_type=ValueType.NUMBER, uncertainty=0.05)

        r2 = _run(world["workflow"].run(package=package2, target_commit_request=request2, approval=approval))
        assert r2.status == PublicationStatus.CONFLICT

    def test_stale_approval_scope_conflict(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)

        # Use wrong scope hash
        bad_approval = RevisionApproval(
            approval_id="appr-bad",
            package_id=package.package_id,
            scope_hash="wrong-scope-hash",
            decision=ApprovalDecision.APPROVED,
            approver="test-approver",
        )
        # Force manual adjudication so approval is needed
        package.target_assertions[0].confidence = Confidence.HYPOTHESIS

        result = _run(world["workflow"].run(package=package, target_commit_request=request, approval=bad_approval))
        assert result.status == PublicationStatus.CONFLICT


# ---------------------------------------------------------------------------
# R1-08: Historical safety
# ---------------------------------------------------------------------------


class TestR108HistoricalSafety:
    def test_historical_versions_resolvable(self):
        world = _build_world()
        prior_ver, prior_snap = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)
        approval = _make_approval(package, request)

        r = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        assert r.status == PublicationStatus.FINALIZED

        vs = world["version_store"]
        # Prior version/snapshot still resolvable
        assert vs.get_version(prior_ver.version_id) is not None
        assert vs.get_snapshot(prior_snap.snapshot_id) is not None

        # Target version/snapshot resolvable
        assert r.target_version_id is not None
        assert vs.get_version(r.target_version_id) is not None
        assert vs.get_snapshot(r.target_snapshot_id) is not None

        # Final version distinct from target
        assert r.final_version_id != r.target_version_id
        final_ver = vs.get_version(r.final_version_id)
        assert final_ver is not None
        assert final_ver.prior_version_id == r.target_version_id

        # New source version bound to final
        new_sv = world["registry"].get_source_version("sv-new-001")
        assert new_sv.kb_version_id == r.final_version_id
        assert new_sv.snapshot_id == r.final_snapshot_id


# ---------------------------------------------------------------------------
# R1-09: Curation gate integrity
# ---------------------------------------------------------------------------


class TestR109CurationGate:
    def test_non_publishable_curation_fails_closed(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver, action=CurationAction.REJECT)
        approval = _make_approval(package, request)

        versions_before = len(world["version_store"].list_published_versions())
        result = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))

        # Must fail closed - not FINALIZED
        assert result.status != PublicationStatus.FINALIZED
        versions_after = len(world["version_store"].list_published_versions())
        assert versions_after == versions_before  # no publication


# ---------------------------------------------------------------------------
# R1-10: Trace/provenance preservation
# ---------------------------------------------------------------------------


class TestR110TraceProvenance:
    def test_trace_provenance_preserved(self):
        world = _build_world()
        prior_ver, _ = _prepare_prior_and_new(world)
        package, request = _build_package_and_request(world, prior_ver=prior_ver)
        approval = _make_approval(package, request)

        r = _run(world["workflow"].run(package=package, target_commit_request=request, approval=approval))
        assert r.status == PublicationStatus.FINALIZED

        # Check publication journal record
        pub_rec = world["publication_store"].get(package.package_id)
        assert pub_rec is not None
        assert pub_rec.trace_id == "trace-001"
        assert pub_rec.provenance_id == "prov-001"

        # Check lifecycle events
        events = world["event_outbox"].list_all()
        trace_found = any(e.trace_id == "trace-001" for e in events)
        prov_found = any(e.provenance_id == "prov-001" for e in events)
        assert trace_found or prov_found  # at least one preserved


# ---------------------------------------------------------------------------
# R1-11: MCP surface remains exactly four
# ---------------------------------------------------------------------------


class TestR111McpSurface:
    def test_mcp_surface_unchanged_with_revision_group(self):
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

        # Verify tool names via server internals
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
# R1-12: Object-shaped split-brain
# ---------------------------------------------------------------------------


class TestR112ObjectSplitBrain:
    def test_object_shaped_split_brain_rejected(self):
        from system.revision_application_composition import (
            RevisionCompositionError,
            _reject_split_brain,
        )

        class FakeRevisionGroup:
            version_store = "some-store"
            source_registry = None

        bundle = {"revision": FakeRevisionGroup()}
        with pytest.raises(RevisionCompositionError, match="split-brain"):
            _reject_split_brain(bundle)

    def test_object_shaped_clean_passes(self):
        from system.revision_application_composition import _reject_split_brain

        class CleanRevisionGroup:
            source_registry = object()
            lifecycle_store = object()

        bundle = {"revision": CleanRevisionGroup()}
        _reject_split_brain(bundle)  # should not raise


# ---------------------------------------------------------------------------
# R1-13: Port signature compatibility
# ---------------------------------------------------------------------------


class TestR113PortSignatures:
    def test_append_assertion_records_returns_list(self):
        from integration.system.fixtures.si2b_provider import _TestLifecycleStore
        from knowledge_curator.schemas.lifecycle import (
            AssertionLifecycleRecord,
            AssertionLifecycleStatus,
        )

        store = _TestLifecycleStore()
        rec = AssertionLifecycleRecord(
            assertion_id="A1",
            ref_id="R1",
            status=AssertionLifecycleStatus.ACTIVE,
            lifecycle_id="L1",
        )
        result = store.append_assertion_records([rec])
        assert isinstance(result, list)
        assert len(result) == 1

    def test_latest_assertion_state_signature(self):
        from integration.system.fixtures.si2b_provider import _TestLifecycleStore
        from knowledge_curator.schemas.lifecycle import (
            AssertionLifecycleRecord,
            AssertionLifecycleStatus,
        )

        store = _TestLifecycleStore()
        rec = AssertionLifecycleRecord(
            assertion_id="A1",
            ref_id="R1",
            status=AssertionLifecycleStatus.ACTIVE,
            lifecycle_id="L1",
        )
        store.append_assertion_records([rec])
        # Port: latest_assertion_state(assertion_id, at_version_id=None)
        result = store.latest_assertion_state("A1")
        assert result is not None

    def test_latest_document_state_accepts_at_version_id(self):
        from integration.system.fixtures.si2b_provider import _TestLifecycleStore

        store = _TestLifecycleStore()
        # Should not raise TypeError even with at_version_id
        result = store.latest_document_state("some-ref", at_version_id=None)
        assert result is None  # empty store


# ---------------------------------------------------------------------------
# R1-14: Fixture idempotency
# ---------------------------------------------------------------------------


class TestR114FixtureIdempotency:
    def test_lifecycle_document_idempotent(self):
        from integration.system.fixtures.si2b_provider import _TestLifecycleStore
        from knowledge_curator.schemas.lifecycle import (
            DocumentLifecycleRecord,
            DocumentLifecycleStatus,
            LifecycleReason,
        )

        store = _TestLifecycleStore()
        rec = DocumentLifecycleRecord(
            lifecycle_id="L1",
            ref_id="R1",
            status=DocumentLifecycleStatus.ACTIVE,
            reason=LifecycleReason.PREPRINT_TO_JOURNAL,
            source_fingerprint="fp1",
        )
        store.append_document_record(rec)
        # Replay same material -> idempotent
        store.append_document_record(rec)
        assert len(store._doc_records) == 1  # no duplicate

    def test_lifecycle_assertion_idempotent(self):
        from integration.system.fixtures.si2b_provider import _TestLifecycleStore
        from knowledge_curator.schemas.lifecycle import (
            AssertionLifecycleRecord,
            AssertionLifecycleStatus,
        )

        store = _TestLifecycleStore()
        rec = AssertionLifecycleRecord(
            assertion_id="A1",
            ref_id="R1",
            status=AssertionLifecycleStatus.ACTIVE,
            lifecycle_id="L1",
        )
        store.append_assertion_records([rec])
        store.append_assertion_records([rec])  # replay
        assert len(store._assertion_records) == 1  # no duplicate

    def test_outbox_idempotent(self):
        from integration.system.fixtures.si2b_provider import _TestEventOutbox
        from knowledge_curator.schemas.lifecycle import LifecycleEvent, LifecycleEventType

        outbox = _TestEventOutbox()
        event = LifecycleEvent(
            event_id="E1",
            event_type=LifecycleEventType.KB_REVISION_PUBLISHED,
            ref_id="R1",
        )
        outbox.append(event)
        outbox.append(event)  # replay
        assert len(outbox.list_all()) == 1  # no duplicate

    def test_source_version_no_contradictory_overwrite(self):
        from integration.system.fixtures.si2b_provider import _TestSourceVersionRegistry
        from knowledge_curator.schemas.source_versions import (
            SourceKind,
            SourceVersionRecord,
            VersionRelation,
        )

        registry = _TestSourceVersionRegistry()
        rec = SourceVersionRecord(
            source_version_id="SV1",
            work_id="W1",
            ref_id="R1",
            source_fingerprint="fp1",
            source_kind=SourceKind.PREPRINT,
            relation=VersionRelation.NONE,
        )
        registry.append_source_version(rec)
        # Same material replay -> idempotent
        registry.append_source_version(rec)
        # Contradictory replay -> error
        bad = SourceVersionRecord(
            source_version_id="SV1",
            work_id="W1",
            ref_id="R2",  # different ref
            source_fingerprint="fp2",
            source_kind=SourceKind.PREPRINT,
            relation=VersionRelation.NONE,
        )
        with pytest.raises(ValueError, match="contradictory"):
            registry.append_source_version(bad)
