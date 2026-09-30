"""Phase 5.1-R1 tests: identity precedence, prior-only lineage, registry invariants."""

from __future__ import annotations

import pytest

from knowledge_curator.adapters.in_memory_source_versions import (
    InMemorySourceVersionRegistry,
)
from knowledge_curator.core.source_identity import IncrementalIntakeService
from knowledge_curator.schemas.source_versions import (
    IntakeDisposition,
    SourceCandidate,
    SourceKind,
    SourceVersionRecord,
    VersionRelation,
    WorkRecord,
)


def _svc():
    reg = InMemorySourceVersionRegistry()
    return IncrementalIntakeService(reg), reg


def _cand(**kw):
    defaults = dict(
        ref_id="REF-1",
        source_fingerprint="fp1",
        title="A Study of Membranes",
        doi="10.1000/xyz",
        stable_id="ST-1",
        source_kind=SourceKind.JOURNAL,
    )
    defaults.update(kw)
    return SourceCandidate(**defaults)


def _seed_work_a(svc, reg):
    """Work A: DOI X / stable ST-A."""
    c = _cand(ref_id="REF-A", source_fingerprint="fpA", doi="10.1000/X", stable_id="ST-A", title="Work A")
    d = svc.prepare(c)
    svc.proceed(c, d)
    return d


def _seed_work_b(svc, reg):
    """Work B: DOI Y / stable ST-B."""
    c = _cand(ref_id="REF-B", source_fingerprint="fpB", doi="10.1000/Y", stable_id="ST-B", title="Work B")
    d = svc.prepare(c)
    svc.proceed(c, d)
    return d


# ---- R1-01 DOI/stable precedence conflict ----

