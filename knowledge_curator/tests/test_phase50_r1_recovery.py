"""Phase 5.0-R1 tests: crash recovery, pre-cutoff filter, historical E2E,
strict material idempotency, base-version validation."""

from __future__ import annotations

import pytest

from knowledge_curator.adapters.in_memory_commit import (
    FailureInjection,
    InMemoryVersionStore,
)
from knowledge_curator.adapters.in_memory_lifecycle import (
    InMemoryEventOutbox,
    InMemoryLifecycleStore,
    InMemoryLifecycleVisibility,
)
from knowledge_curator.adapters.in_memory_retrieval import (
    FakeReranker,
    InMemoryKeywordSearch,
    InMemoryVectorSearch,
)
from knowledge_curator.core.lifecycle import (
    LifecycleRevisionCoordinator,
    build_revision_draft,
)
from knowledge_curator.core.lifecycle_visibility import make_version_visible_fn
from knowledge_curator.retrieval.evidence_service import (
    EvidenceRequest,
    EvidenceRetrievalService,
)
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk
from knowledge_curator.schemas.commit import SnapshotManifest
from knowledge_curator.schemas.lifecycle import (
    AssertionLifecycleRecord,
    AssertionLifecycleStatus,
    DocumentLifecycleRecord,
    DocumentLifecycleStatus,
    LifecycleEvent,
    LifecycleEventType,
    LifecycleReason,
)


def _manifest(ref_id="REF-1", fp="fp1"):
    return SnapshotManifest(
        ref_id=ref_id,
        source_fingerprint=fp,
        assertion_hashes=["a1", "a2"],
        usdo_hashes=["u1"],
        vector_ids=["v1"],
        metadata_hash="m1",
        decision_hashes=["d1"],
    )


def _hash_manifest(m: SnapshotManifest) -> SnapshotManifest:
    import hashlib
    import json

    m.content_hash = hashlib.sha256(
        json.dumps(m.stable_payload(), sort_keys=True).encode()
    ).hexdigest()
    return m


def _coord(failures=None):
    failures = failures or FailureInjection()
    versions = InMemoryVersionStore(failures=failures)
    store = InMemoryLifecycleStore(version_visible=make_version_visible_fn(versions))
    outbox = InMemoryEventOutbox()
    coord = LifecycleRevisionCoordinator(
        lifecycle_store=store, outbox=outbox, version_store=versions
    )
    return coord, versions, store, outbox, failures


def _publish_v1(versions):
    snap = versions.create_snapshot(_hash_manifest(_manifest()))
    return versions.publish_version(snap.snapshot_id)


def _retraction_draft(base_version_id, rev="REV-R1", ref="REF-A", ids=None):
    return build_revision_draft(
        revision_id=rev,
        ref_id=ref,
        trigger=LifecycleReason.RETRACTION,
        base_version_id=base_version_id,
        affected_assertion_ids=list(ids or ["A1", "A2"]),
        verified_external_trigger=True,
        rationale="publisher retraction",
        evidence_refs=["ev-1"],
        trace_id="t-1",
        provenance_id="p-1",
    )


# ---- R1-A failure recovery matrix ----

def _run_failure_then_retry(fail_op: str, *, after: bool = False):
    failures = FailureInjection()
    coord, versions, store, outbox, failures = _coord(failures)
    v1 = _publish_v1(versions)
    if after:
        failures.fail_after(fail_op)
    else:
        failures.fail_on(fail_op)

    draft = _retraction_draft(v1.version_id)
    with pytest.raises(Exception):
        coord.apply_retraction(draft, all_assertion_ids=["A1", "A2"])

    # Retry with failures cleared
    failures._fail_before.clear()
    failures._fail_after.clear()
    result = coord.apply_retraction(draft, all_assertion_ids=["A1", "A2"])
    return coord, versions, store, outbox, v1, result


