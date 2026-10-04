"""Phase 5.1-R3 tests: exact replay material consistency."""

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
    VersionRelation,
)


def _svc():
    reg = InMemorySourceVersionRegistry()
    return IncrementalIntakeService(reg), reg


def _cand(**kw):
    defaults = dict(
        ref_id="REF-1",
        source_fingerprint="fp1",
        title="A Study",
        doi="10.1000/xyz",
        stable_id="ST-1",
        source_kind=SourceKind.JOURNAL,
    )
    defaults.update(kw)
    return SourceCandidate(**defaults)


def _seed_root(svc, reg, ref="REF-A", fp="fpA", doi="10.1000/X", stable="ST-A", kind=SourceKind.JOURNAL, title="Work A"):
    c = _cand(ref_id=ref, source_fingerprint=fp, doi=doi, stable_id=stable, title=title, source_kind=kind)
    d = svc.prepare(c)
    rec = svc.proceed(c, d)
    return d, rec


# ---- R3-01 prior equality ----

def test_root_replay_self_prior_conflict():
    svc, reg = _svc()
    da, rec = _seed_root(svc, reg)
    # Root version with prior=itself -> must conflict
    c = _cand(
        ref_id="REF-A", source_fingerprint="fpA", doi="10.1000/X", stable_id="ST-A",
        explicit_prior_version_id=rec.source_version_id,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_existing_prior_p1_incoming_p2_same_work_conflict():
    svc, reg = _svc()
    # Build P1 (root) then V2 (prior=P1)
    _, p1 = _seed_root(svc, reg, ref="REF-P", fp="fpP", doi="10.1000/P", stable="ST-P", title="P")
    c2 = _cand(
        ref_id="REF-V2", source_fingerprint="fpV2", doi="10.1000/V2", stable_id="ST-V2",
        title="V2", explicit_prior_version_id=p1.source_version_id,
    )
    d2 = svc.prepare(c2)
    rec2 = svc.proceed(c2, d2)

    # Build P2 in same work (a sibling with prior omitted -> root-like)
    c3 = _cand(
        ref_id="REF-P2", source_fingerprint="fpP2", doi="10.1000/P2", stable_id="ST-P2",
        title="P2", explicit_work_id=d2.work_id,
    )
    d3 = svc.prepare(c3)
    p2 = svc.proceed(c3, d3)

    # Replay V2 with prior=P2 (same work, different prior) -> conflict
    c = _cand(
        ref_id="REF-V2", source_fingerprint="fpV2", doi="10.1000/V2", stable_id="ST-V2",
        title="V2", explicit_prior_version_id=p2.source_version_id,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_existing_prior_p1_incoming_p1_replay():
    svc, reg = _svc()
    _, p1 = _seed_root(svc, reg, ref="REF-P", fp="fpP", doi="10.1000/P", stable="ST-P", title="P")
    c2 = _cand(
        ref_id="REF-V2", source_fingerprint="fpV2", doi="10.1000/V2", stable_id="ST-V2",
        title="V2", explicit_prior_version_id=p1.source_version_id,
    )
    d2 = svc.prepare(c2)
    svc.proceed(c2, d2)

    # Replay V2 with same prior P1 -> replay
    c = _cand(
        ref_id="REF-V2", source_fingerprint="fpV2", doi="10.1000/V2", stable_id="ST-V2",
        title="V2", explicit_prior_version_id=p1.source_version_id,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.EXACT_REPLAY


def test_existing_prior_p1_omitted_prior_replay():
    svc, reg = _svc()
    _, p1 = _seed_root(svc, reg, ref="REF-P", fp="fpP", doi="10.1000/P", stable="ST-P", title="P")
    c2 = _cand(
        ref_id="REF-V2", source_fingerprint="fpV2", doi="10.1000/V2", stable_id="ST-V2",
        title="V2", explicit_prior_version_id=p1.source_version_id,
    )
    d2 = svc.prepare(c2)
    svc.proceed(c2, d2)

    # Replay with prior omitted -> compatible
    c = _cand(
        ref_id="REF-V2", source_fingerprint="fpV2", doi="10.1000/V2", stable_id="ST-V2",
        title="V2",
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.EXACT_REPLAY


# ---- R3-02 relation equality ----

def test_existing_revision_of_explicit_revision_of_replay():
    svc, reg = _svc()
    _, p1 = _seed_root(svc, reg, ref="REF-P", fp="fpP", doi="10.1000/P", stable="ST-P", title="P")
    c2 = _cand(
        ref_id="REF-V2", source_fingerprint="fpV2", doi="10.1000/V2", stable_id="ST-V2",
        title="V2", explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.REVISION_OF,
    )
    d2 = svc.prepare(c2)
    svc.proceed(c2, d2)

    # Replay with same explicit relation -> replay
    c = _cand(
        ref_id="REF-V2", source_fingerprint="fpV2", doi="10.1000/V2", stable_id="ST-V2",
        title="V2", explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.REVISION_OF,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.EXACT_REPLAY


def test_existing_revision_of_incoming_different_relation_conflict():
    svc, reg = _svc()
    _, p1 = _seed_root(svc, reg, ref="REF-P", fp="fpP", doi="10.1000/P", stable="ST-P", title="P")
    c2 = _cand(
        ref_id="REF-V2", source_fingerprint="fpV2", doi="10.1000/V2", stable_id="ST-V2",
        title="V2", explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.REVISION_OF,
    )
    d2 = svc.prepare(c2)
    svc.proceed(c2, d2)

    c = _cand(
        ref_id="REF-V2", source_fingerprint="fpV2", doi="10.1000/V2", stable_id="ST-V2",
        title="V2", explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.CORRECTED_VERSION,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_existing_none_explicit_none_replay():
    svc, reg = _svc()
    _, rec = _seed_root(svc, reg, ref="REF-A", fp="fpA", doi="10.1000/X", stable="ST-A", title="A Study")
    assert rec.relation == VersionRelation.NONE

    c = _cand(
        ref_id="REF-A", source_fingerprint="fpA", doi="10.1000/X", stable_id="ST-A",
        title="A Study",
        explicit_relation=VersionRelation.NONE,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.EXACT_REPLAY


# ---- R3-03 source_kind consistency ----

def test_source_kind_mismatch_conflict():
    svc, reg = _svc()
    _seed_root(svc, reg, ref="REF-A", fp="fpA", doi="10.1000/X", stable="ST-A", kind=SourceKind.PREPRINT, title="A")
    c = _cand(
        ref_id="REF-A", source_fingerprint="fpA", doi="10.1000/X", stable_id="ST-A",
        title="A", source_kind=SourceKind.JOURNAL,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT
    assert "source_kind" in d.diagnostics.get("conflict_reason", "")


# ---- R3-04 normalized title consistency ----

def test_normalized_title_true_change_conflict():
    svc, reg = _svc()
    _seed_root(svc, reg, ref="REF-A", fp="fpA", doi="10.1000/X", stable="ST-A", title="Original Title")
    c = _cand(
        ref_id="REF-A", source_fingerprint="fpA", doi="10.1000/X", stable_id="ST-A",
        title="Completely Different Title",
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_title_formatting_only_difference_replay():
    svc, reg = _svc()
    _seed_root(svc, reg, ref="REF-A", fp="fpA", doi="10.1000/X", stable="ST-A", title="A Study")
    # NFKC / case / whitespace differences normalize to the same value
    c = _cand(
        ref_id="REF-A", source_fingerprint="fpA", doi="10.1000/X", stable_id="ST-A",
        title="  a   STUDY ",
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.EXACT_REPLAY


def test_missing_incoming_title_not_conflict():
    svc, reg = _svc()
    _seed_root(svc, reg, ref="REF-A", fp="fpA", doi="10.1000/X", stable="ST-A", title="A Study")
    c = _cand(
        ref_id="REF-A", source_fingerprint="fpA", doi="10.1000/X", stable_id="ST-A",
        title="",
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.EXACT_REPLAY


# ---- R3 P2J target replay ----

def _seed_p2j(svc, reg):
    """Build P1 (PREPRINT root) then J1 (JOURNAL, prior=P1, P2J)."""
    _, p1 = _seed_root(
        svc, reg, ref="ARXIV-1", fp="fp-pre", doi="10.48550/arxiv.1",
        stable="ARXIV:1", kind=SourceKind.PREPRINT, title="Preprint Study",
    )
    cj = _cand(
        ref_id="JOURNAL-1", source_fingerprint="fp-j", doi="10.1000/j.1",
        stable_id="J:1", title="Journal Study", source_kind=SourceKind.JOURNAL,
        explicit_work_id=p1.work_id if hasattr(p1, "work_id") else None,
        explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    # Fix work_id from the decision
    dj = svc.prepare(cj)
    # Set explicit_work_id correctly
    cj.explicit_work_id = dj.work_id
    dj = svc.prepare(cj)
    recj = svc.proceed(cj, dj)
    return p1, dj, recj


def test_valid_p2j_target_replay():
    svc, reg = _svc()
    p1, dj, recj = _seed_p2j(svc, reg)

    # Replay J1 with full compatible lineage
    c = _cand(
        ref_id="JOURNAL-1", source_fingerprint="fp-j", doi="10.1000/j.1",
        stable_id="J:1", title="Journal Study", source_kind=SourceKind.JOURNAL,
        explicit_work_id=dj.work_id,
        explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.EXACT_REPLAY


def test_p2j_target_wrong_prior_conflict():
    svc, reg = _svc()
    p1, dj, recj = _seed_p2j(svc, reg)

    # Replay J1 with wrong prior (J1 itself)
    c = _cand(
        ref_id="JOURNAL-1", source_fingerprint="fp-j", doi="10.1000/j.1",
        stable_id="J:1", title="Journal Study", source_kind=SourceKind.JOURNAL,
        explicit_prior_version_id=recj.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_p2j_target_wrong_relation_conflict():
    svc, reg = _svc()
    p1, dj, recj = _seed_p2j(svc, reg)

    c = _cand(
        ref_id="JOURNAL-1", source_fingerprint="fp-j", doi="10.1000/j.1",
        stable_id="J:1", title="Journal Study", source_kind=SourceKind.JOURNAL,
        explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.REVISION_OF,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_p2j_target_wrong_kind_conflict():
    svc, reg = _svc()
    p1, dj, recj = _seed_p2j(svc, reg)

    c = _cand(
        ref_id="JOURNAL-1", source_fingerprint="fp-j", doi="10.1000/j.1",
        stable_id="J:1", title="Journal Study", source_kind=SourceKind.PREPRINT,
        explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT
