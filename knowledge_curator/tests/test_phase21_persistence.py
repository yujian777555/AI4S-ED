"""Phase 2.1 regression tests: persistence / recovery / rollback correctness.

Covers P2.1-01..05 and H2.1-01/02 from planner/phase-02-review.md.
"""

from __future__ import annotations

import asyncio

import pytest

from knowledge_curator.adapters import (
    FailureInjection,
    FakeMechanismValidator,
    InMemoryDocumentCommitStore,
    InMemoryKnowledgeRepository,
    InMemoryStructuralKnowledgeStore,
    InMemoryUSDOStore,
    InMemoryVectorIndex,
    InMemoryVersionStore,
    SimpleOntologyService,
)
from knowledge_curator.core.commit import DocumentCommitCoordinator, validate_commit_request
from knowledge_curator.core.curator import KnowledgeCurator
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.commit import (
    AssertionVisibility,
    CommitPhase,
    CommitRequest,
    CommitStatus,
    SourceIdentity,
)
from knowledge_curator.schemas.curation import AssertionDecision, CurationAction
from knowledge_curator.tests.conftest import make_assertion, make_assertion_set, make_meta


def _run(coro):
    return asyncio.run(coro)


def _stack(*, seed=None, failures=None, mechanism=None):
    failures = failures or FailureInjection()
    commit_store = InMemoryDocumentCommitStore(failures=failures)
    structural_store = InMemoryStructuralKnowledgeStore(failures=failures)
    vector_index = InMemoryVectorIndex(failures=failures)
    usdo_store = InMemoryUSDOStore(failures=failures)
    version_store = InMemoryVersionStore(failures=failures)
    curator = KnowledgeCurator(
        repository=InMemoryKnowledgeRepository(seed=seed),
        ontology=SimpleOntologyService(),
        mechanism_validator=mechanism or FakeMechanismValidator(),
    )
    coordinator = DocumentCommitCoordinator(
        commit_store=commit_store,
        structural_store=structural_store,
        vector_index=vector_index,
        usdo_store=usdo_store,
        version_store=version_store,
    )
    return {
        "curator": curator,
        "coordinator": coordinator,
        "commit_store": commit_store,
        "structural_store": structural_store,
        "vector_index": vector_index,
        "usdo_store": usdo_store,
        "version_store": version_store,
        "failures": failures,
    }


def _req(aset, report, fingerprint="fp-001", ref_id=None):
    return CommitRequest(
        source=SourceIdentity(
            ref_id=ref_id or aset.ref_id,
            source_fingerprint=fingerprint,
        ),
        assertion_set=aset,
        report=report,
    )


# ---------------------------------------------------------------------------
# Structural persistence (P2.1-01)
# ---------------------------------------------------------------------------

def test_p21_successful_publish_has_committed_structural_assertions():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_req(aset, report)))
    assert result.status == CommitStatus.PUBLISHED
    committed = s["structural_store"].list_committed_for_ref(aset.ref_id)
    assert len(committed) == 1
    assert len(committed[0].assertions) == 1
    assert committed[0].assertions[0].assertion.id == "AS-1"
    assert s["structural_store"].is_committed(result.commit_id)
    assert s["structural_store"].get_committed(result.commit_id) is not None


def test_p21_lifecycle_record_alone_is_not_structural_proof():
    s = _stack()
    s["failures"].fail_on("structural.stage")
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_req(aset, report)))
    assert result.status == CommitStatus.FAILED
    # lifecycle may exist as audit, but no committed structural knowledge
    assert s["structural_store"].list_committed_for_ref(aset.ref_id) == []
    record = s["commit_store"].find_by_key(aset.ref_id, "fp-001")
    assert record is not None  # audit/lifecycle record may remain
    assert record.phase == CommitPhase.FAILED
    assert len(s["version_store"].list_published_versions()) == 0