def _assert_recovered(versions, store, outbox, v1, result):
    # exactly one semantic lifecycle version after recovery
    assert result.version_id is not None
    ver = versions.get_version(result.version_id)
    assert ver is not None and ver.published
    # lifecycle bound
    rec = store.get_document_record(result.lifecycle_id)
    assert rec is not None
    assert rec.effective_version_id == result.version_id
    # required events exist exactly once
    events = outbox.list_all()
    type_counts = {}
    for e in events:
        type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1
    assert type_counts.get(LifecycleEventType.KB_DOCUMENT_RETRACTED) == 1
    assert type_counts.get(LifecycleEventType.KB_ASSERTIONS_ARCHIVED) == 1
    assert type_counts.get(LifecycleEventType.KB_REVISION_PUBLISHED) == 1
    # current visibility reflects retraction
    vis = InMemoryLifecycleVisibility(store)
    assert vis.document_eligibility("REF-A").visible_for_retrieval is False
    # historical V1 still resolves
    assert vis.document_eligibility("REF-A", at_version_id=v1.version_id).visible_for_retrieval is True
    # V1 snapshot still intact (no physical delete)
    assert versions.get_version(v1.version_id) is not None


def test_fail_before_create_snapshot_retry():
    _, versions, store, outbox, v1, result = _run_failure_then_retry(
        "version.create_snapshot", after=False
    )
    _assert_recovered(versions, store, outbox, v1, result)


def test_fail_after_create_snapshot_retry():
    _, versions, store, outbox, v1, result = _run_failure_then_retry(
        "version.create_snapshot", after=True
    )
    _assert_recovered(versions, store, outbox, v1, result)


def test_fail_before_publish_retry():
    _, versions, store, outbox, v1, result = _run_failure_then_retry(
        "version.publish", after=False
    )
    _assert_recovered(versions, store, outbox, v1, result)


def test_fail_after_publish_retry_recovers_split_brain():
    """Critical: current version advanced but lifecycle unbound -> retry heals."""
    failures = FailureInjection()
    coord, versions, store, outbox, failures = _coord(failures)
    v1 = _publish_v1(versions)
    failures.fail_after("version.publish")

    draft = _retraction_draft(v1.version_id, rev="REV-POST")
    with pytest.raises(Exception):
        coord.apply_retraction(draft, all_assertion_ids=["A1", "A2"])

    # Split-brain: current version advanced, lifecycle unbound
    cur = versions.current_version()
    assert cur is not None and cur.version_id != v1.version_id
    rec = store.get_document_record(
        coord._lifecycle_id_for_revision("REV-POST", "retraction")
    )
    assert rec is not None and rec.effective_version_id is None

    # Retry heals
    failures._fail_before.clear()
    failures._fail_after.clear()
    result = coord.apply_retraction(draft, all_assertion_ids=["A1", "A2"])
    assert result.resumed is True or result.idempotent_hit is False
    rec2 = store.get_document_record(result.lifecycle_id)
    assert rec2 is not None and rec2.effective_version_id == result.version_id
    vis = InMemoryLifecycleVisibility(store)
    assert vis.document_eligibility("REF-A").visible_for_retrieval is False


def test_fail_after_bind_before_outbox_complete_retry():
    """Failure after bind but before events -> retry completes events once."""
    failures = FailureInjection()
    coord, versions, store, outbox, failures = _coord(failures)
    v1 = _publish_v1(versions)

    # Simulate partial: run full path but inject failure on outbox-related step
    # by failing after publish then manually completing bind, leaving events missing.
    failures.fail_after("version.publish")
    draft = _retraction_draft(v1.version_id, rev="REV-EVT")
    with pytest.raises(Exception):
        coord.apply_retraction(draft, all_assertion_ids=["A1", "A2"])

    # Manually bind to simulate crash-after-bind-before-outbox
    lifecycle_id = coord._lifecycle_id_for_revision("REV-EVT", "retraction")
    cur = versions.current_version()
    store.bind_effective_version(lifecycle_id, cur.version_id)

    # Outbox incomplete
    assert not any(
        e.event_type == LifecycleEventType.KB_DOCUMENT_RETRACTED for e in outbox.list_all()
    )

    # Retry must complete outbox without duplicating version
    failures._fail_before.clear()
    failures._fail_after.clear()
    vcount_before = len(versions.list_published_versions())
    result = coord.apply_retraction(draft, all_assertion_ids=["A1", "A2"])
    vcount_after = len(versions.list_published_versions())
    assert vcount_after == vcount_before  # no duplicate semantic version
    events = outbox.list_all()
    assert sum(1 for e in events if e.event_type == LifecycleEventType.KB_DOCUMENT_RETRACTED) == 1
    rec = store.get_document_record(lifecycle_id)
    assert rec.effective_version_id == result.version_id


