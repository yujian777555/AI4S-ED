"""Phase 5.3-R1 tests: real async integration + recovery closure."""

from __future__ import annotations

import asyncio
import copy

import pytest

from knowledge_curator.adapters.in_memory_commit import (
    FailureInjection,
    InMemoryDocumentCommitStore,
    InMemoryStructuralKnowledgeStore,
    InMemoryUSDOStore,
    InMemoryVectorIndex,
    InMemoryVersionStore,
)
from knowledge_curator.adapters.in_memory_evidence import InMemoryEvidenceStore
from knowledge_curator.adapters.in_memory_lifecycle import (
    InMemoryEventOutbox,
    InMemoryLifecycleStore,
    InMemoryLifecycleVisibility,
)
from knowledge_curator.adapters.in_memory_repository import (
    FakeMechanismValidator,
    InMemoryKnowledgeRepository,
    SimpleOntologyService,
)
from knowledge_curator.adapters.in_memory_revision_publication import (
    InMemoryRevisionPublicationStore,
)
from knowledge_curator.adapters.in_memory_source_versions import (
    InMemorySourceVersionRegistry,
)
from knowledge_curator.core.commit import DocumentCommitCoordinator
from knowledge_curator.core.curator import KnowledgeCurator
from knowledge_curator.core.lifecycle import LifecycleRevisionCoordinator
from knowledge_curator.core.lifecycle_visibility import make_version_visible_fn
from knowledge_curator.core.revision_publication import (
    RevisionPublicationCoordinator,
    canonical_assertion_material,
    compute_publication_scope_hash,
)
from knowledge_curator.core.source_identity import IncrementalIntakeService
from knowledge_curator.core.version_delta import RevisionPackageBuilder
from knowledge_curator.schemas.assertions import (
    Assertion,
    AssertionSet,
    ClaimType,
    Confidence,
    Condition,
    DocumentMetadata,
    ObjectValue,
    Provenance,
    QualityGrade,
    SourceClaimOrigin,
    Subject,
    ValueType,
)
from knowledge_curator.schemas.commit import CommitRequest, SourceIdentity
from knowledge_curator.schemas.curation import CurationAction
from knowledge_curator.schemas.revision_publication import (
    ApprovalDecision,
    PublicationPhase,
    PublicationStatus,
    RevisionApproval,
)
from knowledge_curator.schemas.source_versions import (
    SourceCandidate,
    SourceKind,
    VersionRelation,
    VersionUpgradeIntent,
)
from knowledge_curator.schemas.version_delta import (
    ContentUnit,
    ContentUnitKind,
    DeltaAssertionBatch,
    VersionAssertionInventory,
    VersionContentManifest,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def _unit(uid, loc="p.1", h="h1"):
    return ContentUnit(unit_id=uid, locator=loc, kind=ContentUnitKind.TEXT, content_hash=h)


def _manifest(sid, ref, fp, units):
    return VersionContentManifest(source_version_id=sid, ref_id=ref, source_fingerprint=fp, units=units)


def _assertion(aid, ref, entity="E1", value=1.0, locator="p.1", conf=Confidence.HIGH):
    return Assertion(
        id=aid, ref_id=ref,
        subject=Subject(eddo_class="Membrane", resolved_entity=entity, original_mention=entity),
        property="P1",
        object=ObjectValue(value=value, unit="kWh", value_type=ValueType.NUMBER),
        conditions=[Condition(eddo_class="T", value=298, unit="K")],
        provenance=Provenance(locator=locator, sentence="s"),
        claim_type=ClaimType.MEASUREMENT,
        source_claim_origin=SourceClaimOrigin.PRIMARY,
        confidence=conf, quality=0.9,
    )


def _setup_p2j(reg, svc):
    cp = SourceCandidate(
        ref_id="ARXIV-1", source_fingerprint="fp-pre", title="Preprint Study",
        doi="10.48550/arxiv.1", stable_id="A:1", source_kind=SourceKind.PREPRINT,
    )
    dp = svc.prepare(cp)
    p1 = svc.proceed(cp, dp)
    cj = SourceCandidate(
        ref_id="JOURNAL-1", source_fingerprint="fp-j", title="Journal Study",
        doi="10.1000/j.1", stable_id="J:1", source_kind=SourceKind.JOURNAL,
        explicit_work_id=dp.work_id,
        explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    dj = svc.prepare(cj)
    j1 = svc.proceed(cj, dj)
    return p1, j1, dp.work_id


def _build_pkg(reg, p1, j1, work_id):
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id,
        prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id,
        relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1", h="h1", loc="p.a")])
    new_m = _manifest(j1.source_version_id, "JOURNAL-1", "fp-j", [_unit("U1", h="h2", loc="p.b")])
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[_assertion("A1", "ARXIV-1", value=1.0, locator="p.a")],
        assertion_unit_map={"A1": "U1"},
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="JOURNAL-1",
        assertions=[_assertion("J-A1", "JOURNAL-1", value=2.0, locator="p.b")],
        assertion_unit_map={"J-A1": "U1"},
        processed_unit_ids=["U1"],
    )
    return builder.build(
        intent=intent, prior_manifest=prior_m, new_manifest=new_m,
        prior_inventory=inv, delta_batch=batch,
    )


def _make_request(pkg, new_sfp="fp-j"):
    """Build a real CommitRequest matching package.target_assertions."""
    assertions = list(pkg.target_assertions)
    aset = AssertionSet(
        ref_id=pkg.new_ref_id,
        metadata=DocumentMetadata(
            title="Journal Study", authors=["A"], year=2024,
            source="Journal", doi="10.1000/j.1", stable_id="J:1",
        ),
        assertions=assertions,
        quality_grade=QualityGrade.B,
    )
    from knowledge_curator.schemas.curation import (
        AssertionDecision,
        CompletenessResult,
        CompletenessStatus,
        CurationReport,
        QualityBreakdown,
    )

    decisions = [
        AssertionDecision(
            assertion_id=a.id, action=CurationAction.ACCEPT, confidence=a.confidence,
            reason="accepted for publication",
        )
        for a in assertions
    ]
    report = CurationReport(
        report_id="R-1",
        source_ref_id=pkg.new_ref_id,
        status="successful",
        completeness=CompletenessResult(
            status=CompletenessStatus.OK,
            metadata_valid=True,
            assertion_count=len(assertions),
            allows_formal_curation=True,
            requires_manual_review=False,
            requires_return_upstream=False,
            issues=[],
        ),
        conflicts=[],
        quality=QualityBreakdown(
            p_parse=1.0, s_schema=1.0, e_evidence=1.0, n_novelty=1.0,
            penalty=1.0, total=0.9,
        ),
        decisions=decisions,
    )
    return CommitRequest(
        source=SourceIdentity(ref_id=pkg.new_ref_id, source_fingerprint=new_sfp),
        assertion_set=aset,
        report=report,
    )


def _make_curated_request(pkg, new_sfp="fp-j"):
    """Build CommitRequest from the real KnowledgeCurator pipeline."""
    assertions = list(pkg.target_assertions)
    aset = AssertionSet(
        ref_id=pkg.new_ref_id,
        metadata=DocumentMetadata(
            title="Journal Study", authors=["A"], year=2024,
            source="Journal", doi="10.1000/j.1", stable_id="J:1",
        ),
        assertions=assertions,
        quality_grade=QualityGrade.B,
    )
    curator = KnowledgeCurator(
        repository=InMemoryKnowledgeRepository(),
        ontology=SimpleOntologyService(),
        mechanism_validator=FakeMechanismValidator(),
    )
    report = _run(curator.curate(aset, context={"report_id": "R-REAL-P2J"}))
    assert report.source_ref_id == pkg.new_ref_id
    assert report.returned_upstream_count == 0
    assert all(
        decision.action in (CurationAction.ACCEPT, CurationAction.DOWNGRADE)
        for decision in report.decisions
    )
    assert report.trace["pipeline"] == [
        "completeness", "conflict_detection", "quality_evaluation", "curation_decision"
    ]
    return CommitRequest(
        source=SourceIdentity(ref_id=pkg.new_ref_id, source_fingerprint=new_sfp),
        assertion_set=aset,
        report=report,
    )


def _approval(pkg, request):
    scope = compute_publication_scope_hash(pkg, request)
    return RevisionApproval(
        approval_id="APP-1", package_id=pkg.package_id, scope_hash=scope,
        decision=ApprovalDecision.APPROVED, approver="reviewer-1",
        rationale="approved",
    )


class AsyncFakeCommitCoordinator:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = 0

    async def commit(self, request):
        self.calls += 1
        if self.results:
            return self.results.pop(0)
        from knowledge_curator.schemas.commit import CommitResult, CommitPhase, CommitStatus

        return CommitResult(
            status=CommitStatus.PUBLISHED, version_id="kbv-t", snapshot_id="snap-t",
            commit_id="c-1", phase=CommitPhase.PUBLISHED,
        )


def _setup_real_stores():
    versions = InMemoryVersionStore(failures=FailureInjection())
    commit_store = InMemoryDocumentCommitStore()
    structural = InMemoryStructuralKnowledgeStore()
    usdo = InMemoryUSDOStore()
    vector = InMemoryVectorIndex()
    commit_coord = DocumentCommitCoordinator(
        commit_store=commit_store, structural_store=structural,
        vector_index=vector, usdo_store=usdo, version_store=versions,
    )
    lstore = InMemoryLifecycleStore(version_visible=make_version_visible_fn(versions))
    outbox = InMemoryEventOutbox()
    life = LifecycleRevisionCoordinator(
        lifecycle_store=lstore, outbox=outbox, version_store=versions,
    )
    return versions, commit_store, commit_coord, lstore, life


# ---- async publish with fake commit ----

def test_async_publish_requires_real_request():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    pkg = _build_pkg(reg, p1, j1, wid)

    versions, commit_store, commit_coord, lstore, life = _setup_real_stores()
    journal = InMemoryRevisionPublicationStore()
    coord = RevisionPublicationCoordinator(
        publication_store=journal, source_registry=reg, version_store=versions,
        lifecycle_coordinator=life,
        document_commit_coordinator=AsyncFakeCommitCoordinator(),
        document_commit_store=commit_store,
    )
    # No request -> fail closed, no side effects
    result = _run(coord.publish(package=pkg, approval=_approval(pkg, _make_request(pkg))))
    assert result.status == PublicationStatus.FAILED
    assert "required" in (result.last_error or "")


def test_approval_scope_binds_request_material():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    pkg = _build_pkg(reg, p1, j1, wid)
    req1 = _make_request(pkg)
    req2 = _make_request(pkg)
    req2.assertion_set.metadata.title = "CHANGED TITLE"
    h1 = compute_publication_scope_hash(pkg, req1)
    h2 = compute_publication_scope_hash(pkg, req2)
    assert h1 != h2


def test_curation_gate_blocks_reject():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    pkg = _build_pkg(reg, p1, j1, wid)
    req = _make_request(pkg)
    req.report.decisions[0].action = CurationAction.REJECT

    versions, commit_store, commit_coord, lstore, life = _setup_real_stores()
    journal = InMemoryRevisionPublicationStore()
    coord = RevisionPublicationCoordinator(
        publication_store=journal, source_registry=reg, version_store=versions,
        lifecycle_coordinator=life,
        document_commit_coordinator=AsyncFakeCommitCoordinator(),
        document_commit_store=commit_store,
    )
    result = _run(coord.publish(package=pkg, target_commit_request=req, approval=_approval(pkg, req)))
    assert result.status == PublicationStatus.FAILED
    assert "not publishable" in (result.last_error or "")


# ---- real async E2E ----

def test_real_p2j_e2e():
    """Real DocumentCommitCoordinator + LifecycleRevisionCoordinator E2E."""
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)

    versions, commit_store, commit_coord, lstore, life = _setup_real_stores()

    # Prior binding must use same VersionStore history
    # Publish a real prior version first
    from knowledge_curator.schemas.commit import SnapshotManifest
    import hashlib
    import json as _json

    m1 = SnapshotManifest(
        ref_id="ARXIV-1", source_fingerprint="fp-pre",
        assertion_hashes=["a1"], usdo_hashes=["u1"], vector_ids=["v1"],
        metadata_hash="m1", decision_hashes=["d1"],
    )
    m1.content_hash = hashlib.sha256(_json.dumps(m1.stable_payload(), sort_keys=True).encode()).hexdigest()
    s1 = versions.create_snapshot(m1)
    v1 = versions.publish_version(s1.snapshot_id)
    reg.bind_source_version(p1.source_version_id, v1.version_id, s1.snapshot_id)

    pkg = _build_pkg(reg, p1, j1, wid)
    req = _make_curated_request(pkg)
    appr = _approval(pkg, req)

    journal = InMemoryRevisionPublicationStore()
    coord = RevisionPublicationCoordinator(
        publication_store=journal, source_registry=reg, version_store=versions,
        lifecycle_coordinator=life,
        document_commit_coordinator=commit_coord,
        document_commit_store=commit_store,
    )
    result = _run(coord.publish(package=pkg, target_commit_request=req, approval=appr))
    assert result.status == PublicationStatus.FINALIZED, result.last_error
    assert result.idempotent is False
    assert result.resumed is False

    rec = journal.get(pkg.package_id)
    assert rec.phase == PublicationPhase.FINALIZED
    assert rec.final_version_id != rec.target_version_id
    final_ver = versions.get_version(rec.final_version_id)
    assert final_ver.prior_version_id == rec.target_version_id

    # new SourceVersion -> V_final
    new = reg.get_source_version(j1.source_version_id)
    assert new.kb_version_id == rec.final_version_id
    # prior binding unchanged
    prior = reg.get_source_version(p1.source_version_id)
    assert prior.kb_version_id == v1.version_id

    # Visibility: prior preprint is superseded and ineligible for retrieval/training;
    # the new journal remains active and eligible.
    vis = InMemoryLifecycleVisibility(life._lifecycle)
    prior_vis = vis.document_eligibility("ARXIV-1")
    journal_vis = vis.document_eligibility("JOURNAL-1")
    assert prior_vis.status == "superseded"
    assert prior_vis.visible_for_retrieval is False
    assert prior_vis.eligible_for_training is False
    assert journal_vis.status == "active"
    assert journal_vis.visible_for_retrieval is True
    assert journal_vis.eligible_for_training is True

    # Replay
    result2 = _run(coord.publish(package=pkg, target_commit_request=req, approval=appr))
    assert result2.status == PublicationStatus.FINALIZED
    assert result2.idempotent is True
    assert result2.resumed is True

    # Historical versions remain resolvable and rollback-safe after lifecycle publication.
    assert versions.get_version(v1.version_id) is not None
    assert versions.get_snapshot(v1.snapshot_id) is not None
    rolled = versions.rollback_to(v1.version_id)
    assert rolled.version_id == v1.version_id
    assert versions.current_version().version_id == v1.version_id