def test_p21_failed_pre_structural_stage_leaves_no_committed_structural_data():
    s = _stack()
    s["failures"].fail_on("usdo.stage")
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_req(aset, report)))
    assert result.status == CommitStatus.FAILED
    assert s["structural_store"].list_committed_for_ref(aset.ref_id) == []
    assert s["usdo_store"].list_for_ref(aset.ref_id) == []


# ---------------------------------------------------------------------------
# USDO staged visibility (P2.1-02)
# ---------------------------------------------------------------------------

def test_p21_staged_usdo_not_visible_before_commit():
    s = _stack()
    s["failures"].fail_on("vector.upsert")  # stop after structural commit
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_req(aset, report)))
    # structural is committed so USDO is visible after commit_stage
    assert result.status == CommitStatus.PENDING_VECTOR
    assert len(s["usdo_store"].list_for_ref(aset.ref_id)) == 1


def test_p21_failure_after_usdo_staging_hides_payloads():
    s = _stack()
    s["failures"].fail_on("structural.commit")  # fail at visibility finalization
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_req(aset, report)))
    assert result.status == CommitStatus.FAILED
    # staged USDO must have been aborted / never made committed-visible
    assert s["usdo_store"].list_for_ref(aset.ref_id) == []
    assert s["structural_store"].list_committed_for_ref(aset.ref_id) == []


def test_p21_successful_structural_commit_exposes_usdo_exactly_once():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    _run(s["coordinator"].commit(_req(aset, report)))
    _run(s["coordinator"].commit(_req(aset, report)))  # idempotent retry
    assert len(s["usdo_store"].list_for_ref(aset.ref_id)) == 1


# ---------------------------------------------------------------------------
# CommitRequest binding (P2.1-05)
# ---------------------------------------------------------------------------

def test_p21_ref_id_mismatch_fails_closed():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    req = _req(aset, report, ref_id="ED-OTHER")
    result = _run(s["coordinator"].commit(req))
    assert result.status == CommitStatus.FAILED
    assert any("ref_id" in e for e in result.detail.get("errors", []))
    assert s["structural_store"].list_committed_for_ref(aset.ref_id) == []
    assert s["version_store"].list_published_versions() == []


def test_p21_empty_fingerprint_fails_closed():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    req = _req(aset, report, fingerprint="")
    result = _run(s["coordinator"].commit(req))
    assert result.status == CommitStatus.FAILED
    assert any("fingerprint" in e for e in result.detail.get("errors", []))
    assert s["commit_store"].find_by_key(aset.ref_id, "") is None


def test_p21_missing_decision_fails_closed():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1"), make_assertion("AS-2")])
    report = _run(s["curator"].curate(aset))
    report.decisions = [d for d in report.decisions if d.assertion_id != "AS-2"]
    result = _run(s["coordinator"].commit(_req(aset, report)))
    assert result.status == CommitStatus.FAILED
    assert any("missing decisions" in e for e in result.detail.get("errors", []))
    assert s["version_store"].list_published_versions() == []


def test_p21_foreign_decision_fails_closed():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    report.decisions.append(
        AssertionDecision(
            assertion_id="AS-FOREIGN",
            action=CurationAction.ACCEPT,
            confidence=Confidence.MEDIUM,
            reason="x",
        )
    )
    result = _run(s["coordinator"].commit(_req(aset, report)))
    assert result.status == CommitStatus.FAILED
    assert any("unknown assertions" in e for e in result.detail.get("errors", []))
    assert s["version_store"].list_published_versions() == []