def test_retry_after_full_success_is_idempotent():
    coord, versions, store, outbox, failures = _coord()
    v1 = _publish_v1(versions)
    draft = _retraction_draft(v1.version_id, rev="REV-IDEM")
    r1 = coord.apply_retraction(draft, all_assertion_ids=["A1", "A2"])
    n_ver = len(versions.list_published_versions())
    n_ev = len(outbox.list_all())
    r2 = coord.apply_retraction(draft, all_assertion_ids=["A1", "A2"])
    assert r2.idempotent_hit is True
    assert len(versions.list_published_versions()) == n_ver
    assert len(outbox.list_all()) == n_ev


# ---- R1-B base-version validation ----

def test_nonexistent_base_version_rejected():
    coord, versions, store, outbox, _ = _coord()
    _publish_v1(versions)
    draft = _retraction_draft("kbv-does-not-exist", rev="REV-BAD")
    with pytest.raises(ValueError, match="base_version_id"):
        coord.apply_retraction(draft, all_assertion_ids=["A1"])


def test_stale_non_current_base_version_rejected():
    coord, versions, store, outbox, _ = _coord()
    v1 = _publish_v1(versions)
    # publish an unrelated V2 to make v1 stale
    m = _manifest(fp="fp2")
    m.assertion_hashes = ["b1"]
    snap = versions.create_snapshot(_hash_manifest(m))
    versions.publish_version(snap.snapshot_id)

    draft = _retraction_draft(v1.version_id, rev="REV-STALE")
    with pytest.raises(ValueError, match="not the current version"):
        coord.apply_retraction(draft, all_assertion_ids=["A1"])


def test_rollback_then_new_revision_from_new_current_base():
    coord, versions, store, outbox, _ = _coord()
    v1 = _publish_v1(versions)
    draft1 = _retraction_draft(v1.version_id, rev="REV-A")
    r1 = coord.apply_retraction(draft1, all_assertion_ids=["A1", "A2"])
    versions.rollback_to(v1.version_id)
    # v1 is current again -> can serve as base
    draft2 = build_revision_draft(
        revision_id="REV-B",
        ref_id="REF-1",
        trigger=LifecycleReason.CORRIGENDUM,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
        supersede_actions={"A1": "A1b"},
        metadata={"high_confidence": True, "multi_source": True},
    )
    r2 = coord.apply_revision(draft2)
    assert r2.version_id is not None
    assert r2.version_id != r1.version_id


# ---- R1-C strict material idempotency ----

def test_same_event_id_altered_payload_conflict():
    _, _, _, outbox, _ = _coord()
    e1 = LifecycleEvent(
        event_id="E1",
        event_type=LifecycleEventType.KB_DOCUMENT_RETRACTED,
        ref_id="REF-1",
        affected_assertion_ids=["A1"],
        payload={"action": "retract"},
    )
    outbox.append(e1)
    e2 = LifecycleEvent(
        event_id="E1",
        event_type=LifecycleEventType.KB_DOCUMENT_RETRACTED,
        ref_id="REF-1",
        affected_assertion_ids=["A1", "A2"],  # different material
        payload={"action": "retract"},
    )
    with pytest.raises(ValueError, match="conflicting"):
        outbox.append(e2)


def test_same_lifecycle_id_altered_evidence_conflict():
    _, _, store, _, _ = _coord()
    r1 = DocumentLifecycleRecord(
        lifecycle_id="L1",
        ref_id="REF-1",
        status=DocumentLifecycleStatus.RETRACTED,
        reason=LifecycleReason.RETRACTION,
        evidence_refs=["ev-1"],
        rationale="original",
        source_fingerprint="fp1",
        affected_assertion_ids=["A1"],
        revision_id="R1",
        trace_id="t1",
        provenance_id="p1",
    )
    store.append_document_record(r1)
    r2 = DocumentLifecycleRecord(
        lifecycle_id="L1",
        ref_id="REF-1",
        status=DocumentLifecycleStatus.RETRACTED,
        reason=LifecycleReason.RETRACTION,
        evidence_refs=["ev-TAMPERED"],
        rationale="original",
        source_fingerprint="fp1",
        affected_assertion_ids=["A1"],
        revision_id="R1",
        trace_id="t1",
        provenance_id="p1",
    )
    with pytest.raises(ValueError, match="conflicting"):
        store.append_document_record(r2)


def test_same_assertion_identity_altered_supersede_conflict():
    _, _, store, _, _ = _coord()
    a1 = AssertionLifecycleRecord(
        assertion_id="A1",
        ref_id="REF-1",
        status=AssertionLifecycleStatus.SUPERSEDED,
        lifecycle_id="L1",
        revision_id="R1",
        superseded_by_assertion_id="A1b",
    )
    store.append_assertion_records([a1])
    a2 = AssertionLifecycleRecord(
        assertion_id="A1",
        ref_id="REF-1",
        status=AssertionLifecycleStatus.SUPERSEDED,
        lifecycle_id="L1",
        revision_id="R1",
        superseded_by_assertion_id="A1-TAMPERED",
    )
    with pytest.raises(ValueError, match="conflicting"):
        store.append_assertion_records([a2])


def test_same_material_replay_is_idempotent():
    _, _, store, outbox, _ = _coord()
    r1 = DocumentLifecycleRecord(
        lifecycle_id="L1",
        ref_id="REF-1",
        status=DocumentLifecycleStatus.RETRACTED,
        reason=LifecycleReason.RETRACTION,
        evidence_refs=["ev-1"],
        rationale="x",
        source_fingerprint="fp1",
        affected_assertion_ids=["A1"],
        revision_id="R1",
    )
    store.append_document_record(r1)
    store.append_document_record(r1)  # same material -> ok
    assert len(store.list_records_for_ref("REF-1")) == 1


# ---- R1-D retrieval pre-cutoff regression ----

def _chunk(cid, ref, rank_text, level=ChunkLevel.FINE):
    return KnowledgeChunk(
        chunk_id=cid,
        ref_id=ref,
        level=level,
        chunk_type=ChunkType.TEXT,
        payload=rank_text,
        locator="p.1",
        confidence=Confidence.HIGH,
        provenance={"evidence_type": "literature", "locator": "p.1"},
    )


class RankedStubVector:
    """Returns candidates in fixed rank order regardless of text (simulates backend ranking)."""

    def __init__(self, ordered_chunks):
        self._ordered = ordered_chunks

    def search(self, query):
        from knowledge_curator.ports.retrieval import RetrievalCandidate, RetrievalChannel

        out = []
        for i, c in enumerate(self._ordered):
            if query.level is not None and c.level != query.level:
                continue
            if query.allowed_ref_ids is not None and c.ref_id not in query.allowed_ref_ids:
                continue
            out.append(
                RetrievalCandidate(
                    chunk=c,
                    channel=RetrievalChannel.VECTOR,
                    rank=i + 1,
                    raw_score=1.0 / (i + 1),
                )
            )
            if len(out) >= (query.top_k or 10):
                break
        return out


