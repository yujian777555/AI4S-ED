"""Phase 5.3-R2 tests: typed canonical material + decision/manifest lock."""

from __future__ import annotations

import asyncio
import copy

import pytest

from knowledge_curator.core.revision_publication import (
    canonical_assertion_material,
    canonical_value,
    compute_publication_scope_hash,
)
from knowledge_curator.schemas.curation import CurationAction
from knowledge_curator.schemas.assertions import (
    Assertion,
    ClaimType,
    Confidence,
    Condition,
    ObjectValue,
    Provenance,
    SourceClaimOrigin,
    Subject,
    ValueType,
)


def _assertion(aid="A1", value=1.0, conds=None):
    return Assertion(
        id=aid, ref_id="R1",
        subject=Subject(eddo_class="M", resolved_entity="E", original_mention="E"),
        property="P",
        object=ObjectValue(value=value, unit="u", value_type=ValueType.NUMBER),
        conditions=conds or [],
        provenance=Provenance(locator="p.1", sentence="s"),
        claim_type=ClaimType.MEASUREMENT,
        source_claim_origin=SourceClaimOrigin.PRIMARY,
        confidence=Confidence.HIGH, quality=0.9,
    )


# ---- typed canonical values ----

def test_condition_int_vs_str_differs():
    a1 = _assertion(conds=[Condition(eddo_class="T", value=1, unit="K")])
    a2 = _assertion(conds=[Condition(eddo_class="T", value="1", unit="K")])
    assert canonical_assertion_material(a1) != canonical_assertion_material(a2)


def test_list_vs_string_differs():
    a1 = _assertion(value=[1, 2])
    a2 = _assertion(value="[1, 2]")
    assert canonical_assertion_material(a1) != canonical_assertion_material(a2)


def test_dict_insertion_order_stable():
    a1 = _assertion(conds=[Condition(eddo_class="T", value={"a": 1, "b": 2}, unit=None)])
    a2 = _assertion(conds=[Condition(eddo_class="T", value={"b": 2, "a": 1}, unit=None)])
    assert canonical_assertion_material(a1) == canonical_assertion_material(a2)


def test_nested_condition_change_changes_scope():
    from knowledge_curator.schemas.commit import CommitRequest, SourceIdentity
    from knowledge_curator.schemas.assertions import AssertionSet, DocumentMetadata, QualityGrade
    from knowledge_curator.schemas.curation import (
        AssertionDecision, CompletenessResult, CompletenessStatus, CurationAction, CurationReport,
    )

    def _mk_pkg_and_req(cond_value):
        class FakePkg:
            package_id = "P1"
            new_source_version_id = "N1"
            new_ref_id = "REF-N"
            prior_ref_id = "REF-P"
            target_assertions = [
                _assertion("J-A1", value=1.0, conds=[Condition(eddo_class="T", value=cond_value, unit="K")])
            ]
        pkg = FakePkg()
        assertions = list(pkg.target_assertions)
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
        req = CommitRequest(source=SourceIdentity(ref_id="REF-N", source_fingerprint="fp"), assertion_set=aset, report=report)
        return pkg, req

    pkg1, req1 = _mk_pkg_and_req({"x": 1})
    pkg2, req2 = _mk_pkg_and_req({"x": 2})
    h1 = compute_publication_scope_hash(pkg1, req1)
    h2 = compute_publication_scope_hash(pkg2, req2)
    assert h1 != h2


def test_canonical_value_types():
    assert canonical_value(1) == 1
    assert canonical_value("1") == "1"
    assert canonical_value(1) != canonical_value("1")
    assert canonical_value([1, 2]) == [1, 2]
    assert canonical_value([1, 2]) != canonical_value("[1, 2]")
    assert canonical_value({"a": 1, "b": 2}) == canonical_value({"b": 2, "a": 1})
    assert canonical_value((1, 2)) != canonical_value([1, 2])


# ---- existing decision guard (unit-level with fake store) ----

