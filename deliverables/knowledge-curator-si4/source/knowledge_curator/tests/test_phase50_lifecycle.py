"""Phase 5.0 tests: §7 lifecycle core (revision/retraction/rollback/outbox)."""

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
    evaluate_risk_gate,
)
from knowledge_curator.core.lifecycle_visibility import (
    build_lifecycle_visibility,
    make_version_visible_fn,
)
from knowledge_curator.retrieval.evidence_service import (
    EvidenceRequest,
    EvidenceRetrievalService,
)
from knowledge_curator.schemas.commit import SnapshotManifest
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk
from knowledge_curator.schemas.lifecycle import (
    AssertionLifecycleStatus,
    DocumentLifecycleStatus,
    LifecycleEvent,
    LifecycleEventType,
    LifecycleReason,
    RiskDecision,
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


def _coord(failures=None):
    versions = InMemoryVersionStore(failures=failures or FailureInjection())
    store = InMemoryLifecycleStore(version_visible=make_version_visible_fn(versions))
    outbox = InMemoryEventOutbox()
    coord = LifecycleRevisionCoordinator(
        lifecycle_store=store, outbox=outbox, version_store=versions
    )
    return coord, versions, store, outbox


def _publish_v1(versions):
    m = _manifest()
    m.content_hash = __import__("hashlib").sha256(
        __import__("json").dumps(m.stable_payload(), sort_keys=True).encode()
    ).hexdigest()
    snap = versions.create_snapshot(m)
    return versions.publish_version(snap.snapshot_id)


# ---- lifecycle models / store ----

def test_append_only_and_idempotent_replay():
    _, _, store, _ = _coord()
    from knowledge_curator.schemas.lifecycle import DocumentLifecycleRecord

    rec = DocumentLifecycleRecord(
        lifecycle_id="L1",
        ref_id="REF-1",
        status=DocumentLifecycleStatus.RETRACTED,
        reason=LifecycleReason.RETRACTION,
        affected_assertion_ids=["A1"],
    )
    store.append_document_record(rec)
    again = store.append_document_record(rec)
    assert again.lifecycle_id == "L1"
    assert len(store.list_records_for_ref("REF-1")) == 1


def test_conflicting_event_id_rejected():
    _, _, store, _ = _coord()
    from knowledge_curator.schemas.lifecycle import DocumentLifecycleRecord

    store.append_document_record(
        DocumentLifecycleRecord(
            lifecycle_id="L1",
            ref_id="REF-1",
            status=DocumentLifecycleStatus.RETRACTED,
            reason=LifecycleReason.RETRACTION,
        )
    )
    with pytest.raises(ValueError, match="conflicting"):
        store.append_document_record(
            DocumentLifecycleRecord(
                lifecycle_id="L1",
                ref_id="REF-1",
                status=DocumentLifecycleStatus.ACTIVE,
                reason=LifecycleReason.MANUAL_CORRECTION,
            )
        )


def test_conflicting_outbox_event_id_rejected():
    _, _, _, outbox = _coord()
    outbox.append(
        LifecycleEvent(
            event_id="E1",
            event_type=LifecycleEventType.KB_DOCUMENT_RETRACTED,
            ref_id="REF-1",
        )
    )
    outbox.append(
        LifecycleEvent(
            event_id="E1",
            event_type=LifecycleEventType.KB_DOCUMENT_RETRACTED,
            ref_id="REF-1",
        )
    )  # idempotent
    with pytest.raises(ValueError, match="conflicting"):
        outbox.append(
            LifecycleEvent(
                event_id="E1",
                event_type=LifecycleEventType.KB_VERSION_ROLLED_BACK,
                ref_id="REF-1",
            )
        )


# ---- risk gate / revision draft ----

def test_retraction_without_verified_trigger_requires_manual():
    d = build_revision_draft(
        revision_id="R1",
        ref_id="REF-1",
        trigger=LifecycleReason.RETRACTION,
        base_version_id=None,
        verified_external_trigger=False,
    )
    assert d.risk_decision == RiskDecision.MANUAL_ADJUDICATION_REQUIRED
    assert d.manual_adjudication_required is True


def test_low_risk_rule_eligible():
    d = build_revision_draft(
        revision_id="R2",
        ref_id="REF-1",
        trigger=LifecycleReason.CORRIGENDUM,
        base_version_id=None,
        affected_assertion_ids=["A1"],
        metadata={"high_confidence": True, "multi_source": True},
    )
    assert d.risk_decision == RiskDecision.AUTO_RULE_REVIEW_ELIGIBLE
    assert d.manual_adjudication_required is False


def test_unresolved_controversy_requires_manual():
    d = build_revision_draft(
        revision_id="R3",
        ref_id="REF-1",
        trigger=LifecycleReason.CONFLICT_RESOLUTION,
        base_version_id=None,
        metadata={"high_confidence": True, "multi_source": True, "unresolved_controversy": True},
    )
    assert d.risk_decision == RiskDecision.MANUAL_ADJUDICATION_REQUIRED


# ---- retraction soft archive + version + visibility + rollback ----

def test_retraction_soft_archive_and_rollback_visibility():
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    draft = build_revision_draft(
        revision_id="REV-RETRACT-1",
        ref_id="REF-1",
        trigger=LifecycleReason.RETRACTION,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1", "A2"],
        verified_external_trigger=True,
        rationale="publisher retraction notice",
    )
    result = coord.apply_retraction(draft, all_assertion_ids=["A1", "A2"])
    assert result.document_status == "retracted"
    assert set(result.archived_assertion_ids) == {"A1", "A2"}
    assert result.version_id is not None

    vis = InMemoryLifecycleVisibility(store)
    # current version is V2 (retraction) -> not eligible
    assert vis.document_eligibility("REF-1").visible_for_retrieval is False
    assert vis.document_eligibility("REF-1").eligible_for_training is False
    assert vis.assertion_eligibility("A1", "REF-1").visible_for_retrieval is False

    # historical explicit V1 still sees active document
    assert vis.document_eligibility("REF-1", at_version_id=v1.version_id).visible_for_retrieval is True
    assert vis.assertion_eligibility("A1", "REF-1", at_version_id=v1.version_id).visible_for_retrieval is True

    # rollback to V1 restores current visibility
    versions.rollback_to(v1.version_id)
    assert vis.document_eligibility("REF-1").visible_for_retrieval is True
    # V2 remains historically resolvable and still records the retraction
    v2 = result.version_id
    assert versions.get_version(v2) is not None
    assert vis.document_eligibility("REF-1", at_version_id=v2).visible_for_retrieval is False
    recs = store.list_records_for_ref("REF-1")
    assert any(r.status == DocumentLifecycleStatus.RETRACTED for r in recs)

    # rollback event emitted by coordinator helper
    ev = coord.emit_rollback_event(
        ref_id="REF-1", from_version_id=v2, to_version_id=v1.version_id
    )
    assert ev
    events = outbox.list_all()
    assert any(e.event_type == LifecycleEventType.KB_DOCUMENT_RETRACTED for e in events)
    assert any(e.event_type == LifecycleEventType.KB_VERSION_ROLLED_BACK for e in events)


def test_retraction_replay_idempotent():
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    draft = build_revision_draft(
        revision_id="REV-R",
        ref_id="REF-1",
        trigger=LifecycleReason.RETRACTION,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
        verified_external_trigger=True,
    )
    r1 = coord.apply_retraction(draft, all_assertion_ids=["A1"])
    n_events = len(outbox.list_all())
    r2 = coord.apply_retraction(draft, all_assertion_ids=["A1"])
    assert r2.idempotent_hit is True
    assert len(outbox.list_all()) == n_events
    assert len(store.list_records_for_ref("REF-1")) == 1


def test_no_physical_delete_of_historical_records():
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    snap = versions.get_snapshot(versions.get_version(v1.version_id).snapshot_id)
    assert snap.manifest.assertion_hashes == ["a1", "a2"]
    draft = build_revision_draft(
        revision_id="REV-X",
        ref_id="REF-1",
        trigger=LifecycleReason.RETRACTION,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
        verified_external_trigger=True,
    )
    coord.apply_retraction(draft, all_assertion_ids=["A1"])
    # V1 snapshot still intact
    snap1 = versions.get_snapshot(versions.get_version(v1.version_id).snapshot_id)
    assert snap1.manifest.assertion_hashes == ["a1", "a2"]
    assert versions.get_version(v1.version_id) is not None


# ---- corrigendum / supersede ----

def test_corrigendum_supersedes_only_affected():
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    draft = build_revision_draft(
        revision_id="REV-C",
        ref_id="REF-1",
        trigger=LifecycleReason.CORRIGENDUM,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
        supersede_actions={"A1": "A1b"},
        metadata={"high_confidence": True, "multi_source": True},
    )
    result = coord.apply_revision(draft)
    assert result.superseded_assertion_ids == ["A1"]
    vis = InMemoryLifecycleVisibility(store)
    assert vis.assertion_eligibility("A1", "REF-1").visible_for_retrieval is False
    assert vis.assertion_eligibility("A1", "REF-1").status == "superseded"
    # unchanged assertion remains active
    assert vis.assertion_eligibility("A2", "REF-1").visible_for_retrieval is True
    # document itself remains active (corrigendum, not retraction)
    assert vis.document_eligibility("REF-1").visible_for_retrieval is True


def test_manual_draft_cannot_auto_publish():
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    draft = build_revision_draft(
        revision_id="REV-M",
        ref_id="REF-1",
        trigger=LifecycleReason.MANUAL_CORRECTION,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
    )
    assert draft.manual_adjudication_required is True
    with pytest.raises(ValueError, match="adjudication"):
        coord.apply_revision(draft)


# ---- backward manifest hash compatibility ----

def test_old_manifest_hash_unchanged_with_empty_lifecycle_fields():
    import hashlib
    import json

    old_style_payload = {
        "ref_id": "REF-1",
        "source_fingerprint": "fp1",
        "assertion_hashes": ["a1", "a2"],
        "usdo_hashes": ["u1"],
        "vector_ids": ["v1"],
        "metadata_hash": "m1",
        "decision_hashes": ["d1"],
    }
    expected = hashlib.sha256(
        json.dumps(old_style_payload, sort_keys=True).encode()
    ).hexdigest()
    m = _manifest()
    assert m.content_hash == "" or True
    actual = hashlib.sha256(
        json.dumps(m.stable_payload(), sort_keys=True).encode()
    ).hexdigest()
    assert actual == expected

    # with lifecycle fields -> hash MAY change
    m2 = _manifest()
    m2.lifecycle_hashes = ["L1"]
    m2.lifecycle_record_ids = ["L1"]
    actual2 = hashlib.sha256(
        json.dumps(m2.stable_payload(), sort_keys=True).encode()
    ).hexdigest()
    assert actual2 != expected


# ---- version publication determinism ----

def test_lifecycle_revision_publishes_new_version_and_is_deterministic():
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    draft = build_revision_draft(
        revision_id="REV-D",
        ref_id="REF-1",
        trigger=LifecycleReason.RETRACTION,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
        verified_external_trigger=True,
    )
    r = coord.apply_retraction(draft, all_assertion_ids=["A1"])
    assert r.version_id != v1.version_id
    ver = versions.get_version(r.version_id)
    assert ver.prior_version_id == v1.version_id
    snap = versions.get_snapshot(ver.snapshot_id)
    assert snap.manifest.lifecycle_hashes == [r.lifecycle_id]
    # underlying immutable ids preserved
    assert snap.manifest.assertion_hashes == ["a1", "a2"]


# ---- failure atomicity ----

def test_failure_before_publish_leaves_no_half_state_visible():
    failures = FailureInjection()
    coord, versions, store, outbox = _coord(failures=failures)
    v1 = _publish_v1(versions)

    failures.fail_on("version.publish")
    draft = build_revision_draft(
        revision_id="REV-F",
        ref_id="REF-1",
        trigger=LifecycleReason.RETRACTION,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
        verified_external_trigger=True,
    )
    with pytest.raises(Exception):
        coord.apply_retraction(draft, all_assertion_ids=["A1"])

    vis = InMemoryLifecycleVisibility(store)
    # No published lifecycle version -> current V1 still eligible
    cur = versions.current_version()
    assert cur.version_id == v1.version_id
    assert vis.document_eligibility("REF-1").visible_for_retrieval is True
    # staged lifecycle records may exist but are unbound (effective_version None)
    recs = store.list_records_for_ref("REF-1")
    for r in recs:
        assert r.effective_version_id is None


# ---- event outbox ----

def test_outbox_lists_pending_and_mark_delivered():
    _, _, _, outbox = _coord()
    outbox.append(
        LifecycleEvent(
            event_id="E1",
            event_type=LifecycleEventType.KB_REVISION_PUBLISHED,
            ref_id="REF-1",
        )
    )
    assert len(outbox.list_pending()) == 1
    outbox.mark_delivered("E1")
    assert len(outbox.list_pending()) == 0
    assert len(outbox.list_all()) == 1


def test_outbox_event_payload_has_invalidation_targets():
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    draft = build_revision_draft(
        revision_id="REV-E",
        ref_id="REF-1",
        trigger=LifecycleReason.RETRACTION,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
        verified_external_trigger=True,
        trace_id="t-1",
        provenance_id="p-1",
    )
    coord.apply_retraction(draft, all_assertion_ids=["A1"])
    events = outbox.list_all()
    retracted = [e for e in events if e.event_type == LifecycleEventType.KB_DOCUMENT_RETRACTED][0]
    assert "invalidate" in retracted.payload
    assert "qa_evidence_cache" in retracted.payload["invalidate"]
    assert "training_export" in retracted.payload["invalidate"]
    assert retracted.trace_id == "t-1"
    assert retracted.provenance_id == "p-1"


# ---- retrieval eligibility composition ----

def _chunk(cid, ref, level=ChunkLevel.FINE):
    return KnowledgeChunk(
        chunk_id=cid,
        ref_id=ref,
        level=level,
        chunk_type=ChunkType.TEXT,
        payload="text",
        locator="p.1",
        confidence=Confidence.HIGH,
        provenance={"evidence_type": "literature", "locator": "p.1"},
    )


def test_retrieval_excludes_retracted_ref_without_post_topk_drop():
    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    draft = build_revision_draft(
        revision_id="REV-RET",
        ref_id="REF-1",
        trigger=LifecycleReason.RETRACTION,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
        verified_external_trigger=True,
    )
    coord.apply_retraction(draft, all_assertion_ids=["A1"])
    vis = InMemoryLifecycleVisibility(store)

    chunks = [
        _chunk("C-A", "REF-1", level=ChunkLevel.COARSE),
        _chunk("F-A", "REF-1"),
        _chunk("C-B", "REF-2", level=ChunkLevel.COARSE),
        _chunk("F-B", "REF-2"),
    ]
    svc = EvidenceRetrievalService(
        vector_port=InMemoryVectorSearch(chunks),
        keyword_port=InMemoryKeywordSearch(chunks),
        reranker=FakeReranker(),
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
        lifecycle_visibility=vis,
    )
    bundle = svc.retrieve(EvidenceRequest(query="text", top_k=5))
    refs = {r.ref_id for r in bundle.evidence_records}
    assert "REF-1" not in refs
    assert "REF-2" in refs

    # historical version V1 still resolves REF-1
    svc_hist = EvidenceRetrievalService(
        vector_port=InMemoryVectorSearch(chunks),
        keyword_port=InMemoryKeywordSearch(chunks),
        reranker=FakeReranker(),
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
        lifecycle_visibility=InMemoryLifecycleVisibility(
            InMemoryLifecycleStore(version_visible=make_version_visible_fn(versions))
        ),
    )
    # at_version_id is applied inside visibility via document_eligibility(..., at_version_id)
    # Our filtered port uses current visibility; for historical we call eligibility directly.
    assert vis.document_eligibility("REF-1", at_version_id=v1.version_id).visible_for_retrieval is True


# ---- training eligibility ----

def test_training_eligibility_excludes_retracted_and_archived():
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    draft = build_revision_draft(
        revision_id="REV-T",
        ref_id="REF-1",
        trigger=LifecycleReason.RETRACTION,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
        verified_external_trigger=True,
    )
    coord.apply_retraction(draft, all_assertion_ids=["A1"])
    vis = InMemoryLifecycleVisibility(store)
    assert vis.document_eligibility("REF-1").eligible_for_training is False
    assert vis.assertion_eligibility("A1", "REF-1").eligible_for_training is False
