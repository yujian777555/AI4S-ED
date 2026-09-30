"""Phase 5.1-R2 tests: replay lineage, relation state machine, registry integrity."""

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
        title="A Study",
        doi="10.1000/xyz",
        stable_id="ST-1",
        source_kind=SourceKind.JOURNAL,
    )
    defaults.update(kw)
    return SourceCandidate(**defaults)


def _seed(svc, reg, ref="REF-A", fp="fpA", doi="10.1000/X", stable="ST-A"):
    c = _cand(ref_id=ref, source_fingerprint=fp, doi=doi, stable_id=stable, title=f"Work {ref}")
    d = svc.prepare(c)
    svc.proceed(c, d)
    return d


# ---- R2-A replay explicit-lineage consistency ----

def test_replay_contradictory_work_conflict():
    svc, reg = _svc()
    da = _seed(svc, reg, ref="REF-A", fp="fpA", doi="10.1000/X", stable="ST-A")
    db = _seed(svc, reg, ref="REF-B", fp="fpB", doi="10.1000/Y", stable="ST-B")

    # Same ref+fingerprint as Work A, but explicit_work_id=Work B
    c = _cand(
        ref_id="REF-A",
        source_fingerprint="fpA",
        doi="10.1000/X",
        stable_id="ST-A",
        explicit_work_id=db.work_id,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT
    assert "explicit_work_id" in d.diagnostics.get("conflict_reason", "")


def test_replay_cross_work_prior_conflict():
    svc, reg = _svc()
    da = _seed(svc, reg, ref="REF-A", fp="fpA", doi="10.1000/X", stable="ST-A")
    db = _seed(svc, reg, ref="REF-B", fp="fpB", doi="10.1000/Y", stable="ST-B")
    prior_b = reg.list_versions(db.work_id)[0]

    c = _cand(
        ref_id="REF-A",
        source_fingerprint="fpA",
        doi="10.1000/X",
        stable_id="ST-A",
        explicit_prior_version_id=prior_b.source_version_id,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_replay_compatible_lineage_still_replay():
    svc, reg = _svc()
    da = _seed(svc, reg, ref="REF-A", fp="fpA", doi="10.1000/X", stable="ST-A")
    prior = reg.list_versions(da.work_id)[0]

    c = _cand(
        ref_id="REF-A",
        source_fingerprint="fpA",
        doi="10.1000/X",
        stable_id="ST-A",
        explicit_work_id=da.work_id,
        explicit_prior_version_id=prior.source_version_id,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.EXACT_REPLAY


# ---- R2-B relation-only validation ----

def test_relation_only_p2j_conflict():
    svc, reg = _svc()
    c = _cand(
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
        explicit_work_id=None,
        explicit_prior_version_id=None,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT
    assert d.upgrade_intent is None


def test_relation_only_revision_of_conflict():
    svc, reg = _svc()
    c = _cand(explicit_relation=VersionRelation.REVISION_OF)
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_relation_only_corrected_version_conflict():
    svc, reg = _svc()
    c = _cand(explicit_relation=VersionRelation.CORRECTED_VERSION)
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


# ---- R2-B explicit NONE fail-closed ----

def test_explicit_none_with_prior_conflict():
    svc, reg = _svc()
    da = _seed(svc, reg)
    prior = reg.list_versions(da.work_id)[0]
    c = _cand(
        ref_id="REF-NEW",
        source_fingerprint="fp-new",
        doi="10.1000/NEW",
        stable_id="ST-NEW",
        explicit_relation=VersionRelation.NONE,
        explicit_prior_version_id=prior.source_version_id,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


def test_explicit_none_with_work_conflict():
    svc, reg = _svc()
    da = _seed(svc, reg)
    c = _cand(
        ref_id="REF-NEW",
        source_fingerprint="fp-new",
        doi="10.1000/NEW",
        stable_id="ST-NEW",
        explicit_relation=VersionRelation.NONE,
        explicit_work_id=da.work_id,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.IDENTITY_CONFLICT


# ---- omitted relation defaults ----

def test_omitted_relation_with_prior_defaults_revision_of():
    svc, reg = _svc()
    da = _seed(svc, reg)
    prior = reg.list_versions(da.work_id)[0]
    c = _cand(
        ref_id="REF-NEW",
        source_fingerprint="fp-new",
        doi="10.1000/NEW",
        stable_id="ST-NEW",
        explicit_relation=None,  # omitted
        explicit_prior_version_id=prior.source_version_id,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.SAME_WORK_NEW_VERSION
    assert d.diagnostics.get("explicit_relation") == "revision_of"
    rec = svc.proceed(c, d)
    assert rec.relation == VersionRelation.REVISION_OF


def test_omitted_relation_with_work_defaults_explicit_same_work():
    svc, reg = _svc()
    da = _seed(svc, reg)
    c = _cand(
        ref_id="REF-NEW",
        source_fingerprint="fp-new",
        doi="10.1000/NEW",
        stable_id="ST-NEW",
        explicit_relation=None,  # omitted
        explicit_work_id=da.work_id,
    )
    d = svc.prepare(c)
    assert d.disposition == IntakeDisposition.SAME_WORK_NEW_VERSION
    assert d.diagnostics.get("explicit_relation") == "explicit_same_work"


# ---- R2-C registry work/prior integrity ----

def test_append_unknown_work_reject():
    reg = InMemorySourceVersionRegistry()
    with pytest.raises(ValueError, match="work_id"):
        reg.append_source_version(
            SourceVersionRecord(
                source_version_id="SV-1",
                work_id="W-UNKNOWN",
                ref_id="R-1",
                source_fingerprint="f1",
            )
        )


def test_append_missing_prior_reject():
    reg = InMemorySourceVersionRegistry()
    reg.append_work(WorkRecord(work_id="W-A", created_evidence="a"))
    with pytest.raises(ValueError, match="prior"):
        reg.append_source_version(
            SourceVersionRecord(
                source_version_id="SV-1",
                work_id="W-A",
                ref_id="R-1",
                source_fingerprint="f1",
                prior_source_version_id="NO-SUCH",
            )
        )


def test_append_cross_work_prior_reject():
    reg = InMemorySourceVersionRegistry()
    reg.append_work(WorkRecord(work_id="W-A", created_evidence="a"))
    reg.append_work(WorkRecord(work_id="W-B", created_evidence="b"))
    reg.append_source_version(
        SourceVersionRecord(
            source_version_id="SV-A", work_id="W-A", ref_id="R-A", source_fingerprint="fA"
        )
    )
    with pytest.raises(ValueError, match="cross-work prior"):
        reg.append_source_version(
            SourceVersionRecord(
                source_version_id="SV-B",
                work_id="W-B",
                ref_id="R-B",
                source_fingerprint="fB",
                prior_source_version_id="SV-A",  # prior in W-A, record in W-B
            )
        )


def test_failed_orphan_append_leaves_registry_unchanged():
    reg = InMemorySourceVersionRegistry()
    reg.append_work(WorkRecord(work_id="W-A", created_evidence="a"))
    reg.append_source_version(
        SourceVersionRecord(
            source_version_id="SV-1", work_id="W-A", ref_id="R-1", source_fingerprint="f1"
        )
    )
    n_before = len(reg.list_versions("W-A"))
    with pytest.raises(ValueError, match="work_id"):
        reg.append_source_version(
            SourceVersionRecord(
                source_version_id="SV-ORPHAN",
                work_id="W-UNKNOWN",
                ref_id="R-2",
                source_fingerprint="f2",
            )
        )
    assert len(reg.list_versions("W-A")) == n_before
    assert reg.get_source_version("SV-ORPHAN") is None