class FakeAdmitted:
    def __init__(self, assertion, action="accept", confidence="high", visibility="active"):
        self.assertion = assertion
        self.action = action
        self.confidence = confidence
        self.visibility = visibility


class FakeCommitRecord:
    def __init__(self, admitted, metadata_hash=None, manifest=None):
        self.admitted = admitted
        self.metadata_hash = metadata_hash
        self.manifest = manifest
        self.phase = "published"
        self.version_id = "v1"
        self.snapshot_id = "s1"


class FakeStore:
    def __init__(self, record):
        self.record = record
    def find_by_key(self, ref, fp):
        return self.record


def _run(coro):
    return asyncio.run(coro)


def _make_pkg_req_for_guard():
    from knowledge_curator.schemas.commit import CommitRequest, SourceIdentity
    from knowledge_curator.schemas.assertions import AssertionSet, DocumentMetadata, QualityGrade
    from knowledge_curator.schemas.curation import (
        AssertionDecision, CompletenessResult, CompletenessStatus, CurationAction, CurationReport,
    )

    class FakePkg:
        package_id = "P1"
        new_source_version_id = "N1"
        new_ref_id = "REF-N"
        prior_ref_id = "REF-P"
        target_assertions = [_assertion("J-A1", value=2.0)]
    pkg = FakePkg()
    assertions = list(pkg.target_assertions)
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
    req = CommitRequest(source=SourceIdentity(ref_id="REF-N", source_fingerprint="fp"), assertion_set=aset, report=report)
    return pkg, req


def test_existing_accept_vs_downgrade_conflict():
    from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator
    from knowledge_curator.adapters.in_memory_revision_publication import InMemoryRevisionPublicationStore
    from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
    from knowledge_curator.adapters.in_memory_commit import InMemoryVersionStore, FailureInjection

    pkg, req = _make_pkg_req_for_guard()
    # Existing: ACCEPT/ACTIVE
    record = FakeCommitRecord([FakeAdmitted(_assertion("J-A1", value=2.0), action="accept", confidence="high", visibility="active")])
    store = FakeStore(record)
    versions = InMemoryVersionStore(failures=FailureInjection())
    coord = RevisionPublicationCoordinator(
        publication_store=InMemoryRevisionPublicationStore(),
        source_registry=InMemorySourceVersionRegistry(),
        version_store=versions,
        lifecycle_coordinator=None,
        document_commit_coordinator=None,
        document_commit_store=store,
    )
    # Change decision to DOWNGRADE
    req.report.decisions[0].action = CurationAction.DOWNGRADE
    err = coord._existing_commit_guard(pkg, req)
    assert err is not None
    assert err.status.value == "conflict"


def test_existing_confidence_mismatch_conflict():
    from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator
    from knowledge_curator.adapters.in_memory_revision_publication import InMemoryRevisionPublicationStore
    from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
    from knowledge_curator.adapters.in_memory_commit import InMemoryVersionStore, FailureInjection

    pkg, req = _make_pkg_req_for_guard()
    record = FakeCommitRecord([FakeAdmitted(_assertion("J-A1", value=2.0), action="accept", confidence="medium", visibility="active")])
    store = FakeStore(record)
    coord = RevisionPublicationCoordinator(
        publication_store=InMemoryRevisionPublicationStore(),
        source_registry=InMemorySourceVersionRegistry(),
        version_store=InMemoryVersionStore(failures=FailureInjection()),
        lifecycle_coordinator=None,
        document_commit_coordinator=None,
        document_commit_store=store,
    )
    err = coord._existing_commit_guard(pkg, req)  # request expects HIGH
    assert err is not None
    assert "confidence" in (err.last_error or "")


