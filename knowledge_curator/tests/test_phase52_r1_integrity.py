"""Phase 5.2-R1 tests: input/material integrity hardening."""

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
    validate_delta_batch,
    validate_prior_inventory,
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
    VersionAssertionInventory,
    VersionContentManifest,
)


def _unit(uid, loc="p.1", h="h1", prior=None):
    return ContentUnit(unit_id=uid, locator=loc, kind=ContentUnitKind.TEXT, content_hash=h, prior_unit_id=prior)


def _manifest(sid, ref, fp, units):
    return VersionContentManifest(
        source_version_id=sid, ref_id=ref, source_fingerprint=fp, units=units
    )


def _assertion(aid, ref, entity="E1", prop="P1", value=1.0, locator="p.1", conf=Confidence.HIGH):
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
        confidence=conf,
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


# ---- R1-01 deep-copy carry-forward ----

def test_deep_copy_independence():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1", loc="p.old")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1", loc="p.new")])
    plan = compute_content_delta(prior_m, new_m)
    old_a = _assertion("A1", "R-P", locator="p.old")
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[old_a], assertion_unit_map={"A1": "U1"},
    )
    carried, _ = carry_forward_unchanged(
        prior_inventory=inv, plan=plan, new_manifest=new_m,
        new_ref_id="R-N", new_source_version_id="N",
    )
    new_a = carried[0]
    # Mutate nested objects on new
    new_a.subject.original_mention = "MUTATED"
    new_a.object.value = 999.0
    new_a.conditions[0].value = 999
    # Old assertion and nested objects unchanged
    assert old_a.subject.original_mention == "E1"
    assert old_a.object.value == 1.0
    assert old_a.conditions[0].value == 298
    # Real semantic equality before mutation
    old2 = _assertion("A1", "R-P", locator="p.old")
    assert semantic_payload_hash(old_a) == semantic_payload_hash(old2)


# ---- R1-02 manifest/inventory/batch identity ----

def test_prior_manifest_identity_mismatch_reject():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    # Wrong prior manifest ref_id
    bad_prior = _manifest(p1.source_version_id, "WRONG-REF", "fp-pre", [_unit("U1")])
    new_m = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U1", h="h1")])
    inv = VersionAssertionInventory(source_version_id=p1.source_version_id, ref_id="ARXIV-1", assertions=[], assertion_unit_map={})
    batch = DeltaAssertionBatch(source_version_id=j1.source_version_id, ref_id="J-1", assertions=[], assertion_unit_map={}, processed_unit_ids=["U1"])
    with pytest.raises(ValueError, match="prior manifest"):
        builder.build(intent=intent, prior_manifest=bad_prior, new_manifest=new_m, prior_inventory=inv, delta_batch=batch)


def test_new_manifest_fingerprint_mismatch_reject():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1")])
    bad_new = _manifest(j1.source_version_id, "J-1", "WRONG-FP", [_unit("U1", h="h1")])
    inv = VersionAssertionInventory(source_version_id=p1.source_version_id, ref_id="ARXIV-1", assertions=[], assertion_unit_map={})
    batch = DeltaAssertionBatch(source_version_id=j1.source_version_id, ref_id="J-1", assertions=[], assertion_unit_map={}, processed_unit_ids=["U1"])
    with pytest.raises(ValueError, match="new manifest"):
        builder.build(intent=intent, prior_manifest=prior_m, new_manifest=bad_new, prior_inventory=inv, delta_batch=batch)


def test_inventory_identity_mismatch_reject():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1")])
    new_m = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U1", h="h1")])
    bad_inv = VersionAssertionInventory(source_version_id="WRONG", ref_id="ARXIV-1", assertions=[], assertion_unit_map={})
    batch = DeltaAssertionBatch(source_version_id=j1.source_version_id, ref_id="J-1", assertions=[], assertion_unit_map={}, processed_unit_ids=["U1"])
    with pytest.raises(ValueError, match="prior inventory"):
        builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=bad_inv, delta_batch=batch)


# ---- R1-03 intent relation / prior binding ----

def test_intent_relation_mismatch_reject():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    bad = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.REVISION_OF,
    )
    with pytest.raises(ValueError, match="relation"):
        builder.validate_intent(bad)


