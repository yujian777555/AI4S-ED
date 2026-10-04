"""Phase 5.3 tests: revision publication orchestration (async)."""

from __future__ import annotations

import asyncio

import pytest

from knowledge_curator.adapters.in_memory_commit import (
    FailureInjection,
    InMemoryDocumentCommitStore,
    InMemoryVersionStore,
)
from knowledge_curator.adapters.in_memory_lifecycle import (
    InMemoryEventOutbox,
    InMemoryLifecycleStore,
    InMemoryLifecycleVisibility,
)
from knowledge_curator.adapters.in_memory_revision_publication import (
    InMemoryRevisionPublicationStore,
)
from knowledge_curator.adapters.in_memory_source_versions import (
    InMemorySourceVersionRegistry,
)
from knowledge_curator.core.lifecycle import LifecycleRevisionCoordinator
from knowledge_curator.core.lifecycle_visibility import make_version_visible_fn
from knowledge_curator.core.revision_publication import (
    RevisionPublicationCoordinator,
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
from knowledge_curator.schemas.commit import CommitRequest, SnapshotManifest, SourceIdentity
from knowledge_curator.schemas.curation import (
    AssertionDecision,
    CompletenessResult,
    CompletenessStatus,
    CurationAction,
    CurationReport,
    QualityBreakdown,
)
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
import hashlib
import json as _json


def _run(coro):
    return asyncio.run(coro)


def _unit(uid, loc="p.1", h="h1"):
    return ContentUnit(unit_id=uid, locator=loc, kind=ContentUnitKind.TEXT, content_hash=h)


def _manifest(sid, ref, fp, units):
    return VersionContentManifest(source_version_id=sid, ref_id=ref, source_fingerprint=fp, units=units)


def _assertion(aid, ref, entity="E1", value=1.0, locator="p.1"):
    return Assertion(
        id=aid, ref_id=ref,
        subject=Subject(eddo_class="Membrane", resolved_entity=entity, original_mention=entity),
        property="P1",
        object=ObjectValue(value=value, unit="kWh", value_type=ValueType.NUMBER),
        conditions=[Condition(eddo_class="T", value=298, unit="K")],
        provenance=Provenance(locator=locator, sentence="s"),
        claim_type=ClaimType.MEASUREMENT,
        source_claim_origin=SourceClaimOrigin.PRIMARY,
        confidence=Confidence.HIGH, quality=0.9,
    )


class AsyncFakeCommit:
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
        explicit_work_id=dp.work_id, explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    dj = svc.prepare(cj)
    j1 = svc.proceed(cj, dj)
    return p1, j1, dp.work_id


def _build_pkg(reg, p1, j1, work_id):
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
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
        assertion_unit_map={"J-A1": "U1"}, processed_unit_ids=["U1"],
    )
    return builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch)


def _make_request(pkg, fp="fp-j"):
    assertions = list(pkg.target_assertions)
    aset = AssertionSet(
        ref_id=pkg.new_ref_id,
        metadata=DocumentMetadata(title="Journal Study", authors=["A"], year=2024, source="Journal", doi="10.1000/j.1", stable_id="J:1"),
        assertions=assertions, quality_grade=QualityGrade.B,
    )
    decisions = [
        AssertionDecision(assertion_id=a.id, action=CurationAction.ACCEPT, confidence=a.confidence, reason="ok")
        for a in assertions
    ]
    report = CurationReport(
        report_id="R-1", source_ref_id=pkg.new_ref_id, status="successful",
        completeness=CompletenessResult(status=CompletenessStatus.OK, metadata_valid=True, assertion_count=len(assertions), allows_formal_curation=True, requires_manual_review=False, requires_return_upstream=False, issues=[]),
        conflicts=[], decisions=decisions,
    )
    return CommitRequest(source=SourceIdentity(ref_id=pkg.new_ref_id, source_fingerprint=fp), assertion_set=aset, report=report)


def _approval(pkg, request):
    scope = compute_publication_scope_hash(pkg, request)
    return RevisionApproval(approval_id="APP-1", package_id=pkg.package_id, scope_hash=scope, decision=ApprovalDecision.APPROVED, approver="r1")


