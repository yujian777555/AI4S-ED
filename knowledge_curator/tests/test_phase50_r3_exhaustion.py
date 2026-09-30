"""Phase 5.0-R3 tests: all-candidate exhaustion, #101 recovery, allowed_ref filtering."""

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
    EligibilitySearchLimitError,
    EvidenceRequest,
    EvidenceRetrievalService,
    _EligibilityFilteredPort,
)
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk
from knowledge_curator.schemas.commit import SnapshotManifest
from knowledge_curator.schemas.lifecycle import LifecycleReason
from knowledge_curator.ports.retrieval import RetrievalQuery


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
    versions = InMemoryVersionStore(failures=FailureInjection())
    store = InMemoryLifecycleStore(version_visible=make_version_visible_fn(versions))
    outbox = InMemoryEventOutbox()
    coord = LifecycleRevisionCoordinator(
        lifecycle_store=store, outbox=outbox, version_store=versions
    )
    return coord, versions, store, outbox


def _publish_v1(versions):
    snap = versions.create_snapshot(_hash_manifest(_manifest()))
    return versions.publish_version(snap.snapshot_id)


def _chunk(cid, ref, payload="x", *, level=ChunkLevel.FINE, assertion_id=None):
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
    """Returns at most `cap` candidates regardless of requested top_k."""

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


class GrowingStub:
    """Backend that always grows the candidate set, never exhausts (for resource guard)."""

    def __init__(self):
        self.calls = []

    def search(self, query):
        from knowledge_curator.ports.retrieval import RetrievalCandidate, RetrievalChannel

        self.calls.append(query.top_k)
        n = query.top_k or 10
        out = []
        for i in range(n):
            c = _chunk(f"GROW-{i}", "BAD", "x")
            out.append(
                RetrievalCandidate(
                    chunk=c, channel=RetrievalChannel.VECTOR, rank=i + 1, raw_score=1.0
                )
            )
        return out


class LevelSplitStub:
    def __init__(self, coarse, fine):
        self._coarse = coarse
        self._fine = fine

    def search(self, query):
        src = self._coarse if query.level == ChunkLevel.COARSE else self._fine
        return src.search(query)


def _make_vis(store):
    return InMemoryLifecycleVisibility(store)


# ---- R3-A all-candidate exhaustion ----

