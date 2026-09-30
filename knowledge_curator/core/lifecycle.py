"""Lifecycle core: revision draft, risk gate, retraction/corrigendum, publish (Phase 5.0).

Composes existing VersionStore snapshot/version behavior with append-only
LifecycleStore + EventOutbox. Never physically deletes historical
structural/USDO/vector identities.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
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
)


def _hash_json(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluate_risk_gate(draft: RevisionDraft) -> RiskDecision:
    """§7.3 rule-level risk gate. No numeric global score.

    - Retraction is always high-impact (manual) unless the caller marks the
      trigger as already externally verified/authorized.
    - Low-risk may be rule-approved when high-confidence multi-source and no
      unresolved controversy (encoded via draft metadata).
    """
    if draft.trigger == LifecycleReason.RETRACTION and not draft.verified_external_trigger:
        return RiskDecision.MANUAL_ADJUDICATION_REQUIRED
    if draft.trigger == LifecycleReason.RETRACTION and draft.verified_external_trigger:
        # Publication may proceed deterministically; still record the decision.
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

    # ---- helpers ----

    def _lifecycle_id_for_revision(self, revision_id: str, kind: str) -> str:
        return _hash_json({"revision_id": revision_id, "kind": kind})[:16]

    def _event_id(self, event_type: str, ref_id: str, revision_id: str, extra: str = "") -> str:
        return _hash_json(
            {
                "type": event_type,
                "ref_id": ref_id,
                "revision_id": revision_id,
                "extra": extra,
            }
        )[:16]

    def _build_lifecycle_manifest(
        self,
        *,
        base_manifest: Optional[SnapshotManifest],
        ref_id: str,
        source_fingerprint: str,
        lifecycle_id: str,
    ) -> SnapshotManifest:
        """New deterministic snapshot referencing the same immutable payload ids.

        Backward compatibility: lifecycle fields only enter stable_payload when
        non-empty, so old-style manifests keep their historical content hash.
        """
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

    def _find_base_manifest(self, base_version_id: Optional[str]) -> Optional[SnapshotManifest]:
        if not base_version_id:
            cur = self._versions.current_version()
            base_version_id = cur.version_id if cur else None
        if not base_version_id:
            return None
        ver = self._versions.get_version(base_version_id)
        if ver is None:
            return None
        snap = self._versions.get_snapshot(ver.snapshot_id)
        return snap.manifest if snap else None

    def _emit(self, event: LifecycleEvent) -> str:
        stored = self._outbox.append(event)
        return stored.event_id

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

        lifecycle_id = self._lifecycle_id_for_revision(draft.revision_id, "retraction")
        existing = self._lifecycle.get_document_record(lifecycle_id)
        if existing is not None:
            # Idempotent replay
            cur = self._versions.current_version()
            return LifecyclePublishResult(
                revision_id=draft.revision_id,
                lifecycle_id=lifecycle_id,
                version_id=existing.effective_version_id,
                snapshot_id=None,
                document_status=existing.status.value,
                archived_assertion_ids=list(existing.affected_assertion_ids),
                event_ids=[],
                idempotent_hit=True,
            )

        assertion_ids = list(
            dict.fromkeys(list(draft.affected_assertion_ids) + list(all_assertion_ids or []))
        )
        base_manifest = self._find_base_manifest(draft.base_version_id)

        # 1) append lifecycle records (staged, not yet bound to published version)
        doc_rec = DocumentLifecycleRecord(
            lifecycle_id=lifecycle_id,
            ref_id=draft.ref_id,
            status=DocumentLifecycleStatus.RETRACTED,
            reason=LifecycleReason.RETRACTION,
            effective_version_id=None,  # bound after publish
            source_fingerprint=source_fingerprint or (base_manifest.source_fingerprint if base_manifest else ""),
            affected_assertion_ids=assertion_ids,
            rationale=draft.rationale,
            evidence_refs=list(draft.evidence_refs),
            trace_id=draft.trace_id,
            provenance_id=draft.provenance_id,
            revision_id=draft.revision_id,
        )
        self._lifecycle.append_document_record(doc_rec)

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

        # 2) create snapshot + publish NEW version (same immutable payload ids)
        manifest = self._build_lifecycle_manifest(
            base_manifest=base_manifest,
            ref_id=draft.ref_id,
            source_fingerprint=source_fingerprint,
            lifecycle_id=lifecycle_id,
        )
        snap = self._versions.create_snapshot(manifest)
        ver = self._versions.publish_version(snap.snapshot_id)

        # 3) bind effective version on records (append-only: store binding via new seq? )
        # Re-append same ids is idempotent only when compatible; effective_version_id
        # is part of stored record. We record binding through a follow-up field update
        # that is still append-only at the event level. To keep the store append-only
        # without mutating history, we store the binding in a dedicated binding record.
        # For Phase 5.0 in-memory adapter we update the staged record's effective version
        # by appending a compatible record with the same id (allowed only if identical).
        # Simpler: keep effective_version_id on the staged record as None and track
        # binding in the event payload + a version_binding map on the coordinator.
        self._bind_version(lifecycle_id, ver.version_id)

        # 4) events
        e1 = self._emit(
            LifecycleEvent(
                event_id=self._event_id(
                    LifecycleEventType.KB_DOCUMENT_RETRACTED.value,
                    draft.ref_id,
                    draft.revision_id,
                ),
                event_type=LifecycleEventType.KB_DOCUMENT_RETRACTED,
                ref_id=draft.ref_id,
                affected_assertion_ids=assertion_ids,
                old_version_id=draft.base_version_id,
                new_version_id=ver.version_id,
                lifecycle_id=lifecycle_id,
                revision_id=draft.revision_id,
                trace_id=draft.trace_id,
                provenance_id=draft.provenance_id,
                payload={
                    "action": "retract",
                    "invalidate": ["qa_evidence_cache", "training_export", "audit_metrics"],
                },
            )
        )
        e2 = self._emit(
            LifecycleEvent(
                event_id=self._event_id(
                    LifecycleEventType.KB_ASSERTIONS_ARCHIVED.value,
                    draft.ref_id,
                    draft.revision_id,
                    extra=",".join(assertion_ids),
                ),
                event_type=LifecycleEventType.KB_ASSERTIONS_ARCHIVED,
                ref_id=draft.ref_id,
                affected_assertion_ids=assertion_ids,
                old_version_id=draft.base_version_id,
                new_version_id=ver.version_id,
                lifecycle_id=lifecycle_id,
                revision_id=draft.revision_id,
                trace_id=draft.trace_id,
                provenance_id=draft.provenance_id,
                payload={"action": "archive_assertions"},
            )
        )
        e3 = self._emit(
            LifecycleEvent(
                event_id=self._event_id(
                    LifecycleEventType.KB_REVISION_PUBLISHED.value,
                    draft.ref_id,
                    draft.revision_id,
                    extra="retraction",
                ),
                event_type=LifecycleEventType.KB_REVISION_PUBLISHED,
                ref_id=draft.ref_id,
                affected_assertion_ids=assertion_ids,
                old_version_id=draft.base_version_id,
                new_version_id=ver.version_id,
                lifecycle_id=lifecycle_id,
                revision_id=draft.revision_id,
                trace_id=draft.trace_id,
                provenance_id=draft.provenance_id,
                payload={"revision_kind": "retraction"},
            )
        )

        return LifecyclePublishResult(
            revision_id=draft.revision_id,
            lifecycle_id=lifecycle_id,
            version_id=ver.version_id,
            snapshot_id=snap.snapshot_id,
            document_status=DocumentLifecycleStatus.RETRACTED.value,
            archived_assertion_ids=assertion_ids,
            event_ids=[e1, e2, e3],
        )

    def _bind_version(self, lifecycle_id: str, version_id: str) -> None:
        """Bind staged lifecycle records to the published version id."""
        self._lifecycle.bind_effective_version(lifecycle_id, version_id)

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
        if draft.manual_adjudication_required and draft.trigger not in (
            LifecycleReason.RETRACTION,
        ):
            # Caller must not publish unadjudicated high-risk drafts.
            if draft.risk_decision == RiskDecision.MANUAL_ADJUDICATION_REQUIRED:
                raise ValueError("manual adjudication required for this draft")

        lifecycle_id = self._lifecycle_id_for_revision(draft.revision_id, "revision")
        existing = self._lifecycle.get_document_record(lifecycle_id)
        if existing is not None:
            return LifecyclePublishResult(
                revision_id=draft.revision_id,
                lifecycle_id=lifecycle_id,
                version_id=existing.effective_version_id,
                snapshot_id=None,
                document_status=existing.status.value,
                superseded_assertion_ids=list(draft.supersede_actions.keys()),
                event_ids=[],
                idempotent_hit=True,
            )

        archived = list(draft.archive_actions)
        superseded = list(draft.supersede_actions.keys())
        affected = list(
            dict.fromkeys(list(draft.affected_assertion_ids) + archived + superseded)
        )
        base_manifest = self._find_base_manifest(draft.base_version_id)

        doc_status = DocumentLifecycleStatus.ACTIVE
        if draft.trigger == LifecycleReason.PREPRINT_TO_JOURNAL:
            doc_status = DocumentLifecycleStatus.SUPERSEDED

        doc_rec = DocumentLifecycleRecord(
            lifecycle_id=lifecycle_id,
            ref_id=draft.ref_id,
            status=doc_status,
            reason=draft.trigger,
            effective_version_id=None,
            source_fingerprint=source_fingerprint,
            affected_assertion_ids=affected,
            rationale=draft.rationale,
            evidence_refs=list(draft.evidence_refs),
            trace_id=draft.trace_id,
            provenance_id=draft.provenance_id,
            revision_id=draft.revision_id,
        )
        self._lifecycle.append_document_record(doc_rec)

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
            source_fingerprint=source_fingerprint,
            lifecycle_id=lifecycle_id,
        )
        snap = self._versions.create_snapshot(manifest)
        ver = self._versions.publish_version(snap.snapshot_id)
        self._bind_version(lifecycle_id, ver.version_id)

        event_ids = []
        if superseded:
            event_ids.append(
                self._emit(
                    LifecycleEvent(
                        event_id=self._event_id(
                            LifecycleEventType.KB_ASSERTIONS_SUPERSEDED.value,
                            draft.ref_id,
                            draft.revision_id,
                            extra=",".join(superseded),
                        ),
                        event_type=LifecycleEventType.KB_ASSERTIONS_SUPERSEDED,
                        ref_id=draft.ref_id,
                        affected_assertion_ids=superseded,
                        old_version_id=draft.base_version_id,
                        new_version_id=ver.version_id,
                        lifecycle_id=lifecycle_id,
                        revision_id=draft.revision_id,
                        trace_id=draft.trace_id,
                        provenance_id=draft.provenance_id,
                        payload={
                            "supersede_actions": dict(draft.supersede_actions),
                            "invalidate": ["qa_evidence_cache", "training_export", "audit_metrics"],
                        },
                    )
                )
            )
        if archived:
            event_ids.append(
                self._emit(
                    LifecycleEvent(
                        event_id=self._event_id(
                            LifecycleEventType.KB_ASSERTIONS_ARCHIVED.value,
                            draft.ref_id,
                            draft.revision_id,
                            extra=",".join(archived),
                        ),
                        event_type=LifecycleEventType.KB_ASSERTIONS_ARCHIVED,
                        ref_id=draft.ref_id,
                        affected_assertion_ids=archived,
                        old_version_id=draft.base_version_id,
                        new_version_id=ver.version_id,
                        lifecycle_id=lifecycle_id,
                        revision_id=draft.revision_id,
                        trace_id=draft.trace_id,
                        provenance_id=draft.provenance_id,
                        payload={"action": "archive_assertions"},
                    )
                )
            )
        kind = (
            LifecycleEventType.KB_CORRIGENDUM_PUBLISHED
            if draft.trigger == LifecycleReason.CORRIGENDUM
            else LifecycleEventType.KB_REVISION_PUBLISHED
        )
        event_ids.append(
            self._emit(
                LifecycleEvent(
                    event_id=self._event_id(kind.value, draft.ref_id, draft.revision_id),
                    event_type=kind,
                    ref_id=draft.ref_id,
                    affected_assertion_ids=affected,
                    old_version_id=draft.base_version_id,
                    new_version_id=ver.version_id,
                    lifecycle_id=lifecycle_id,
                    revision_id=draft.revision_id,
                    trace_id=draft.trace_id,
                    provenance_id=draft.provenance_id,
                    payload={"revision_kind": draft.trigger.value},
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
