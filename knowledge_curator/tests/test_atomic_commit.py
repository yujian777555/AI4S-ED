"""Phase 2 tests: 03 §5.4 atomic ingest, pending_vector, idempotency, KB version/rollback."""

from __future__ import annotations

import asyncio

import pytest

from knowledge_curator.adapters import (
    FailureInjection,
    FakeMechanismValidator,
    InMemoryDocumentCommitStore,
    InMemoryKnowledgeRepository,
    InMemoryUSDOStore,
    InMemoryVectorIndex,
    InMemoryVersionStore,
    SimpleOntologyService,
)
from knowledge_curator.core.commit import DocumentCommitCoordinator
from knowledge_curator.core.curator import KnowledgeCurator
from knowledge_curator.schemas.assertions import Confidence, SourceClaimOrigin
from knowledge_curator.schemas.commit import (
    CommitPhase,
    CommitRequest,
    CommitStatus,
    SourceIdentity,
)
from knowledge_curator.schemas.curation import CurationAction
from knowledge_curator.tests.conftest import make_assertion, make_assertion_set, make_meta


def _run(coro):
    return asyncio.run(coro)


def _stack(*, seed=None, failures=None):
    failures = failures or FailureInjection()
    commit_store = InMemoryDocumentCommitStore(failures=failures)
    vector_index = InMemoryVectorIndex(failures=failures)
    usdo_store = InMemoryUSDOStore(failures=failures)
    version_store = InMemoryVersionStore(failures=failures)
    curator = KnowledgeCurator(
        repository=InMemoryKnowledgeRepository(seed=seed),
        ontology=SimpleOntologyService(),
        mechanism_validator=FakeMechanismValidator(),
    )
    coordinator = DocumentCommitCoordinator(
        commit_store=commit_store,
        vector_index=vector_index,
        usdo_store=usdo_store,
        version_store=version_store,
    )
    return {
        "curator": curator,
        "coordinator": coordinator,
        "commit_store": commit_store,
        "vector_index": vector_index,
        "usdo_store": usdo_store,
        "version_store": version_store,
        "failures": failures,
    }


def _commit_request(assertion_set, report, fingerprint="fp-001"):
    return CommitRequest(
        source=SourceIdentity(ref_id=assertion_set.ref_id, source_fingerprint=fingerprint),
        assertion_set=assertion_set,
        report=report,
    )


# ---------------------------------------------------------------------------
# A. Success
# ---------------------------------------------------------------------------

def test_p2_success_commits_and_publishes_one_version():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_commit_request(aset, report)))
    assert result.status == CommitStatus.PUBLISHED
    assert result.commit_id
    assert result.snapshot_id
    assert result.version_id
    published = s["version_store"].list_published_versions()
    assert len(published) == 1
    assert s["version_store"].current_version().version_id == result.version_id


def test_p2_snapshot_manifest_is_deterministic():
    s1 = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report1 = _run(s1["curator"].curate(aset))
    r1 = _run(s1["coordinator"].commit(_commit_request(aset, report1)))
    m1 = s1["version_store"].get_snapshot(r1.snapshot_id).manifest

    s2 = _stack()
    # Identical content (new curator run has new report_id; manifest must ignore it)
    aset2 = make_assertion_set([make_assertion("AS-1")])
    report2 = _run(s2["curator"].curate(aset2))
    r2 = _run(s2["coordinator"].commit(_commit_request(aset2, report2)))
    m2 = s2["version_store"].get_snapshot(r2.snapshot_id).manifest

    assert m1.content_hash == m2.content_hash
    assert m1.stable_payload() == m2.stable_payload()


def test_p2_curate_and_commit_convenience():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report, result = _run(
        s["curator"].curate_and_commit(aset, "fp-001", s["coordinator"])
    )
    assert report is not None
    assert result.status == CommitStatus.PUBLISHED


# ---------------------------------------------------------------------------
# B. Pre-publish rollback
# ---------------------------------------------------------------------------

def test_p2_structural_failure_leaves_no_published_version():
    s = _stack()
    s["failures"].fail_on("usdo.register")
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_commit_request(aset, report)))
    assert result.status == CommitStatus.FAILED
    assert s["version_store"].list_published_versions() == []
    assert s["version_store"].current_version() is None


