"""Phase 5.0-R2 tests: progressive filter, same-history E2E, assertion lifecycle."""

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
from knowledge_curator.schemas.lifecycle import LifecycleReason


def _manifest(ref_id="REF-A", fp="fp1"):
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


def _coord():
    failures = FailureInjection()
    versions = InMemoryVersionStore(failures=failures)
    store = InMemoryLifecycleStore(version_visible=make_version_visible_fn(versions))
    outbox = InMemoryEventOutbox()
    coord = LifecycleRevisionCoordinator(
        lifecycle_store=store, outbox=outbox, version_store=versions
    )
    return coord, versions, store, outbox


def _publish_v1(versions):
    snap = versions.create_snapshot(_hash_manifest(_manifest()))
    return versions.publish_version(snap.snapshot_id)


def _chunk(cid, ref, payload, *, level=ChunkLevel.FINE, assertion_id=None):
    return KnowledgeChunk(
        chunk_id=cid,
        ref_id=ref,
        level=level,
        chunk_type=ChunkType.TEXT,
        payload=payload,
        locator="p.1",
        assertion_id=assertion_id,
        confidence=Confidence.HIGH,
        provenance={"evidence_type": "literature", "locator": "p.1"},
    )


class OrderedStub:
    """Returns candidates in fixed rank order, honouring top_k as a cap."""

    def __init__(self, ordered):
        self._ordered = ordered
        self.calls = []

    def search(self, query):
        from knowledge_curator.ports.retrieval import RetrievalCandidate, RetrievalChannel

        self.calls.append(query.top_k)
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


class CappedStub(OrderedStub):
    """Backend that never returns more than `cap` candidates regardless of top_k."""

    def __init__(self, ordered, cap):
        super().__init__(ordered)
        self.cap = cap

    def search(self, query):
        from knowledge_curator.ports.retrieval import RetrievalCandidate, RetrievalChannel

        self.calls.append(query.top_k)
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
            if len(out) >= min(query.top_k or 10, self.cap):
                break
        return out


class LevelSplitStub:
    def __init__(self, coarse, fine):
        self._coarse = coarse
        self._fine = fine

    def search(self, query):
        src = self._coarse if query.level == ChunkLevel.COARSE else self._fine
        return src.search(query)


def _retraction(base_id, ref="REF-A", rev="REV-R2", ids=None):
    return build_revision_draft(
        revision_id=rev,
        ref_id=ref,
        trigger=LifecycleReason.RETRACTION,
        base_version_id=base_id,
        affected_assertion_ids=list(ids or ["A1", "A2"]),
        verified_external_trigger=True,
        rationale="retraction notice",
    )


# ---- R2-A progressive filtering ----

def test_deep_rank_eligible_recovery_after_55_ineligible():
    """top_k=1; 55 ineligible then rank #56 eligible -> returns #56."""
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    coord.apply_retraction(_retraction(v1.version_id, ref="REF-BAD", ids=["X1"]), all_assertion_ids=["X1"])
    vis = InMemoryLifecycleVisibility(store)

    ordered = []
    for i in range(55):
        ordered.append(_chunk(f"BAD-{i}", "REF-BAD", f"bad {i}"))
    ordered.append(_chunk("GOOD-56", "REF-GOOD", "good 56"))
    for i in range(57, 60):
        ordered.append(_chunk(f"GOOD-{i}", "REF-GOOD", f"good {i}"))

    stub = OrderedStub(ordered)
    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    svc = EvidenceRetrievalService(
        vector_port=stub,
        keyword_port=None,
        reranker=None,
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
        lifecycle_visibility=vis,
    )
    bundle = svc.retrieve(EvidenceRequest(query="good", top_k=1))
    ids = [r.chunk_id for r in bundle.evidence_records]
    assert "GOOD-56" in ids
    assert not any(i.startswith("BAD-") for i in ids)


