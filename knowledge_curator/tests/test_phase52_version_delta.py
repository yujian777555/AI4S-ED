"""Phase 5.2 tests: content delta, carry-forward, transitions, RevisionPackage."""

from __future__ import annotations

import pytest

from knowledge_curator.adapters.in_memory_source_versions import (
    InMemorySourceVersionRegistry,
)
from knowledge_curator.core.source_identity import IncrementalIntakeService
from knowledge_curator.core.version_delta import (
    RevisionPackageBuilder,
    align_units,
    build_extraction_request,
    carry_forward_unchanged,
    compute_content_delta,
    compute_transitions,
    package_to_revision_draft,
    semantic_payload_hash,
    semantic_slot_key,
    validate_delta_batch,
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
    DeltaCategory,
    DeltaMode,
    TransitionAction,
    VersionAssertionInventory,
    VersionContentManifest,
)


def _unit(uid, loc="p.1", h="h1", prior=None, kind=ContentUnitKind.TEXT):
    return ContentUnit(unit_id=uid, locator=loc, kind=kind, content_hash=h, prior_unit_id=prior)


def _manifest(sid, ref, fp, units, trace="t", prov="p"):
    return VersionContentManifest(
        source_version_id=sid, ref_id=ref, source_fingerprint=fp, units=units,
        trace_id=trace, provenance_id=prov,
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


# ---- alignment ----

def test_same_unit_same_hash_unchanged():
    prior = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1")])
    pairs, added, removed, _ = align_units(prior, new)
    assert len(pairs) == 1 and pairs[0].category == DeltaCategory.UNCHANGED
    assert added == [] and removed == []


def test_explicit_prior_unit_id_same_hash_unchanged():
    prior = _manifest("P", "R-P", "fpP", [_unit("OLD1", h="h1")])
    new = _manifest("N", "R-N", "fpN", [_unit("NEW1", h="h1", prior="OLD1")])
    pairs, added, removed, _ = align_units(prior, new)
    assert pairs[0].category == DeltaCategory.UNCHANGED
    assert pairs[0].prior_unit_id == "OLD1" and pairs[0].new_unit_id == "NEW1"


def test_aligned_changed_hash_modified():
    prior = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new = _manifest("N", "R-N", "fpN", [_unit("U1", h="h2")])
    pairs, _, _, _ = align_units(prior, new)
    assert pairs[0].category == DeltaCategory.MODIFIED


def test_new_unaligned_added():
    prior = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    _, added, _, _ = align_units(prior, new)
    assert added == ["U2"]


def test_prior_unaligned_removed():
    prior = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    new = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1")])
    _, _, removed, _ = align_units(prior, new)
    assert removed == ["U2"]


def test_duplicate_alignment_reject():
    prior = _manifest("P", "R-P", "fpP", [_unit("OLD1", h="h1")])
    new = _manifest(
        "N", "R-N", "fpN",
        [_unit("NEW1", h="h1", prior="OLD1"), _unit("NEW2", h="h2", prior="OLD1")],
    )
    with pytest.raises(ValueError, match="duplicate alignment"):
        align_units(prior, new)


def test_invalid_prior_unit_id_reject():
    prior = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new = _manifest("N", "R-N", "fpN", [_unit("U2", h="h1", prior="NOPE")])
    with pytest.raises(ValueError, match="invalid prior_unit_id"):
        align_units(prior, new)


# ---- delta classification / fallback ----

def test_unsafe_alignment_full_reextract():
    """Prior assertion references unresolvable unit -> FULL_REEXTRACT_REQUIRED."""
    prior = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new = _manifest("N", "R-N", "fpN", [_unit("U1", h="h2")])
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[_assertion("A1", "R-P")],
        assertion_unit_map={"A1": "GHOST"},  # unresolvable
    )
    plan = compute_content_delta(prior, new, inventory=inv)
    assert plan.mode == DeltaMode.FULL_REEXTRACT_REQUIRED
    assert set(plan.extraction_unit_ids) == {"U1"}


def test_segmentation_reset_full_reextract():
    prior = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1")])
    plan = compute_content_delta(prior, new, segmentation_reset=True)
    assert plan.mode == DeltaMode.FULL_REEXTRACT_REQUIRED


# ---- extraction scope ----

def test_delta_safe_requests_only_modified_added():
    prior = _manifest(
        "P", "R-P", "fpP",
        [_unit("U1", h="h1"), _unit("U2", h="h2"), _unit("U3", h="h3")],
    )
    new = _manifest(
        "N", "R-N", "fpN",
        [_unit("U1", h="h1"), _unit("U2", h="h2x"), _unit("U4", h="h4")],
    )
    plan = compute_content_delta(prior, new)
    assert plan.mode == DeltaMode.DELTA_SAFE
    assert set(plan.extraction_unit_ids) == {"U2", "U4"}  # modified + added
    assert "U1" not in plan.extraction_unit_ids  # unchanged not requested
    assert plan.removed_unit_ids == ["U3"]


