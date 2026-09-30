"""Lifecycle core: revision draft, risk gate, retraction/corrigendum, publish.

Phase 5.0 + R1 hardening:
- crash-safe resume (FINALIZED / STAGED / CONFLICT);
- strict material idempotency;
- explicit base_version validation;
- deterministic snapshot/version reuse on retry.

Composes existing VersionStore with append-only LifecycleStore + EventOutbox.
Never physically deletes historical structural/USDO/vector identities.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from knowledge_curator.ports.lifecycle_store import EventOutbox, LifecycleStore
from knowledge_curator.ports.version_store import VersionStore
from knowledge_curator.schemas.commit import SnapshotManifest
from knowledge_curator.schemas.lifecycle import (
    AssertionLifecycleRecord,
    AssertionLifecycleStatus,
    DocumentLifecycleRecord,
    DocumentLifecycleStatus,
    LifecycleEvent,
    LifecycleEventType,
    LifecycleReason,
    RevisionDraft,
    RiskDecision,
    assertion_material_equal,
    document_material_equal,
    event_material_equal,
)


def _hash_json(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluate_risk_gate(draft: RevisionDraft) -> RiskDecision:
    """§7.3 rule-level risk gate. No numeric global score."""
    if draft.trigger == LifecycleReason.RETRACTION and not draft.verified_external_trigger:
        return RiskDecision.MANUAL_ADJUDICATION_REQUIRED
    if draft.trigger == LifecycleReason.RETRACTION and draft.verified_external_trigger:
        return RiskDecision.AUTO_RULE_REVIEW_ELIGIBLE

    meta = draft.metadata or {}
    high_conf = bool(meta.get("high_confidence"))
    multi_source = bool(meta.get("multi_source"))
    no_controversy = not bool(meta.get("unresolved_controversy"))
    if high_conf and multi_source and no_controversy:
        return RiskDecision.AUTO_RULE_REVIEW_ELIGIBLE
    return RiskDecision.MANUAL_ADJUDICATION_REQUIRED


def build_revision_draft(
    *,
    revision_id: str,
    ref_id: str,
    trigger: LifecycleReason,
    base_version_id: Optional[str],
    affected_assertion_ids: Optional[list[str]] = None,
    archive_actions: Optional[list[str]] = None,
    supersede_actions: Optional[dict[str, str]] = None,
    replacement_assertion_ids: Optional[list[str]] = None,
    evidence_refs: Optional[list[str]] = None,
    rationale: str = "",
    verified_external_trigger: bool = False,
    trace_id: str = "",
    provenance_id: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> RevisionDraft:
    draft = RevisionDraft(
        revision_id=revision_id,
        ref_id=ref_id,
        trigger=trigger,
        base_version_id=base_version_id,
        affected_assertion_ids=list(affected_assertion_ids or []),
        archive_actions=list(archive_actions or []),
        supersede_actions=dict(supersede_actions or {}),
        replacement_assertion_ids=list(replacement_assertion_ids or []),
        evidence_refs=list(evidence_refs or []),
        rationale=rationale,
        verified_external_trigger=verified_external_trigger,
        trace_id=trace_id,
        provenance_id=provenance_id,
        metadata=dict(metadata or {}),
    )
    decision = evaluate_risk_gate(draft)
    draft.risk_decision = decision
    draft.manual_adjudication_required = decision == RiskDecision.MANUAL_ADJUDICATION_REQUIRED
    return draft


class LifecycleState(str, Enum):
    FINALIZED = "finalized"
    STAGED = "staged"
    CONFLICT = "conflict"
    ABSENT = "absent"


@dataclass
class LifecyclePublishResult:
    revision_id: str
    lifecycle_id: str
    version_id: Optional[str]
    snapshot_id: Optional[str]
    document_status: str
    archived_assertion_ids: list[str] = field(default_factory=list)
    superseded_assertion_ids: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    idempotent_hit: bool = False
    resumed: bool = False
    staged: bool = False


class LifecycleRevisionCoordinator:
    """Publish lifecycle revisions as NEW immutable KB versions."""

    def __init__(
        self,
        *,
        lifecycle_store: LifecycleStore,
        outbox: EventOutbox,
        version_store: VersionStore,
    ) -> None:
        self._lifecycle = lifecycle_store
        self._outbox = outbox
        self._versions = version_store

    # ---- identity helpers ----

    def _lifecycle_id_for_revision(self, revision_id: str, kind: str) -> str:
        return _hash_json({"revision_id": revision_id, "kind": kind})[:16]

    def _event_id(self, event_type: str, ref_id: str, revision_id: str, extra: str = "") -> str:
        return _hash_json(
            {"type": event_type, "ref_id": ref_id, "revision_id": revision_id, "extra": extra}
        )[:16]

    # ---- base version validation (R1-B) ----

    def _validate_base_version(self, base_version_id: Optional[str]) -> str:
        """Require explicit base to exist, be published, and equal current version."""
        cur = self._versions.current_version()
        current_id = cur.version_id if cur else None
        if base_version_id is None:
            if current_id is None:
                raise ValueError("no current version available as base")
            return current_id
        ver = self._versions.get_version(base_version_id)
        if ver is None:
            raise ValueError(f"base_version_id does not exist: {base_version_id}")
        if not ver.published:
            raise ValueError(f"base_version_id is not published: {base_version_id}")
        if current_id is not None and base_version_id != current_id:
            raise ValueError(
                f"base_version_id {base_version_id} is not the current version {current_id}"
            )
        return base_version_id

    # ---- manifest / snapshot ----

    def _build_lifecycle_manifest(
        self,
        *,
        base_manifest: Optional[SnapshotManifest],
        ref_id: str,
        source_fingerprint: str,
        lifecycle_id: str,
    ) -> SnapshotManifest:
        if base_manifest is not None:
            manifest = SnapshotManifest(
                ref_id=base_manifest.ref_id,
                source_fingerprint=base_manifest.source_fingerprint,
                assertion_hashes=list(base_manifest.assertion_hashes),
                usdo_hashes=list(base_manifest.usdo_hashes),
                vector_ids=list(base_manifest.vector_ids),
                metadata_hash=base_manifest.metadata_hash,
                decision_hashes=list(base_manifest.decision_hashes),
                structural_stage_id=base_manifest.structural_stage_id,
                usdo_record_ids=list(base_manifest.usdo_record_ids),
                lifecycle_hashes=[lifecycle_id],
                lifecycle_record_ids=[lifecycle_id],
            )
        else:
            manifest = SnapshotManifest(
                ref_id=ref_id,
                source_fingerprint=source_fingerprint,
                assertion_hashes=[],
                usdo_hashes=[],
                vector_ids=[],
                metadata_hash=_hash_json({"ref_id": ref_id}),
                decision_hashes=[],
                lifecycle_hashes=[lifecycle_id],
                lifecycle_record_ids=[lifecycle_id],
            )
        manifest.content_hash = _hash_json(manifest.stable_payload())
        return manifest

    def _find_base_manifest(
        self, base_version_id: Optional[str], *, validate: bool = True
    ) -> Optional[SnapshotManifest]:
        if validate:
            version_id = self._validate_base_version(base_version_id)
        else:
            version_id = base_version_id
            if version_id is None:
                cur = self._versions.current_version()
                version_id = cur.version_id if cur else None
        if not version_id:
            return None
        ver = self._versions.get_version(version_id)
        if ver is None:
            return None
        snap = self._versions.get_snapshot(ver.snapshot_id)
        return snap.manifest if snap else None

    def _emit(self, event: LifecycleEvent) -> str:
        stored = self._outbox.append(event)
        return stored.event_id

    def _event_present(self, event_id: str) -> bool:
        for e in self._outbox.list_all():
            if e.event_id == event_id:
                return True
        return False

    # ---- state classification (R1-A) ----

    def _classify_document_state(
        self,
        lifecycle_id: str,
        expected: DocumentLifecycleRecord,
        required_event_ids: list[str],
    ) -> LifecycleState:
        existing = self._lifecycle.get_document_record(lifecycle_id)
        if existing is None:
            return LifecycleState.ABSENT
        if not document_material_equal(existing, expected) and existing.effective_version_id is None:
            # staged record with different material -> conflict
            if (
                existing.ref_id != expected.ref_id
                or existing.status != expected.status
                or existing.reason != expected.reason
                or list(existing.affected_assertion_ids) != list(expected.affected_assertion_ids)
                or existing.evidence_refs != expected.evidence_refs
                or existing.rationale != expected.rationale
                or existing.source_fingerprint != expected.source_fingerprint
            ):
                return LifecycleState.CONFLICT
        if not document_material_equal(existing, expected):
            # bound finalized record with different material -> conflict
            return LifecycleState.CONFLICT

        events_ok = all(self._event_present(eid) for eid in required_event_ids)
        if existing.effective_version_id is not None and events_ok:
            return LifecycleState.FINALIZED
        return LifecycleState.STAGED

    def _finalize_staged_retraction(
        self,
        *,
        draft: RevisionDraft,
        lifecycle_id: str,
        assertion_ids: list[str],
        source_fingerprint: str,
        expected_doc: DocumentLifecycleRecord,
        required_event_specs: list[tuple[LifecycleEventType, str]],
    ) -> LifecyclePublishResult:
        """Resume a staged/partial retraction to final state (R1-A)."""
        existing = self._lifecycle.get_document_record(lifecycle_id)
        assert existing is not None

        # 1) resume snapshot/version using deterministic manifest hash.
        #    Resume path must NOT re-validate base==current (post-publish retry).
        base_manifest = self._find_base_manifest(draft.base_version_id, validate=False)
        manifest = self._build_lifecycle_manifest(
            base_manifest=base_manifest,
            ref_id=draft.ref_id,
            source_fingerprint=source_fingerprint or expected_doc.source_fingerprint,
            lifecycle_id=lifecycle_id,
        )
        snap = self._versions.create_snapshot(manifest)  # idempotent by content hash
        ver = self._versions.get_version_by_snapshot(snap.snapshot_id)
        if ver is None:
            ver = self._versions.publish_version(snap.snapshot_id)

        # 2) bind if not yet bound
        if existing.effective_version_id is None:
            self._lifecycle.bind_effective_version(lifecycle_id, ver.version_id)
        elif existing.effective_version_id != ver.version_id:
            raise ValueError(
                f"lifecycle {lifecycle_id} bound to {existing.effective_version_id}, "
                f"cannot rebind to {ver.version_id}"
            )

        # 3) ensure required events (idempotent append)
        event_ids: list[str] = []
        for etype, extra in required_event_specs:
            eid = self._event_id(etype.value, draft.ref_id, draft.revision_id, extra=extra)
            if not self._event_present(eid):
                self._emit(
                    LifecycleEvent(
                        event_id=eid,
                        event_type=etype,
                        ref_id=draft.ref_id,
                        affected_assertion_ids=assertion_ids,
                        old_version_id=draft.base_version_id,
                        new_version_id=ver.version_id,
                        lifecycle_id=lifecycle_id,
                        revision_id=draft.revision_id,
                        trace_id=draft.trace_id,
                        provenance_id=draft.provenance_id,
                        payload=self._event_payload(etype, draft, assertion_ids),
                    )
                )
            event_ids.append(eid)

        return LifecyclePublishResult(
            revision_id=draft.revision_id,
            lifecycle_id=lifecycle_id,
            version_id=ver.version_id,
            snapshot_id=snap.snapshot_id,
            document_status=existing.status.value,
            archived_assertion_ids=list(existing.affected_assertion_ids),
            event_ids=event_ids,
            resumed=True,
        )

    def _event_payload(
        self,
        etype: LifecycleEventType,
        draft: RevisionDraft,
        assertion_ids: list[str],
    ) -> dict[str, Any]:
        base = {
            "invalidate": ["qa_evidence_cache", "training_export", "audit_metrics"],
        }
        if etype == LifecycleEventType.KB_DOCUMENT_RETRACTED:
            base["action"] = "retract"
        elif etype == LifecycleEventType.KB_ASSERTIONS_ARCHIVED:
            base["action"] = "archive_assertions"
        elif etype == LifecycleEventType.KB_ASSERTIONS_SUPERSEDED:
            base["action"] = "supersede_assertions"
            base["supersede_actions"] = dict(draft.supersede_actions)
        elif etype == LifecycleEventType.KB_REVISION_PUBLISHED:
            base["revision_kind"] = draft.trigger.value
        elif etype == LifecycleEventType.KB_CORRIGENDUM_PUBLISHED:
            base["revision_kind"] = draft.trigger.value
        elif etype == LifecycleEventType.KB_VERSION_ROLLED_BACK:
            base["action"] = "rollback"
        return base

    def _retraction_event_specs(
        self, draft: RevisionDraft, assertion_ids: list[str]
    ) -> list[tuple[LifecycleEventType, str]]:
        return [
            (LifecycleEventType.KB_DOCUMENT_RETRACTED, ""),
            (
                LifecycleEventType.KB_ASSERTIONS_ARCHIVED,
                ",".join(assertion_ids),
            ),
            (LifecycleEventType.KB_REVISION_PUBLISHED, "retraction"),
        ]

    # ---- retraction ----

    def apply_retraction(
        self,
        draft: RevisionDraft,
        *,
        all_assertion_ids: Optional[list[str]] = None,
        source_fingerprint: str = "",
    ) -> LifecyclePublishResult:
        """Verified retraction: RETRACTED doc + ARCHIVED assertions + new version."""
        if draft.trigger != LifecycleReason.RETRACTION:
            raise ValueError("apply_retraction requires trigger=retraction")
        if not draft.verified_external_trigger:
            raise ValueError("retraction requires verified_external_trigger")
        if draft.risk_decision != RiskDecision.AUTO_RULE_REVIEW_ELIGIBLE:
            raise ValueError("retraction draft is not rule-eligible")

        # R1-B: validate base only for NEW publication. Resume/FINALIZED replay
        # must not be blocked after a post-publish failure advanced current.
        lifecycle_id = self._lifecycle_id_for_revision(draft.revision_id, "retraction")
        assertion_ids = list(
            dict.fromkeys(list(draft.affected_assertion_ids) + list(all_assertion_ids or []))
        )

        # Probe existing state first (without full material compare for base).
        existing_probe = self._lifecycle.get_document_record(lifecycle_id)
        if existing_probe is None:
            validated_base = self._validate_base_version(draft.base_version_id)
            draft.base_version_id = validated_base
        else:
            # Resume/replay path: keep the original base binding.
            if draft.base_version_id is None:
                draft.base_version_id = existing_probe.effective_version_id

        base_manifest = self._find_base_manifest(draft.base_version_id, validate=False)
        fp = source_fingerprint or (base_manifest.source_fingerprint if base_manifest else "")

        expected_doc = DocumentLifecycleRecord(
            lifecycle_id=lifecycle_id,
            ref_id=draft.ref_id,
            status=DocumentLifecycleStatus.RETRACTED,
            reason=LifecycleReason.RETRACTION,
            effective_version_id=None,
            source_fingerprint=fp,
            affected_assertion_ids=assertion_ids,
            rationale=draft.rationale,
            evidence_refs=list(draft.evidence_refs),
            trace_id=draft.trace_id,
            provenance_id=draft.provenance_id,
            revision_id=draft.revision_id,
        )
        event_specs = self._retraction_event_specs(draft, assertion_ids)
        required_event_ids = [
            self._event_id(etype.value, draft.ref_id, draft.revision_id, extra=extra)
            for etype, extra in event_specs
        ]
        state = self._classify_document_state(lifecycle_id, expected_doc, required_event_ids)

        if state == LifecycleState.CONFLICT:
            raise ValueError(f"conflicting lifecycle material for {lifecycle_id}")
        if state == LifecycleState.FINALIZED:
            existing = self._lifecycle.get_document_record(lifecycle_id)
            return LifecyclePublishResult(
                revision_id=draft.revision_id,
                lifecycle_id=lifecycle_id,
                version_id=existing.effective_version_id if existing else None,
                snapshot_id=None,
                document_status=existing.status.value if existing else "retracted",
                archived_assertion_ids=list(existing.affected_assertion_ids) if existing else assertion_ids,
                event_ids=required_event_ids,
                idempotent_hit=True,
            )
        if state == LifecycleState.STAGED:
            return self._finalize_staged_retraction(
                draft=draft,
                lifecycle_id=lifecycle_id,
                assertion_ids=assertion_ids,
                source_fingerprint=fp,
                expected_doc=expected_doc,
                required_event_specs=event_specs,
            )

        # ABSENT: full path
        self._lifecycle.append_document_record(expected_doc)
        assertion_recs = [
            AssertionLifecycleRecord(
                assertion_id=aid,
                ref_id=draft.ref_id,
                status=AssertionLifecycleStatus.ARCHIVED,
                lifecycle_id=lifecycle_id,
                revision_id=draft.revision_id,
                effective_version_id=None,
            )
            for aid in assertion_ids
        ]
        self._lifecycle.append_assertion_records(assertion_recs)

        manifest = self._build_lifecycle_manifest(
            base_manifest=base_manifest,
            ref_id=draft.ref_id,
            source_fingerprint=fp,
            lifecycle_id=lifecycle_id,
        )
        snap = self._versions.create_snapshot(manifest)
        ver = self._versions.publish_version(snap.snapshot_id)
        self._lifecycle.bind_effective_version(lifecycle_id, ver.version_id)

        event_ids = []
        for etype, extra in event_specs:
            event_ids.append(
                self._emit(
                    LifecycleEvent(
                        event_id=self._event_id(etype.value, draft.ref_id, draft.revision_id, extra=extra),
                        event_type=etype,
                        ref_id=draft.ref_id,
                        affected_assertion_ids=assertion_ids,
                        old_version_id=draft.base_version_id,
                        new_version_id=ver.version_id,
                        lifecycle_id=lifecycle_id,
                        revision_id=draft.revision_id,
                        trace_id=draft.trace_id,
                        provenance_id=draft.provenance_id,
                        payload=self._event_payload(etype, draft, assertion_ids),
                    )
                )
            )

        return LifecyclePublishResult(
            revision_id=draft.revision_id,
            lifecycle_id=lifecycle_id,
            version_id=ver.version_id,
            snapshot_id=snap.snapshot_id,
            document_status=DocumentLifecycleStatus.RETRACTED.value,
            archived_assertion_ids=assertion_ids,
            event_ids=event_ids,
        )

    def binding_for(self, lifecycle_id: str) -> Optional[str]:
        rec = self._lifecycle.get_document_record(lifecycle_id)
        return rec.effective_version_id if rec else None

    # ---- corrigendum / generic revision ----

    def apply_revision(
        self,
        draft: RevisionDraft,
        *,
        source_fingerprint: str = "",
    ) -> LifecyclePublishResult:
        """Corrigendum / manual correction: supersede/archive only affected assertions."""
        if draft.manual_adjudication_required and draft.trigger != LifecycleReason.RETRACTION:
            if draft.risk_decision == RiskDecision.MANUAL_ADJUDICATION_REQUIRED:
                raise ValueError("manual adjudication required for this draft")

        lifecycle_id = self._lifecycle_id_for_revision(draft.revision_id, "revision")
        existing_probe = self._lifecycle.get_document_record(lifecycle_id)
        if existing_probe is None:
            validated_base = self._validate_base_version(draft.base_version_id)
            draft.base_version_id = validated_base
        elif draft.base_version_id is None:
            draft.base_version_id = existing_probe.effective_version_id

        archived = list(draft.archive_actions)
        superseded = list(draft.supersede_actions.keys())
        affected = list(dict.fromkeys(list(draft.affected_assertion_ids) + archived + superseded))
        base_manifest = self._find_base_manifest(draft.base_version_id, validate=False)
        fp = source_fingerprint or (base_manifest.source_fingerprint if base_manifest else "")

        doc_status = DocumentLifecycleStatus.ACTIVE
        if draft.trigger == LifecycleReason.PREPRINT_TO_JOURNAL:
            doc_status = DocumentLifecycleStatus.SUPERSEDED

        expected_doc = DocumentLifecycleRecord(
            lifecycle_id=lifecycle_id,
            ref_id=draft.ref_id,
            status=doc_status,
            reason=draft.trigger,
            effective_version_id=None,
            source_fingerprint=fp,
            affected_assertion_ids=affected,
            rationale=draft.rationale,
            evidence_refs=list(draft.evidence_refs),
            trace_id=draft.trace_id,
            provenance_id=draft.provenance_id,
            revision_id=draft.revision_id,
        )
        event_specs: list[tuple[LifecycleEventType, str]] = []
        if superseded:
            event_specs.append(
                (
                    LifecycleEventType.KB_ASSERTIONS_SUPERSEDED,
                    ",".join(superseded),
                )
            )
        if archived:
            event_specs.append(
                (
                    LifecycleEventType.KB_ASSERTIONS_ARCHIVED,
                    ",".join(archived),
                )
            )
        kind = (
            LifecycleEventType.KB_CORRIGENDUM_PUBLISHED
            if draft.trigger == LifecycleReason.CORRIGENDUM
            else LifecycleEventType.KB_REVISION_PUBLISHED
        )
        event_specs.append((kind, draft.trigger.value))

        required_event_ids = [
            self._event_id(etype.value, draft.ref_id, draft.revision_id, extra=extra)
            for etype, extra in event_specs
        ]
        state = self._classify_document_state(lifecycle_id, expected_doc, required_event_ids)

        if state == LifecycleState.CONFLICT:
            raise ValueError(f"conflicting lifecycle material for {lifecycle_id}")
        if state == LifecycleState.FINALIZED:
            existing = self._lifecycle.get_document_record(lifecycle_id)
            return LifecyclePublishResult(
                revision_id=draft.revision_id,
                lifecycle_id=lifecycle_id,
                version_id=existing.effective_version_id if existing else None,
                snapshot_id=None,
                document_status=existing.status.value if existing else doc_status.value,
                superseded_assertion_ids=superseded,
                archived_assertion_ids=archived,
                event_ids=required_event_ids,
                idempotent_hit=True,
            )
        if state == LifecycleState.STAGED:
            return self._finalize_staged_retraction(
                draft=draft,
                lifecycle_id=lifecycle_id,
                assertion_ids=affected,
                source_fingerprint=fp,
                expected_doc=expected_doc,
                required_event_specs=event_specs,
            )

        # ABSENT
        self._lifecycle.append_document_record(expected_doc)
        assertion_recs: list[AssertionLifecycleRecord] = []
        for aid in archived:
            assertion_recs.append(
                AssertionLifecycleRecord(
                    assertion_id=aid,
                    ref_id=draft.ref_id,
                    status=AssertionLifecycleStatus.ARCHIVED,
                    lifecycle_id=lifecycle_id,
                    revision_id=draft.revision_id,
                )
            )
        for old_id, new_id in draft.supersede_actions.items():
            assertion_recs.append(
                AssertionLifecycleRecord(
                    assertion_id=old_id,
                    ref_id=draft.ref_id,
                    status=AssertionLifecycleStatus.SUPERSEDED,
                    lifecycle_id=lifecycle_id,
                    revision_id=draft.revision_id,
                    superseded_by_assertion_id=new_id,
                )
            )
        self._lifecycle.append_assertion_records(assertion_recs)

        manifest = self._build_lifecycle_manifest(
            base_manifest=base_manifest,
            ref_id=draft.ref_id,
            source_fingerprint=fp,
            lifecycle_id=lifecycle_id,
        )
        snap = self._versions.create_snapshot(manifest)
        ver = self._versions.publish_version(snap.snapshot_id)
        self._lifecycle.bind_effective_version(lifecycle_id, ver.version_id)

        event_ids = []
        for etype, extra in event_specs:
            event_ids.append(
                self._emit(
                    LifecycleEvent(
                        event_id=self._event_id(etype.value, draft.ref_id, draft.revision_id, extra=extra),
                        event_type=etype,
                        ref_id=draft.ref_id,
                        affected_assertion_ids=affected,
                        old_version_id=draft.base_version_id,
                        new_version_id=ver.version_id,
                        lifecycle_id=lifecycle_id,
                        revision_id=draft.revision_id,
                        trace_id=draft.trace_id,
                        provenance_id=draft.provenance_id,
                        payload=self._event_payload(etype, draft, affected),
                    )
                )
            )

        return LifecyclePublishResult(
            revision_id=draft.revision_id,
            lifecycle_id=lifecycle_id,
            version_id=ver.version_id,
            snapshot_id=snap.snapshot_id,
            document_status=doc_status.value,
            archived_assertion_ids=archived,
            superseded_assertion_ids=superseded,
            event_ids=event_ids,
        )

    def emit_rollback_event(
        self,
        *,
        ref_id: str,
        from_version_id: Optional[str],
        to_version_id: str,
        trace_id: str = "",
        provenance_id: str = "",
    ) -> str:
        return self._emit(
            LifecycleEvent(
                event_id=self._event_id(
                    LifecycleEventType.KB_VERSION_ROLLED_BACK.value,
                    ref_id,
                    f"{from_version_id}->{to_version_id}",
                ),
                event_type=LifecycleEventType.KB_VERSION_ROLLED_BACK,
                ref_id=ref_id,
                old_version_id=from_version_id,
                new_version_id=to_version_id,
                trace_id=trace_id,
                provenance_id=provenance_id,
                payload={"action": "rollback", "invalidate": ["qa_evidence_cache"]},
            )
        )