def test_existing_visibility_mismatch_conflict():
    from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator
    from knowledge_curator.adapters.in_memory_revision_publication import InMemoryRevisionPublicationStore
    from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
    from knowledge_curator.adapters.in_memory_commit import InMemoryVersionStore, FailureInjection

    pkg, req = _make_pkg_req_for_guard()
    # Request expects ACCEPT -> ACTIVE, but existing has DOWNGRADED
    record = FakeCommitRecord([FakeAdmitted(_assertion("J-A1", value=2.0), action="accept", confidence="high", visibility="downgraded")])
    store = FakeStore(record)
    coord = RevisionPublicationCoordinator(
        publication_store=InMemoryRevisionPublicationStore(),
        source_registry=InMemorySourceVersionRegistry(),
        version_store=InMemoryVersionStore(failures=FailureInjection()),
        lifecycle_coordinator=None,
        document_commit_coordinator=None,
        document_commit_store=store,
    )
    err = coord._existing_commit_guard(pkg, req)
    assert err is not None
    assert "visibility" in (err.last_error or "")


def test_existing_metadata_hash_mismatch_conflict():
    from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator
    from knowledge_curator.adapters.in_memory_revision_publication import InMemoryRevisionPublicationStore
    from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
    from knowledge_curator.adapters.in_memory_commit import InMemoryVersionStore, FailureInjection

    pkg, req = _make_pkg_req_for_guard()
    record = FakeCommitRecord([FakeAdmitted(_assertion("J-A1", value=2.0))], metadata_hash="WRONG")
    store = FakeStore(record)
    coord = RevisionPublicationCoordinator(
        publication_store=InMemoryRevisionPublicationStore(),
        source_registry=InMemorySourceVersionRegistry(),
        version_store=InMemoryVersionStore(failures=FailureInjection()),
        lifecycle_coordinator=None,
        document_commit_coordinator=None,
        document_commit_store=store,
    )
    err = coord._existing_commit_guard(pkg, req)
    assert err is not None
    assert "metadata" in (err.last_error or "")


def test_commit_store_unreadable_fail_closed():
    from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator
    from knowledge_curator.adapters.in_memory_revision_publication import InMemoryRevisionPublicationStore
    from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
    from knowledge_curator.adapters.in_memory_commit import InMemoryVersionStore, FailureInjection

    pkg, req = _make_pkg_req_for_guard()

    class BrokenStore:
        def find_by_key(self, ref, fp):
            raise RuntimeError("store broken")

    coord = RevisionPublicationCoordinator(
        publication_store=InMemoryRevisionPublicationStore(),
        source_registry=InMemorySourceVersionRegistry(),
        version_store=InMemoryVersionStore(failures=FailureInjection()),
        lifecycle_coordinator=None,
        document_commit_coordinator=None,
        document_commit_store=BrokenStore(),
    )
    err = coord._existing_commit_guard(pkg, req)
    assert err is not None
    assert err.status.value == "failed"


# ---- strict published-manifest / post-target store agreement ----

def test_existing_published_missing_manifest_fails_closed():
    from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator
    from knowledge_curator.adapters.in_memory_revision_publication import InMemoryRevisionPublicationStore
    from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
    from knowledge_curator.adapters.in_memory_commit import InMemoryVersionStore, FailureInjection

    pkg, req = _make_pkg_req_for_guard()
    versions = InMemoryVersionStore(failures=FailureInjection())
    coord = RevisionPublicationCoordinator(
        publication_store=InMemoryRevisionPublicationStore(),
        source_registry=InMemorySourceVersionRegistry(),
        version_store=versions,
        lifecycle_coordinator=None,
        document_commit_coordinator=None,
        document_commit_store=None,
    )
    record = FakeCommitRecord(
        [FakeAdmitted(_assertion("J-A1", value=2.0))],
        metadata_hash=coord._expected_metadata_hash(req),
        manifest=None,
    )
    coord._commit_store = FakeStore(record)
    err = coord._existing_commit_guard(pkg, req)
    assert err is not None
    assert err.status.value == "conflict"
    assert "manifest" in (err.last_error or "")