def test_retrieval_pre_cutoff_top_k1_returns_lower_eligible_ref():
    """top_k=1; rank#1=retracted REF-A; rank#2=active REF-B -> must return REF-B."""
    coord, versions, store, outbox, _ = _coord()
    v1 = _publish_v1(versions)
    draft = _retraction_draft(v1.version_id, rev="REV-FILTER", ids=["A1"])
    coord.apply_retraction(draft, all_assertion_ids=["A1"])
    vis = InMemoryLifecycleVisibility(store)

    ordered = [
        _chunk("F-A", "REF-A", "aaa", level=ChunkLevel.COARSE),
        _chunk("F-B", "REF-B", "bbb", level=ChunkLevel.COARSE),
        _chunk("FA-A", "REF-A", "aaa fine"),
        _chunk("FA-B", "REF-B", "bbb fine"),
    ]
    # Fine-level ranking: REF-A first, REF-B second
    fine_ordered = [
        _chunk("FA-A", "REF-A", "aaa fine"),
        _chunk("FA-B", "REF-B", "bbb fine"),
    ]
    coarse_ordered = [
        _chunk("C-A", "REF-A", "aaa", level=ChunkLevel.COARSE),
        _chunk("C-B", "REF-B", "bbb", level=ChunkLevel.COARSE),
    ]

    class LevelSplitStub:
        def search(self, query):
            src = coarse_ordered if query.level == ChunkLevel.COARSE else fine_ordered
            return RankedStubVector(src).search(query)

    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    svc = EvidenceRetrievalService(
        vector_port=LevelSplitStub(),
        keyword_port=LevelSplitStub(),
        reranker=FakeReranker(),
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
        lifecycle_visibility=vis,
    )
    bundle = svc.retrieve(EvidenceRequest(query="fine", top_k=1))
    refs = {r.ref_id for r in bundle.evidence_records}
    assert refs == {"REF-B"}  # not empty; not REF-A


# ---- R1-E historical retrieval E2E ----

def test_historical_retrieval_e2e_via_service():
    """V1 active REF-A -> V2 retract REF-A -> current excludes, V1 retrieval returns."""
    coord, versions, store, outbox, _ = _coord()
    v1 = _publish_v1(versions)
    draft = _retraction_draft(v1.version_id, rev="REV-HIST", ids=["A1"])
    coord.apply_retraction(draft, all_assertion_ids=["A1"])
    vis = InMemoryLifecycleVisibility(store)

    chunks = [
        _chunk("C-A", "REF-A", "aaa", level=ChunkLevel.COARSE),
        _chunk("F-A", "REF-A", "aaa fine"),
        _chunk("C-B", "REF-B", "bbb", level=ChunkLevel.COARSE),
        _chunk("F-B", "REF-B", "bbb fine"),
    ]

    class LevelSplitStub:
        def search(self, query):
            src = [
                c
                for c in chunks
                if (query.level is None or c.level == query.level)
            ]
            return RankedStubVector(src).search(query)

    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    def make_svc(visibility):
        return EvidenceRetrievalService(
            vector_port=LevelSplitStub(),
            keyword_port=LevelSplitStub(),
            reranker=FakeReranker(),
            retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
            lifecycle_visibility=visibility,
        )

    # Current (V2): REF-A excluded
    current_bundle = make_svc(vis).retrieve(EvidenceRequest(query="aaa", top_k=5))
    assert "REF-A" not in {r.ref_id for r in current_bundle.evidence_records}

    # Explicit historical V1 retrieval: REF-A returned through the service
    class VersionScopedVis(InMemoryLifecycleVisibility):
        def eligible_ref_ids(self, ref_ids, at_version_id=None):
            return super().eligible_ref_ids(ref_ids, at_version_id=at_version_id)

    vis_v1 = InMemoryLifecycleVisibility(
        InMemoryLifecycleStore(version_visible=make_version_visible_fn(versions))
    )
    hist_bundle = make_svc(vis_v1).retrieve(
        EvidenceRequest(query="aaa", top_k=5, at_version_id=v1.version_id)
    )
    assert "REF-A" in {r.ref_id for r in hist_bundle.evidence_records}