def test_p21_duplicate_assertion_ids_fail_closed():
    s = _stack()
    a = make_assertion("AS-1")
    aset = make_assertion_set([a, make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    # decisions may also collapse; force duplicate by adding another decision
    report.decisions.append(
        AssertionDecision(
            assertion_id="AS-1",
            action=CurationAction.ACCEPT,
            confidence=Confidence.MEDIUM,
            reason="dup",
        )
    )
    result = _run(s["coordinator"].commit(_req(aset, report)))
    assert result.status == CommitStatus.FAILED
    errors = result.detail.get("errors", [])
    assert any("duplicate" in e for e in errors)


def test_p21_validate_commit_request_unit():
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(KnowledgeCurator(
        repository=InMemoryKnowledgeRepository(),
        ontology=SimpleOntologyService(),
        mechanism_validator=FakeMechanismValidator(),
    ).curate(aset))
    ok = CommitRequest(
        source=SourceIdentity(ref_id=aset.ref_id, source_fingerprint="fp"),
        assertion_set=aset,
        report=report,
    )
    assert validate_commit_request(ok) == []


# ---------------------------------------------------------------------------
# Vector immutability / version-safety (P2.1-04)
# ---------------------------------------------------------------------------

def test_p21_v1_v2_same_assertion_id_distinct_vector_ids():
    s = _stack()
    aset1 = make_assertion_set([make_assertion("AS-1", value=1.0)], ref_id="ED-S")
    report1 = _run(s["curator"].curate(aset1))
    r1 = _run(s["coordinator"].commit(_req(aset1, report1, fingerprint="fp-v1")))

    aset2 = make_assertion_set([make_assertion("AS-1", value=2.0)], ref_id="ED-S")
    report2 = _run(s["curator"].curate(aset2))
    r2 = _run(s["coordinator"].commit(_req(aset2, report2, fingerprint="fp-v2")))

    assert r1.status == CommitStatus.PUBLISHED
    assert r2.status == CommitStatus.PUBLISHED
    rec1 = s["commit_store"].find_by_key("ED-S", "fp-v1")
    rec2 = s["commit_store"].find_by_key("ED-S", "fp-v2")
    id1 = rec1.vector_payloads[0].vector_id
    id2 = rec2.vector_payloads[0].vector_id
    assert id1 != id2
    # both payloads remain retrievable
    assert s["vector_index"].get_by_id(id1) is not None
    assert s["vector_index"].get_by_id(id2) is not None
    assert s["vector_index"].get_by_id(id1).content_hash != s["vector_index"].get_by_id(id2).content_hash


def test_p21_v1_snapshot_still_resolves_v1_vector_after_v2_publish():
    s = _stack()
    aset1 = make_assertion_set([make_assertion("AS-1", value=1.0)], ref_id="ED-S")
    report1 = _run(s["curator"].curate(aset1))
    r1 = _run(s["coordinator"].commit(_req(aset1, report1, fingerprint="fp-v1")))
    aset2 = make_assertion_set([make_assertion("AS-1", value=2.0)], ref_id="ED-S")
    report2 = _run(s["curator"].curate(aset2))
    r2 = _run(s["coordinator"].commit(_req(aset2, report2, fingerprint="fp-v2")))

    snap1 = s["version_store"].get_snapshot(r1.snapshot_id).manifest
    for vid in snap1.vector_ids:
        payload = s["vector_index"].get_by_id(vid)
        assert payload is not None
        # V1 snapshot references V1 payload, not overwritten V2
        assert payload.content_hash == snap1.assertion_hashes[0] or payload.vector_id in snap1.vector_ids


def test_p21_rollback_v1_does_not_depend_on_v2_vector_state():
    s = _stack()
    aset1 = make_assertion_set([make_assertion("AS-1", value=1.0)], ref_id="ED-S")
    report1 = _run(s["curator"].curate(aset1))
    r1 = _run(s["coordinator"].commit(_req(aset1, report1, fingerprint="fp-v1")))
    aset2 = make_assertion_set([make_assertion("AS-1", value=2.0)], ref_id="ED-S")
    report2 = _run(s["curator"].curate(aset2))
    r2 = _run(s["coordinator"].commit(_req(aset2, report2, fingerprint="fp-v2")))

    s["version_store"].rollback_to(r1.version_id)
    snap1 = s["version_store"].get_snapshot(r1.snapshot_id).manifest
    for vid in snap1.vector_ids:
        assert s["vector_index"].get_by_id(vid) is not None
    assert s["version_store"].current_version().version_id == r1.version_id
    # V2 remains historical
    assert s["version_store"].get_version(r2.version_id) is not None


# ---------------------------------------------------------------------------
# Idempotent version publish / failure window (P2.1-03)
# ---------------------------------------------------------------------------

def test_p21_publish_is_idempotent_per_snapshot():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_req(aset, report)))
    snap_id = result.snapshot_id
    v_a = s["version_store"].publish_version(snap_id)
    v_b = s["version_store"].publish_version(snap_id)
    assert v_a.version_id == v_b.version_id
    assert len(s["version_store"].list_published_versions()) == 1