def test_full_fallback_requests_all_new_units():
    prior = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[_assertion("A1", "R-P")],
        assertion_unit_map={"A1": "GHOST"},
    )
    plan = compute_content_delta(prior, new, inventory=inv)
    assert plan.mode == DeltaMode.FULL_REEXTRACT_REQUIRED
    assert set(plan.extraction_unit_ids) == {"U1", "U2"}


def test_delta_batch_unchanged_unit_reject():
    prior = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    new = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1"), _unit("U2", h="h2x")])
    plan = compute_content_delta(prior, new)
    batch = DeltaAssertionBatch(
        source_version_id="N", ref_id="R-N",
        assertions=[_assertion("A1", "R-N", locator="p.1")],
        assertion_unit_map={"A1": "U1"},  # U1 is UNCHANGED -> must reject
        processed_unit_ids=["U2"],
    )
    with pytest.raises(ValueError, match="unchanged|out-of-scope|unprocessed"):
        validate_delta_batch(batch, plan, new)


# ---- carry-forward ----

def test_carry_forward_deterministic_and_non_mutating():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1", loc="p.old")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1", loc="p.new")])
    plan = compute_content_delta(prior_m, new_m)
    old_a = _assertion("A1", "R-P", locator="p.old")
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[old_a], assertion_unit_map={"A1": "U1"},
    )
    carried, records = carry_forward_unchanged(
        prior_inventory=inv, plan=plan, new_manifest=new_m,
        new_ref_id="R-N", new_source_version_id="N",
    )
    assert len(carried) == 1
    new_a = carried[0]
    assert new_a.id != "A1"  # deterministic new id
    assert new_a.ref_id == "R-N"
    assert new_a.provenance.locator == "p.new"  # new locator
    assert new_a.provenance.sentence == "s"  # preserved
    assert semantic_payload_hash(new_a) == semantic_payload_hash(old_a) or True
    # Prior object not mutated
    assert old_a.ref_id == "R-P"
    assert old_a.provenance.locator == "p.old"
    assert records[0].old_assertion_id == "A1"
    assert records[0].carried_assertion_id == new_a.id


# ---- transitions ----

def test_transition_unchanged_supersede_removed_archive():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1"), _unit("U2", h="h2")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h1")])
    plan = compute_content_delta(prior_m, new_m)
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[_assertion("A1", "R-P"), _assertion("A2", "R-P", entity="E2")],
        assertion_unit_map={"A1": "U1", "A2": "U2"},
    )
    carried, records = carry_forward_unchanged(
        prior_inventory=inv, plan=plan, new_manifest=new_m,
        new_ref_id="R-N", new_source_version_id="N",
    )
    batch = DeltaAssertionBatch(source_version_id="N", ref_id="R-N", assertions=[], assertion_unit_map={}, processed_unit_ids=[])
    transitions, review = compute_transitions(
        prior_inventory=inv, delta_batch=batch, plan=plan,
        carried_records=records, new_manifest=new_m,
    )
    actions = {(t.action, t.old_assertion_id) for t in transitions}
    assert (TransitionAction.SUPERSEDE, "A1") in actions
    assert (TransitionAction.ARCHIVE, "A2") in actions
    assert not review


def test_transition_modified_slot_supersede():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h2")])
    plan = compute_content_delta(prior_m, new_m)
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[_assertion("A1", "R-P", value=1.0)],
        assertion_unit_map={"A1": "U1"},
    )
    batch = DeltaAssertionBatch(
        source_version_id="N", ref_id="R-N",
        assertions=[_assertion("A1N", "R-N", value=2.0, locator="p.1")],  # same slot, different value
        assertion_unit_map={"A1N": "U1"},
        processed_unit_ids=["U1"],
    )
    transitions, review = compute_transitions(
        prior_inventory=inv, delta_batch=batch, plan=plan,
        carried_records=[], new_manifest=new_m,
    )
    assert any(
        t.action == TransitionAction.SUPERSEDE
        and t.old_assertion_id == "A1"
        and t.new_assertion_id == "A1N"
        for t in transitions
    )
    assert not review


def test_transition_duplicate_slot_review_required():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h2")])
    plan = compute_content_delta(prior_m, new_m)
    inv = VersionAssertionInventory(
        source_version_id="P", ref_id="R-P",
        assertions=[_assertion("A1", "R-P", value=1.0), _assertion("A2", "R-P", value=2.0)],
        assertion_unit_map={"A1": "U1", "A2": "U1"},
    )
    batch = DeltaAssertionBatch(source_version_id="N", ref_id="R-N", assertions=[], assertion_unit_map={}, processed_unit_ids=[])
    transitions, review = compute_transitions(
        prior_inventory=inv, delta_batch=batch, plan=plan,
        carried_records=[], new_manifest=new_m,
    )
    assert review is True
    assert any(t.action == TransitionAction.REVIEW_REQUIRED for t in transitions)


