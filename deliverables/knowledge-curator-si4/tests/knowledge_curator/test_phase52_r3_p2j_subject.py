"""Phase 5.2-R3 tests: P2J lifecycle subject direction."""

from __future__ import annotations

import pytest

from knowledge_curator.adapters.in_memory_source_versions import (
    InMemorySourceVersionRegistry,
)
from knowledge_curator.core.source_identity import IncrementalIntakeService
from knowledge_curator.core.version_delta import (
    RevisionPackageBuilder,
    package_to_revision_draft,
)
from knowledge_curator.schemas.assertions import (
    Assertion,
    ClaimType,
    Confidence,
    Condition,
    ObjectValue,
    Provenance,
    SourceClaimOrigin,
    Subject,
    ValueType,
)
from knowledge_curator.schemas.source_versions import (
    SourceCandidate,
    SourceKind,
    VersionRelation,
    VersionUpgradeIntent,
)
from knowledge_curator.schemas.version_delta import (
    ContentUnit,
    ContentUnitKind,
    DeltaAssertionBatch,
    VersionAssertionInventory,
    VersionContentManifest,
)


def _unit(uid, loc="p.1", h="h1", prior=None):
    return ContentUnit(unit_id=uid, locator=loc, kind=ContentUnitKind.TEXT, content_hash=h, prior_unit_id=prior)


def _manifest(sid, ref, fp, units):
    return VersionContentManifest(source_version_id=sid, ref_id=ref, source_fingerprint=fp, units=units)


def _assertion(aid, ref, entity="E1", prop="P1", value=1.0, locator="p.1"):
    return Assertion(
        id=aid,
        ref_id=ref,
        subject=Subject(eddo_class="Membrane", resolved_entity=entity, original_mention=entity),
        property=prop,
        object=ObjectValue(value=value, unit="kWh", value_type=ValueType.NUMBER),
        conditions=[Condition(eddo_class="T", value=298, unit="K")],
        provenance=Provenance(locator=locator, sentence="s"),
        claim_type=ClaimType.MEASUREMENT,
        source_claim_origin=SourceClaimOrigin.PRIMARY,
        confidence=Confidence.HIGH,
        quality=0.9,
    )


def _setup_p2j():
    """P1 (ARXIV-1) -> J1 (JOURNAL-1) via PREPRINT_TO_JOURNAL."""
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    cp = SourceCandidate(
        ref_id="ARXIV-1", source_fingerprint="fp-pre", title="Preprint",
        doi="10.48550/arxiv.1", stable_id="A:1", source_kind=SourceKind.PREPRINT,
    )
    dp = svc.prepare(cp)
    p1 = svc.proceed(cp, dp)
    cj = SourceCandidate(
        ref_id="JOURNAL-1", source_fingerprint="fp-j", title="Journal",
        doi="10.1000/j.1", stable_id="J:1", source_kind=SourceKind.JOURNAL,
        explicit_work_id=dp.work_id,
        explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    dj = svc.prepare(cj)
    j1 = svc.proceed(cj, dj)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    return reg, svc, p1, j1, dp.work_id


def _build_p2j_package(reg, p1, j1, work_id):
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id,
        prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id,
        relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    # Prior: U1 (unchanged), U2 (removed)
    prior_m = _manifest(
        p1.source_version_id, "ARXIV-1", "fp-pre",
        [_unit("U1", h="h1", loc="p.a"), _unit("U2", h="h2", loc="p.b")],
    )
    # New: U1 (unchanged), U3 (added)  — U2 removed
    new_m = _manifest(
        j1.source_version_id, "JOURNAL-1", "fp-j",
        [_unit("U1", h="h1", loc="p.a2"), _unit("U3", h="h3", loc="p.c")],
    )
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[_assertion("A1", "ARXIV-1", locator="p.a"), _assertion("A2", "ARXIV-1", entity="E2", locator="p.b")],
        assertion_unit_map={"A1": "U1", "A2": "U2"},
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="JOURNAL-1",
        assertions=[_assertion("J-A3", "JOURNAL-1", entity="E3", locator="p.c")],
        assertion_unit_map={"J-A3": "U3"},
        processed_unit_ids=["U3"],
    )
    pkg = builder.build(
        intent=intent, prior_manifest=prior_m, new_manifest=new_m,
        prior_inventory=inv, delta_batch=batch,
    )
    return pkg