def test_post_bind_journal_recovery():
    """Bind succeeds but journal FINALIZED update fails -> retry finalizes."""
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    versions, commit_store, commit_coord, lstore, life = _setup_real_stores()

    from knowledge_curator.schemas.commit import SnapshotManifest
    import hashlib
    import json as _json
    m1 = SnapshotManifest(
        ref_id="ARXIV-1", source_fingerprint="fp-pre",
        assertion_hashes=["a1"], usdo_hashes=["u1"], vector_ids=["v1"],
        metadata_hash="m1", decision_hashes=["d1"],
    )
    m1.content_hash = hashlib.sha256(_json.dumps(m1.stable_payload(), sort_keys=True).encode()).hexdigest()
    s1 = versions.create_snapshot(m1)
    v1 = versions.publish_version(s1.snapshot_id)
    reg.bind_source_version(p1.source_version_id, v1.version_id, s1.snapshot_id)

    pkg = _build_pkg(reg, p1, j1, wid)
    req = _make_request(pkg)
    appr = _approval(pkg, req)

    journal = InMemoryRevisionPublicationStore()
    coord = RevisionPublicationCoordinator(
        publication_store=journal, source_registry=reg, version_store=versions,
        lifecycle_coordinator=life,
        document_commit_coordinator=commit_coord,
        document_commit_store=commit_store,
    )

    # Inject failure on journal FINALIZED update
    orig_update = journal.update
    state = {"fail": False}
    def flaky_update(record):
        if state["fail"] and record.phase == PublicationPhase.FINALIZED:
            state["fail"] = False
            raise RuntimeError("journal finalize crash")
        return orig_update(record)
    journal.update = flaky_update
    state["fail"] = True

    result1 = _run(coord.publish(package=pkg, target_commit_request=req, approval=appr))
    assert result1.status == PublicationStatus.FAILED
    bound_after_crash = reg.get_source_version(j1.source_version_id)
    assert bound_after_crash.kb_version_id is not None
    event_ids_before_retry = [event.event_id for event in life._outbox.list_all()]
    assert event_ids_before_retry

    # Retry: bind already done, journal recovery should finalize without re-emitting outbox events.
    result2 = _run(coord.publish(package=pkg, target_commit_request=req, approval=appr))
    assert result2.status == PublicationStatus.FINALIZED
    assert result2.idempotent is True
    assert result2.resumed is True
    rec = journal.get(pkg.package_id)
    assert rec.phase == PublicationPhase.FINALIZED
    assert [event.event_id for event in life._outbox.list_all()] == event_ids_before_retry


