"""Phase 2.2 regression tests: final atomic visibility & versioned read closure.

Covers P2.2-01..04 and H2.2-01/02. Includes the required V1->V2->rollback proof.
"""

from __future__ import annotations

import asyncio

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
from knowledge_curator.core.commit import DocumentCommitCoordinator
from knowledge_curator.core.curator import KnowledgeCurator
from knowledge_curator.core.version_view import VersionedKnowledgeView
from knowledge_curator.schemas.commit import CommitPhase, CommitRequest, CommitStatus, SourceIdentity
from knowledge_curator.tests.conftest import make_assertion, make_assertion_set


def _run(coro):
    return asyncio.run(coro)


def _stack(*, seed=None, failures=None):
    failures = failures or FailureInjection()
    commit_store = InMemoryDocumentCommitStore(failures=failures)
    structural_store = InMemoryStructuralKnowledgeStore(failures=failures)
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
        structural_store=structural_store,
        vector_index=vector_index,
        usdo_store=usdo_store,
        version_store=version_store,
    )
    view = VersionedKnowledgeView(
        version_store=version_store,
        structural_store=structural_store,
        usdo_store=usdo_store,
        vector_index=vector_index,
    )
    return {
        "curator": curator,
        "coordinator": coordinator,
        "view": view,
        "commit_store": commit_store,
        "structural_store": structural_store,
        "vector_index": vector_index,
        "usdo_store": usdo_store,
        "version_store": version_store,
        "failures": failures,
    }


def _req(aset, report, fingerprint="fp-001"):
    return CommitRequest(
        source=SourceIdentity(ref_id=aset.ref_id, source_fingerprint=fingerprint),
        assertion_set=aset,
        report=report,
    )


def _commit(s, aset, fingerprint="fp-001"):
    report = _run(s["curator"].curate(aset))
    return _run(s["coordinator"].commit(_req(aset, report, fingerprint=fingerprint))), report


# ---------------------------------------------------------------------------
# P2.2-01 — structural + USDO atomic visibility / compensation
# ---------------------------------------------------------------------------

def test_p22_structural_ok_usdo_fail_before_neither_visible():
    s = _stack()
    s["failures"].fail_on("usdo.commit")
    aset = make_assertion_set([make_assertion("AS-1")])
    result, _ = _commit(s, aset)
    assert result.status == CommitStatus.FAILED
    assert s["structural_store"].list_committed_for_ref(aset.ref_id) == []
    assert s["usdo_store"].list_for_ref(aset.ref_id) == []
    assert s["version_store"].list_published_versions() == []


def test_p22_structural_ok_usdo_fail_after_side_effect_neither_visible():
    s = _stack()
    s["failures"].fail_after("usdo.commit")
    aset = make_assertion_set([make_assertion("AS-1")])
    result, _ = _commit(s, aset)
    assert result.status == CommitStatus.FAILED
    # compensation must undo structural commit and USDO commit side effects
    assert s["structural_store"].list_committed_for_ref(aset.ref_id) == []
    assert s["usdo_store"].list_for_ref(aset.ref_id) == []
    assert s["version_store"].list_published_versions() == []


def test_p22_structural_fail_after_side_effect_neither_visible():
    s = _stack()
    s["failures"].fail_after("structural.commit")
    aset = make_assertion_set([make_assertion("AS-1")])
    result, _ = _commit(s, aset)
    assert result.status == CommitStatus.FAILED
    assert s["structural_store"].list_committed_for_ref(aset.ref_id) == []
    assert s["usdo_store"].list_for_ref(aset.ref_id) == []
    assert s["version_store"].list_published_versions() == []


def test_p22_lifecycle_structural_ack_failure_no_half_visible_leak():
    s = _stack()
    # After both commit_stages succeed, the STRUCTURAL_COMMITTED lifecycle ack fails.
    s["failures"].fail_after("usdo.commit", also_fail=["document_commit.update"])
    aset = make_assertion_set([make_assertion("AS-1")])
    result, _ = _commit(s, aset)
    # Coordinator compensates on prepare failure even if stores were finalized.
    assert result.status == CommitStatus.FAILED
    assert s["structural_store"].list_committed_for_ref(aset.ref_id) == []
    assert s["usdo_store"].list_for_ref(aset.ref_id) == []
    assert s["version_store"].list_published_versions() == []


def test_p22_successful_commit_exposes_structural_and_usdo_exactly_once():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    result, _ = _commit(s, aset)
    assert result.status == CommitStatus.PUBLISHED
    assert len(s["structural_store"].list_committed_for_ref(aset.ref_id)) == 1
    assert len(s["usdo_store"].list_for_ref(aset.ref_id)) == 1
    # stale staged copies cleaned
    assert s["structural_store"].count_staged() == 0
    assert s["usdo_store"].count_staged() == 0