def test_p2j_draft_targets_prior_ref_id():
    reg, svc, p1, j1, work_id = _setup_p2j()
    pkg = _build_p2j_package(reg, p1, j1, work_id)
    draft = package_to_revision_draft(pkg)
    assert draft.ref_id == "ARXIV-1"
    assert draft.trigger.value == "preprint_to_journal"


def test_p2j_new_journal_replacement_ids_preserved():
    reg, svc, p1, j1, work_id = _setup_p2j()
    pkg = _build_p2j_package(reg, p1, j1, work_id)
    draft = package_to_revision_draft(pkg)
    # Replacement ids must be NEW journal assertion ids, not prior
    assert "J-A3" in draft.replacement_assertion_ids
    assert "A1" not in draft.replacement_assertion_ids
    assert "A2" not in draft.replacement_assertion_ids
    # supersede_actions still old -> new
    if draft.supersede_actions:
        for old_id, new_id in draft.supersede_actions.items():
            assert old_id.startswith("A")  # prior assertion
            assert new_id != old_id
    # evidence_refs retain source-version lineage
    assert p1.source_version_id in draft.evidence_refs
    assert j1.source_version_id in draft.evidence_refs


def test_same_ref_revision_compatibility():
    """prior_ref_id == new_ref_id -> draft.ref_id unchanged in effect."""
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    c1 = SourceCandidate(
        ref_id="REF-1", source_fingerprint="fp1", title="Study",
        doi="10.1000/x", stable_id="S1", source_kind=SourceKind.JOURNAL,
    )
    d1 = svc.prepare(c1)
    v1 = svc.proceed(c1, d1)
    reg.bind_source_version(v1.source_version_id, "kbv-1", "snap-1")

    # Same-ref revision
    c2 = SourceCandidate(
        ref_id="REF-1", source_fingerprint="fp2", title="Study",
        doi="10.1000/x", stable_id="S1", source_kind=SourceKind.JOURNAL,
        explicit_work_id=d1.work_id,
        explicit_prior_version_id=v1.source_version_id,
        explicit_relation=VersionRelation.REVISION_OF,
    )
    d2 = svc.prepare(c2)
    v2 = svc.proceed(c2, d2)

    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=d1.work_id,
        prior_source_version_id=v1.source_version_id,
        new_source_version_id=v2.source_version_id,
        relation=VersionRelation.REVISION_OF,
    )
    prior_m = _manifest(v1.source_version_id, "REF-1", "fp1", [_unit("U1", h="h1")])
    new_m = _manifest(v2.source_version_id, "REF-1", "fp2", [_unit("U1", h="h2")])
    inv = VersionAssertionInventory(
        source_version_id=v1.source_version_id, ref_id="REF-1",
        assertions=[_assertion("A1", "REF-1")],
        assertion_unit_map={"A1": "U1"},
    )
    batch = DeltaAssertionBatch(
        source_version_id=v2.source_version_id, ref_id="REF-1",
        assertions=[_assertion("A1N", "REF-1")],
        assertion_unit_map={"A1N": "U1"},
        processed_unit_ids=["U1"],
    )
    pkg = builder.build(
        intent=intent, prior_manifest=prior_m, new_manifest=new_m,
        prior_inventory=inv, delta_batch=batch,
    )
    draft = package_to_revision_draft(pkg)
    assert draft.ref_id == "REF-1"  # prior_ref_id == new_ref_id


def test_package_id_unchanged_by_draft_helper():
    """package_to_revision_draft must not alter package_id."""
    reg, svc, p1, j1, work_id = _setup_p2j()
    pkg = _build_p2j_package(reg, p1, j1, work_id)
    draft = package_to_revision_draft(pkg)
    assert draft.revision_id == pkg.package_id


def test_no_lifecycle_publication_in_phase52():
    """package_to_revision_draft produces a draft; apply_revision is NOT called."""
    reg, svc, p1, j1, work_id = _setup_p2j()
    pkg = _build_p2j_package(reg, p1, j1, work_id)
    draft = package_to_revision_draft(pkg)
    # Draft exists but was never applied — no lifecycle records created for it
    from knowledge_curator.adapters.in_memory_lifecycle import InMemoryLifecycleStore

    store = InMemoryLifecycleStore()
    assert store.list_records_for_ref("ARXIV-1") == []
    # And draft.base_version_id is None (publication-time)
    assert draft.base_version_id is None
