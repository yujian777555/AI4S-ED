"""Phase 5.1 tests: source identity, registry, preprint lineage, bind semantics."""

from __future__ import annotations

import pytest

from knowledge_curator.adapters.in_memory_source_versions import (
    InMemorySourceVersionRegistry,
)
from knowledge_curator.core.source_identity import (
    IncrementalIntakeService,
    normalize_doi,
    normalize_stable_id,
    normalize_title,
)
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


# ---- normalization ----

def test_doi_normalization_safe_variants():
    assert normalize_doi("doi:10.1000/XYZ") == "10.1000/xyz"
    assert normalize_doi("https://doi.org/10.1000/xyz") == "10.1000/xyz"
    assert normalize_doi("http://doi.org/10.1000/xyz") == "10.1000/xyz"
    assert normalize_doi("http://dx.doi.org/10.1000/xyz") == "10.1000/xyz"
    assert normalize_doi("  10.1000/xyz  ") == "10.1000/xyz"
    assert normalize_doi(None) is None
    assert normalize_doi("   ") is None


def test_title_normalization_nfkc_whitespace_case():
    assert normalize_title("  A   Study  of Membranes ") == "a study of membranes"
    # NFKC fullwidth
    assert normalize_title("Ａ Ｓｔｕｄｙ") == "a study"
    # Punctuation preserved
    assert normalize_title("Study: Membranes & Energy") == "study: membranes & energy"


def test_punctuation_distinct_titles_stay_distinct():
    a = normalize_title("Study of membranes")
    b = normalize_title("Study of membranes!")
    assert a != b


def test_stable_id_trim_only():
    assert normalize_stable_id("  ST-1  ") == "ST-1"
    assert normalize_stable_id(None) is None


# ---- exact replay ----

def test_exact_replay():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    assert d1.disposition == IntakeDisposition.NEW_WORK
    svc.proceed(c1, d1)

    d2 = svc.prepare(_cand())
    assert d2.disposition == IntakeDisposition.EXACT_REPLAY
    assert d2.existing_source_version_id == d1.prepared_source_version_id
    assert "exact_ref_fingerprint" in d2.match_evidence
    assert d2.proceed_to_commit is False


def test_replay_contradictory_metadata_conflict():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    svc.proceed(c1, d1)

    # Same ref+fingerprint but different DOI
    c2 = _cand(doi="10.1000/OTHER")
    d2 = svc.prepare(c2)
    assert d2.disposition == IntakeDisposition.IDENTITY_CONFLICT
    assert "exact_ref_fingerprint" in d2.match_evidence


# ---- same-work new version ----

def test_same_doi_new_fingerprint():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    svc.proceed(c1, d1)

    c2 = _cand(ref_id="REF-2", source_fingerprint="fp2")
    d2 = svc.prepare(c2)
    assert d2.disposition == IntakeDisposition.SAME_WORK_NEW_VERSION
    assert d2.work_id == d1.work_id
    assert "exact_doi" in d2.match_evidence
    assert d2.proceed_to_commit is True
    svc.proceed(c2, d2)
    versions = reg.list_versions(d1.work_id)
    assert len(versions) == 2


def test_same_stable_id_new_fingerprint():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    svc.proceed(c1, d1)

    c2 = _cand(ref_id="REF-2", source_fingerprint="fp2", doi=None)
    d2 = svc.prepare(c2)
    assert d2.disposition == IntakeDisposition.SAME_WORK_NEW_VERSION
    assert "exact_stable_id" in d2.match_evidence


# ---- title-only review gate ----

def test_title_only_review_required():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    svc.proceed(c1, d1)

    c2 = _cand(ref_id="REF-2", source_fingerprint="fp2", doi=None, stable_id=None)
    d2 = svc.prepare(c2)
    assert d2.disposition == IntakeDisposition.REVIEW_REQUIRED
    assert d2.work_id is None
    assert d2.proceed_to_commit is False
    assert "exact_title_review_only" in d2.match_evidence
    assert d1.work_id in d2.ambiguity_candidates


def test_no_match_new_work():
    svc, reg = _svc()
    d = svc.prepare(_cand(ref_id="REF-9", title="Completely Different", doi=None, stable_id=None))
    assert d.disposition == IntakeDisposition.NEW_WORK
    assert d.proceed_to_commit is True


# ---- identity conflict ----