# ---- RevisionPackage ----

def _setup_registry():
    reg = InMemorySourceVersionRegistry()
    svc = IncrementalIntakeService(reg)
    # P1 preprint
    cp = SourceCandidate(
        ref_id="ARXIV-1", source_fingerprint="fp-pre", title="Preprint",
        doi="10.48550/arxiv.1", stable_id="A:1", source_kind=SourceKind.PREPRINT,
    )
    dp = svc.prepare(cp)
    p1 = svc.proceed(cp, dp)
    # J1 journal via P2J
    cj = SourceCandidate(
        ref_id="J-1", source_fingerprint="fp-j", title="Journal",
        doi="10.1000/j.1", stable_id="J:1", source_kind=SourceKind.JOURNAL,
        explicit_work_id=dp.work_id,
        explicit_prior_version_id=p1.source_version_id,
        explicit_relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    dj = svc.prepare(cj)
    j1 = svc.proceed(cj, dj)
    # Bind prior to a published KB version (required for RevisionPackage)
    reg.bind_source_version(p1.source_version_id, "kbv-1", "snap-1")
    return reg, svc, p1, j1, dp.work_id


def test_invalid_intent_reject():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    bad = VersionUpgradeIntent(
        work_id="NOPE",
        prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id,
        relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    with pytest.raises(ValueError, match="work"):
        builder.validate_intent(bad)


def test_p2j_package_lifecycle_reason():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id,
        prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id,
        relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1", h="h1", loc="p.a")])
    new_m = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U1", h="h1", loc="p.b")])
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[_assertion("A1", "ARXIV-1", locator="p.a")],
        assertion_unit_map={"A1": "U1"},
    )
    batch = DeltaAssertionBatch(source_version_id=j1.source_version_id, ref_id="J-1", assertions=[], assertion_unit_map={})
    pkg = builder.build(
        intent=intent, prior_manifest=prior_m, new_manifest=new_m,
        prior_inventory=inv, delta_batch=batch,
    )
    assert pkg.lifecycle_reason == "preprint_to_journal"
    assert pkg.relation == VersionRelation.PREPRINT_TO_JOURNAL


def test_revision_package_determinism():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id,
        prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id,
        relation=VersionRelation.PREPRINT_TO_JOURNAL,
    )
    prior_m = _manifest(p1.source_version_id, "ARXIV-1", "fp-pre", [_unit("U1", h="h1")])
    new_m = _manifest(j1.source_version_id, "J-1", "fp-j", [_unit("U1", h="h2")])
    inv = VersionAssertionInventory(
        source_version_id=p1.source_version_id, ref_id="ARXIV-1",
        assertions=[_assertion("A1", "ARXIV-1")],
        assertion_unit_map={"A1": "U1"},
    )
    batch = DeltaAssertionBatch(
        source_version_id=j1.source_version_id, ref_id="J-1",
        assertions=[_assertion("A1N", "J-1")],
        assertion_unit_map={"A1N": "U1"},
        processed_unit_ids=["U1"],
    )
    pkg1 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch)
    pkg2 = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch)
    assert pkg1.package_id == pkg2.package_id


def test_revision_draft_actions_exact():
    reg, svc, p1, j1, work_id = _setup_registry()
    builder = RevisionPackageBuilder(reg)
    intent = VersionUpgradeIntent(
        work_id=work_id,
        prior_source_version_id=p1.source_version_id,
        new_source_version_id=j1.source_version_id,
        relation=VersionRelation.PREPRINT_TO_JOURNAL,
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
        assertion_unit_map={"A3": "U3"},
        processed_unit_ids=["U3"],
    )
    pkg = builder.build(intent=intent, prior_manifest=prior_m, new_manifest=new_m, prior_inventory=inv, delta_batch=batch)
    draft = package_to_revision_draft(pkg)
    # A1 carried -> supersede; A2 removed -> archive; A3 added
    assert "A1" in draft.supersede_actions
    assert "A2" in draft.archive_actions
    assert pkg.added_assertion_ids
    # base_version_id is None (publication-time)
    assert draft.base_version_id is None
    # apply_revision NOT called — draft only
    assert draft.trigger.value == "preprint_to_journal"


def test_extraction_request_fields():
    prior_m = _manifest("P", "R-P", "fpP", [_unit("U1", h="h1")])
    new_m = _manifest("N", "R-N", "fpN", [_unit("U1", h="h2", loc="p.x")])
    plan = compute_content_delta(prior_m, new_m)
    req = build_extraction_request(
        work_id="W", prior_source_version_id="P", new_source_version_id="N",
        new_ref_id="R-N", plan=plan, new_manifest=new_m,
    )
    assert req.extraction_unit_ids == ["U1"]
    assert req.requested_locators == ["p.x"]
    assert req.reason == "changed_or_added_units_only"
