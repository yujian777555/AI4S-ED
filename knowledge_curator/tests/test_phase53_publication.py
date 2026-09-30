"""Phase 5.3 tests: revision publication orchestration."""

from __future__ import annotations

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
from knowledge_curator.core.lifecycle import (
    LifecycleRevisionCoordinator,
    build_revision_draft,
)
from knowledge_curator.core.lifecycle_visibility import make_version_visible_fn
from knowledge_curator.core.revision_publication import (
    RevisionPublicationCoordinator,
    compute_publication_scope_hash,
)
from knowledge_curator.core.source_identity import IncrementalIntakeService
from knowledge_curator.core.version_delta import RevisionPackageBuilder
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
from knowledge_curator.schemas.curation import CurationAction
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
from knowledge_curator.schemas.revision_publication import (
    ApprovalDecision,
    PublicationPhase,
    PublicationStatus,
    RevisionApproval,
)
from knowledge_curator.schemas.commit import SnapshotManifest


def _unit(uid, loc="p.1", h="h1"):
    return ContentUnit(unit_id=uid, locator=loc, kind=ContentUnitKind.TEXT, content_hash=h)


def _manifest(sid, ref, fp, units):
    return VersionContentManifest(source_version_id=sid, ref_id=ref, source_fingerprint=fp, units=units)


def _assertion(aid, ref, entity="E1", value=1.0, locator="p.1"):
    return Assertion(
        id=aid,
        ref_id=ref,
        subject=Subject(eddo_class="Membrane", resolved_entity=entity, original_mention=entity),
        property="P1",
        object=ObjectValue(value=value, unit="kWh", value_type=ValueType.NUMBER),
        conditions=[Condition(eddo_class="T", value=298, unit="K")],
        provenance=Provenance(locator=locator, sentence="s"),
        claim_type=ClaimType.MEASUREMENT,
        source_claim_origin=SourceClaimOrigin.PRIMARY,
        confidence=Confidence.HIGH,
        quality=0.9,
    )


class FakeDecision:
    def __init__(self, aid, action="accept", conf="high"):
        self.assertion_id = aid
        self.action = action
        self.confidence = conf


class FakeReport:
    def __init__(self, decisions, source_ref_id="JOURNAL-1"):
        self.decisions = decisions
        self.source_ref_id = source_ref_id
        self.status = "successful"


class FakeCommitResult:
    def __init__(self, status="published", version_id="kbv-t", snapshot_id="snap-t", commit_id="c-1"):
        self.status = status
        self.version_id = version_id
        self.snapshot_id = snapshot_id
        self.commit_id = commit_id


class FakeCommitCoordinator:
    def __init__(self, results=None):
        self.results = results or []
        self.calls = 0

    def commit(self, request):
        self.calls += 1
        if self.results:
            return self.results.pop(0)
        return FakeCommitResult()


