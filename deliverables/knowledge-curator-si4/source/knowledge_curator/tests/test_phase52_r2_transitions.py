"""Phase 5.2-R2 tests: FULL_REEXTRACT transitions, recursive deepcopy, package material."""

from __future__ import annotations

import copy

import pytest

from knowledge_curator.adapters.in_memory_source_versions import (
    InMemorySourceVersionRegistry,
)
from knowledge_curator.core.source_identity import IncrementalIntakeService
from knowledge_curator.core.version_delta import (
    RevisionPackageBuilder,
    carry_forward_unchanged,
    compute_content_delta,
    package_to_revision_draft,
    semantic_payload_hash,
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
    DeltaMode,
    TransitionAction,
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


def _setup_registry():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    cp = SourceCandidate(
        ref_id="ARXIV-1", source_fingerprint="fp-pre", title="Preprint",
        doi="10.48550/arxiv.1", stable_id="A:1", source_kind=SourceKind.PREPRINT,
    )
    dp = svc.prepare(cp)
    p1 = svc.proceed(cp, dp)
    cj = SourceCandidate(
        ref_id="J-1", source_fingerprint="fp-j", title="Journal",
        doi="10.1000/j.1", stable_id="J:1", source_kind=SourceKind.JOURNAL,
        explicit_work_id=dp.work_id,
        explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    dj = svc.prepare(cj)
    j1 = svc.proceed(cj, dj)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    return reg, svc, p1, j1, dp.work_id


# ---- R2-01 FULL_REEXTRACT transitions ----

def test_full_reextract_archives_all_prior_adds_all_new():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    new_m = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U3", h="h3"), _unit("U4", h="h4")])
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[_assertion("A1", "ARXIV-1"), _assertion("A2", "ARXIV-1", entity="E2")],
        assertion_unit_map={"A1": "U1", "A2": "U2"},
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[_assertion("A1N", "J-1"), _assertion("A3", "J-1", entity="E3")],
        assertion_unit_map={"A1N": "U3", "A3": "U4"},
        processed_unit_ids=["U3", "U4"],
    )
    pkg = builder.build(
        intent=intent, prior_manifest=prior_m, new_manifest=new_m,
        prior_inventory=inv, delta_batch=batch, segmentation_reset=True,
    )
    assert pkg.content_delta.mode == DeltaMode.FULL_REEXTRACT_REQUIRED
    assert set(pkg.archive_actions) == {"A1", "A2"}
    assert set(pkg.added_assertion_ids) == {"A1N", "A3"}
    assert pkg.supersede_actions == {}
    assert pkg.carried_records == []
    assert len(pkg.target_assertions) == 2

    draft = package_to_revision_draft(pkg)
    assert set(draft.archive_actions) == {"A1", "A2"}
    assert set(draft.replacement_assertion_ids) == {"A1N", "A3"}


def test_full_reextract_no_supersede_even_if_slot_matches():
    """Segmentation reset: even same-slot assertions must not auto-supersede."""
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1", h="h1")])
    new_m = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U2", h="h2")])
    # Same semantic slot (same entity/prop/conditions) but different units
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[_assertion("A1", "ARXIV-1", value=1.0)],
        assertion_unit_map={"A1": "U1"},
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[_assertion("A1N", "J-1", value=2.0)],
        assertion_unit_map={"A1N": "U2"},
        processed_unit_ids=["U2"],
    )
    pkg = builder.build(
        intent=intent, prior_manifest=prior_m, new_manifest=new_m,
        prior_inventory=inv, delta_batch=batch, segmentation_reset=True,
    )
    assert pkg.supersede_actions == {}
    assert set(pkg.archive_actions) == {"A1"}
    assert set(pkg.added_assertion_ids) == {"A1N"}


# ---- R2-02 recursive deep-copy ----