def test_rank_101_eligible_recovery():
    """#1..#100 ineligible, #101 eligible, top_k=1 -> returns #101."""
    class Vis:
        def document_eligibility(self, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = ref_id == "OK"

            return E()

        def assertion_eligibility(self, aid, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = True

            return E()

    ordered = [_chunk(f"BAD-{i}", "BAD", "x") for i in range(100)]
    ordered.append(_chunk("GOOD-101", "OK", "good"))
    for i in range(101, 110):
        ordered.append(_chunk(f"OK-{i}", "OK", "ok"))

    stub = OrderedStub(ordered)
    port = _EligibilityFilteredPort(stub, Vis())
    out = port.search(RetrievalQuery(text="x", top_k=1))
    assert any(getattr(c, "chunk", c).chunk_id == "GOOD-101" for c in out)
    # Must have expanded past 100
    assert max(stub.calls) > 100


def test_exhaustion_tracks_all_candidates_not_eligible():
    """Eligible set stays empty but candidates grow -> must keep expanding."""
    class Vis:
        def document_eligibility(self, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = False

            return E()

        def assertion_eligibility(self, aid, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = False

            return E()

    # 200 all-ineligible candidates; must expand past 50 and 100
    ordered = [_chunk(f"BAD-{i}", "BAD", "x") for i in range(200)]
    stub = OrderedStub(ordered)
    port = _EligibilityFilteredPort(stub, Vis())
    out = port.search(RetrievalQuery(text="x", top_k=1))
    assert out == []
    # Candidates grow 50->100->150... so must have multiple calls
    assert len(stub.calls) >= 2
    assert max(stub.calls) >= 100


def test_capped_backend_repeating_identities_terminates():
    class Vis:
        def document_eligibility(self, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = False

            return E()

        def assertion_eligibility(self, aid, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = False

            return E()

    ordered = [_chunk(f"BAD-{i}", "BAD", "x") for i in range(60)]
    stub = CappedStub(ordered, cap=30)
    port = _EligibilityFilteredPort(stub, Vis())
    out = port.search(RetrievalQuery(text="x", top_k=1))
    assert out == []
    assert len(stub.calls) <= 12  # terminates


def test_resource_guard_fail_closed_not_silent():
    """If MAX_STEPS hit while candidates still growing -> raise, not silent return."""
    class Vis:
        def document_eligibility(self, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = False

            return E()

        def assertion_eligibility(self, aid, ref_id, at_version_id=None):
            class E:
                visible_for_retrieval = False

            return E()

    stub = GrowingStub()
    port = _EligibilityFilteredPort(stub, Vis())
    with pytest.raises(EligibilitySearchLimitError, match="limit reached"):
        port.search(RetrievalQuery(text="x", top_k=1))


# ---- R3-B allowed_ref assertion filtering ----

def test_allowed_ref_assertion_supersede_filtering():
    """allowed_ref_ids=[REF-A]; A1 superseded, A2 active -> returns A2, not A1."""
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
    vis = _make_vis(store)

    coarse = [_chunk("C-A", "REF-A", "doc", level=ChunkLevel.COARSE)]
    fine = [
        _chunk("F1", "REF-A", "A1 text", assertion_id="A1"),
        _chunk("F2", "REF-A", "A2 text", assertion_id="A2"),
    ]

    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    svc = EvidenceRetrievalService(
        vector_port=LevelSplitStub(OrderedStub(coarse), OrderedStub(fine)),
        keyword_port=None,
        reranker=None,
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
        lifecycle_visibility=vis,
    )
    cur = svc.retrieve(
        EvidenceRequest(query="text", top_k=1, allowed_ref_ids=["REF-A"])
    )
    ids = {r.chunk_id for r in cur.evidence_records}
    assert "F2" in ids
    assert "F1" not in ids


def test_historical_allowed_ref_retrieval_returns_superseded():
    """Same request at V1 may return A1 again."""
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    draft = build_revision_draft(
        revision_id="REV-CORR2",
        ref_id="REF-A",
        trigger=LifecycleReason.CORRIGENDUM,
        base_version_id=v1.version_id,
        affected_assertion_ids=["A1"],
        supersede_actions={"A1": "A1b"},
        metadata={"high_confidence": True, "multi_source": True},
    )
    coord.apply_revision(draft)
    vis = _make_vis(store)

    coarse = [_chunk("C-A", "REF-A", "doc", level=ChunkLevel.COARSE)]
    fine = [
        _chunk("F1", "REF-A", "A1 text", assertion_id="A1"),
        _chunk("F2", "REF-A", "A2 text", assertion_id="A2"),
    ]

    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    svc = EvidenceRetrievalService(
        vector_port=LevelSplitStub(OrderedStub(coarse), OrderedStub(fine)),
        keyword_port=None,
        reranker=None,
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
        lifecycle_visibility=vis,
    )
    hist = svc.retrieve(
        EvidenceRequest(
            query="text", top_k=2, allowed_ref_ids=["REF-A"], at_version_id=v1.version_id
        )
    )
    ids = {r.chunk_id for r in hist.evidence_records}
    assert "F1" in ids


def test_empty_allowed_ref_after_prefilter_yields_zero_results():
    """allowed_ref=[RETRACTED] -> empty prefilter -> 0 results, no leak."""
    coord, versions, store, outbox = _coord()
    v1 = _publish_v1(versions)
    coord.apply_retraction(
        build_revision_draft(
            revision_id="REV-R",
            ref_id="REF-RETRACTED",
            trigger=LifecycleReason.RETRACTION,
            base_version_id=v1.version_id,
            affected_assertion_ids=["A1"],
            verified_external_trigger=True,
        ),
        all_assertion_ids=["A1"],
    )
    vis = _make_vis(store)

    coarse = [
        _chunk("C-R", "REF-RETRACTED", "bad", level=ChunkLevel.COARSE),
        _chunk("C-G", "REF-GOOD", "good", level=ChunkLevel.COARSE),
    ]
    fine = [
        _chunk("F-R", "REF-RETRACTED", "bad"),
        _chunk("F-G", "REF-GOOD", "good"),
    ]

    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    svc = EvidenceRetrievalService(
        vector_port=LevelSplitStub(OrderedStub(coarse), OrderedStub(fine)),
        keyword_port=None,
        reranker=None,
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
        lifecycle_visibility=vis,
    )
    bundle = svc.retrieve(
        EvidenceRequest(query="x", top_k=5, allowed_ref_ids=["REF-RETRACTED"])
    )
    # Must not leak REF-GOOD or REF-RETRACTED
    assert bundle.evidence_records == []