def _setup_full():
    """Build registry + package + versions for a P2J upgrade."""
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    cp = SourceCandidate(
        ref_id="ARXIV-1", source_fingerprint="fp-pre", title="Preprint",
        doi="10.48550/arxiv.1", stable_id="A:1", source_kind=SourceKind.PREPRINT,
    )
    dp = svc.prepare(cp)
    p1 = svc.proceed(cp, dp)
    cj = SourceCandidate(
        ref_id="JOURNAL-1", source_fingerprint="fp-j", title="Journal",
        doi="10.1000/j.1", stable_id="J:1", source_kind=SourceKind.JOURNAL,
        explicit_work_id=dp.work_id,
        explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    dj = svc.prepare(cj)
    j1 = svc.proceed(cj, dj)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")

    # Build RevisionPackage
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=dp.work_id,
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
    pkg = builder.build(
        intent=intent, prior_manifest=prior_m, new_manifest=new_m,
        prior_inventory=inv, delta_batch=batch,
    )
    return reg, svc, p1, j1, dp.work_id, pkg


def _make_coordinator(reg, versions=None, commit=None, lifecycle=None):
    versions = versions or InMemoryVersionStore(failures=FailureInjection())
    # Seed V1 so lifecycle can publish
    m = SnapshotManifest(
        ref_id="ARXIV-1", source_fingerprint="fp-pre",
        assertion_hashes=["a1"], usdo_hashes=["u1"], vector_ids=["v1"],
        metadata_hash="m1", decision_hashes=["d1"],
    )
    import hashlib
    import json as _json
    m.content_hash = hashlib.sha256(_json.dumps(m.stable_payload(), sort_keys=True).encode()).hexdigest()
    snap = versions.create_snapshot(m)
    v1 = versions.publish_version(snap.snapshot_id)

    # Create a real target version for FakeCommitResult to reference
    mt = SnapshotManifest(
        ref_id="JOURNAL-1", source_fingerprint="fp-j",
        assertion_hashes=["j1"], usdo_hashes=["ju1"], vector_ids=["jv1"],
        metadata_hash="jm1", decision_hashes=["jd1"],
    )
    mt.content_hash = hashlib.sha256(_json.dumps(mt.stable_payload(), sort_keys=True).encode()).hexdigest()
    snap_t = versions.create_snapshot(mt)
    v_target = versions.publish_version(snap_t.snapshot_id)

    lstore = InMemoryLifecycleStore(version_visible=make_version_visible_fn(versions))
    outbox = InMemoryEventOutbox()
    life = lifecycle or LifecycleRevisionCoordinator(
        lifecycle_store=lstore, outbox=outbox, version_store=versions
    )
    journal = InMemoryRevisionPublicationStore()
    if commit is None:
        commit = FakeCommitCoordinator([
            FakeCommitResult(status="published", version_id=v_target.version_id, snapshot_id=v_target.snapshot_id)
        ])
    coord = RevisionPublicationCoordinator(
        publication_store=journal,
        source_registry=reg,
        version_store=versions,
        lifecycle_coordinator=life,
        document_commit_coordinator=commit,
        document_commit_store=InMemoryDocumentCommitStore(),
    )
    return coord, versions, journal, life, v1


def _approval(pkg, scope="scope1"):
    return RevisionApproval(
        approval_id="APP-1",
        package_id=pkg.package_id,
        scope_hash=scope,
        decision=ApprovalDecision.APPROVED,
        approver="reviewer-1",
        rationale="approved for publication",
    )


# ---- approval-before-side-effects ----

def test_missing_approval_no_commit():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    commit = FakeCommitCoordinator()
    coord, versions, journal, life, v1 = _make_coordinator(reg, commit=commit)
    result = coord.publish(package=pkg)
    assert result.status == PublicationStatus.APPROVAL_REQUIRED
    assert commit.calls == 0
    assert journal.get(pkg.package_id) is None or journal.get(pkg.package_id).phase == PublicationPhase.PREPARED


def test_rejected_approval_no_commit():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    commit = FakeCommitCoordinator()
    coord, versions, journal, life, v1 = _make_coordinator(reg, commit=commit)
    scope = compute_publication_scope_hash(pkg, None)
    appr = RevisionApproval(
        approval_id="APP-R", package_id=pkg.package_id, scope_hash=scope,
        decision=ApprovalDecision.REJECTED, approver="reviewer-1",
    )
    result = coord.publish(package=pkg, approval=appr)
    assert result.status == PublicationStatus.APPROVAL_REJECTED
    assert commit.calls == 0


def test_package_requires_manual_review_no_commit():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    pkg.requires_manual_review = True
    commit = FakeCommitCoordinator()
    coord, versions, journal, life, v1 = _make_coordinator(reg, commit=commit)
    result = coord.publish(package=pkg, approval=_approval(pkg))
    assert result.status == PublicationStatus.PACKAGE_REVIEW_REQUIRED
    assert commit.calls == 0


def test_wrong_scope_hash_no_commit():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    commit = FakeCommitCoordinator()
    coord, versions, journal, life, v1 = _make_coordinator(reg, commit=commit)
    appr = RevisionApproval(
        approval_id="APP-1", package_id=pkg.package_id, scope_hash="WRONG",
        decision=ApprovalDecision.APPROVED, approver="r1",
    )
    result = coord.publish(package=pkg, approval=appr)
    assert result.status == PublicationStatus.CONFLICT
    assert commit.calls == 0


# ---- curation gate ----

def test_curation_reject_blocks_publication():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    commit = FakeCommitCoordinator()
    coord, versions, journal, life, v1 = _make_coordinator(reg, commit=commit)
    report = FakeReport([FakeDecision("J-A1", action="reject")])
    scope = compute_publication_scope_hash(pkg, None)
    result = coord.publish(package=pkg, curation_report=report, approval=_approval(pkg, scope))
    assert result.status == PublicationStatus.FAILED
    assert "not publishable" in (result.last_error or "")
    assert commit.calls == 0


# ---- target commit ----

def test_valid_target_commit_publishes():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    coord, versions, journal, life, v1 = _make_coordinator(reg)
    scope = compute_publication_scope_hash(pkg, None)
    result = coord.publish(package=pkg, approval=_approval(pkg, scope))
    # Should progress past target commit
    assert coord._commit.calls == 1
    rec = journal.get(pkg.package_id)
    assert rec is not None
    assert rec.phase in (PublicationPhase.TARGET_PUBLISHED, PublicationPhase.LIFECYCLE_PUBLISHED, PublicationPhase.FINALIZED)


def test_pending_vector_stops():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    commit = FakeCommitCoordinator([FakeCommitResult(status="pending_vector")])
    coord, versions, journal, life, v1 = _make_coordinator(reg, commit=commit)
    scope = compute_publication_scope_hash(pkg, None)
    result = coord.publish(package=pkg, approval=_approval(pkg, scope))
    assert result.status == PublicationStatus.TARGET_PENDING
    rec = journal.get(pkg.package_id)
    assert rec.phase == PublicationPhase.PREPARED  # not advanced


def test_failed_commit_stops():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    commit = FakeCommitCoordinator([FakeCommitResult(status="failed")])
    coord, versions, journal, life, v1 = _make_coordinator(reg, commit=commit)
    scope = compute_publication_scope_hash(pkg, None)
    result = coord.publish(package=pkg, approval=_approval(pkg, scope))
    assert result.status == PublicationStatus.FAILED


# ---- full happy path ----

def _run_full_publication(reg, pkg, versions=None, commit=None):
    coord, versions, journal, life, v1 = _make_coordinator(reg, versions=versions, commit=commit)
    scope = compute_publication_scope_hash(pkg, None)
    result = coord.publish(package=pkg, approval=_approval(pkg, scope))
    return coord, versions, journal, life, v1, result


def test_full_publication_finalized():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    coord, versions, journal, life, v1, result = _run_full_publication(reg, pkg)
    assert result.status == PublicationStatus.FINALIZED
    rec = journal.get(pkg.package_id)
    assert rec.phase == PublicationPhase.FINALIZED
    # V_final != V_target
    assert rec.final_version_id != rec.target_version_id
    # V_final.prior_version_id == V_target
    final_ver = versions.get_version(rec.final_version_id)
    assert final_ver.prior_version_id == rec.target_version_id
    # new SourceVersion bound to V_final, not V_target
    new = reg.get_source_version(j1.source_version_id)
    assert new.kb_version_id == rec.final_version_id
    assert new.kb_version_id != rec.target_version_id
    # prior binding unchanged
    prior = reg.get_source_version(p1.source_version_id)
    assert prior.kb_version_id == "kbv-1"


def test_full_replay_idempotent():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    coord, versions, journal, life, v1, result1 = _run_full_publication(reg, pkg)
    assert result1.status == PublicationStatus.FINALIZED
    # Replay with same material
    scope = compute_publication_scope_hash(pkg, None)
    result2 = coord.publish(package=pkg, approval=_approval(pkg, scope))
    assert result2.status == PublicationStatus.FINALIZED
    assert result2.idempotent is True


# ---- lifecycle recovery ----

def test_lifecycle_failure_leaves_unbound():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    coord, versions, journal, life, v1 = _make_coordinator(reg)

    class FailingLifecycle:
        def apply_revision(self, draft, source_fingerprint=None):
            raise RuntimeError("simulated lifecycle failure")

    coord._lifecycle = FailingLifecycle()
    scope = compute_publication_scope_hash(pkg, None)
    result = coord.publish(package=pkg, approval=_approval(pkg, scope))
    assert result.status in (PublicationStatus.LIFECYCLE_PENDING, PublicationStatus.FAILED)
    new = reg.get_source_version(j1.source_version_id)
    assert new.kb_version_id is None  # unbound


def test_bind_after_lifecycle_recovery():
    """Lifecycle succeeds but bind fails once -> retry completes."""
    reg, svc, p1, j1, wid, pkg = _setup_full()
    coord, versions, journal, life, v1 = _make_coordinator(reg)

    # First run: bind will fail once
    orig_bind = reg.bind_source_version
    state = {"failed": False}
    def flaky_bind(sid, kb, snap):
        if not state["failed"]:
            state["failed"] = True
            raise ValueError("simulated bind crash")
        return orig_bind(sid, kb, snap)
    reg.bind_source_version = flaky_bind

    scope = compute_publication_scope_hash(pkg, None)
    result1 = coord.publish(package=pkg, approval=_approval(pkg, scope))
    assert result1.status in (PublicationStatus.FAILED, PublicationStatus.LIFECYCLE_PENDING)
    # Retry with working bind
    reg.bind_source_version = orig_bind
    result2 = coord.publish(package=pkg, approval=_approval(pkg, scope))
    assert result2.status == PublicationStatus.FINALIZED


# ---- stale base ----

def test_stale_base_fail_closed():
    """Insert unrelated version after target publish -> lifecycle fails closed."""
    reg, svc, p1, j1, wid, pkg = _setup_full()
    coord, versions, journal, life, v1 = _make_coordinator(reg)

    # Intercept: after target commit, insert unrelated version
    orig_commit = coord._run_target_commit
    def commit_then_interleave(package, request, record):
        r = orig_commit(package, request, record)
        if r is None:
            # Insert unrelated version to make target stale
            m2 = SnapshotManifest(
                ref_id="OTHER", source_fingerprint="fp-x",
                assertion_hashes=["x"], usdo_hashes=[], vector_ids=[],
                metadata_hash="mx", decision_hashes=[],
            )
            import hashlib
            import json as _json
            m2.content_hash = hashlib.sha256(_json.dumps(m2.stable_payload(), sort_keys=True).encode()).hexdigest()
            s2 = versions.create_snapshot(m2)
            versions.publish_version(s2.snapshot_id)
        return r
    coord._run_target_commit = commit_then_interleave

    scope = compute_publication_scope_hash(pkg, None)
    result = coord.publish(package=pkg, approval=_approval(pkg, scope))
    assert result.status == PublicationStatus.CONFLICT
    new = reg.get_source_version(j1.source_version_id)
    assert new.kb_version_id is None  # no bind


# ---- P2J visibility E2E ----

def test_p2j_visibility_e2e():
    reg, svc, p1, j1, wid, pkg = _setup_full()
    coord, versions, journal, life, v1, result = _run_full_publication(reg, pkg)
    assert result.status == PublicationStatus.FINALIZED

    # Visibility check
    from knowledge_curator.adapters.in_memory_lifecycle import InMemoryLifecycleStore
    # lifecycle coordinator has its own store - get from coordinator
    # We need the lifecycle store used during publication
    # Rebuild visibility from the same store
    # The lifecycle coordinator was created inside _make_coordinator
    # Let's query via the lifecycle coordinator's store
    lstore = life._lifecycle
    vis = InMemoryLifecycleVisibility(lstore)

    # Prior preprint ref -> superseded/ineligible
    assert vis.document_eligibility("ARXIV-1").visible_for_retrieval is False
    assert vis.document_eligibility("ARXIV-1").eligible_for_training is False
    # New journal ref -> active/eligible
    assert vis.document_eligibility("JOURNAL-1").visible_for_retrieval is True
    # Historical V1 still resolvable
    assert versions.get_version(v1.version_id) is not None
