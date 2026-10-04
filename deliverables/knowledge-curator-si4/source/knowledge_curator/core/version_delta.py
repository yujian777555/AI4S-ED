"""Structured content delta + assertion transition planning (Phase 5.2).

Deterministic, exact-only alignment. No fuzzy/embedding/LLM matching.
Consumes upstream content manifests; produces RevisionPackage for frozen
lifecycle publication (does NOT call apply_revision).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from knowledge_curator.ports.source_version_registry import SourceVersionRegistry
from knowledge_curator.schemas.assertions import (
    Assertion,
    Confidence,
    Condition,
    ObjectValue,
    Provenance,
    Subject,
    ValueType,
)
from knowledge_curator.schemas.source_versions import (
    SourceKind,
    VersionRelation,
    VersionUpgradeIntent,
)
from knowledge_curator.schemas.version_delta import (
    AlignedPair,
    AssertionTransition,
    CarriedAssertionRecord,
    ContentDeltaPlan,
    ContentUnit,
    ContentUnitKind,
    DeltaAssertionBatch,
    DeltaCategory,
    DeltaExtractionRequest,
    DeltaMode,
    RevisionPackage,
    TransitionAction,
    VersionAssertionInventory,
    VersionContentManifest,
)


def _hash_json(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Semantic slot key / semantic hash (internal, not §5 commit hash)
# ---------------------------------------------------------------------------


def _norm_conditions(assertion: Assertion) -> tuple:
    conds = []
    for c in assertion.conditions or []:
        conds.append((c.eddo_class, str(c.value), c.unit or ""))
    return tuple(sorted(conds))


def semantic_slot_key(assertion: Assertion) -> str:
    """Deterministic slot key excluding value/locator/id/ref."""
    return _hash_json(
        {
            "eddo_class": assertion.subject.eddo_class,
            "resolved_entity": assertion.subject.resolved_entity,
            "property": assertion.property,
            "conditions": _norm_conditions(assertion),
            "claim_type": assertion.claim_type.value,
            "value_type": assertion.object.value_type.value,
        }
    )[:16]


def semantic_payload_hash(assertion: Assertion) -> str:
    """Deterministic semantic hash for assertion content comparison."""
    return _hash_json(
        {
            "eddo_class": assertion.subject.eddo_class,
            "resolved_entity": assertion.subject.resolved_entity,
            "original_mention": assertion.subject.original_mention,
            "property": assertion.property,
            "value": assertion.object.value,
            "unit": assertion.object.unit,
            "value_type": assertion.object.value_type.value,
            "uncertainty": assertion.object.uncertainty,
            "conditions": _norm_conditions(assertion),
            "claim_type": assertion.claim_type.value,
            "origin": assertion.source_claim_origin.value,
            "missing_unit": assertion.missing_unit,
            "speculative_wording": assertion.speculative_wording,
            "chart_quality_low": assertion.chart_quality_low,
        }
    )[:16]


# ---------------------------------------------------------------------------
# Exact content-unit alignment
# ---------------------------------------------------------------------------


def align_units(
    prior_manifest: VersionContentManifest,
    new_manifest: VersionContentManifest,
) -> tuple[list[AlignedPair], list[str], list[str], dict[str, Any]]:
    """Exact-only alignment. Returns (pairs, added_ids, removed_ids, diagnostics).

    Precedence: explicit prior_unit_id > same unit_id > unaligned.
    Fails closed on duplicate/invalid alignment.
    """
    prior_map = prior_manifest.unit_map()
    new_map = new_manifest.unit_map()
    diagnostics: dict[str, Any] = {}

    # Validate unique unit_ids within each manifest
    if len(prior_map) != len(prior_manifest.units):
        raise ValueError("duplicate unit_id in prior manifest")
    if len(new_map) != len(new_manifest.units):
        raise ValueError("duplicate unit_id in new manifest")

    # Build alignment: new_unit -> prior_unit
    alignment: dict[str, str] = {}  # new_unit_id -> prior_unit_id
    claimed_prior: dict[str, str] = {}  # prior_unit_id -> new_unit_id

    for nu in new_manifest.units:
        target_prior: Optional[str] = None
        if nu.prior_unit_id is not None:
            # 1. explicit prior_unit_id
            if nu.prior_unit_id not in prior_map:
                raise ValueError(
                    f"invalid prior_unit_id {nu.prior_unit_id!r} for new unit {nu.unit_id!r}"
                )
            target_prior = nu.prior_unit_id
        elif nu.unit_id in prior_map:
            # 2. same unit_id only when prior_unit_id is absent
            target_prior = nu.unit_id

        if target_prior is not None:
            # Duplicate alignment check
            if target_prior in claimed_prior:
                raise ValueError(
                    f"duplicate alignment: prior unit {target_prior!r} claimed by "
                    f"{claimed_prior[target_prior]!r} and {nu.unit_id!r}"
                )
            claimed_prior[target_prior] = nu.unit_id
            alignment[nu.unit_id] = target_prior

    # Classify
    pairs: list[AlignedPair] = []
    added_ids: list[str] = []
    removed_ids: list[str] = []

    for nu in new_manifest.units:
        if nu.unit_id not in alignment:
            added_ids.append(nu.unit_id)
        else:
            pu_id = alignment[nu.unit_id]
            pu = prior_map[pu_id]
            if pu.content_hash == nu.content_hash:
                pairs.append(AlignedPair(pu_id, nu.unit_id, DeltaCategory.UNCHANGED))
            else:
                pairs.append(AlignedPair(pu_id, nu.unit_id, DeltaCategory.MODIFIED))

    for pu_id in prior_map:
        if pu_id not in claimed_prior:
            removed_ids.append(pu_id)

    diagnostics["alignment_count"] = len(alignment)
    diagnostics["added_count"] = len(added_ids)
    diagnostics["removed_count"] = len(removed_ids)
    return pairs, added_ids, removed_ids, diagnostics


# ---------------------------------------------------------------------------
# Content delta classification
# ---------------------------------------------------------------------------


def compute_content_delta(
    prior_manifest: VersionContentManifest,
    new_manifest: VersionContentManifest,
    *,
    inventory: Optional[VersionAssertionInventory] = None,
    segmentation_reset: bool = False,
) -> ContentDeltaPlan:
    """Classify content delta. Falls back to FULL_REEXTRACT when unsafe."""
    if segmentation_reset:
        all_new = [u.unit_id for u in new_manifest.units]
        return ContentDeltaPlan(
            mode=DeltaMode.FULL_REEXTRACT_REQUIRED,
            extraction_unit_ids=all_new,
            diagnostics={"reason": "upstream declared segmentation/identity reset"},
        )

    pairs, added_ids, removed_ids, diag = align_units(prior_manifest, new_manifest)
    unchanged = [p for p in pairs if p.category == DeltaCategory.UNCHANGED]
    modified = [p for p in pairs if p.category == DeltaCategory.MODIFIED]

    # Safety: prior assertions referencing unalignable prior units cannot be
    # safely carried forward when those units are not removed-by-design.
    if inventory is not None:
        prior_unit_ids = set(prior_manifest.unit_map().keys())
        aligned_prior = {p.prior_unit_id for p in pairs}
        removed_set = set(removed_ids)
        for aid, uid in inventory.assertion_unit_map.items():
            if uid not in prior_unit_ids:
                # Assertion references a unit not in prior manifest -> unsafe
                return ContentDeltaPlan(
                    mode=DeltaMode.FULL_REEXTRACT_REQUIRED,
                    extraction_unit_ids=[u.unit_id for u in new_manifest.units],
                    diagnostics={
                        "reason": "prior assertion references unresolved unit",
                        "assertion_id": aid,
                        "unit_id": uid,
                    },
                )
            if uid not in aligned_prior and uid not in removed_set:
                # Should not happen, but treat as unsafe
                return ContentDeltaPlan(
                    mode=DeltaMode.FULL_REEXTRACT_REQUIRED,
                    extraction_unit_ids=[u.unit_id for u in new_manifest.units],
                    diagnostics={"reason": "prior unit neither aligned nor removed", "unit_id": uid},
                )

    extraction_ids = [p.new_unit_id for p in modified] + list(added_ids)
    return ContentDeltaPlan(
        mode=DeltaMode.DELTA_SAFE,
        unchanged_pairs=unchanged,
        modified_pairs=modified,
        added_unit_ids=list(added_ids),
        removed_unit_ids=list(removed_ids),
        extraction_unit_ids=extraction_ids,
        diagnostics=diag,
    )


# ---------------------------------------------------------------------------
# DeltaExtractionRequest
# ---------------------------------------------------------------------------


def build_extraction_request(
    *,
    work_id: str,
    prior_source_version_id: str,
    new_source_version_id: str,
    new_ref_id: str,
    plan: ContentDeltaPlan,
    new_manifest: VersionContentManifest,
    relation: VersionRelation = VersionRelation.NONE,
    trace_id: str = "",
    provenance_id: str = "",
) -> DeltaExtractionRequest:
    new_map = new_manifest.unit_map()
    locators = [new_map[uid].locator for uid in plan.extraction_unit_ids if uid in new_map]
    if plan.mode == DeltaMode.DELTA_SAFE:
        reason = "changed_or_added_units_only"
    else:
        reason = "full_reextract_required"
    return DeltaExtractionRequest(
        work_id=work_id,
        prior_source_version_id=prior_source_version_id,
        new_source_version_id=new_source_version_id,
        new_ref_id=new_ref_id,
        extraction_unit_ids=list(plan.extraction_unit_ids),
        requested_locators=locators,
        reason=reason,
        trace_id=trace_id,
        provenance_id=provenance_id,
    )


# ---------------------------------------------------------------------------
# Assertion inventory / delta batch validation
# ---------------------------------------------------------------------------


def validate_delta_batch(
    batch: DeltaAssertionBatch,
    plan: ContentDeltaPlan,
    new_manifest: VersionContentManifest,
) -> None:
    """Validate delta batch structural invariants in ALL modes (R1).

    Also validates extraction completion coverage via processed_unit_ids.
    """
    new_units = set(new_manifest.unit_map().keys())
    processed = set(batch.processed_unit_ids)
    seen: set[str] = set()

    # Structural invariants (all modes)
    for a in batch.assertions:
        if a.id in seen:
            raise ValueError(f"duplicate assertion id in delta batch: {a.id}")
        seen.add(a.id)
        if a.ref_id != batch.ref_id:
            raise ValueError(f"assertion {a.id} ref_id mismatch with batch ref_id")
        uid = batch.assertion_unit_map.get(a.id)
        if uid is None:
            raise ValueError(f"assertion {a.id} has no unit binding")
        if uid not in new_units:
            raise ValueError(f"assertion {a.id} maps to unknown unit {uid}")
        if uid not in processed:
            raise ValueError(f"assertion {a.id} maps to unprocessed unit {uid}")

    # Dangling map entries
    for aid in batch.assertion_unit_map:
        if aid not in seen:
            raise ValueError(f"dangling assertion_unit_map entry: {aid}")

    # Mode-specific processed scope (R1-04/05)
    if plan.mode == DeltaMode.DELTA_SAFE:
        required = set(plan.extraction_unit_ids)
        if processed != required:
            raise ValueError(
                f"DELTA_SAFE processed_unit_ids {sorted(processed)} != "
                f"extraction_unit_ids {sorted(required)}"
            )
        # Processed units must not include unchanged/out-of-scope
        for uid in processed:
            if uid not in new_units:
                raise ValueError(f"processed unit {uid} not in new manifest")
    elif plan.mode == DeltaMode.FULL_REEXTRACT_REQUIRED:
        required = new_units
        if processed != required:
            raise ValueError(
                f"FULL_REEXTRACT processed_unit_ids {sorted(processed)} != "
                f"all new units {sorted(required)}"
            )
    # REVIEW_REQUIRED: structural checks already done above


def validate_prior_inventory(
    inventory: VersionAssertionInventory,
    prior_manifest: VersionContentManifest,
    *,
    allow_unresolvable_units: bool = False,
) -> None:
    """Validate prior inventory completeness (R1-04).

    Structural invalidity always fails. Unresolvable unit mappings may be
    allowed when the caller will fall back to FULL_REEXTRACT_REQUIRED.
    """
    prior_units = set(prior_manifest.unit_map().keys())
    seen: set[str] = set()
    for a in inventory.assertions:
        if a.id in seen:
            raise ValueError(f"duplicate assertion id in prior inventory: {a.id}")
        seen.add(a.id)
        if a.ref_id != inventory.ref_id:
            raise ValueError(f"assertion {a.id} ref_id mismatch with inventory ref_id")
        uid = inventory.assertion_unit_map.get(a.id)
        if uid is None:
            raise ValueError(f"assertion {a.id} has no unit binding in prior inventory")
        if uid not in prior_units and not allow_unresolvable_units:
            raise ValueError(f"assertion {a.id} maps to unknown prior unit {uid}")
    for aid in inventory.assertion_unit_map:
        if aid not in seen:
            raise ValueError(f"dangling prior assertion_unit_map entry: {aid}")


def _validate_manifest_identity(
    manifest: VersionContentManifest,
    *,
    expected_version_id: str,
    expected_ref_id: str,
    expected_fingerprint: str,
    label: str,
) -> None:
    if manifest.source_version_id != expected_version_id:
        raise ValueError(
            f"{label} manifest source_version_id {manifest.source_version_id!r} != "
            f"expected {expected_version_id!r}"
        )
    if manifest.ref_id != expected_ref_id:
        raise ValueError(
            f"{label} manifest ref_id {manifest.ref_id!r} != expected {expected_ref_id!r}"
        )
    if manifest.source_fingerprint != expected_fingerprint:
        raise ValueError(
            f"{label} manifest source_fingerprint {manifest.source_fingerprint!r} != "
            f"expected {expected_fingerprint!r}"
        )


def _validate_inventory_identity(
    inventory: VersionAssertionInventory,
    *,
    expected_version_id: str,
    expected_ref_id: str,
    label: str,
) -> None:
    if inventory.source_version_id != expected_version_id:
        raise ValueError(
            f"{label} inventory source_version_id {inventory.source_version_id!r} != "
            f"expected {expected_version_id!r}"
        )
    if inventory.ref_id != expected_ref_id:
        raise ValueError(
            f"{label} inventory ref_id {inventory.ref_id!r} != expected {expected_ref_id!r}"
        )


# ---------------------------------------------------------------------------
# Carry-forward unchanged assertions
# ---------------------------------------------------------------------------


def _deterministic_carried_id(
    prior_assertion_id: str, new_source_version_id: str, new_unit_id: str
) -> str:
    return _hash_json(
        {
            "prior_assertion_id": prior_assertion_id,
            "new_source_version_id": new_source_version_id,
            "new_unit_id": new_unit_id,
        }
    )[:16]


def _deep_copy_subject(s: Subject) -> Subject:
    return Subject(
        eddo_class=s.eddo_class,
        resolved_entity=s.resolved_entity,
        original_mention=s.original_mention,
    )


def _deep_copy_object(o: ObjectValue) -> ObjectValue:
    # R2-02: recursive deep-copy of mutable value payload.
    import copy as _copy

    return ObjectValue(
        value=_copy.deepcopy(o.value),
        unit=o.unit,
        value_type=o.value_type,
        uncertainty=o.uncertainty,
    )


def _deep_copy_condition(c: Condition) -> Condition:
    import copy as _copy

    return Condition(eddo_class=c.eddo_class, value=_copy.deepcopy(c.value), unit=c.unit)


def carry_forward_unchanged(
    *,
    prior_inventory: VersionAssertionInventory,
    plan: ContentDeltaPlan,
    new_manifest: VersionContentManifest,
    new_ref_id: str,
    new_source_version_id: str,
) -> tuple[list[Assertion], list[CarriedAssertionRecord]]:
    """Clone prior assertions for unchanged units into new-version assertions.

    R1: deep-copies all nested scientific material so the new Assertion graph
    is fully independent of the prior Assertion.
    """
    new_map = new_manifest.unit_map()
    unchanged_by_prior = {p.prior_unit_id: p.new_unit_id for p in plan.unchanged_pairs}
    carried: list[Assertion] = []
    records: list[CarriedAssertionRecord] = []

    for prior_a in prior_inventory.assertions:
        uid = prior_inventory.assertion_unit_map.get(prior_a.id)
        if uid is None or uid not in unchanged_by_prior:
            continue
        new_uid = unchanged_by_prior[uid]
        new_unit = new_map[new_uid]
        new_id = _deterministic_carried_id(prior_a.id, new_source_version_id, new_uid)

        # Deep-copy nested scientific material (R1-01).
        new_a = Assertion(
            id=new_id,
            ref_id=new_ref_id,
            subject=_deep_copy_subject(prior_a.subject),
            property=prior_a.property,
            object=_deep_copy_object(prior_a.object),
            conditions=[_deep_copy_condition(c) for c in (prior_a.conditions or [])],
            provenance=None,
            claim_type=prior_a.claim_type,
            source_claim_origin=prior_a.source_claim_origin,
            confidence=prior_a.confidence,
            quality=prior_a.quality,
            missing_unit=prior_a.missing_unit,
            speculative_wording=prior_a.speculative_wording,
            chart_quality_low=prior_a.chart_quality_low,
        )
        # Provenance rebuilt: locator = new unit locator; sentence copied by value.
        from knowledge_curator.schemas.assertions import Provenance

        sentence = prior_a.provenance.sentence if prior_a.provenance else None
        new_a.provenance = Provenance(locator=new_unit.locator, sentence=sentence)

        carried.append(new_a)
        records.append(
            CarriedAssertionRecord(
                old_assertion_id=prior_a.id,
                carried_assertion_id=new_id,
                unit_id=new_uid,
            )
        )
    return carried, records


# ---------------------------------------------------------------------------
# Assertion transition diff
# ---------------------------------------------------------------------------


def compute_transitions(
    *,
    prior_inventory: VersionAssertionInventory,
    delta_batch: DeltaAssertionBatch,
    plan: ContentDeltaPlan,
    carried_records: list[CarriedAssertionRecord],
    new_manifest: VersionContentManifest,
) -> tuple[list[AssertionTransition], bool]:
    """Deterministic transition diff. Returns (transitions, requires_manual_review)."""
    transitions: list[AssertionTransition] = []
    requires_review = False

    # R2-01: FULL_REEXTRACT safe semantics — archive all prior, add all new.
    if plan.mode == DeltaMode.FULL_REEXTRACT_REQUIRED:
        for prior_a in prior_inventory.assertions:
            transitions.append(
                AssertionTransition(
                    action=TransitionAction.ARCHIVE,
                    old_assertion_id=prior_a.id,
                    slot_key=semantic_slot_key(prior_a),
                    reason="full_reextract_prior_archived",
                )
            )
        for new_a in delta_batch.assertions:
            transitions.append(
                AssertionTransition(
                    action=TransitionAction.ADDED,
                    new_assertion_id=new_a.id,
                    slot_key=semantic_slot_key(new_a),
                    reason="full_reextract_new_added",
                )
            )
        return transitions, requires_review

    carried_by_old = {r.old_assertion_id: r.carried_assertion_id for r in carried_records}
    new_by_id = {a.id: a for a in delta_batch.assertions}
    prior_by_id = {a.id: a for a in prior_inventory.assertions}

    # 1. Unchanged carried -> supersede old -> new
    for r in carried_records:
        transitions.append(
            AssertionTransition(
                action=TransitionAction.SUPERSEDE,
                old_assertion_id=r.old_assertion_id,
                new_assertion_id=r.carried_assertion_id,
                slot_key=semantic_slot_key(prior_by_id[r.old_assertion_id])
                if r.old_assertion_id in prior_by_id
                else "",
                reason="unchanged_unit_carry_forward",
            )
        )

    # 2. Removed unit assertions -> archive
    removed_units = set(plan.removed_unit_ids)
    for prior_a in prior_inventory.assertions:
        uid = prior_inventory.assertion_unit_map.get(prior_a.id)
        if uid is not None and uid in removed_units:
            transitions.append(
                AssertionTransition(
                    action=TransitionAction.ARCHIVE,
                    old_assertion_id=prior_a.id,
                    slot_key=semantic_slot_key(prior_a),
                    reason="removed_unit",
                )
            )

    # 3. Modified units: semantic slot matching
    modified_pairs = {p.prior_unit_id: p.new_unit_id for p in plan.modified_pairs}
    for pu_id, nu_id in modified_pairs.items():
        old_in_unit = [
            a
            for a in prior_inventory.assertions
            if prior_inventory.assertion_unit_map.get(a.id) == pu_id
        ]
        new_in_unit = [
            a
            for a in delta_batch.assertions
            if delta_batch.assertion_unit_map.get(a.id) == nu_id
        ]

        old_slots: dict[str, list[Assertion]] = {}
        for a in old_in_unit:
            old_slots.setdefault(semantic_slot_key(a), []).append(a)
        new_slots: dict[str, list[Assertion]] = {}
        for a in new_in_unit:
            new_slots.setdefault(semantic_slot_key(a), []).append(a)

        # Duplicate slots -> REVIEW_REQUIRED for this unit
        if any(len(v) > 1 for v in old_slots.values()) or any(
            len(v) > 1 for v in new_slots.values()
        ):
            requires_review = True
            transitions.append(
                AssertionTransition(
                    action=TransitionAction.REVIEW_REQUIRED,
                    slot_key="",
                    reason=f"duplicate semantic slot in modified unit {pu_id}->{nu_id}",
                )
            )
            continue

        matched_new: set[str] = set()
        for slot, old_list in old_slots.items():
            old_a = old_list[0]
            if slot in new_slots:
                new_a = new_slots[slot][0]
                matched_new.add(new_a.id)
                transitions.append(
                    AssertionTransition(
                        action=TransitionAction.SUPERSEDE,
                        old_assertion_id=old_a.id,
                        new_assertion_id=new_a.id,
                        slot_key=slot,
                        reason="modified_unit_slot_match",
                    )
                )
            else:
                transitions.append(
                    AssertionTransition(
                        action=TransitionAction.ARCHIVE,
                        old_assertion_id=old_a.id,
                        slot_key=slot,
                        reason="modified_unit_old_slot_unmatched",
                    )
                )
        for slot, new_list in new_slots.items():
            new_a = new_list[0]
            if new_a.id not in matched_new:
                transitions.append(
                    AssertionTransition(
                        action=TransitionAction.ADDED,
                        new_assertion_id=new_a.id,
                        slot_key=slot,
                        reason="modified_unit_new_slot_unmatched",
                    )
                )

    # 4. Added unit assertions -> added only
    added_units = set(plan.added_unit_ids)
    for a in delta_batch.assertions:
        uid = delta_batch.assertion_unit_map.get(a.id)
        if uid is not None and uid in added_units:
            transitions.append(
                AssertionTransition(
                    action=TransitionAction.ADDED,
                    new_assertion_id=a.id,
                    slot_key=semantic_slot_key(a),
                    reason="added_unit",
                )
            )

    return transitions, requires_review


# ---------------------------------------------------------------------------
# RevisionPackage builder
# ---------------------------------------------------------------------------


class RevisionPackageBuilder:
    """Build deterministic RevisionPackage from upgrade intent + manifests + assertions."""

    def __init__(self, registry: SourceVersionRegistry) -> None:
        self._registry = registry

    def validate_intent(self, intent: VersionUpgradeIntent) -> dict[str, Any]:
        work = self._registry.get_work(intent.work_id)
        if work is None:
            raise ValueError(f"intent work not found: {intent.work_id}")
        prior = self._registry.get_source_version(intent.prior_source_version_id)
        new = self._registry.get_source_version(intent.new_source_version_id)
        if prior is None:
            raise ValueError(f"prior source version not found: {intent.prior_source_version_id}")
        if new is None:
            raise ValueError(f"new source version not found: {intent.new_source_version_id}")
        if prior.work_id != intent.work_id or new.work_id != intent.work_id:
            raise ValueError("source versions do not belong to intent work")
        if new.prior_source_version_id != prior.source_version_id:
            raise ValueError("new.prior_source_version_id does not match prior")
        # R1-03: intent relation must equal new record relation
        if new.relation != intent.relation:
            raise ValueError(
                f"intent relation {intent.relation.value} != new.relation {new.relation.value}"
            )
        # R1-03: prior must be bound to a published KB version
        if not prior.kb_version_id or not prior.snapshot_id:
            raise ValueError(
                "prior source version is not bound to a published KB version"
            )
        if intent.relation == VersionRelation.PREPRINT_TO_JOURNAL:
            if prior.source_kind != SourceKind.PREPRINT:
                raise ValueError("P2J prior must be PREPRINT")
            if new.source_kind != SourceKind.JOURNAL:
                raise ValueError("P2J new must be JOURNAL")
        return {"prior": prior, "new": new, "work": work}

    def build(
        self,
        *,
        intent: VersionUpgradeIntent,
        prior_manifest: VersionContentManifest,
        new_manifest: VersionContentManifest,
        prior_inventory: VersionAssertionInventory,
        delta_batch: DeltaAssertionBatch,
        segmentation_reset: bool = False,
        trace_id: str = "",
        provenance_id: str = "",
    ) -> RevisionPackage:
        ctx = self.validate_intent(intent)
        prior = ctx["prior"]
        new = ctx["new"]

        # R1-02: validate manifest/inventory/batch identity against registry lineage.
        _validate_manifest_identity(
            prior_manifest,
            expected_version_id=prior.source_version_id,
            expected_ref_id=prior.ref_id,
            expected_fingerprint=prior.source_fingerprint,
            label="prior",
        )
        _validate_manifest_identity(
            new_manifest,
            expected_version_id=new.source_version_id,
            expected_ref_id=new.ref_id,
            expected_fingerprint=new.source_fingerprint,
            label="new",
        )
        _validate_inventory_identity(
            prior_inventory,
            expected_version_id=prior.source_version_id,
            expected_ref_id=prior.ref_id,
            label="prior",
        )
        _validate_inventory_identity(
            delta_batch,
            expected_version_id=new.source_version_id,
            expected_ref_id=new.ref_id,
            label="delta",
        )
        # R2-03: strict prior inventory validation for publication-bound builder.
        # Malformed prior material must fail closed, not trigger FULL_REEXTRACT.
        validate_prior_inventory(prior_inventory, prior_manifest)

        plan = compute_content_delta(
            prior_manifest,
            new_manifest,
            inventory=prior_inventory,
            segmentation_reset=segmentation_reset,
        )

        # R1-05: validate batch in ALL modes
        validate_delta_batch(delta_batch, plan, new_manifest)

        # R1-12: FULL_REEXTRACT has no carry-forward
        if plan.mode == DeltaMode.FULL_REEXTRACT_REQUIRED:
            carried, carried_records = [], []
        else:
            carried, carried_records = carry_forward_unchanged(
                prior_inventory=prior_inventory,
                plan=plan,
                new_manifest=new_manifest,
                new_ref_id=new_manifest.ref_id,
                new_source_version_id=new.source_version_id,
            )

        # Target assertion set
        if plan.mode == DeltaMode.DELTA_SAFE:
            target = carried + list(delta_batch.assertions)
        else:
            target = list(delta_batch.assertions)

        # Transitions
        transitions, requires_review = compute_transitions(
            prior_inventory=prior_inventory,
            delta_batch=delta_batch,
            plan=plan,
            carried_records=carried_records,
            new_manifest=new_manifest,
        )

        supersede = {
            t.old_assertion_id: t.new_assertion_id
            for t in transitions
            if t.action == TransitionAction.SUPERSEDE
            and t.old_assertion_id
            and t.new_assertion_id
        }
        archive = [
            t.old_assertion_id
            for t in transitions
            if t.action == TransitionAction.ARCHIVE and t.old_assertion_id
        ]
        added = [
            t.new_assertion_id
            for t in transitions
            if t.action == TransitionAction.ADDED and t.new_assertion_id
        ]

        if plan.mode == DeltaMode.REVIEW_REQUIRED:
            requires_review = True

        # R2-04/05: side-labelled package material with unit binding + trace/provenance.
        def _unit_mat(u: ContentUnit) -> dict:
            return {
                "id": u.unit_id,
                "loc": u.locator,
                "kind": u.kind.value,
                "hash": u.content_hash,
                "prior_id": u.prior_unit_id,
            }

        # Build target assertion -> unit binding map
        binding: dict[str, str] = {}
        binding.update(delta_batch.assertion_unit_map)
        for r in carried_records:
            binding[r.carried_assertion_id] = r.unit_id

        package_id = _hash_json(
            {
                "work_id": intent.work_id,
                "prior_sv": intent.prior_source_version_id,
                "new_sv": intent.new_source_version_id,
                "relation": intent.relation.value,
                "prior_ref": prior_manifest.ref_id,
                "new_ref": new_manifest.ref_id,
                "prior_fp": prior_manifest.source_fingerprint,
                "new_fp": new_manifest.source_fingerprint,
                "prior_kb": prior.kb_version_id,
                "prior_snap": prior.snapshot_id,
                "plan_mode": plan.mode.value,
                "prior_units": sorted(
                    [_unit_mat(u) for u in prior_manifest.units], key=lambda x: x["id"]
                ),
                "new_units": sorted(
                    [_unit_mat(u) for u in new_manifest.units], key=lambda x: x["id"]
                ),
                "unchanged_pairs": sorted(
                    [[p.prior_unit_id, p.new_unit_id] for p in plan.unchanged_pairs]
                ),
                "modified_pairs": sorted(
                    [[p.prior_unit_id, p.new_unit_id] for p in plan.modified_pairs]
                ),
                "added_units": sorted(plan.added_unit_ids),
                "removed_units": sorted(plan.removed_unit_ids),
                "extraction": sorted(plan.extraction_unit_ids),
                "processed": sorted(delta_batch.processed_unit_ids),
                "target": sorted(
                    [
                        {
                            "id": a.id,
                            "ref": a.ref_id,
                            "sem": semantic_payload_hash(a),
                            "loc": a.provenance.locator if a.provenance else "",
                            "sent": a.provenance.sentence if a.provenance else "",
                            "unit": binding.get(a.id, ""),
                        }
                        for a in target
                    ],
                    key=lambda x: x["id"],
                ),
                "supersede": sorted(supersede.items()),
                "archive": sorted(archive),
                "added": sorted(added),
                "trace_id": trace_id,
                "provenance_id": provenance_id,
            }
        )[:16]

        lifecycle_reason = (
            "preprint_to_journal"
            if intent.relation == VersionRelation.PREPRINT_TO_JOURNAL
            else intent.relation.value
        )

        return RevisionPackage(
            package_id=package_id,
            work_id=intent.work_id,
            prior_source_version_id=intent.prior_source_version_id,
            new_source_version_id=intent.new_source_version_id,
            relation=intent.relation,
            prior_ref_id=prior_manifest.ref_id,
            new_ref_id=new_manifest.ref_id,
            prior_bound_kb_version_id=prior.kb_version_id,
            content_delta=plan,
            target_assertions=target,
            supersede_actions=supersede,
            archive_actions=archive,
            added_assertion_ids=added,
            carried_records=carried_records,
            transitions=transitions,
            diagnostics={
                "delta_mode": plan.mode.value,
                "extraction_unit_ids": list(plan.extraction_unit_ids),
                "carried_count": len(carried_records),
                "target_count": len(target),
            },
            requires_manual_review=requires_review,
            lifecycle_reason=lifecycle_reason,
            trace_id=trace_id,
            provenance_id=provenance_id,
        )


# ---------------------------------------------------------------------------
# RevisionPackage -> RevisionDraft (frozen §7 lifecycle; do NOT apply)
# ---------------------------------------------------------------------------


def package_to_revision_draft(package: RevisionPackage):
    """Build a frozen §7 RevisionDraft. Does NOT call apply_revision()."""
    from knowledge_curator.core.lifecycle import build_revision_draft
    from knowledge_curator.schemas.lifecycle import LifecycleReason

    reason_map = {
        "preprint_to_journal": LifecycleReason.PREPRINT_TO_JOURNAL,
        "revision_of": LifecycleReason.MANUAL_CORRECTION,
        "corrected_version": LifecycleReason.MANUAL_CORRECTION,
        "explicit_same_work": LifecycleReason.MANUAL_CORRECTION,
    }
    trigger = reason_map.get(package.lifecycle_reason, LifecycleReason.MANUAL_CORRECTION)

    affected = sorted(
        set(package.supersede_actions.keys())
        | set(package.archive_actions)
        | set(package.added_assertion_ids)
    )

    # R1-07: replacement ids = supersede targets + added ids (deduped, sorted).
    replacement = sorted(
        set(package.supersede_actions.values()) | set(package.added_assertion_ids)
    )

    # base_version_id left None: publication-time bind (see plan §13).
    # R3: lifecycle subject is PRIOR ref — transition actions archive/supersede
    # prior-version assertions. New journal ref stays active.
    return build_revision_draft(
        revision_id=package.package_id,
        ref_id=package.prior_ref_id,
        trigger=trigger,
        base_version_id=None,
        affected_assertion_ids=affected,
        archive_actions=list(package.archive_actions),
        supersede_actions=dict(package.supersede_actions),
        replacement_assertion_ids=replacement,
        evidence_refs=[package.prior_source_version_id, package.new_source_version_id],
        rationale=f"delta {package.content_delta.mode.value}",
        trace_id=package.trace_id,
        provenance_id=package.provenance_id,
    )