def test_doi_vs_explicit_work_conflict():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    svc.proceed(c1, d1)

    # Create a second work
    c2 = _cand(ref_id="REF-9", source_fingerprint="fp9", doi="10.2000/other", stable_id="ST-9", title="Other")
    d2 = svc.prepare(c2)
    svc.proceed(c2, d2)

    # Candidate with DOI -> Work1 but explicit_work_id -> Work2
    c3 = _cand(
        ref_id="REF-3",
        source_fingerprint="fp3",
        explicit_work_id=d2.work_id,
        explicit_relation=VersionRelation.EXPLICIT_SAME_WORK,
    )
    d3 = svc.prepare(c3)
    assert d3.disposition == IntakeDisposition.IDENTITY_CONFLICT
    assert "explicit_lineage" in d3.match_evidence


def test_invalid_explicit_work_rejected():
    svc, reg = _svc()
    c = _cand(explicit_work_id="no-such-work")
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_invalid_explicit_prior_rejected():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    svc.proceed(c1, d1)
    c = _cand(
        ref_id="REF-2",
        source_fingerprint="fp2",
        explicit_work_id=d1.work_id,
        explicit_prior_version_id="no-such-version",
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_explicit_prior_wrong_work_rejected():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    svc.proceed(c1, d1)
    c2 = _cand(ref_id="REF-9", source_fingerprint="fp9", doi="10.2000/x", stable_id="ST-9", title="Other")
    d2 = svc.prepare(c2)
    svc.proceed(c2, d2)

    # prior from Work1 but explicit_work_id = Work2
    prior = reg.list_versions(d1.work_id)[0]
    c3 = _cand(
        ref_id="REF-3",
        source_fingerprint="fp3",
        explicit_work_id=d2.work_id,
        explicit_prior_version_id=prior.source_version_id,
    )
    d3 = svc.prepare(c3)
    assert d3.disposition == IntakeDisposition.IDENTITY_CONFLICT


# ---- explicit preprint -> journal ----

def test_explicit_preprint_to_journal_lineage():
    svc, reg = _svc()
    p1 = _cand(
        ref_id="ARXIV-1",
        source_fingerprint="fp-pre",
        doi="10.48550/arxiv.1234",
        stable_id="ARXIV:1234",
        title="Preprint Study",
        source_kind=SourceKind.PREPRINT,
    )
    d1 = svc.prepare(p1)
    svc.proceed(p1, d1)

    j1 = _cand(
        ref_id="JOURNAL-1",
        source_fingerprint="fp-j",
        doi="10.1000/journal.5678",
        stable_id="JOURNAL:5678",
        title="Journal Study",
        source_kind=SourceKind.JOURNAL,
        explicit_work_id=d1.work_id,
        explicit_prior_version_id=d1.prepared_source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    d2 = svc.prepare(j1)
    assert d2.disposition == IntakeDisposition.SAME_WORK_NEW_VERSION
    assert d2.work_id == d1.work_id
    assert d2.upgrade_intent is not None
    assert d2.upgrade_intent.relation == VersionRelation.PREPRINT_TO_JOURNAL
    assert d2.upgrade_intent.requires_delta_extraction is True
    assert d2.upgrade_intent.lifecycle_reason == "preprint_to_journal"
    svc.proceed(j1, d2)

    versions = reg.list_versions(d1.work_id)
    assert len(versions) == 2
    # P1 not deleted
    assert reg.get_source_version(d1.prepared_source_version_id) is not None


def test_no_fuzzy_preprint_merge_without_explicit_relation():
    svc, reg = _svc()
    p1 = _cand(
        ref_id="ARXIV-1",
        source_fingerprint="fp-pre",
        doi="10.48550/arxiv.1234",
        stable_id="ARXIV:1234",
        title="Membrane Energy Study",
        source_kind=SourceKind.PREPRINT,
    )
    d1 = svc.prepare(p1)
    svc.proceed(p1, d1)

    # Similar title, different DOI, no explicit relation -> NOT auto-merged.
    # Title-only hit is REVIEW_REQUIRED (gate), not NEW_WORK merge.
    j1 = _cand(
        ref_id="JOURNAL-1",
        source_fingerprint="fp-j",
        doi="10.1000/journal.5678",
        stable_id="JOURNAL:5678",
        title="Membrane Energy Study",
        source_kind=SourceKind.JOURNAL,
    )
    d2 = svc.prepare(j1)
    assert d2.disposition == IntakeDisposition.REVIEW_REQUIRED
    assert d2.work_id is None  # no auto-merge
    assert d1.work_id in d2.ambiguity_candidates


# ---- bind after publish ----

def test_bind_only_after_published():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    rec = svc.proceed(c1, d1)

    with pytest.raises(ValueError, match="commit_status"):
        svc.finalize_bind(
            rec.source_version_id,
            kb_version_id="kbv-1",
            snapshot_id="snap-1",
            commit_status="failed",
        )
    with pytest.raises(ValueError, match="commit_status"):
        svc.finalize_bind(
            rec.source_version_id,
            kb_version_id="kbv-1",
            snapshot_id="snap-1",
            commit_status="pending_vector",
        )
    with pytest.raises(ValueError, match="commit_status"):
        svc.finalize_bind(
            rec.source_version_id,
            kb_version_id="kbv-1",
            snapshot_id="snap-1",
            commit_status="pending_finalize",
        )
    with pytest.raises(ValueError, match="commit_status"):
        svc.finalize_bind(
            rec.source_version_id,
            kb_version_id="kbv-1",
            snapshot_id="snap-1",
            commit_status="not_publishable",
        )

    bound = svc.finalize_bind(
        rec.source_version_id,
        kb_version_id="kbv-1",
        snapshot_id="snap-1",
        commit_status="published",
    )
    assert bound.kb_version_id == "kbv-1"


def test_bind_retry_idempotent():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    rec = svc.proceed(c1, d1)
    b1 = svc.finalize_bind(rec.source_version_id, kb_version_id="kbv-1", snapshot_id="snap-1", commit_status="published")
    b2 = svc.finalize_bind(rec.source_version_id, kb_version_id="kbv-1", snapshot_id="snap-1", commit_status="idempotent_hit")
    assert b2.kb_version_id == "kbv-1"


def test_conflicting_rebind_rejected():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    rec = svc.proceed(c1, d1)
    svc.finalize_bind(rec.source_version_id, kb_version_id="kbv-1", snapshot_id="snap-1", commit_status="published")
    with pytest.raises(ValueError, match="already bound|conflicting"):
        svc.finalize_bind(rec.source_version_id, kb_version_id="kbv-2", snapshot_id="snap-2", commit_status="published")


# ---- append-only / material idempotency ----

def test_list_versions_append_only():
    svc, reg = _svc()
    c1 = _cand()
    d1 = svc.prepare(c1)
    rec1 = svc.proceed(c1, d1)
    c2 = _cand(ref_id="REF-2", source_fingerprint="fp2", doi="10.2000/z", stable_id="ST-2", title="Second")
    d2 = svc.prepare(c2)
    svc.proceed(c2, d2)
    # Second version in same work via same DOI? No — this is a new work.
    # Use explicit lineage to add to same work
    c3 = _cand(
        ref_id="REF-3",
        source_fingerprint="fp3",
        doi="10.3000/w",
        stable_id="ST-3",
        title="Third",
        explicit_work_id=d1.work_id,
        explicit_prior_version_id=rec1.source_version_id,
        explicit_relation=VersionRelation.REVISION_OF,
    )
    d3 = svc.prepare(c3)
    svc.proceed(c3, d3)
    versions = reg.list_versions(d1.work_id)
    assert len(versions) == 2
    assert all(v.work_id == d1.work_id for v in versions)
    # Append-only: order is registration order
    assert [v.source_version_id for v in versions][0] == rec1.source_version_id


def test_source_version_material_idempotent_and_conflict():
    reg = InMemorySourceVersionRegistry()
    rec = SourceVersionRecord(
        source_version_id="SV1",
        work_id="W1",
        ref_id="REF-1",
        source_fingerprint="fp1",
        normalized_doi="10.1000/xyz",
        normalized_title="title",
        stable_id="ST-1",
        source_kind=SourceKind.JOURNAL,
        relation=VersionRelation.NONE,
    )
    reg.append_work(WorkRecord(work_id="W1"))
    reg.append_source_version(rec)
    reg.append_source_version(rec)  # idempotent
    assert len(reg.list_versions("W1")) == 1

    conflicting = SourceVersionRecord(
        source_version_id="SV1",
        work_id="W1",
        ref_id="REF-1",
        source_fingerprint="fp1",
        normalized_doi="10.1000/DIFFERENT",
        normalized_title="title",
        stable_id="ST-1",
        source_kind=SourceKind.JOURNAL,
        relation=VersionRelation.NONE,
    )
    with pytest.raises(ValueError, match="conflicting"):
        reg.append_source_version(conflicting)