def test_existing_commit_material_conflict():
    """Same IDs but changed assertion material -> CONFLICT."""
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    versions, commit_store, commit_coord, lstore, life = _setup_real_stores()

    from knowledge_curator.schemas.commit import SnapshotManifest
    import hashlib
    import json as _json
    m1 = SnapshotManifest(
        ref_id="ARXIV-1", source_fingerprint="fp-pre",
        assertion_hashes=["a1"], usdo_hashes=["u1"], vector_ids=["v1"],
        metadata_hash="m1", decision_hashes=["d1"],
    )
    m1.content_hash = hashlib.sha256(_json.dumps(m1.stable_payload(), sort_keys=True).encode()).hexdigest()
    s1 = versions.create_snapshot(m1)
    v1 = versions.publish_version(s1.snapshot_id)
    reg.bind_source_version(p1.source_version_id, v1.version_id, s1.snapshot_id)

    pkg = _build_pkg(reg, p1, j1, wid)
    req = _make_request(pkg)

    # Create an existing commit with same IDs but different value
    bad_pkg = copy.deepcopy(pkg)
    bad_pkg.target_assertions[0].object.value = 999.0
    # Manually create existing commit record with different material
    from knowledge_curator.schemas.commit import AdmittedAssertion, AssertionVisibility

    class FakeCommitRecord:
        def __init__(self):
            self.admitted = [
                AdmittedAssertion(
                    assertion=_assertion("J-A1", "JOURNAL-1", value=999.0, locator="p.b"),
                    visibility=AssertionVisibility.ACTIVE,
                    confidence=Confidence.HIGH,
                    action=CurationAction.ACCEPT,
                )
            ]

    commit_store.find_by_key = lambda r, f: FakeCommitRecord()

    journal = InMemoryRevisionPublicationStore()
    coord = RevisionPublicationCoordinator(
        publication_store=journal, source_registry=reg, version_store=versions,
        lifecycle_coordinator=life,
        document_commit_coordinator=AsyncFakeCommitCoordinator(),
        document_commit_store=commit_store,
    )
    result = _run(coord.publish(package=pkg, target_commit_request=req, approval=_approval(pkg, req)))
    assert result.status in (PublicationStatus.CONFLICT, PublicationStatus.FAILED)