def test_prior_unbound_kb_reject():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    cp = SourceCandidate(ref_id="R-P", source_fingerprint="fpP", title="P", doi="10.1/P", stable_id="S-P", source_kind=SourceKind.PREPRINT)
    dp = svc.prepare(cp)
    p1 = svc.proceed(cp, dp)
    # NOT bound
    builder = RevisionPackageBuilder(reg)
    # Create a new version in same work
    cj = SourceCandidate(ref_id="R-J", source_fingerprint="fpJ", title="J", doi="10.1/J", stable_id="S-J", source_kind=SourceKind.JOURNAL,
                        explicit_work_id=dp.work_id, explicit_prior_version_id=p1.source_version_id,
                        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL)
    dj = svc.prepare(cj)
    j1 = svc.proceed(cj, dj)
    intent = VersionUpgradeIntent(
        work_id=dp.work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    with pytest.raises(ValueError, match="bound"):
        builder.validate_intent(intent)


def test_prior_bound_kb_pass():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    ctx = builder.validate_intent(intent)
    assert ctx["prior"].kb_version_id == "kbv-1"


# ---- R1-04 prior inventory integrity ----

def test_inventory_duplicate_id_reject():
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[_assertion("A1", "R-P"), _assertion("A1", "R-P")],
        assertion_unit_map={"A1": "U1"},
    )
    m = _manifest("P", "R-P", "fpP", [_unit("U1")])
    with pytest.raises(ValueError, match="duplicate"):
        validate_prior_inventory(inv, m)


def test_inventory_missing_unit_map_reject():
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[_assertion("A1", "R-P")],
        assertion_unit_map={},
    )
    m = _manifest("P", "R-P", "fpP", [_unit("U1")])
    with pytest.raises(ValueError, match="no unit binding"):
        validate_prior_inventory(inv, m)


def test_inventory_dangling_map_reject():
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[_assertion("A1", "R-P")],
        assertion_unit_map={"A1": "U1", "GHOST": "U1"},
    )
    m = _manifest("P", "R-P", "fpP", [_unit("U1")])
    with pytest.raises(ValueError, match="dangling"):
        validate_prior_inventory(inv, m)


# ---- R1-04/05 extraction completion ----

def test_delta_safe_processed_incomplete_reject():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1"), _unit("U2", h="h2x")])
    plan = compute_content_delta(prior_m, new_m)
    assert plan.mode == DeltaMode.DELTA_SAFE
    assert set(plan.extraction_unit_ids) == {"U2"}
    batch = DeltaAssertionBatch(
        source_version_id="N", ref_id="R-N",
        assertions=[], assertion_unit_map={},
        processed_unit_ids=[],  # missing U2
    )
    with pytest.raises(ValueError, match="processed_unit_ids"):
        validate_delta_batch(batch, plan, new_m)


def test_delta_safe_processed_out_of_scope_reject():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1"), _unit("U2", h="h2x")])
    plan = compute_content_delta(prior_m, new_m)
    batch = DeltaAssertionBatch(
        source_version_id="N", ref_id="R-N",
        assertions=[], assertion_unit_map={},
        processed_unit_ids=["U2", "U1"],  # U1 is UNCHANGED -> out of scope
    )
    with pytest.raises(ValueError, match="processed_unit_ids"):
        validate_delta_batch(batch, plan, new_m)


def test_full_reextract_processed_incomplete_reject():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[_assertion("A1", "R-P")],
        assertion_unit_map={"A1": "GHOST"},
    )
    plan = compute_content_delta(prior_m, new_m, inventory=inv)
    assert plan.mode == DeltaMode.FULL_REEXTRACT_REQUIRED
    batch = DeltaAssertionBatch(
        source_version_id="N", ref_id="R-N",
        assertions=[], assertion_unit_map={},
        processed_unit_ids=["U1"],  # missing U2
    )
    with pytest.raises(ValueError, match="processed_unit_ids"):
        validate_delta_batch(batch, plan, new_m)