def test_p2_usdo_failure_before_finalize_no_publish():
    s = _stack()
    s["failures"].fail_on("usdo.register")
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_commit_request(aset, report)))
    assert result.phase == CommitPhase.FAILED
    assert result.version_id is None
    assert len(s["version_store"].list_published_versions()) == 0


# ---------------------------------------------------------------------------
# C. Vector compensation / pending_vector
# ---------------------------------------------------------------------------

def test_p2_vector_failure_marks_pending_vector_no_publish():
    s = _stack()
    s["failures"].fail_on("vector.upsert")
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_commit_request(aset, report)))
    assert result.status == CommitStatus.PENDING_VECTOR
    assert result.phase == CommitPhase.VECTOR_PENDING
    assert result.version_id is None
    assert len(s["version_store"].list_published_versions()) == 0
    # Structural state retained for recovery
    record = s["commit_store"].find_by_key(aset.ref_id, "fp-001")
    assert record is not None
    assert record.phase == CommitPhase.VECTOR_PENDING
    assert len(record.admitted) == 1


def test_p2_pending_vector_retry_publishes_exactly_one_version_without_dup_structural():
    s = _stack()
    s["failures"].fail_on("vector.upsert")
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    first = _run(s["coordinator"].commit(_commit_request(aset, report)))
    assert first.status == CommitStatus.PENDING_VECTOR

    before_count = s["commit_store"].count_structural_assertions(first.commit_id)
    second = _run(s["coordinator"].commit(_commit_request(aset, report)))
    after_count = s["commit_store"].count_structural_assertions(first.commit_id)

    assert second.status == CommitStatus.PUBLISHED
    assert second.version_id is not None
    assert before_count == after_count == 1
    assert len(s["version_store"].list_published_versions()) == 1
    assert s["vector_index"].has_ids([f"vec-{aset.ref_id}-AS-1"])


# ---------------------------------------------------------------------------
# D. Idempotency
# ---------------------------------------------------------------------------

def test_p2_same_fingerprint_after_publish_is_idempotent_hit():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    first = _run(s["coordinator"].commit(_commit_request(aset, report)))
    second = _run(s["coordinator"].commit(_commit_request(aset, report)))
    assert first.status == CommitStatus.PUBLISHED
    assert second.status == CommitStatus.IDEMPOTENT_HIT
    assert second.version_id == first.version_id
    assert len(s["version_store"].list_published_versions()) == 1
    assert s["commit_store"].count_structural_assertions(first.commit_id) == 1
    assert s["vector_index"].count_for_ref(aset.ref_id) == 1
    assert len(s["usdo_store"].list_for_ref(aset.ref_id)) == 1


def test_p2_same_ref_id_new_fingerprint_can_create_new_version():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    v1 = _run(s["coordinator"].commit(_commit_request(aset, report, fingerprint="fp-A")))
    v2 = _run(s["coordinator"].commit(_commit_request(aset, report, fingerprint="fp-B")))
    assert v1.status == CommitStatus.PUBLISHED
    assert v2.status == CommitStatus.PUBLISHED
    assert v1.version_id != v2.version_id
    assert len(s["version_store"].list_published_versions()) == 2


# ---------------------------------------------------------------------------
# E. Eligibility
# ---------------------------------------------------------------------------

def test_p2_return_upstream_cannot_publish():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")], metadata=make_meta(doi=None, stable_id=None))
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_commit_request(aset, report)))
    assert result.status == CommitStatus.NOT_PUBLISHABLE
    assert len(s["version_store"].list_published_versions()) == 0


def test_p2_rejected_assertions_not_admitted_active():
    s = _stack()
    # mechanism violation -> REJECT
    from knowledge_curator.adapters import FakeMechanismValidator

    failures = FailureInjection()
    stack = _stack(failures=failures)
    stack["curator"] = KnowledgeCurator(
        repository=InMemoryKnowledgeRepository(),
        ontology=SimpleOntologyService(),
        mechanism_validator=FakeMechanismValidator(
            violated_ids=["AS-1"], ok=False, messages=["violation"]
        ),
    )
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(stack["curator"].curate(aset))
    assert all(d.action == CurationAction.REJECT for d in report.decisions)
    result = _run(stack["coordinator"].commit(_commit_request(aset, report)))
    assert result.status == CommitStatus.NOT_PUBLISHABLE
    assert len(stack["version_store"].list_published_versions()) == 0


