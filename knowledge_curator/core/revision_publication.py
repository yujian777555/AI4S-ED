"""Revision publication orchestration (Phase 5.3).

Recoverable saga: validate -> target commit -> lifecycle -> final source bind.
No fake cross-store ACID. Composes frozen Phase 2/5.0/5.1/5.2 components.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional

from knowledge_curator.ports.revision_publication_store import RevisionPublicationStore
from knowledge_curator.ports.source_version_registry import SourceVersionRegistry
from knowledge_curator.ports.version_store import VersionStore
from knowledge_curator.schemas.revision_publication import (
    ApprovalDecision,
    PublicationPhase,
    PublicationStatus,
    RevisionApproval,
    RevisionPublicationRecord,
    RevisionPublicationResult,
)
from knowledge_curator.schemas.source_versions import VersionUpgradeIntent
from knowledge_curator.schemas.version_delta import RevisionPackage


def _hash_json(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_publication_scope_hash(
    package: RevisionPackage,
    target_commit_request: Any,
    curation_decisions: Optional[list[dict]] = None,
) -> str:
    """Deterministic scope hash covering publication material (plan §11)."""
    target = [
        {
            "id": a.id,
            "ref": a.ref_id,
            "sem": _hash_json(
                {
                    "subject": [a.subject.eddo_class, a.subject.resolved_entity, a.subject.original_mention],
                    "prop": a.property,
                    "obj": [str(a.object.value), a.object.unit, a.object.value_type.value, a.object.uncertainty],
                    "conds": [[c.eddo_class, str(c.value), c.unit] for c in (a.conditions or [])],
                    "ct": a.claim_type.value,
                    "org": a.source_claim_origin.value,
                    "conf": a.confidence.value,
                    "q": a.quality,
                    "flags": [a.missing_unit, a.speculative_wording, a.chart_quality_low],
                    "loc": a.provenance.locator if a.provenance else "",
                    "sent": a.provenance.sentence if a.provenance else "",
                }
            ),
        }
        for a in package.target_assertions
    ]
    decisions = curation_decisions or []
    return _hash_json(
        {
            "package_id": package.package_id,
            "new_sv": package.new_source_version_id,
            "new_ref": package.new_ref_id,
            "prior_ref": package.prior_ref_id,
            "target": sorted(target, key=lambda x: x["id"]),
            "decisions": sorted(decisions, key=lambda x: x.get("assertion_id", "")),
        }
    )[:16]


def compute_request_material_hash(
    package: RevisionPackage,
    scope_hash: str,
    approval: Optional[RevisionApproval],
) -> str:
    """Request material hash for publication idempotency/conflict (plan §14)."""
    appr_mat = None
    if approval is not None:
        appr_mat = {
            "id": approval.approval_id,
            "pkg": approval.package_id,
            "scope": approval.scope_hash,
            "dec": approval.decision.value,
            "appr": approval.approver,
            "rat": approval.rationale,
        }
    return _hash_json(
        {
            "package_id": package.package_id,
            "scope": scope_hash,
            "approval": appr_mat,
            "trace": package.trace_id,
            "prov": package.provenance_id,
        }
    )[:16]


@dataclass
class _CommitResultRef:
    """Minimal view of a DocumentCommitCoordinator result."""

    status: str
    version_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    commit_id: Optional[str] = None
    admitted: list[Any] = None  # list of AdmittedAssertion-like


class RevisionPublicationCoordinator:
    """Orchestrate approval -> target commit -> lifecycle -> final bind."""

    def __init__(
        self,
        *,
        publication_store: RevisionPublicationStore,
        source_registry: SourceVersionRegistry,
        version_store: VersionStore,
        lifecycle_coordinator: Any,
        document_commit_coordinator: Any = None,
        document_commit_store: Any = None,
    ) -> None:
        self._journal = publication_store
        self._registry = source_registry
        self._versions = version_store
        self._lifecycle = lifecycle_coordinator
        self._commit = document_commit_coordinator
        self._commit_store = document_commit_store

    # ---- validation helpers ----

    def _validate_package_gate(self, package: RevisionPackage) -> Optional[RevisionPublicationResult]:
        if package.requires_manual_review:
            return RevisionPublicationResult(
                status=PublicationStatus.PACKAGE_REVIEW_REQUIRED,
                publication_id=package.package_id,
                last_error="package.requires_manual_review=true; semantic ambiguity unresolved",
            )
        return None

    def _validate_lineage(self, package: RevisionPackage) -> tuple[Optional[dict], Optional[RevisionPublicationResult]]:
        prior = self._registry.get_source_version(package.prior_source_version_id)
        new = self._registry.get_source_version(package.new_source_version_id)
        if prior is None or new is None:
            return None, RevisionPublicationResult(
                status=PublicationStatus.FAILED,
                publication_id=package.package_id,
                last_error="source version not found",
            )
        if prior.work_id != package.work_id or new.work_id != package.work_id:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT,
                publication_id=package.package_id,
                last_error="source versions do not belong to package work",
            )
        if prior.kb_version_id != package.prior_bound_kb_version_id:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT,
                publication_id=package.package_id,
                last_error="prior.kb_version_id does not match package.prior_bound_kb_version_id",
            )
        if not prior.snapshot_id:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT,
                publication_id=package.package_id,
                last_error="prior source version has no snapshot binding",
            )
        if new.prior_source_version_id != prior.source_version_id:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT,
                publication_id=package.package_id,
                last_error="new.prior_source_version_id mismatch",
            )
        return {"prior": prior, "new": new}, None

    def _validate_approval(
        self,
        package: RevisionPackage,
        approval: Optional[RevisionApproval],
        scope_hash: str,
    ) -> Optional[RevisionPublicationResult]:
        """Approval must be valid BEFORE any KB side effect (plan §12)."""
        # If draft is manual-required (default for our packages), approval is mandatory.
        if approval is None:
            return RevisionPublicationResult(
                status=PublicationStatus.APPROVAL_REQUIRED,
                publication_id=package.package_id,
                last_error="revision approval required before KB side effects",
            )
        if approval.decision != ApprovalDecision.APPROVED:
            return RevisionPublicationResult(
                status=PublicationStatus.APPROVAL_REJECTED,
                publication_id=package.package_id,
                last_error="approval decision is REJECTED",
            )
        if approval.package_id != package.package_id:
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT,
                publication_id=package.package_id,
                last_error="approval.package_id mismatch",
            )
        if approval.scope_hash != scope_hash:
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT,
                publication_id=package.package_id,
                last_error="approval.scope_hash mismatch",
            )
        if not approval.approval_id or not approval.approver:
            return RevisionPublicationResult(
                status=PublicationStatus.APPROVAL_REQUIRED,
                publication_id=package.package_id,
                last_error="approval_id/approver must be non-empty",
            )
        return None

    def _validate_curation(self, package: RevisionPackage, report: Any) -> Optional[RevisionPublicationResult]:
        """Curation gate: only ACCEPT/DOWNGRADE allowed (plan §10)."""
        allowed = {"accept", "downgrade", "accepted", "downgraded"}
        decisions = getattr(report, "decisions", None) or []
        target_ids = {a.id for a in package.target_assertions}
        seen: set[str] = set()
        for d in decisions:
            aid = getattr(d, "assertion_id", None) or (d.get("assertion_id") if isinstance(d, dict) else None)
            action = getattr(d, "action", None) or (d.get("action") if isinstance(d, dict) else None)
            action_val = action.value if hasattr(action, "value") else str(action or "").lower()
            if aid is None:
                return RevisionPublicationResult(
                    status=PublicationStatus.FAILED,
                    publication_id=package.package_id,
                    last_error="decision missing assertion_id",
                )
            if aid in seen:
                return RevisionPublicationResult(
                    status=PublicationStatus.FAILED,
                    publication_id=package.package_id,
                    last_error=f"duplicate decision for {aid}",
                )
            seen.add(aid)
            if aid not in target_ids:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT,
                    publication_id=package.package_id,
                    last_error=f"decision for unknown assertion {aid}",
                )
            if action_val not in allowed:
                return RevisionPublicationResult(
                    status=PublicationStatus.FAILED,
                    publication_id=package.package_id,
                    last_error=f"curation action {action_val} not publishable",
                )
        # Every target assertion must have exactly one decision
        if seen != target_ids:
            missing = target_ids - seen
            extra = seen - target_ids
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED,
                publication_id=package.package_id,
                last_error=f"decision coverage mismatch: missing={sorted(missing)} extra={sorted(extra)}",
            )
        return None

    def _existing_commit_material_guard(
        self,
        package: RevisionPackage,
        ref_id: str,
        fingerprint: str,
    ) -> Optional[RevisionPublicationResult]:
        """Inspect existing commit for material conflict (plan §15)."""
        if self._commit_store is None:
            return None
        try:
            existing = self._commit_store.find_by_key(ref_id, fingerprint)
        except Exception:
            return None
        if existing is None:
            return None
        admitted = getattr(existing, "admitted", None) or []
        if not admitted:
            return None
        target_ids = {a.id for a in package.target_assertions}
        admitted_ids = set()
        for item in admitted:
            a = getattr(item, "assertion", item)
            admitted_ids.add(getattr(a, "id", None) or (a.get("id") if isinstance(a, dict) else None))
        if admitted_ids != target_ids:
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT,
                publication_id=package.package_id,
                last_error="existing commit admitted material differs from package target",
            )
        return None

    # ---- main entry ----

    def publish(
        self,
        *,
        package: RevisionPackage,
        target_commit_request: Any = None,
        curation_report: Any = None,
        approval: Optional[RevisionApproval] = None,
        curation_decisions: Optional[list[dict]] = None,
    ) -> RevisionPublicationResult:
        """Run the recoverable publication saga."""
        # --- Pre-side-effect validation ---
        gate_err = self._validate_package_gate(package)
        if gate_err is not None:
            return gate_err

        lineage, lineage_err = self._validate_lineage(package)
        if lineage_err is not None:
            return lineage_err
        prior = lineage["prior"]
        new = lineage["new"]

        # Existing binding check (replay exception handled later)
        if new.kb_version_id is not None:
            # Allowed only if journal already finalized with matching binding.
            pub_id = package.package_id
            existing_rec = self._journal.get(pub_id)
            if (
                existing_rec is not None
                and existing_rec.phase == PublicationPhase.FINALIZED
                and existing_rec.final_version_id == new.kb_version_id
                and existing_rec.final_snapshot_id == new.snapshot_id
            ):
                return RevisionPublicationResult(
                    status=PublicationStatus.FINALIZED,
                    publication_id=pub_id,
                    final_version_id=new.kb_version_id,
                    final_snapshot_id=new.snapshot_id,
                    idempotent=True,
                )
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT,
                publication_id=package.package_id,
                last_error="new source version already bound to a different KB version",
            )

        scope_hash = compute_publication_scope_hash(
            package, target_commit_request, curation_decisions
        )
        appr_err = self._validate_approval(package, approval, scope_hash)
        if appr_err is not None:
            return appr_err

        # Curation gate
        if curation_report is not None:
            cur_err = self._validate_curation(package, curation_report)
            if cur_err is not None:
                return cur_err

        # Existing commit material guard
        guard_err = self._existing_commit_material_guard(
            package, package.new_ref_id, new.source_fingerprint
        )
        if guard_err is not None:
            return guard_err

        request_mat = compute_request_material_hash(package, scope_hash, approval)
        pub_id = package.package_id  # deterministic from package_id

        # Journal: create or validate idempotency
        existing = self._journal.get(pub_id)
        if existing is not None:
            if existing.request_material_hash != request_mat:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT,
                    publication_id=pub_id,
                    last_error="publication request material conflict",
                )
            if existing.phase == PublicationPhase.FINALIZED:
                return RevisionPublicationResult(
                    status=PublicationStatus.FINALIZED,
                    publication_id=pub_id,
                    final_version_id=existing.final_version_id,
                    final_snapshot_id=existing.final_snapshot_id,
                    idempotent=True,
                )
            record = existing
        else:
            record = RevisionPublicationRecord(
                publication_id=pub_id,
                package_id=package.package_id,
                request_material_hash=request_mat,
                phase=PublicationPhase.PREPARED,
                approval_id=approval.approval_id if approval else None,
                trace_id=package.trace_id,
                provenance_id=package.provenance_id,
            )
            record = self._journal.create(record)

        # --- Step A: target commit ---
        if record.phase == PublicationPhase.PREPARED:
            commit_result = self._run_target_commit(package, target_commit_request, record)
            if commit_result is not None:
                return commit_result
            record = self._journal.get(pub_id)

        # --- Step B: lifecycle ---
        if record.phase == PublicationPhase.TARGET_PUBLISHED:
            life_result = self._run_lifecycle(package, record, prior, approval)
            if life_result is not None:
                return life_result
            record = self._journal.get(pub_id)

        # --- Step C: final bind ---
        if record.phase == PublicationPhase.LIFECYCLE_PUBLISHED:
            bind_result = self._run_final_bind(package, record, new)
            if bind_result is not None:
                return bind_result
            record = self._journal.get(pub_id)

        if record.phase == PublicationPhase.FINALIZED:
            return RevisionPublicationResult(
                status=PublicationStatus.FINALIZED,
                publication_id=pub_id,
                target_version_id=record.target_version_id,
                target_snapshot_id=record.target_snapshot_id,
                final_version_id=record.final_version_id,
                final_snapshot_id=record.final_snapshot_id,
                lifecycle_id=record.lifecycle_id,
                idempotent=True,
            )

        return RevisionPublicationResult(
            status=PublicationStatus.FAILED,
            publication_id=pub_id,
            last_error="publication did not reach FINALIZED",
        )

    def _run_target_commit(
        self,
        package: RevisionPackage,
        request: Any,
        record: RevisionPublicationRecord,
    ) -> Optional[RevisionPublicationResult]:
        if self._commit is None:
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED,
                publication_id=record.publication_id,
                last_error="document commit coordinator not configured",
            )
        try:
            result = self._commit.commit(request)
        except Exception as exc:
            record.last_error = f"target commit error: {exc}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED,
                publication_id=record.publication_id,
                last_error=record.last_error,
            )

        status = getattr(result, "status", None)
        status_val = status.value if hasattr(status, "value") else str(status or "").lower()

        if status_val in ("pending_vector", "pending_finalize"):
            record.last_error = f"target commit pending: {status_val}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.TARGET_PENDING,
                publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if status_val not in ("published", "idempotent_hit"):
            record.last_error = f"target commit not publishable: {status_val}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED,
                publication_id=record.publication_id,
                last_error=record.last_error,
            )

        version_id = getattr(result, "version_id", None) or getattr(result, "kb_version_id", None)
        snapshot_id = getattr(result, "snapshot_id", None)
        if version_id is None or snapshot_id is None:
            record.last_error = "target commit result missing version/snapshot"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED,
                publication_id=record.publication_id,
                last_error=record.last_error,
            )

        # Validate target version exists/published
        ver = self._versions.get_version(version_id)
        if ver is None or not ver.published:
            record.last_error = f"target version {version_id} not published"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED,
                publication_id=record.publication_id,
                last_error=record.last_error,
            )

        record.target_commit_id = getattr(result, "commit_id", None)
        record.target_version_id = version_id
        record.target_snapshot_id = snapshot_id
        record.phase = PublicationPhase.TARGET_PUBLISHED
        self._journal.update(record)
        return None

    def _run_lifecycle(
        self,
        package: RevisionPackage,
        record: RevisionPublicationRecord,
        prior: Any,
        approval: Optional[RevisionApproval],
    ) -> Optional[RevisionPublicationResult]:
        from knowledge_curator.core.version_delta import package_to_revision_draft

        draft = package_to_revision_draft(package)
        # Authorized draft: manual adjudication completed via explicit approval.
        draft = copy.deepcopy(draft)
        draft.base_version_id = record.target_version_id
        if approval is not None:
            draft.manual_adjudication_required = False  # approval validated
            # KEEP risk_decision = MANUAL_ADJUDICATION_REQUIRED (do not fake auto-eligible)
            draft.evidence_refs = list(draft.evidence_refs) + [
                f"approval:{approval.approval_id}",
                f"approval_scope:{approval.scope_hash}",
            ]
            draft.rationale = (
                f"{draft.rationale}; approved by {approval.approver} ({approval.approval_id})"
            )

        try:
            life_result = self._lifecycle.apply_revision(
                draft, source_fingerprint=prior.source_fingerprint
            )
        except ValueError as exc:
            msg = str(exc)
            if "not the current version" in msg or "base_version" in msg:
                record.last_error = f"stale base / interleaving: {msg}"
                self._journal.update(record)
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT,
                    publication_id=record.publication_id,
                    last_error=record.last_error,
                )
            record.last_error = f"lifecycle error: {msg}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.LIFECYCLE_PENDING,
                publication_id=record.publication_id,
                last_error=record.last_error,
            )
        except Exception as exc:
            record.last_error = f"lifecycle error: {exc}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.LIFECYCLE_PENDING,
                publication_id=record.publication_id,
                last_error=record.last_error,
            )

        final_version_id = getattr(life_result, "version_id", None)
        final_snapshot_id = getattr(life_result, "snapshot_id", None)

        # R3 plan §21: recover snapshot if missing on idempotent replay
        if final_version_id is not None and final_snapshot_id is None:
            ver = self._versions.get_version(final_version_id)
            if ver is not None:
                final_snapshot_id = ver.snapshot_id

        if final_version_id is None:
            record.last_error = "lifecycle produced no version"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED,
                publication_id=record.publication_id,
                last_error=record.last_error,
            )

        # Validate final chain
        final_ver = self._versions.get_version(final_version_id)
        if final_ver is None or not final_ver.published:
            record.last_error = f"final version {final_version_id} not published"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED,
                publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if final_ver.prior_version_id != record.target_version_id:
            record.last_error = (
                f"final version prior {final_ver.prior_version_id} != target {record.target_version_id}"
            )
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT,
                publication_id=record.publication_id,
                last_error=record.last_error,
            )

        record.lifecycle_id = getattr(life_result, "lifecycle_id", None)
        record.final_version_id = final_version_id
        record.final_snapshot_id = final_snapshot_id
        record.phase = PublicationPhase.LIFECYCLE_PUBLISHED
        self._journal.update(record)
        return None

    def _run_final_bind(
        self,
        package: RevisionPackage,
        record: RevisionPublicationRecord,
        new: Any,
    ) -> Optional[RevisionPublicationResult]:
        try:
            bound = self._registry.bind_source_version(
                package.new_source_version_id,
                record.final_version_id,
                record.final_snapshot_id or "",
            )
        except ValueError as exc:
            msg = str(exc)
            # Idempotent exact rebind
            if "already bound" in msg:
                current = self._registry.get_source_version(package.new_source_version_id)
                if (
                    current is not None
                    and current.kb_version_id == record.final_version_id
                    and current.snapshot_id == record.final_snapshot_id
                ):
                    record.phase = PublicationPhase.FINALIZED
                    self._journal.update(record)
                    return None
                record.last_error = msg
                self._journal.update(record)
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT,
                    publication_id=record.publication_id,
                    last_error=record.last_error,
                )
            record.last_error = f"bind error: {msg}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED,
                publication_id=record.publication_id,
                last_error=record.last_error,
            )

        record.phase = PublicationPhase.FINALIZED
        self._journal.update(record)
        return None