# ---------------------------------------------------------------------------
# P2.2-02 — snapshot create idempotency
# ---------------------------------------------------------------------------

def test_p22_snapshot_create_fail_after_side_effect_retry_reuses_snapshot():
    s = _stack()
    s["failures"].fail_after("version.create_snapshot")
    aset = make_assertion_set([make_assertion("AS-1")])
    first, _ = _commit(s, aset)
    assert first.status == CommitStatus.PENDING_FINALIZE
    assert first.version_id is None

    # retry: same deterministic manifest must reuse the orphaned snapshot
    s["failures"].clear()
    second, _ = _commit(s, aset, fingerprint="fp-001")
    # second is idempotent-hit or completed; either way no duplicate version
    assert second.status in (CommitStatus.PUBLISHED, CommitStatus.IDEMPOTENT_HIT)
    assert len(s["version_store"].list_published_versions()) == 1

    # snapshot count for this content hash is 1
    record = s["commit_store"].find_by_key(aset.ref_id, "fp-001")
    assert record.snapshot_id is not None
    snap = s["version_store"].get_snapshot(record.snapshot_id)
    by_hash = s["version_store"].get_snapshot_by_hash(snap.manifest.content_hash)
    assert by_hash is not None
    assert by_hash.snapshot_id == record.snapshot_id


def test_p22_same_manifest_content_reuses_snapshot_id():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    result, _ = _commit(s, aset)
    snap1 = s["version_store"].get_snapshot(result.snapshot_id)
    again = s["version_store"].create_snapshot(snap1.manifest)
    assert again.snapshot_id == snap1.snapshot_id


# ---------------------------------------------------------------------------
# P2.2-03 — transient FAILED exact retry
# ---------------------------------------------------------------------------

def test_p22_transient_structural_stage_failure_allows_exact_retry():
    s = _stack()
    s["failures"].fail_on("structural.stage")
    aset = make_assertion_set([make_assertion("AS-1")])
    first, report = _commit(s, aset, fingerprint="fp-001")
    assert first.status == CommitStatus.FAILED
    assert first.version_id is None

    s["failures"].clear()
    second, _ = _commit(s, aset, fingerprint="fp-001")
    assert second.status == CommitStatus.PUBLISHED
    assert len(s["version_store"].list_published_versions()) == 1
    assert s["structural_store"].count_staged() == 0
    assert s["usdo_store"].count_staged() == 0


def test_p22_transient_usdo_commit_failure_allows_exact_retry():
    s = _stack()
    s["failures"].fail_on("usdo.commit")
    aset = make_assertion_set([make_assertion("AS-1")])
    first, _ = _commit(s, aset, fingerprint="fp-001")
    assert first.status == CommitStatus.FAILED

    s["failures"].clear()
    second, _ = _commit(s, aset, fingerprint="fp-001")
    assert second.status == CommitStatus.PUBLISHED
    assert len(s["version_store"].list_published_versions()) == 1
    assert len(s["usdo_store"].list_for_ref(aset.ref_id)) == 1


def test_p22_transient_structural_ack_failure_allows_exact_retry():
    s = _stack()
    s["failures"].fail_after("structural.commit", also_fail=["document_commit.update"])
    aset = make_assertion_set([make_assertion("AS-1")])
    first, _ = _commit(s, aset, fingerprint="fp-001")
    assert first.status == CommitStatus.FAILED
    assert s["structural_store"].list_committed_for_ref(aset.ref_id) == []

    s["failures"].clear()
    second, _ = _commit(s, aset, fingerprint="fp-001")
    assert second.status == CommitStatus.PUBLISHED
    assert len(s["version_store"].list_published_versions()) == 1


# ---------------------------------------------------------------------------
# P2.2-04 — version-scoped read view + V1/V2/rollback proof
# ---------------------------------------------------------------------------