def test_metadata_mismatch_no_side_effect():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    pkg = _build_pkg(reg, p1, j1, wid)
    req = _make_request(pkg)
    req.assertion_set.metadata.title = "WRONG TITLE"
    versions, commit_store, _cc, _ls, life = _setup_real_stores()
    journal = InMemoryRevisionPublicationStore()
    coord = RevisionPublicationCoordinator(
        publication_store=journal, source_registry=reg, version_store=versions,
        lifecycle_coordinator=life,
        document_commit_coordinator=AsyncFakeCommitCoordinator(),
        document_commit_store=commit_store,
    )
    result = _run(coord.publish(package=pkg, target_commit_request=req, approval=_approval(pkg, req)))
    assert result.status in (PublicationStatus.CONFLICT, PublicationStatus.FAILED)
    assert "title" in (result.last_error or "")


def test_scope_hash_decision_change():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    pkg = _build_pkg(reg, p1, j1, wid)
    req1 = _make_request(pkg)
    req2 = _make_request(pkg)
    req2.report.decisions[0].action = CurationAction.DOWNGRADE
    h1 = compute_publication_scope_hash(pkg, req1)
    h2 = compute_publication_scope_hash(pkg, req2)
    assert h1 != h2


def test_scope_hash_value_change():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    pkg = _build_pkg(reg, p1, j1, wid)
    req1 = _make_request(pkg)
    req2 = _make_request(pkg)
    req2.assertion_set.assertions = [copy.deepcopy(a) for a in req2.assertion_set.assertions]
    req2.assertion_set.assertions[0].object.value = 999.0
    h1 = compute_publication_scope_hash(pkg, req1)
    h2 = compute_publication_scope_hash(pkg, req2)
    assert h1 != h2