def test_existing_published_manifest_assertion_hashes_mismatch_conflict():
    from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator
    from knowledge_curator.adapters.in_memory_revision_publication import InMemoryRevisionPublicationStore
    from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
    from knowledge_curator.adapters.in_memory_commit import InMemoryVersionStore, FailureInjection
    from knowledge_curator.schemas.commit import SnapshotManifest

    pkg, req = _make_pkg_req_for_guard()
    versions = InMemoryVersionStore(failures=FailureInjection())
    coord = RevisionPublicationCoordinator(
        publication_store=InMemoryRevisionPublicationStore(),
        source_registry=InMemorySourceVersionRegistry(),
        version_store=versions,
        lifecycle_coordinator=None,
        document_commit_coordinator=None,
        document_commit_store=None,
    )
    mh = coord._expected_metadata_hash(req)
    manifest = SnapshotManifest(
        ref_id="REF-N", source_fingerprint="fp",
        assertion_hashes=["WRONG"], usdo_hashes=[], vector_ids=[],
        metadata_hash=mh, decision_hashes=[],
    )
    record = FakeCommitRecord(
        [FakeAdmitted(_assertion("J-A1", value=2.0))],
        metadata_hash=mh,
        manifest=manifest,
    )
    coord._commit_store = FakeStore(record)
    err = coord._existing_commit_guard(pkg, req)
    assert err is not None
    assert "assertion_hashes" in (err.last_error or "")


def test_existing_published_manifest_decision_hashes_mismatch_conflict():
    from knowledge_curator.core.revision_publication import (
        RevisionPublicationCoordinator,
        _commit_assertion_hash,
    )
    from knowledge_curator.adapters.in_memory_revision_publication import InMemoryRevisionPublicationStore
    from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
    from knowledge_curator.adapters.in_memory_commit import InMemoryVersionStore, FailureInjection
    from knowledge_curator.schemas.commit import SnapshotManifest

    pkg, req = _make_pkg_req_for_guard()
    versions = InMemoryVersionStore(failures=FailureInjection())
    coord = RevisionPublicationCoordinator(
        publication_store=InMemoryRevisionPublicationStore(),
        source_registry=InMemorySourceVersionRegistry(),
        version_store=versions,
        lifecycle_coordinator=None,
        document_commit_coordinator=None,
        document_commit_store=None,
    )
    mh = coord._expected_metadata_hash(req)
    manifest = SnapshotManifest(
        ref_id="REF-N", source_fingerprint="fp",
        assertion_hashes=[_commit_assertion_hash(req.assertion_set.assertions[0])],
        usdo_hashes=[], vector_ids=[], metadata_hash=mh,
        decision_hashes=["WRONG"],
    )
    record = FakeCommitRecord(
        [FakeAdmitted(_assertion("J-A1", value=2.0))],
        metadata_hash=mh,
        manifest=manifest,
    )
    coord._commit_store = FakeStore(record)
    err = coord._existing_commit_guard(pkg, req)
    assert err is not None
    assert "decision_hashes" in (err.last_error or "")