def test_progressive_filter_is_not_fixed_10x():
    """First expansion is 50, then grows — not capped at top_k*10."""
    from knowledge_curator.retrieval.evidence_service import _EligibilityFilteredPort

    class Vis:
        def document_eligibility(self, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = ref_id == "OK"

            return E()

        def assertion_eligibility(self, aid, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = True

            return E()

    ordered = [_chunk(f"C{i}", "OK" if i == 59 else "BAD", "x") for i in range(60)]
    stub = OrderedStub(ordered)
    port = _EligibilityFilteredPort(stub, Vis())
    from knowledge_curator.ports.retrieval import RetrievalQuery

    out = port.search(RetrievalQuery(text="x", top_k=1))
    assert any(c.chunk.chunk_id == "C59" for c in out)
    # Requested depths must have grown beyond 50
    assert max(stub.calls) > 50


def test_backend_exhaustion_terminates_without_infinite_expansion():
    """All candidates ineligible -> wrapper terminates and returns []."""
    from knowledge_curator.retrieval.evidence_service import _EligibilityFilteredPort

    class Vis:
        def document_eligibility(self, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = False

            return E()

        def assertion_eligibility(self, aid, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = False

            return E()

    ordered = [_chunk(f"C{i}", "BAD", "x") for i in range(60)]
    stub = OrderedStub(ordered)
    port = _EligibilityFilteredPort(stub, Vis())
    from knowledge_curator.ports.retrieval import RetrievalQuery

    out = port.search(RetrievalQuery(text="x", top_k=1))
    assert out == []
    # Must terminate (bounded calls), not expand forever
    assert len(stub.calls) <= 12


def test_capped_backend_repeating_candidates_terminates():
    """Backend that caps output and repeats identities -> no infinite loop."""
    from knowledge_curator.retrieval.evidence_service import _EligibilityFilteredPort

    class Vis:
        def document_eligibility(self, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = False

            return E()

        def assertion_eligibility(self, aid, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = False

            return E()

    ordered = [_chunk(f"C{i}", "BAD", "x") for i in range(60)]
    stub = CappedStub(ordered, cap=30)
    port = _EligibilityFilteredPort(stub, Vis())
    from knowledge_curator.ports.retrieval import RetrievalQuery

    out = port.search(RetrievalQuery(text="x", top_k=1))
    assert out == []
    assert len(stub.calls) <= 12


# ---- R2-B same-history historical retrieval ----

def test_same_history_historical_retrieval_e2e():
    """ONE store with V2 retraction: current excludes REF-A, V1 view returns it."""
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    coord.apply_retraction(_retraction(v1.version_id, rev="REV-HIST"), all_assertion_ids=["A1", "A2"])
    vis = InMemoryLifecycleVisibility(store)  # SAME store

    # Store still has the retraction record
    recs = store.list_records_for_ref("REF-A")
    assert any(r.status.value == "retracted" for r in recs)

    chunks = [
        _chunk("C-A", "REF-A", "aaa", level=ChunkLevel.COARSE),
        _chunk("F-A", "REF-A", "aaa fine"),
        _chunk("C-B", "REF-B", "bbb", level=ChunkLevel.COARSE),
        _chunk("F-B", "REF-B", "bbb fine"),
    ]

    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    svc = EvidenceRetrievalService(
        vector_port=LevelSplitStub(OrderedStub([c for c in chunks if c.level == ChunkLevel.COARSE]),
                                   OrderedStub([c for c in chunks if c.level == ChunkLevel.FINE])),
        keyword_port=None,
        reranker=None,
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
        lifecycle_visibility=vis,
    )

    # Current: REF-A absent
    current = svc.retrieve(EvidenceRequest(query="aaa", top_k=5))
    assert "REF-A" not in {r.ref_id for r in current.evidence_records}

    # Historical V1 on the SAME service/visibility/store: REF-A present
    hist = svc.retrieve(EvidenceRequest(query="aaa", top_k=5, at_version_id=v1.version_id))
    assert "REF-A" in {r.ref_id for r in hist.evidence_records}

    # Retraction record still present
    recs2 = store.list_records_for_ref("REF-A")
    assert any(r.status.value == "retracted" for r in recs2)


# ---- R2-C assertion-level filtering + corrigendum ----

def test_corrigendum_current_and_historical_retrieval():
    """A1 superseded, A2 active: current excludes F1, V1 returns F1, coarse stays."""
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    draft = build_revision_draft(
        revision_id="REV-CORR",
        ref_id="REF-A",
        trigger=LifecycleReason.CORRIGENDUM,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
        supersede_actions={"A1": "A1b"},
        metadata={"high_confidence": True, "multi_source": True},
    )
    coord.apply_revision(draft)
    vis = InMemoryLifecycleVisibility(store)

    coarse = [_chunk("C-A", "REF-A", "doc summary", level=ChunkLevel.COARSE)]
    fine = [
        _chunk("F1", "REF-A", "assertion A1 text", assertion_id="A1"),
        _chunk("F2", "REF-A", "assertion A2 text", assertion_id="A2"),
    ]

    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    svc = EvidenceRetrievalService(
        vector_port=LevelSplitStub(OrderedStub(coarse), OrderedStub(fine)),
        keyword_port=None,
        reranker=None,
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
        lifecycle_visibility=vis,
    )

    # Current: F1/A1 excluded, F2/A2 present
    cur = svc.retrieve(EvidenceRequest(query="assertion", top_k=5))
    ids = {r.chunk_id for r in cur.evidence_records}
    assert "F1" not in ids
    assert "F2" in ids
    # Document still active -> coarse summary chunk remains eligible
    # (coarse stage is used for filtering; eligibility check via visibility).
    assert vis.document_eligibility("REF-A").visible_for_retrieval is True
    assert vis.assertion_eligibility("A2", "REF-A").visible_for_retrieval is True

    # Historical V1: F1/A1 can return again
    hist = svc.retrieve(EvidenceRequest(query="assertion", top_k=5, at_version_id=v1.version_id))
    hids = {r.chunk_id for r in hist.evidence_records}
    assert "F1" in hids

    # Training eligibility
    assert vis.assertion_eligibility("A1", "REF-A").eligible_for_training is False
    assert vis.assertion_eligibility("A2", "REF-A").eligible_for_training is True
    assert vis.assertion_eligibility("A1", "REF-A", at_version_id=v1.version_id).eligible_for_training is True


def test_assertion_filter_ignores_chunk_id_conventions():
    """Must use chunk.assertion_id only; chunk_id text is not parsed."""
    from knowledge_curator.retrieval.evidence_service import _EligibilityFilteredPort

    calls = []

    class Vis:
        def document_eligibility(self, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = True

            return E()

        def assertion_eligibility(self, aid, ref_id, at_version_id=None):
            calls.append(aid)

            class E:
                visible_for_retrieval = aid != "A1"

            return E()

    # chunk_id looks like an assertion but assertion_id is None -> no assertion check
    c1 = _chunk("A1", "REF-A", "x", assertion_id=None)
    c2 = _chunk("whatever", "REF-A", "x", assertion_id="A1")
    stub = OrderedStub([c1, c2])
    port = _EligibilityFilteredPort(stub, Vis())
    from knowledge_curator.ports.retrieval import RetrievalQuery

    out = port.search(RetrievalQuery(text="x", top_k=5))
    ids = {c.chunk.chunk_id for c in out}
    assert "A1" in ids  # no assertion_id -> document eligibility only
    assert "whatever" not in ids  # assertion_id=A1 superseded
    assert "A1" in calls