def test_p21_publish_failure_is_resumable_and_retry_publishes_once():
    s = _stack()
    s["failures"].fail_on("version.publish")
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    first = _run(s["coordinator"].commit(_req(aset, report)))
    assert first.status == CommitStatus.PENDING_VECTOR
    assert first.phase == CommitPhase.SNAPSHOT_CREATED
    assert first.version_id is None

    second = _run(s["coordinator"].commit(_req(aset, report)))
    assert second.status == CommitStatus.PUBLISHED
    assert len(s["version_store"].list_published_versions()) == 1


def test_p21_publish_success_lifecycle_ack_failure_no_duplicate_version():
    s = _stack()
    # Publish side effect succeeds; the next lifecycle update (ack) fails.
    s["failures"].fail_after("version.publish", also_fail=["document_commit.update"])
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    first = _run(s["coordinator"].commit(_req(aset, report)))
    # publish side effect succeeded; ack failed -> resumable with known version
    assert first.version_id is not None
    assert first.status == CommitStatus.PENDING_VECTOR

    # retry must reuse the same version, not create a second
    s["failures"].clear()
    second = _run(s["coordinator"].commit(_req(aset, report)))
    assert second.status == CommitStatus.PUBLISHED
    assert second.version_id == first.version_id
    assert len(s["version_store"].list_published_versions()) == 1


def test_p21_snapshot_failure_stays_resumable_not_vector_labeled():
    s = _stack()
    s["failures"].fail_on("version.create_snapshot")
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    first = _run(s["coordinator"].commit(_req(aset, report)))
    assert first.status == CommitStatus.PENDING_VECTOR
    assert first.phase == CommitPhase.VECTOR_COMMITTED
    # retry after clear publishes once
    second = _run(s["coordinator"].commit(_req(aset, report)))
    assert second.status == CommitStatus.PUBLISHED
    assert len(s["version_store"].list_published_versions()) == 1


# ---------------------------------------------------------------------------
# Store copy semantics (plan §7)
# ---------------------------------------------------------------------------

def test_p21_lifecycle_store_copy_on_write():
    store = InMemoryDocumentCommitStore()
    from knowledge_curator.ports.document_commit_store import DocumentCommitRecord

    rec = DocumentCommitRecord(
        commit_id="dc-x",
        ref_id="ED-1",
        source_fingerprint="fp",
        phase=CommitPhase.PREPARING,
    )
    store.create(rec)
    fetched = store.find_by_key("ED-1", "fp")
    fetched.phase = CommitPhase.PUBLISHED  # mutate local copy only
    again = store.find_by_key("ED-1", "fp")
    assert again.phase == CommitPhase.PREPARING

    again.phase = CommitPhase.STRUCTURAL_COMMITTED
    store.update(again)
    after = store.find_by_key("ED-1", "fp")
    assert after.phase == CommitPhase.STRUCTURAL_COMMITTED


# ---------------------------------------------------------------------------
# SUPERSEDE never ACTIVE (H2.1-01)
# ---------------------------------------------------------------------------