def _post_target_case(store_record_factory):
    import hashlib
    import json
    from types import SimpleNamespace

    from knowledge_curator.adapters.in_memory_commit import InMemoryVersionStore, FailureInjection
    from knowledge_curator.adapters.in_memory_revision_publication import InMemoryRevisionPublicationStore
    from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
    from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator
    from knowledge_curator.ports.document_commit_store import DocumentCommitRecord
    from knowledge_curator.schemas.commit import (
        CommitPhase, CommitResult, CommitStatus, SnapshotManifest,
    )
    from knowledge_curator.schemas.revision_publication import (
        PublicationPhase, RevisionPublicationRecord,
    )

    pkg, req = _make_pkg_req_for_guard()
    versions = InMemoryVersionStore(failures=FailureInjection())
    manifest = SnapshotManifest(
        ref_id="REF-N", source_fingerprint="fp",
        assertion_hashes=["a1"], usdo_hashes=["u1"], vector_ids=["v1"],
        metadata_hash="m1", decision_hashes=["d1"],
    )
    manifest.content_hash = hashlib.sha256(
        json.dumps(manifest.stable_payload(), sort_keys=True).encode()
    ).hexdigest()
    snap = versions.create_snapshot(manifest)
    ver = versions.publish_version(snap.snapshot_id)

    store_record = store_record_factory(
        DocumentCommitRecord(
            commit_id="dc-1", ref_id="REF-N", source_fingerprint="fp",
            phase=CommitPhase.PUBLISHED, snapshot_id=snap.snapshot_id,
            version_id=ver.version_id, manifest=copy.deepcopy(manifest),
        ),
        ver,
        snap,
    )
    store = FakeStore(store_record)

    class Committer:
        async def commit(self, request):
            return CommitResult(
                status=CommitStatus.PUBLISHED, commit_id="dc-1", phase=CommitPhase.PUBLISHED,
                version_id=ver.version_id, snapshot_id=snap.snapshot_id,
            )

    journal = InMemoryRevisionPublicationStore()
    pub_record = RevisionPublicationRecord(
        publication_id=pkg.package_id, package_id=pkg.package_id,
        request_material_hash="rmh", phase=PublicationPhase.PREPARED,
    )
    pub_record = journal.create(pub_record)
    coord = RevisionPublicationCoordinator(
        publication_store=journal,
        source_registry=InMemorySourceVersionRegistry(),
        version_store=versions,
        lifecycle_coordinator=None,
        document_commit_coordinator=Committer(),
        document_commit_store=store,
    )
    new = SimpleNamespace(ref_id="REF-N", source_fingerprint="fp")
    return coord, pkg, req, pub_record, new


def test_post_target_store_record_missing_fails_closed():
    coord, pkg, req, record, new = _post_target_case(lambda rec, ver, snap: None)
    err = _run(coord._run_target_commit(pkg, req, record, new))
    assert err is not None
    assert err.status.value == "failed"
    assert "record missing" in (err.last_error or "")


def test_post_target_version_mismatch_conflict():
    def mutate(rec, ver, snap):
        rec.version_id = "kbv-wrong"
        return rec
    coord, pkg, req, record, new = _post_target_case(mutate)
    err = _run(coord._run_target_commit(pkg, req, record, new))
    assert err is not None
    assert err.status.value == "conflict"
    assert "version_id" in (err.last_error or "")


def test_post_target_snapshot_mismatch_conflict():
    def mutate(rec, ver, snap):
        rec.snapshot_id = "snap-wrong"
        return rec
    coord, pkg, req, record, new = _post_target_case(mutate)
    err = _run(coord._run_target_commit(pkg, req, record, new))
    assert err is not None
    assert err.status.value == "conflict"
    assert "snapshot_id" in (err.last_error or "")


def test_post_target_missing_manifest_conflict():
    def mutate(rec, ver, snap):
        rec.manifest = None
        return rec
    coord, pkg, req, record, new = _post_target_case(mutate)
    err = _run(coord._run_target_commit(pkg, req, record, new))
    assert err is not None
    assert err.status.value == "conflict"
    assert "manifest missing" in (err.last_error or "")


def test_post_target_manifest_content_hash_mismatch_conflict():
    def mutate(rec, ver, snap):
        rec.manifest.content_hash = "WRONG"
        return rec
    coord, pkg, req, record, new = _post_target_case(mutate)
    err = _run(coord._run_target_commit(pkg, req, record, new))
    assert err is not None
    assert err.status.value == "conflict"
    assert "content_hash" in (err.last_error or "")


def test_post_target_exact_store_agreement_passes():
    coord, pkg, req, record, new = _post_target_case(lambda rec, ver, snap: rec)
    err = _run(coord._run_target_commit(pkg, req, record, new))
    assert err is None