def test_nested_object_value_deepcopy():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1", loc="p.old")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1", loc="p.new")])
    plan = compute_content_delta(prior_m, new_m)
    old_a = _assertion("A1", "R-P", value=[1.0, 2.0], locator="p.old")
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[old_a], assertion_unit_map={"A1": "U1"},
    )
    carried, _ = carry_forward_unchanged(
        prior_inventory=inv, plan=plan, new_manifest=new_m,
        new_ref_id="R-N", new_source_version_id="N",
    )
    new_a = carried[0]
    # Real semantic equality before mutation
    assert semantic_payload_hash(new_a) == semantic_payload_hash(old_a)
    # Mutate nested list on new
    new_a.object.value[0] = 999.0
    # Old unchanged
    assert old_a.object.value == [1.0, 2.0]


def test_nested_condition_value_deepcopy():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1", loc="p.old")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1", loc="p.new")])
    plan = compute_content_delta(prior_m, new_m)
    old_a = _assertion("A1", "R-P", locator="p.old")
    old_a.conditions = [Condition(eddo_class="R", value={"range": [1, 2]}, unit=None)]
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[old_a], assertion_unit_map={"A1": "U1"},
    )
    carried, _ = carry_forward_unchanged(
        prior_inventory=inv, plan=plan, new_manifest=new_m,
        new_ref_id="R-N", new_source_version_id="N",
    )
    new_a = carried[0]
    assert semantic_payload_hash(new_a) == semantic_payload_hash(old_a)
    new_a.conditions[0].value["range"][0] = 999
    assert old_a.conditions[0].value == {"range": [1, 2]}


# ---- R2-03 strict prior inventory in builder ----

def test_builder_unknown_prior_unit_reject():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1")])
    new_m = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U1", h="h1")])
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[_assertion("A1", "ARXIV-1")],
        assertion_unit_map={"A1": "GHOST"},  # malformed
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[], assertion_unit_map={}, processed_unit_ids=["U1"],
    )
    with pytest.raises(ValueError, match="unknown prior unit"):
        builder.build(
            intent=intent, prior_manifest=prior_m, new_manifest=new_m,
            prior_inventory=inv, delta_batch=batch,
        )


# ---- R2-04 side-labelled package material ----

def test_prior_new_hash_direction_changes_package_id():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[], assertion_unit_map={},
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[], assertion_unit_map={}, processed_unit_ids=["U1"],
    )
    # Case 1: prior U1=h1, new U1=h2
    prior_m1 = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1", h="h1")])
    new_m1 = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U1", h="h2")])
    pkg1 = builder.build(intent=intent, prior_manifest=prior_m1, new_manifest=new_m1, prior_inventory=inv, delta_batch=batch)
    # Case 2: swap hashes
    prior_m2 = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1", h="h2")])
    new_m2 = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U1", h="h1")])
    pkg2 = builder.build(intent=intent, prior_manifest=prior_m2, new_manifest=new_m2, prior_inventory=inv, delta_batch=batch)
    assert pkg1.package_id != pkg2.package_id


def test_assertion_unit_binding_changes_package_id():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    new_m = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U1", h="h1x"), _unit("U2", h="h2x")])
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[], assertion_unit_map={},
    )
    batch1 = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[_assertion("X1", "J-1")],
        assertion_unit_map={"X1": "U1"}, processed_unit_ids=["U1", "U2"],
    )
    batch2 = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[_assertion("X1", "J-1")],
        assertion_unit_map={"X1": "U2"}, processed_unit_ids=["U1", "U2"],
    )
    pkg1 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch1)
    pkg2 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch2)
    assert pkg1.package_id != pkg2.package_id


# ---- R2-05 trace/provenance identity ----

def test_trace_id_change_changes_package_id():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1", h="h1")])
    new_m = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U1", h="h2")])
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[], assertion_unit_map={},
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[], assertion_unit_map={}, processed_unit_ids=["U1"],
    )
    pkg1 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch, trace_id="t1")
    pkg2 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch, trace_id="t2")
    assert pkg1.package_id != pkg2.package_id


def test_identical_material_same_package_id():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1", h="h1")])
    new_m = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U1", h="h2")])
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[], assertion_unit_map={},
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[], assertion_unit_map={}, processed_unit_ids=["U1"],
    )
    pkg1 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch, trace_id="t1", provenance_id="p1")
    pkg2 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch, trace_id="t1", provenance_id="p1")
    assert pkg1.package_id == pkg2.package_id
