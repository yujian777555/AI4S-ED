"""Phase 5.3-R3 tests: commit-store/manifest integrity closure."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json as _json

import pytest

from knowledge_curator.core.revision_publication import (
    RevisionPublicationCoordinator,
    _frozen_hash_assertion,
    _frozen_hash_decision,
)
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
)


def _assertion(aid="J-A1", ref="REF-N", value=2.0, locator="p.b"):
    return Assertion(
        id=aid, ref_id=ref,
        subject=Subject(eddo_class="Membrane", resolved_entity="E", original_mention="E"),
        property="P1",
        object=ObjectValue(value=value, unit="kWh", value_type=ValueType.NUMBER),
        conditions=[Condition(eddo_class="T", value=298, unit="K")],
        provenance=Provenance(locator=locator, sentence="s"),
        claim_type=ClaimType.MEASUREMENT,
        source_claim_origin=SourceClaimOrigin.PRIMARY,
        confidence=Confidence.HIGH, quality=0.9,
    )


class FakePkg:
    def __init__(self):
        self.package_id = "P1"
        self.work_id = "W1"
        self.prior_source_version_id = "P1SV"
        self.new_source_version_id = "N1"
        self.new_ref_id = "REF-N"
        self.prior_ref_id = "REF-P"
        self.relation = None  # will be set
        self.prior_bound_kb_version_id = "kbv-1"
        self.target_assertions = [_assertion()]
        self.requires_manual_review = False
        self.trace_id = "t1"
        self.provenance_id = "p1"


def _mk_request():
    assertions = [_assertion()]
    aset = AssertionSet(
        ref_id="REF-N",
        metadata=DocumentMetadata(title="T", authors=["A"], year=2024, source="S", doi="10.1/x", stable_id="S1"),
        assertions=assertions, quality_grade=QualityGrade.B,
    )
    report = CurationReport(
        report_id="R", source_ref_id="REF-N", status="successful",
        completeness=CompletenessResult(status=CompletenessStatus.OK, metadata_valid=True, assertion_count=1, allows_formal_curation=True, requires_manual_review=False, requires_return_upstream=False, issues=[]),
        conflicts=[],
        decisions=[AssertionDecision(assertion_id="J-A1", action=CurationAction.ACCEPT, confidence=Confidence.HIGH, reason="ok")],
    )
    return CommitRequest(source=SourceIdentity(ref_id="REF-N", source_fingerprint="fp"), assertion_set=aset, report=report)


def _mk_manifest():
    return SnapshotManifest(
        ref_id="REF-N", source_fingerprint="fp",
        assertion_hashes=[_frozen_hash_assertion(_assertion())],
        usdo_hashes=["u1"], vector_ids=["v1"],
        metadata_hash="will-be-computed",
        decision_hashes=[_frozen_hash_decision("J-A1", "accept", "high", "active")],
    )


class FakeAdmitted:
    def __init__(self, assertion, action="accept", confidence="high", visibility="active"):
        self.assertion = assertion
        self.action = action
        self.confidence = confidence
        self.visibility = visibility


class FakeCommitRecord:
    def __init__(self, admitted=None, metadata_hash=None, manifest=None, phase="published", version_id="v1", snapshot_id="s1", ref_id="REF-N", source_fingerprint="fp"):
        self.admitted = admitted or []
        self.metadata_hash = metadata_hash
        self.manifest = manifest
        self.phase = phase
        self.version_id = version_id
        self.snapshot_id = snapshot_id
        self.ref_id = ref_id
        self.source_fingerprint = source_fingerprint


class FakeStore:
    def __init__(self, record):
        self.record = record
    def find_by_key(self, ref, fp):
        return self.record


def _make_coord(store, commit=None):
    from knowledge_curator.adapters.in_memory_commit import InMemoryVersionStore, FailureInjection
    from knowledge_curator.adapters.in_memory_lifecycle import InMemoryEventOutbox, InMemoryLifecycleStore
    from knowledge_curator.adapters.in_memory_revision_publication import InMemoryRevisionPublicationStore
    from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
    from knowledge_curator.core.lifecycle import LifecycleRevisionCoordinator
    from knowledge_curator.core.lifecycle_visibility import make_version_visible_fn

    versions = InMemoryVersionStore(failures=FailureInjection())
    lstore = InMemoryLifecycleStore(version_visible=make_version_visible_fn(versions))
    outbox = InMemoryEventOutbox()
    life = LifecycleRevisionCoordinator(lifecycle_store=lstore, outbox=outbox, version_store=versions)
    journal = InMemoryRevisionPublicationStore()
    coord = RevisionPublicationCoordinator(
        publication_store=journal, source_registry=InMemorySourceVersionRegistry(),
        version_store=versions, lifecycle_coordinator=life,
        document_commit_coordinator=commit,
        document_commit_store=store,
    )
    return coord, versions, journal, life


def test_document_commit_store_required():
    """document_commit_store=None -> FAILED before any side effect."""
    coord, versions, journal, life = _make_coord(store=None)
    pkg = FakePkg()
    req = _mk_request()
    from knowledge_curator.core.revision_publication import compute_publication_scope_hash
    from knowledge_curator.schemas.revision_publication import ApprovalDecision, RevisionApproval
    scope = compute_publication_scope_hash(pkg, req)
    appr = RevisionApproval(approval_id="A", package_id="P1", scope_hash=scope, decision=ApprovalDecision.APPROVED, approver="r")
    result = asyncio.run(coord.publish(package=pkg, target_commit_request=req, approval=appr))
    assert result.status.value == "failed"
    assert "commit_store" in (result.last_error or "").lower() or "required" in (result.last_error or "").lower()


def test_frozen_assertion_hash_mirror():
    """_frozen_hash_assertion produces deterministic SHA256."""
    a = _assertion()
    h1 = _frozen_hash_assertion(a)
    h2 = _frozen_hash_assertion(a)
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex


def test_frozen_decision_hash_mirror():
    h1 = _frozen_hash_decision("A1", "accept", "high", "active")
    h2 = _frozen_hash_decision("A1", "accept", "high", "active")
    assert h1 == h2
    h3 = _frozen_hash_decision("A1", "downgrade", "high", "active")
    assert h1 != h3


def _mk_valid_record():
    """Build a fully valid published record matching the request."""
    req = _mk_request()
    pkg = FakePkg()
    admitted = [FakeAdmitted(_assertion(), action="accept", confidence="high", visibility="active")]
    # Compute expected metadata hash
    meta = req.assertion_set.metadata
    meta_hash = hashlib.sha256(_json.dumps({
        "title": meta.title, "authors": list(meta.authors), "year": meta.year,
        "source": meta.source, "doi": meta.doi, "stable_id": meta.stable_id,
    }, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    manifest = _mk_manifest()
    manifest.metadata_hash = meta_hash
    manifest.content_hash = hashlib.sha256(_json.dumps(manifest.stable_payload(), sort_keys=True).encode()).hexdigest()
    rec = FakeCommitRecord(admitted=admitted, metadata_hash=meta_hash, manifest=manifest)
    return rec, req, pkg


def test_manifest_assertion_hash_tampered():
    rec, req, pkg = _mk_valid_record()
    rec.manifest.assertion_hashes = ["TAMPERED"]
    coord, _, _, _ = _make_coord(store=FakeStore(rec))
    err = coord._validate_committed_record_material(rec, req, pkg)
    assert err is not None and "assertion_hashes" in err


def test_manifest_decision_hash_tampered():
    rec, req, pkg = _mk_valid_record()
    rec.manifest.decision_hashes = ["TAMPERED"]
    coord, _, _, _ = _make_coord(store=FakeStore(rec))
    err = coord._validate_committed_record_material(rec, req, pkg)
    assert err is not None and "decision_hashes" in err


def test_manifest_metadata_hash_tampered():
    rec, req, pkg = _mk_valid_record()
    rec.manifest.metadata_hash = "WRONG"
    coord, _, _, _ = _make_coord(store=FakeStore(rec))
    err = coord._validate_committed_record_material(rec, req, pkg)
    assert err is not None and "metadata" in err


def test_manifest_missing_fail_closed():
    rec, req, pkg = _mk_valid_record()
    rec.manifest = None
    coord, _, _, _ = _make_coord(store=FakeStore(rec))
    err = coord._validate_committed_record_material(rec, req, pkg)
    assert err is not None and "manifest" in err


def test_post_target_missing_record_fail_closed():
    """commit returns PUBLISHED but store returns None -> FAILED."""
    from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
    from knowledge_curator.core.source_identity import IncrementalIntakeService
    from knowledge_curator.schemas.source_versions import SourceCandidate, SourceKind, VersionRelation

    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    cp = SourceCandidate(ref_id="REF-P", source_fingerprint="fp-pre", title="P", doi="10.1/p", stable_id="SP", source_kind=SourceKind.PREPRINT)
    dp = svc.prepare(cp)
    p1 = svc.proceed(cp, dp)
    cj = SourceCandidate(ref_id="REF-N", source_fingerprint="fp", title="N", doi="10.1/n", stable_id="SN", source_kind=SourceKind.JOURNAL,
                        explicit_work_id=dp.work_id, explicit_prior_version_id=p1.source_version_id,
                        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL)
    dj = svc.prepare(cj)
    j1 = svc.proceed(cj, dj)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")

    class FakeCommit:
        async def commit(self, request):
            from knowledge_curator.schemas.commit import CommitResult, CommitPhase, CommitStatus
            return CommitResult(status=CommitStatus.PUBLISHED, version_id="v1", snapshot_id="s1", commit_id="c1", phase=CommitPhase.PUBLISHED)

    store = FakeStore(None)  # find_by_key returns None
    coord, versions, journal, life = _make_coord(store=store, commit=FakeCommit())
    # Override registry
    coord._registry = reg
    # Need real version in VersionStore for validation
    m = SnapshotManifest(ref_id="REF-N", source_fingerprint="fp", assertion_hashes=["a"], usdo_hashes=[], vector_ids=[], metadata_hash="m", decision_hashes=[])
    m.content_hash = hashlib.sha256(_json.dumps(m.stable_payload(), sort_keys=True).encode()).hexdigest()
    snap = versions.create_snapshot(m)
    ver = versions.publish_version(snap.snapshot_id)

    # Build a proper package
    from knowledge_curator.core.version_delta import RevisionPackageBuilder
    from knowledge_curator.schemas.version_delta import (
        ContentUnit, ContentUnitKind, DeltaAssertionBatch,
        VersionAssertionInventory, VersionContentManifest,
    )
    from knowledge_curator.schemas.source_versions import VersionUpgradeIntent

    def _unit(uid, h="h1"):
        return ContentUnit(unit_id=uid, locator="p.1", kind=ContentUnitKind.TEXT, content_hash=h)

    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=dp.work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = VersionContentManifest(source_version_id=p1.source_version_id, ref_id="REF-P", source_fingerprint="fp-pre", units=[_unit("U1")])
    new_m = VersionContentManifest(source_version_id=j1.source_version_id, ref_id="REF-N", source_fingerprint="fp", units=[_unit("U1", "h2")])
    inv = VersionAssertionInventory(source_version_id=p1.source_version_id, ref_id="REF-P",
        assertions=[_assertion("A1", "REF-P", value=1.0, locator="p.a")], assertion_unit_map={"A1": "U1"})
    batch = DeltaAssertionBatch(source_version_id=j1.source_version_id, ref_id="REF-N",
        assertions=[_assertion("J-A1", "REF-N", value=2.0, locator="p.b")], assertion_unit_map={"J-A1": "U1"}, processed_unit_ids=["U1"])
    pkg = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch)
    # Build request matching package.target_assertions exactly
    pkg_assertions = list(pkg.target_assertions)
    aset = AssertionSet(
        ref_id="REF-N",
        metadata=DocumentMetadata(title="N", authors=["A"], year=2024, source="S", doi="10.1/n", stable_id="SN"),
        assertions=pkg_assertions, quality_grade=QualityGrade.B,
    )
    report = CurationReport(
        report_id="R", source_ref_id="REF-N", status="successful",
        completeness=CompletenessResult(status=CompletenessStatus.OK, metadata_valid=True, assertion_count=len(pkg_assertions), allows_formal_curation=True, requires_manual_review=False, requires_return_upstream=False, issues=[]),
        conflicts=[],
        decisions=[AssertionDecision(assertion_id=a.id, action=CurationAction.ACCEPT, confidence=a.confidence, reason="ok") for a in pkg_assertions],
    )
    req = CommitRequest(source=SourceIdentity(ref_id="REF-N", source_fingerprint="fp"), assertion_set=aset, report=report)
    from knowledge_curator.core.revision_publication import compute_publication_scope_hash
    from knowledge_curator.schemas.revision_publication import ApprovalDecision, RevisionApproval
    scope = compute_publication_scope_hash(pkg, req)
    appr = RevisionApproval(approval_id="A", package_id=pkg.package_id, scope_hash=scope, decision=ApprovalDecision.APPROVED, approver="r")

    # Patch commit to return real version
    class FakeCommit2:
        async def commit(self, request):
            from knowledge_curator.schemas.commit import CommitResult, CommitPhase, CommitStatus
            return CommitResult(status=CommitStatus.PUBLISHED, version_id=ver.version_id, snapshot_id=snap.snapshot_id, commit_id="c1", phase=CommitPhase.PUBLISHED)
    coord._commit = FakeCommit2()
    result = asyncio.run(coord.publish(package=pkg, target_commit_request=req, approval=appr))
    assert result.status.value == "failed"
    assert "missing" in (result.last_error or "")


def test_post_target_store_read_exception_fail_closed():
    class BrokenStore:
        def find_by_key(self, ref, fp):
            raise RuntimeError("store broken")

    class FakeCommit:
        async def commit(self, request):
            from knowledge_curator.schemas.commit import CommitResult, CommitPhase, CommitStatus
            return CommitResult(status=CommitStatus.PUBLISHED, version_id="v1", snapshot_id="s1", commit_id="c1", phase=CommitPhase.PUBLISHED)

    coord, versions, journal, life = _make_coord(store=BrokenStore(), commit=FakeCommit())
    pkg = FakePkg()
    req = _mk_request()
    from knowledge_curator.core.revision_publication import compute_publication_scope_hash
    from knowledge_curator.schemas.revision_publication import ApprovalDecision, RevisionApproval
    scope = compute_publication_scope_hash(pkg, req)
    appr = RevisionApproval(approval_id="A", package_id="P1", scope_hash=scope, decision=ApprovalDecision.APPROVED, approver="r")
    result = asyncio.run(coord.publish(package=pkg, target_commit_request=req, approval=appr))
    assert result.status.value == "failed"


def test_published_empty_admitted_with_target_conflict():
    """PUBLISHED record with empty admitted but package target non-empty -> CONFLICT."""
    rec, req, pkg = _mk_valid_record()
    rec.admitted = []  # tamper: empty admitted
    coord, _, _, _ = _make_coord(store=FakeStore(rec))
    err = coord._validate_committed_record_material(rec, req, pkg)
    assert err is not None and "empty admitted" in err