def test_p22_v1_v2_rollback_current_view_resolves_v1_dependencies():
    """Acceptance chain: V1 publish -> V2 publish -> rollback V1 -> current = V1 data."""
    s = _stack()
    aset1 = make_assertion_set([make_assertion("AS-1", value=1.0)], ref_id="ED-S")
    r1, _ = _commit(s, aset1, fingerprint="fp-v1")
    assert r1.status == CommitStatus.PUBLISHED

    aset2 = make_assertion_set([make_assertion("AS-1", value=2.0)], ref_id="ED-S")
    r2, _ = _commit(s, aset2, fingerprint="fp-v2")
    assert r2.status == CommitStatus.PUBLISHED

    assert s["version_store"].current_version().version_id == r2.version_id

    s["version_store"].rollback_to(r1.version_id)
    assert s["version_store"].current_version().version_id == r1.version_id

    current = s["view"].resolve_current()
    assert current is not None
    assert current.version_id == r1.version_id

    # V1 structural
    assert current.structural is not None
    assert current.structural.stage_id == r1.commit_id
    assert current.structural.source_fingerprint == "fp-v1"
    assert current.structural.assertions[0].assertion.object.value == 1.0

    # V1 USDO
    assert len(current.usdo_records) == 1
    assert current.usdo_records[0].record_id.endswith("fp-v1") or "fp-v1"[:8] in current.usdo_records[0].record_id

    # V1 vectors
    assert len(current.vector_payloads) == 1
    assert "fp-v1" in current.vector_payloads[0].vector_id
    assert current.vector_payloads[0].content_hash != s["view"].resolve(r2.version_id).vector_payloads[0].content_hash

    # Must NOT return V2 substitutions
    assert current.structural.stage_id != r2.commit_id
    assert all("fp-v2" not in v.vector_id for v in current.vector_payloads)

    # Explicit resolve(V2) still works
    v2 = s["view"].resolve(r2.version_id)
    assert v2 is not None
    assert v2.version_id == r2.version_id
    assert v2.structural is not None
    assert v2.structural.stage_id == r2.commit_id
    assert v2.structural.assertions[0].assertion.object.value == 2.0
    assert len(v2.vector_payloads) == 1
    assert "fp-v2" in v2.vector_payloads[0].vector_id


def test_p22_view_resolve_current_is_v2_before_rollback():
    s = _stack()
    aset1 = make_assertion_set([make_assertion("AS-1", value=1.0)], ref_id="ED-S")
    r1, _ = _commit(s, aset1, fingerprint="fp-v1")
    aset2 = make_assertion_set([make_assertion("AS-1", value=2.0)], ref_id="ED-S")
    r2, _ = _commit(s, aset2, fingerprint="fp-v2")
    current = s["view"].resolve_current()
    assert current.version_id == r2.version_id
    assert current.structural.assertions[0].assertion.object.value == 2.0


# ---------------------------------------------------------------------------
# H2.2-01 — PENDING_VECTOR vs PENDING_FINALIZE
# ---------------------------------------------------------------------------

def test_p22_vector_failure_is_pending_vector_only():
    s = _stack()
    s["failures"].fail_on("vector.upsert")
    aset = make_assertion_set([make_assertion("AS-1")])
    result, _ = _commit(s, aset)
    assert result.status == CommitStatus.PENDING_VECTOR
    assert result.phase == CommitPhase.VECTOR_PENDING


def test_p22_snapshot_failure_is_pending_finalize():
    s = _stack()
    s["failures"].fail_on("version.create_snapshot")
    aset = make_assertion_set([make_assertion("AS-1")])
    result, _ = _commit(s, aset)
    assert result.status == CommitStatus.PENDING_FINALIZE
    assert result.status != CommitStatus.PENDING_VECTOR
    assert result.phase == CommitPhase.VECTOR_COMMITTED


def test_p22_publish_failure_is_pending_finalize():
    s = _stack()
    s["failures"].fail_on("version.publish")
    aset = make_assertion_set([make_assertion("AS-1")])
    result, _ = _commit(s, aset)
    assert result.status == CommitStatus.PENDING_FINALIZE
    assert result.status != CommitStatus.PENDING_VECTOR


# ---------------------------------------------------------------------------
# H2.2-02 — staged cleanup
# ---------------------------------------------------------------------------

def test_p22_successful_commit_leaves_no_stale_staged_state():
    s = _stack()
    aset = make_assertion_set([make_assertion("AS-1")])
    _commit(s, aset)
    assert s["structural_store"].count_staged() == 0
    assert s["usdo_store"].count_staged() == 0


# ---------------------------------------------------------------------------
# Preserve Phase 1/2 guarantees
# ---------------------------------------------------------------------------

def test_p22_confidence_gate_still_frozen():
    s = _stack()
    from knowledge_curator.schemas.assertions import Confidence, SourceClaimOrigin

    aset = make_assertion_set(
        [make_assertion("AS-1", confidence=Confidence.HIGH, origin=SourceClaimOrigin.PRIMARY)]
    )
    report = _run(s["curator"].curate(aset))
    assert report.decisions[0].confidence == Confidence.MEDIUM


def test_p22_no_dsh_deepseek_mcp_imports_in_core():
    forbidden = ("deepseek", "dsh_sdk", "dsh.agent", "@dsh", "mcp.server", "fastmcp")
    modules = [
        "knowledge_curator.core.commit",
        "knowledge_curator.core.version_view",
        "knowledge_curator.core.curator",
        "knowledge_curator.adapters.in_memory_commit",
        "knowledge_curator.schemas.commit",
    ]
    import sys

    for name in modules:
        if name not in sys.modules:
            __import__(name)
        src = open(sys.modules[name].__file__, encoding="utf-8").read().lower()
        for token in forbidden:
            if f"import {token}" in src or f"from {token}" in src:
                raise AssertionError(f"{name} must not import {token}")