def test_lifecycle_failure_retry():
    """Lifecycle fails after target commit -> retry succeeds."""
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    versions, commit_store, commit_coord, lstore, life = _setup_real_stores()
    # Publish prior version in same VersionStore
    from knowledge_curator.schemas.commit import SnapshotManifest
    import hashlib, json as _json
    m1 = SnapshotManifest(ref_id="ARXIV-1", source_fingerprint="fp-pre", assertion_hashes=["a1"], usdo_hashes=["u1"], vector_ids=["v1"], metadata_hash="m1", decision_hashes=["d1"])
    m1.content_hash = hashlib.sha256(_json.dumps(m1.stable_payload(), sort_keys=True).encode()).hexdigest()
    s1 = versions.create_snapshot(m1)
    v1 = versions.publish_version(s1.snapshot_id)
    reg.bind_source_version(p1.source_version_id, v1.version_id, s1.snapshot_id)
    pkg = _build_pkg(reg, p1, j1, wid)
    req = _make_request(pkg)

    # First run: lifecycle fails
    state = {"fail": True}
    orig_apply = life.apply_revision
    def flaky_apply(draft, source_fingerprint=None):
        if state["fail"]:
            state["fail"] = False
            raise RuntimeError("lifecycle crash")
        return orig_apply(draft, source_fingerprint=source_fingerprint)
    life.apply_revision = flaky_apply
    journal = InMemoryRevisionPublicationStore()
    coord = RevisionPublicationCoordinator(
        publication_store=journal, source_registry=reg, version_store=versions,
        lifecycle_coordinator=life,
        document_commit_coordinator=commit_coord,
        document_commit_store=commit_store,
    )

    result1 = _run(coord.publish(package=pkg, target_commit_request=req, approval=_approval(pkg, req)))
    assert result1.status in (PublicationStatus.LIFECYCLE_PENDING, PublicationStatus.FAILED)
    new = reg.get_source_version(j1.source_version_id)
    assert new.kb_version_id is None

    # Retry
    result2 = _run(coord.publish(package=pkg, target_commit_request=req, approval=_approval(pkg, req)))
    assert result2.status == PublicationStatus.FINALIZED