def test_doi_work_a_stable_work_b_conflict():
    """DOI->Work A, stable->Work B, candidate has both -> IDENTITY_CONFLICT."""
    svc, reg = _svc()
    da = _seed_work_a(svc, reg)
    db = _seed_work_b(svc, reg)

    c = _cand(
        ref_id="REF-C",
        source_fingerprint="fpC",
        doi="10.1000/X",  # -> Work A
        stable_id="ST-B",  # -> Work B
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT
    assert da.work_id in d.ambiguity_candidates
    assert db.work_id in d.ambiguity_candidates
    # Must NOT return Work A merely from DOI precedence
    assert d.work_id != da.work_id


# ---- R1-02 stable_id multi-work ----

def test_stable_id_multi_work_conflict():
    """stable_id S mapped to Work A and Work B -> any hit on S is IDENTITY_CONFLICT."""
    reg = InMemorySourceVersionRegistry()
    reg.append_work(WorkRecord(work_id="W-A", created_evidence="a"))
    reg.append_work(WorkRecord(work_id="W-B", created_evidence="b"))
    # Directly inject conflicting index state via two appends with same stable but different work
    # This should be REJECTED by the registry invariant.
    rec_a = SourceVersionRecord(
        source_version_id="SV-A", work_id="W-A", ref_id="R-A", source_fingerprint="f1",
        stable_id="S", normalized_title="t-a",
    )
    reg.append_source_version(rec_a)
    rec_b = SourceVersionRecord(
        source_version_id="SV-B", work_id="W-B", ref_id="R-B", source_fingerprint="f2",
        stable_id="S", normalized_title="t-b",
    )
    with pytest.raises(ValueError, match="stable_id"):
        reg.append_source_version(rec_b)


# ---- R1-03 prior-only explicit lineage ----

def test_prior_only_valid_lineage():
    svc, reg = _svc()
    da = _seed_work_a(svc, reg)
    prior = reg.list_versions(da.work_id)[0]

    c = _cand(
        ref_id="REF-NEW",
        source_fingerprint="fp-new",
        doi="10.1000/NEW",
        stable_id="ST-NEW",
        title="New Version",
        explicit_work_id=None,
        explicit_prior_version_id=prior.source_version_id,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.SAME_WORK_NEW_VERSION
    assert d.work_id == da.work_id
    assert "explicit_lineage" in d.match_evidence


def test_prior_only_invalid_lineage():
    svc, reg = _svc()
    c = _cand(explicit_work_id=None, explicit_prior_version_id="no-such-prior")
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_prior_only_doi_conflict():
    svc, reg = _svc()
    da = _seed_work_a(svc, reg)
    db = _seed_work_b(svc, reg)
    prior = reg.list_versions(db.work_id)[0]  # prior in Work B

    # Candidate with DOI of Work A but prior from Work B
    c = _cand(
        ref_id="REF-C",
        source_fingerprint="fpC",
        doi="10.1000/X",  # -> Work A
        stable_id="ST-C",
        explicit_prior_version_id=prior.source_version_id,  # -> Work B
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


# ---- R1-04 PREPRINT_TO_JOURNAL compatibility ----

def _seed_preprint(svc, reg):
    c = _cand(
        ref_id="ARXIV-1",
        source_fingerprint="fp-pre",
        doi="10.48550/arxiv.1",
        stable_id="ARXIV:1",
        title="Preprint",
        source_kind=SourceKind.PREPRINT,
    )
    d = svc.prepare(c)
    svc.proceed(c, d)
    return d


def test_p2j_without_prior_conflict():
    svc, reg = _svc()
    da = _seed_work_a(svc, reg)
    c = _cand(
        ref_id="J-1",
        source_fingerprint="fp-j",
        doi="10.1000/J",
        stable_id="ST-J",
        title="Journal",
        source_kind=SourceKind.JOURNAL,
        explicit_work_id=da.work_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT
    assert d.upgrade_intent is None


def test_p2j_prior_is_journal_conflict():
    svc, reg = _svc()
    da = _seed_work_a(svc, reg)  # JOURNAL kind
    prior = reg.list_versions(da.work_id)[0]
    c = _cand(
        ref_id="J-1",
        source_fingerprint="fp-j",
        doi="10.1000/J",
        stable_id="ST-J",
        title="Journal",
        source_kind=SourceKind.JOURNAL,
        explicit_work_id=da.work_id,
        explicit_prior_version_id=prior.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT
    assert d.upgrade_intent is None


def test_p2j_candidate_is_preprint_conflict():
    svc, reg = _svc()
    dp = _seed_preprint(svc, reg)
    prior = reg.list_versions(dp.work_id)[0]
    c = _cand(
        ref_id="ARXIV-2",
        source_fingerprint="fp-pre2",
        doi="10.48550/arxiv.2",
        stable_id="ARXIV:2",
        title="Another Preprint",
        source_kind=SourceKind.PREPRINT,
        explicit_work_id=dp.work_id,
        explicit_prior_version_id=prior.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT
    assert d.upgrade_intent is None


def test_valid_p2j_remains_pass():
    svc, reg = _svc()
    dp = _seed_preprint(svc, reg)
    prior = reg.list_versions(dp.work_id)[0]
    c = _cand(
        ref_id="J-1",
        source_fingerprint="fp-j",
        doi="10.1000/J",
        stable_id="ST-J",
        title="Journal Version",
        source_kind=SourceKind.JOURNAL,
        explicit_work_id=dp.work_id,
        explicit_prior_version_id=prior.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.SAME_WORK_NEW_VERSION
    assert d.work_id == dp.work_id
    assert d.upgrade_intent is not None
    assert d.upgrade_intent.requires_delta_extraction is True
    svc.proceed(c, d)
    versions = reg.list_versions(dp.work_id)
    assert len(versions) == 2


# ---- R1-05 registry uniqueness ----

def test_duplicate_ref_fingerprint_across_work_reject():
    reg = InMemorySourceVersionRegistry()
    reg.append_work(WorkRecord(work_id="W-A", created_evidence="a"))
    reg.append_work(WorkRecord(work_id="W-B", created_evidence="b"))
    reg.append_source_version(
        SourceVersionRecord(
            source_version_id="SV-1", work_id="W-A", ref_id="R-1", source_fingerprint="fp1",
        )
    )
    with pytest.raises(ValueError, match="ref_id, fingerprint|different source version"):
        reg.append_source_version(
            SourceVersionRecord(
                source_version_id="SV-2", work_id="W-B", ref_id="R-1", source_fingerprint="fp1",
            )
        )


def test_doi_reused_across_work_reject():
    reg = InMemorySourceVersionRegistry()
    reg.append_work(WorkRecord(work_id="W-A", created_evidence="a"))
    reg.append_work(WorkRecord(work_id="W-B", created_evidence="b"))
    reg.append_source_version(
        SourceVersionRecord(
            source_version_id="SV-1", work_id="W-A", ref_id="R-1", source_fingerprint="f1",
            normalized_doi="10.1000/xyz",
        )
    )
    with pytest.raises(ValueError, match="DOI"):
        reg.append_source_version(
            SourceVersionRecord(
                source_version_id="SV-2", work_id="W-B", ref_id="R-2", source_fingerprint="f2",
                normalized_doi="10.1000/xyz",
            )
        )


def test_same_doi_same_work_allowed():
    reg = InMemorySourceVersionRegistry()
    reg.append_work(WorkRecord(work_id="W-A", created_evidence="a"))
    reg.append_source_version(
        SourceVersionRecord(
            source_version_id="SV-1", work_id="W-A", ref_id="R-1", source_fingerprint="f1",
            normalized_doi="10.1000/xyz",
        )
    )
    reg.append_source_version(
        SourceVersionRecord(
            source_version_id="SV-2", work_id="W-A", ref_id="R-2", source_fingerprint="f2",
            normalized_doi="10.1000/xyz",
        )
    )
    assert len(reg.list_versions("W-A")) == 2


def test_failed_append_leaves_registry_unchanged():
    reg = InMemorySourceVersionRegistry()
    reg.append_work(WorkRecord(work_id="W-A", created_evidence="a"))
    reg.append_source_version(
        SourceVersionRecord(
            source_version_id="SV-1", work_id="W-A", ref_id="R-1", source_fingerprint="f1",
            normalized_doi="10.1000/xyz", stable_id="S1",
        )
    )
    n_versions = len(reg.list_versions("W-A"))
    # Conflicting DOI append must fail atomically
    with pytest.raises(ValueError, match="DOI"):
        reg.append_source_version(
            SourceVersionRecord(
                source_version_id="SV-2", work_id="W-B", ref_id="R-2", source_fingerprint="f2",
                normalized_doi="10.1000/xyz",
            )
        )
    # Registry unchanged
    assert len(reg.list_versions("W-A")) == n_versions
    assert reg.get_source_version("SV-2") is None
    # DOI index still only has SV-1
    assert len(reg.lookup_by_doi("10.1000/xyz")) == 1