def test_p2_pending_review_not_promoted_to_high_verified():
    s = _stack()
    old = make_assertion(
        "AS-OLD",
        ref_id="ED-OLD",
        value=0.35,
        uncertainty=0.05,
        conditions=make_assertion("AS-X").conditions,
    )
    # use same conditions as default make_assertion
    new = make_assertion(
        "AS-1",
        value=2.50,
        uncertainty=0.05,
        conditions=old.conditions,
    )
    s = _stack(seed=[old])
    aset = make_assertion_set([new])
    report = _run(s["curator"].curate(aset))
    assert report.decisions[0].action == CurationAction.PENDING_REVIEW
    result = _run(s["coordinator"].commit(_commit_request(aset, report)))
    assert result.status == CommitStatus.PUBLISHED
    record = s["commit_store"].find_by_key(aset.ref_id, "fp-001")
    admitted = record.admitted[0]
    assert admitted.visibility.value == "pending"
    assert admitted.confidence == Confidence.HYPOTHESIS
    assert admitted.confidence not in (Confidence.HIGH, Confidence.VERIFIED)


def test_p2_downgrade_keeps_downgraded_confidence():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1", unit=None, missing_unit=True)])
    report = _run(s["curator"].curate(aset))
    result = _run(s["coordinator"].commit(_commit_request(aset, report)))
    assert result.status == CommitStatus.PUBLISHED
    record = s["commit_store"].find_by_key(aset.ref_id, "fp-001")
    admitted = record.admitted[0]
    assert admitted.visibility.value == "downgraded"
    assert admitted.confidence == Confidence.HYPOTHESIS


# ---------------------------------------------------------------------------
# F. Rollback
# ---------------------------------------------------------------------------

def test_p2_rollback_switches_visible_pointer_and_retains_history():
    s = _stack()
    aset1 = make_assertion_set([make_assertion("AS-1")], ref_id="ED-1")
    report1 = _run(s["curator"].curate(aset1))
    v1 = _run(s["coordinator"].commit(_commit_request(aset1, report1, fingerprint="fp-1")))

    aset2 = make_assertion_set([make_assertion("AS-2")], ref_id="ED-2")
    report2 = _run(s["curator"].curate(aset2))
    v2 = _run(s["coordinator"].commit(_commit_request(aset2, report2, fingerprint="fp-2")))

    assert s["version_store"].current_version().version_id == v2.version_id
    rolled = s["version_store"].rollback_to(v1.version_id)
    assert rolled.version_id == v1.version_id
    assert s["version_store"].current_version().version_id == v1.version_id
    # V2 remains historically present (not deleted)
    historical = {v.version_id for v in s["version_store"].list_published_versions()}
    assert v2.version_id in historical
    assert v1.version_id in historical
    assert s["version_store"].get_version(v2.version_id) is not None


def test_p2_rollback_nonexistent_target_fails_explicitly():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    report = _run(s["curator"].curate(aset))
    _run(s["coordinator"].commit(_commit_request(aset, report)))
    with pytest.raises(ValueError):
        s["version_store"].rollback_to("kbv-does-not-exist")


# ---------------------------------------------------------------------------
# G. Boundaries
# ---------------------------------------------------------------------------

def test_p2_core_has_no_sqlite_faiss_deepseek_dsh_imports():
    forbidden = ("sqlite", "faiss", "deepseek", "dsh_sdk", "dsh.agent", "@dsh")
    modules = [
        "knowledge_curator.core.commit",
        "knowledge_curator.core.curator",
        "knowledge_curator.schemas.commit",
        "knowledge_curator.ports.document_commit_store",
        "knowledge_curator.ports.vector_index",
        "knowledge_curator.ports.usdo_store",
        "knowledge_curator.ports.version_store",
        "knowledge_curator.adapters.in_memory_commit",
    ]
    import sys

    for name in modules:
        if name not in sys.modules:
            __import__(name)
        src = open(sys.modules[name].__file__, encoding="utf-8").read().lower()
        for token in forbidden:
            if f"import {token}" in src or f"from {token}" in src:
                raise AssertionError(f"{name} must not import {token}")


def test_p2_phase1_tests_still_isolated():
    """Smoke: Phase 2 stack does not mutate Phase 1 confidence gates."""
    s = _stack()
    aset = make_assertion_set(
        [make_assertion("AS-1", confidence=Confidence.HIGH, origin=SourceClaimOrigin.PRIMARY)]
    )
    report = _run(s["curator"].curate(aset))
    assert report.decisions[0].confidence == Confidence.MEDIUM