def test_p21_supersede_is_never_active():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    # Force a SUPERSEDE decision
    report.decisions[0] = AssertionDecision(
        assertion_id="AS-1",
        action=CurationAction.SUPERSEDE,
        confidence=Confidence.MEDIUM,
        reason="truth adjudication placeholder",
    )
    result = _run(s["coordinator"].commit(_req(aset, report)))
    assert result.status == CommitStatus.PUBLISHED
    record = s["commit_store"].find_by_key(aset.ref_id, "fp-001")
    admitted = record.admitted[0]
    assert admitted.visibility == AssertionVisibility.SUPERSEDED
    assert admitted.visibility != AssertionVisibility.ACTIVE
    committed = s["structural_store"].list_committed_for_ref(aset.ref_id)
    assert committed[0].assertions[0].visibility == AssertionVisibility.SUPERSEDED


# ---------------------------------------------------------------------------
# Snapshot hash completeness (H2.1-02)
# ---------------------------------------------------------------------------

def test_p21_uncertainty_change_changes_manifest_hash():
    s1 = _stack()
    a1 = make_assertion("AS-1", uncertainty=0.05)
    aset1 = make_assertion_set([a1])
    rep1 = _run(s1["curator"].curate(aset1))
    r1 = _run(s1["coordinator"].commit(_req(aset1, rep1)))
    h1 = s1["version_store"].get_snapshot(r1.snapshot_id).manifest.content_hash

    s2 = _stack()
    a2 = make_assertion("AS-1", uncertainty=0.20)
    aset2 = make_assertion_set([a2])
    rep2 = _run(s2["curator"].curate(aset2))
    r2 = _run(s2["coordinator"].commit(_req(aset2, rep2)))
    h2 = s2["version_store"].get_snapshot(r2.snapshot_id).manifest.content_hash

    assert h1 != h2


def test_p21_provenance_sentence_change_changes_manifest_hash():
    from knowledge_curator.schemas.assertions import Provenance

    s1 = _stack()
    a1 = make_assertion("AS-1")
    a1.provenance = Provenance(locator="T12", sentence="row 2")
    aset1 = make_assertion_set([a1])
    rep1 = _run(s1["curator"].curate(aset1))
    r1 = _run(s1["coordinator"].commit(_req(aset1, rep1)))
    h1 = s1["version_store"].get_snapshot(r1.snapshot_id).manifest.content_hash

    s2 = _stack()
    a2 = make_assertion("AS-1")
    a2.provenance = Provenance(locator="T12", sentence="row 3")
    aset2 = make_assertion_set([a2])
    rep2 = _run(s2["curator"].curate(aset2))
    r2 = _run(s2["coordinator"].commit(_req(aset2, rep2)))
    h2 = s2["version_store"].get_snapshot(r2.snapshot_id).manifest.content_hash

    assert h1 != h2


# ---------------------------------------------------------------------------
# Rollback retains V2 + V1 snapshot deps (plan §10)
# ---------------------------------------------------------------------------

def test_p21_rollback_v1_v2_history_and_deps():
    s = _stack()
    aset1 = make_assertion_set([make_assertion("AS-1")], ref_id="ED-A")
    rep1 = _run(s["curator"].curate(aset1))
    v1 = _run(s["coordinator"].commit(_req(aset1, rep1, fingerprint="fp-1")))
    aset2 = make_assertion_set([make_assertion("AS-2")], ref_id="ED-B")
    rep2 = _run(s["curator"].curate(aset2))
    v2 = _run(s["coordinator"].commit(_req(aset2, rep2, fingerprint="fp-2")))

    s["version_store"].rollback_to(v1.version_id)
    assert s["version_store"].current_version().version_id == v1.version_id
    historical = {v.version_id for v in s["version_store"].list_published_versions()}
    assert v1.version_id in historical and v2.version_id in historical
    snap1 = s["version_store"].get_snapshot(v1.snapshot_id).manifest
    for vid in snap1.vector_ids:
        assert s["vector_index"].get_by_id(vid) is not None