def _make_coord(reg, commit=None):
    versions = InMemoryVersionStore(failures=FailureInjection())
    m = SnapshotManifest(ref_id="ARXIV-1", source_fingerprint="fp-pre", assertion_hashes=["a1"], usdo_hashes=["u1"], vector_ids=["v1"], metadata_hash="m1", decision_hashes=["d1"])
    m.content_hash = hashlib.sha256(_json.dumps(m.stable_payload(), sort_keys=True).encode()).hexdigest()
    snap = versions.create_snapshot(m)
    v1 = versions.publish_version(snap.snapshot_id)
    commit_store = InMemoryDocumentCommitStore()

    lstore = InMemoryLifecycleStore(version_visible=make_version_visible_fn(versions))
    outbox = InMemoryEventOutbox()
    life = LifecycleRevisionCoordinator(lifecycle_store=lstore, outbox=outbox, version_store=versions)
    journal = InMemoryRevisionPublicationStore()
    if commit is None:
        # Successful publication coverage must use the real DocumentCommitCoordinator.
        from knowledge_curator.adapters.in_memory_commit import (
            InMemoryStructuralKnowledgeStore,
            InMemoryUSDOStore,
            InMemoryVectorIndex,
        )
        from knowledge_curator.core.commit import DocumentCommitCoordinator

        commit = DocumentCommitCoordinator(
            commit_store=commit_store,
            structural_store=InMemoryStructuralKnowledgeStore(),
            vector_index=InMemoryVectorIndex(),
            usdo_store=InMemoryUSDOStore(),
            version_store=versions,
        )
    coord = RevisionPublicationCoordinator(
        publication_store=journal, source_registry=reg, version_store=versions,
        lifecycle_coordinator=life, document_commit_coordinator=commit,
        document_commit_store=commit_store,
    )
    return coord, versions, journal, life, v1


def test_approval_required_no_commit():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    pkg = _build_pkg(reg, p1, j1, wid)
    commit = AsyncFakeCommit()
    coord, versions, journal, life, v1 = _make_coord(reg, commit=commit)
    req = _make_request(pkg)
    result = _run(coord.publish(package=pkg, target_commit_request=req))
    assert result.status == PublicationStatus.APPROVAL_REQUIRED
    assert commit.calls == 0


def test_rejected_approval_no_commit():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    pkg = _build_pkg(reg, p1, j1, wid)
    commit = AsyncFakeCommit()
    coord, versions, journal, life, v1 = _make_coord(reg, commit=commit)
    req = _make_request(pkg)
    scope = compute_publication_scope_hash(pkg, req)
    appr = RevisionApproval(approval_id="A", package_id=pkg.package_id, scope_hash=scope, decision=ApprovalDecision.REJECTED, approver="r1")
    result = _run(coord.publish(package=pkg, target_commit_request=req, approval=appr))
    assert result.status == PublicationStatus.APPROVAL_REJECTED
    assert commit.calls == 0


def test_package_review_required_no_commit():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    pkg = _build_pkg(reg, p1, j1, wid)
    pkg.requires_manual_review = True
    commit = AsyncFakeCommit()
    coord, versions, journal, life, v1 = _make_coord(reg, commit=commit)
    req = _make_request(pkg)
    result = _run(coord.publish(package=pkg, target_commit_request=req, approval=_approval(pkg, req)))
    assert result.status == PublicationStatus.PACKAGE_REVIEW_REQUIRED
    assert commit.calls == 0


def test_full_publication_finalized():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    p1, j1, wid = _setup_p2j(reg, svc)
    coord, versions, journal, life, v1 = _make_coord(reg)
    reg.bind_source_version(p1.source_version_id, v1.version_id, v1.snapshot_id)
    pkg = _build_pkg(reg, p1, j1, wid)
    req = _make_request(pkg)
    result = _run(coord.publish(package=pkg, target_commit_request=req, approval=_approval(pkg, req)))
    assert result.status == PublicationStatus.FINALIZED, result.last_error
    rec = journal.get(pkg.package_id)
    assert rec.phase == PublicationPhase.FINALIZED
    assert rec.final_version_id != rec.target_version_id
    new = reg.get_source_version(j1.source_version_id)
    assert new.kb_version_id == rec.final_version_id