def test_full_reextract_duplicate_id_reject():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1")])
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[_assertion("A1", "R-P")],
        assertion_unit_map={"A1": "GHOST"},
    )
    plan = compute_content_delta(prior_m, new_m, inventory=inv)
    batch = DeltaAssertionBatch(
        source_version_id="N", ref_id="R-N",
        assertions=[_assertion("X1", "R-N"), _assertion("X1", "R-N")],
        assertion_unit_map={"X1": "U1"},
        processed_unit_ids=["U1"],
    )
    with pytest.raises(ValueError, match="duplicate"):
        validate_delta_batch(batch, plan, new_m)


def test_processed_unit_zero_assertions_valid():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1"), _unit("U2", h="h2x")])
    plan = compute_content_delta(prior_m, new_m)
    # U2 processed but produced 0 assertions -> valid
    batch = DeltaAssertionBatch(
        source_version_id="N", ref_id="R-N",
        assertions=[], assertion_unit_map={},
        processed_unit_ids=["U2"],
    )
    validate_delta_batch(batch, plan, new_m)  # should not raise


# ---- R1-12 FULL_REEXTRACT no carry-forward ----

def test_full_reextract_no_carry_forward():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1", h="h1")])
    new_m = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[_assertion("A1", "ARXIV-1")],
        assertion_unit_map={"A1": "U1"},
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[_assertion("N1", "J-1", locator="p.1")],
        assertion_unit_map={"N1": "U1"},
        processed_unit_ids=["U1", "U2"],
    )
    pkg = builder.build(
        intent=intent, prior_manifest=prior_m, new_manifest=new_m,
        prior_inventory=inv, delta_batch=batch, segmentation_reset=True,
    )
    assert pkg.content_delta.mode == DeltaMode.FULL_REEXTRACT_REQUIRED
    assert pkg.carried_records == []
    assert all(a.id.startswith("N") for a in pkg.target_assertions)


# ---- R1-06 package material identity ----

def test_value_change_changes_package_id():
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
        assertions=[_assertion("A1", "ARXIV-1", value=1.0)],
        assertion_unit_map={"A1": "U1"},
    )
    batch1 = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[_assertion("A1N", "J-1", value=2.0)],
        assertion_unit_map={"A1N": "U1"}, processed_unit_ids=["U1"],
    )
    batch2 = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[_assertion("A1N", "J-1", value=3.0)],  # value changed
        assertion_unit_map={"A1N": "U1"}, processed_unit_ids=["U1"],
    )
    pkg1 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch1)
    pkg2 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch2)
    assert pkg1.package_id != pkg2.package_id


def test_same_material_same_package_id():
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
        assertions=[_assertion("A1", "ARXIV-1", value=1.0)],
        assertion_unit_map={"A1": "U1"},
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[_assertion("A1N", "J-1", value=2.0)],
        assertion_unit_map={"A1N": "U1"}, processed_unit_ids=["U1"],
    )
    pkg1 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch)
    pkg2 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch)
    assert pkg1.package_id == pkg2.package_id


# ---- R1-07 replacement ids ----

def test_replacement_ids_complete():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id, prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id, relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(
        p1.source_version_id, "ARXIV-1", "fp-pre",
        [_unit("U1", h="h1"), _unit("U2", h="h2")],
    )
    new_m = _manifest(
        j1.source_version_id, "J-1", "fp-j",
        [_unit("U1", h="h1"), _unit("U3", h="h3")],  # U1 unchanged, U2 removed, U3 added
    )
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[_assertion("A1", "ARXIV-1"), _assertion("A2", "ARXIV-1", entity="E2")],
        assertion_unit_map={"A1": "U1", "A2": "U2"},
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[_assertion("A3", "J-1", entity="E3", locator="p.3")],
        assertion_unit_map={"A3": "U3"}, processed_unit_ids=["U3"],
    )
    pkg = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch)
    draft = package_to_revision_draft(pkg)
    # replacement = supersede targets (carried A1->new) + added (A3)
    carried_ids = {r.carried_assertion_id for r in pkg.carried_records}
    assert set(draft.replacement_assertion_ids) == carried_ids | {"A3"}
    # Old ids never in replacement
    assert "A1" not in draft.replacement_assertion_ids
    assert "A2" not in draft.replacement_assertion_ids
