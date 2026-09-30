"""Revision publication orchestration (Phase 5.3 / R1).

Recoverable saga: validate -> target commit -> lifecycle -> final source bind.
Real async DocumentCommitCoordinator integration. No fake cross-store ACID.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional

from knowledge_curator.core.commit import validate_commit_request
from knowledge_curator.ports.revision_publication_store import RevisionPublicationStore
from knowledge_curator.ports.source_version_registry import SourceVersionRegistry
from knowledge_curator.ports.version_store import VersionStore
from knowledge_curator.schemas.assertions import Assertion
from knowledge_curator.schemas.commit import CommitRequest
from knowledge_curator.schemas.curation import CurationAction
from knowledge_curator.schemas.revision_publication import (
    ApprovalDecision,
    PublicationPhase,
    PublicationStatus,
    RevisionApproval,
    RevisionPublicationRecord,
    RevisionPublicationResult,
)
from knowledge_curator.schemas.version_delta import RevisionPackage


def _hash_json(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_assertion_material(a: Assertion) -> dict:
    """Canonical publication material for one assertion (R1-04)."""
    return {
        "id": a.id,
        "ref": a.ref_id,
        "eddo": a.subject.eddo_class,
        "entity": a.subject.resolved_entity,
        "mention": a.subject.original_mention,
        "prop": a.property,
        "val": a.object.value,
        "unit": a.object.unit,
        "vt": a.object.value_type.value,
        "unc": a.object.uncertainty,
        "conds": sorted(
            [[c.eddo_class, str(c.value), c.unit or ""] for c in (a.conditions or [])]
        ),
        "loc": a.provenance.locator if a.provenance else "",
        "sent": a.provenance.sentence if a.provenance else "",
        "ct": a.claim_type.value,
        "org": a.source_claim_origin.value,
        "conf": a.confidence.value,
        "q": a.quality,
        "flags": [a.missing_unit, a.speculative_wording, a.chart_quality_low],
    }


def _assertion_material_equal(a: Assertion, b: Assertion) -> bool:
    return canonical_assertion_material(a) == canonical_assertion_material(b)


def compute_publication_scope_hash(
    package: RevisionPackage,
    request: CommitRequest,
) -> str:
    """Scope hash binding actual CommitRequest material (R1-03)."""
    meta = request.assertion_set.metadata
    report = request.report
    decisions = []
    for d in getattr(report, "decisions", []) or []:
        action = getattr(d, "action", None)
        conf = getattr(d, "confidence", None)
        decisions.append(
            {
                "aid": getattr(d, "assertion_id", None) or getattr(d, "assertion_id", ""),
                "act": action.value if hasattr(action, "value") else str(action),
                "conf": conf.value if hasattr(conf, "value") else str(conf),
            }
        )
    return _hash_json(
        {
            "package_id": package.package_id,
            "new_sv": package.new_source_version_id,
            "new_ref": package.new_ref_id,
            "prior_ref": package.prior_ref_id,
            "src_ref": request.source.ref_id,
            "src_fp": request.source.source_fingerprint,
            "meta": {
                "title": meta.title,
                "authors": list(meta.authors),
                "year": meta.year,
                "source": meta.source,
                "doi": meta.doi,
                "stable_id": meta.stable_id,
                "quality_grade": getattr(request.assertion_set, "quality_grade", None),
                "no_structured_data": getattr(request.assertion_set, "no_structured_data", False),
                "schema_valid": getattr(request.assertion_set, "schema_valid_count", None),
                "schema_total": getattr(request.assertion_set, "schema_total_count", None),
            },
            "assertions": sorted(
                [canonical_assertion_material(a) for a in request.assertion_set.assertions],
                key=lambda x: x["id"],
            ),
            "decisions": sorted(decisions, key=lambda x: x["aid"]),
            "report_status": str(getattr(report, "status", "")),
            "returned_upstream": getattr(report, "returned_upstream_count", 0) or 0,
        }
    )[:16]


def compute_request_material_hash(
    package: RevisionPackage,
    scope_hash: str,
    approval: Optional[RevisionApproval],
) -> str:
    appr_mat = None
    if approval is not None:
        appr_mat = {
            "id": approval.approval_id,
            "pkg": approval.package_id,
            "scope": approval.scope_hash,
            "dec": approval.decision.value,
            "appr": approval.approver,
            "rat": approval.rationale,
            "trace": approval.trace_id,
            "prov": approval.provenance_id,
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
                last_error="package.requires_manual_review=true",
            )
        return None

    def _validate_lineage(self, package: RevisionPackage, request: CommitRequest) -> tuple[Optional[dict], Optional[RevisionPublicationResult]]:
        prior = self._registry.get_source_version(package.prior_source_version_id)
        new = self._registry.get_source_version(package.new_source_version_id)
        if prior is None or new is None:
            return None, RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=package.package_id,
                last_error="source version not found",
            )
        # R1-06: exact lineage
        if prior.ref_id != package.prior_ref_id:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="prior.ref_id mismatch",
            )
        if new.ref_id != package.new_ref_id:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="new.ref_id mismatch",
            )
        if new.relation != package.relation:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="new.relation mismatch",
            )
        if prior.work_id != package.work_id or new.work_id != package.work_id:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="work_id mismatch",
            )
        if new.prior_source_version_id != prior.source_version_id:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="new.prior_source_version_id mismatch",
            )
        if prior.kb_version_id != package.prior_bound_kb_version_id:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="prior.kb_version_id mismatch",
            )
        if not prior.snapshot_id:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="prior has no snapshot binding",
            )
        # R1-05: fingerprint agrees with request
        if request.source.source_fingerprint != new.source_fingerprint:
            return None, RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="request source fingerprint != new source fingerprint",
            )
        return {"prior": prior, "new": new}, None

    def _validate_target_request(
        self, package: RevisionPackage, request: Optional[CommitRequest], new: Any
    ) -> Optional[RevisionPublicationResult]:
        """R1-02: exact CommitRequest/package gate."""
        if request is None:
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=package.package_id,
                last_error="target_commit_request is required",
            )
        errors = validate_commit_request(request)
        if errors:
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=package.package_id,
                last_error=f"invalid CommitRequest: {'; '.join(errors)}",
            )
        # Source identity
        if request.source.ref_id != package.new_ref_id or request.source.ref_id != new.ref_id:
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="request.source.ref_id mismatch",
            )
        if request.assertion_set.ref_id != package.new_ref_id:
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="assertion_set.ref_id mismatch",
            )
        if request.report.source_ref_id != package.new_ref_id:
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="report.source_ref_id mismatch",
            )
        # R1-04: exact assertion material
        pkg_by_id = {a.id: a for a in package.target_assertions}
        req_by_id = {a.id: a for a in request.assertion_set.assertions}
        if set(pkg_by_id) != set(req_by_id):
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error=f"assertion ID set mismatch: pkg={sorted(pkg_by_id)} req={sorted(req_by_id)}",
            )
        for aid in pkg_by_id:
            if not _assertion_material_equal(pkg_by_id[aid], req_by_id[aid]):
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error=f"assertion material mismatch for {aid}",
                )
        # R1-05: metadata validation
        meta = request.assertion_set.metadata
        if meta.title and new.normalized_title:
            from knowledge_curator.core.source_identity import normalize_title

            if normalize_title(meta.title) != new.normalized_title:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="metadata title mismatch",
                )
        if meta.doi and new.normalized_doi:
            from knowledge_curator.core.source_identity import normalize_doi

            if normalize_doi(meta.doi) != new.normalized_doi:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="metadata DOI mismatch",
                )
        if meta.stable_id and new.stable_id:
            if meta.stable_id.strip() != new.stable_id.strip():
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="metadata stable_id mismatch",
                )
        return None

    def _validate_curation(self, package: RevisionPackage, request: CommitRequest) -> Optional[RevisionPublicationResult]:
        """R1-06: curation gate from request.report only."""
        report = request.report
        allowed = {CurationAction.ACCEPT, CurationAction.DOWNGRADE}
        target_ids = {a.id for a in package.target_assertions}
        seen: set[str] = set()
        for d in getattr(report, "decisions", []) or []:
            aid = getattr(d, "assertion_id", None)
            action = getattr(d, "action", None)
            if aid is None:
                return RevisionPublicationResult(
                    status=PublicationStatus.FAILED, publication_id=package.package_id,
                    last_error="decision missing assertion_id",
                )
            if aid in seen:
                return RevisionPublicationResult(
                    status=PublicationStatus.FAILED, publication_id=package.package_id,
                    last_error=f"duplicate decision for {aid}",
                )
            seen.add(aid)
            if aid not in target_ids:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error=f"decision for unknown assertion {aid}",
                )
            if action not in allowed:
                av = action.value if hasattr(action, "value") else str(action)
                return RevisionPublicationResult(
                    status=PublicationStatus.FAILED, publication_id=package.package_id,
                    last_error=f"curation action {av} not publishable",
                )
        if seen != target_ids:
            missing = target_ids - seen
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=package.package_id,
                last_error=f"decision coverage mismatch: missing={sorted(missing)}",
            )
        # returned_upstream_count gate
        if getattr(report, "returned_upstream_count", 0):
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=package.package_id,
                last_error="returned_upstream_count > 0",
            )
        status_val = str(getattr(report, "status", "") or "").lower()
        if status_val in ("return_upstream", "pending_review", "rejected"):
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=package.package_id,
                last_error=f"report.status {status_val} blocks publication",
            )
        return None

    def _existing_commit_guard(
        self, package: RevisionPackage, ref_id: str, fingerprint: str
    ) -> Optional[RevisionPublicationResult]:
        """R1-05: material-exact existing commit guard. Fail closed on store errors."""
        if self._commit_store is None:
            return None
        try:
            existing = self._commit_store.find_by_key(ref_id, fingerprint)
        except Exception as exc:
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=package.package_id,
                last_error=f"commit store inspection failed: {exc}",
            )
        if existing is None:
            return None
        admitted = getattr(existing, "admitted", None) or []
        if not admitted:
            return None
        target_by_id = {a.id: a for a in package.target_assertions}
        admitted_ids = set()
        for item in admitted:
            a = getattr(item, "assertion", item)
            aid = getattr(a, "id", None)
            admitted_ids.add(aid)
            if aid not in target_by_id:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error=f"existing commit has unknown assertion {aid}",
                )
            if not _assertion_material_equal(target_by_id[aid], a):
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error=f"existing commit material mismatch for {aid}",
                )
        if admitted_ids != set(target_by_id):
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="existing commit admitted ID set mismatch",
            )
        return None

    # ---- main async entry ----

    async def publish(
        self,
        *,
        package: RevisionPackage,
        target_commit_request: Optional[CommitRequest] = None,
        approval: Optional[RevisionApproval] = None,
    ) -> RevisionPublicationResult:
        """Run the recoverable publication saga (async)."""
        # Pre-side-effect validation
        gate_err = self._validate_package_gate(package)
        if gate_err is not None:
            return gate_err

        lineage, lineage_err = self._validate_lineage(package, target_commit_request) if target_commit_request else (None, RevisionPublicationResult(
            status=PublicationStatus.FAILED, publication_id=package.package_id,
            last_error="target_commit_request is required",
        ))
        if lineage_err is not None:
            return lineage_err
        prior = lineage["prior"]
        new = lineage["new"]

        req_err = self._validate_target_request(package, target_commit_request, new)
        if req_err is not None:
            return req_err

        cur_err = self._validate_curation(package, target_commit_request)
        if cur_err is not None:
            return cur_err

        guard_err = self._existing_commit_guard(package, package.new_ref_id, new.source_fingerprint)
        if guard_err is not None:
            return guard_err

        # R1-03: scope hash binds actual CommitRequest
        scope_hash = compute_publication_scope_hash(package, target_commit_request)

        # R1-08: approval logic based on real draft risk state
        from knowledge_curator.core.version_delta import package_to_revision_draft

        draft = package_to_revision_draft(package)
        if draft.manual_adjudication_required:
            if approval is None:
                return RevisionPublicationResult(
                    status=PublicationStatus.APPROVAL_REQUIRED, publication_id=package.package_id,
                    last_error="revision approval required",
                )
            if approval.decision != ApprovalDecision.APPROVED:
                return RevisionPublicationResult(
                    status=PublicationStatus.APPROVAL_REJECTED, publication_id=package.package_id,
                    last_error="approval decision is REJECTED",
                )
            if approval.package_id != package.package_id:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="approval.package_id mismatch",
                )
            if approval.scope_hash != scope_hash:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="approval.scope_hash mismatch",
                )
            if not approval.approval_id or not approval.approver:
                return RevisionPublicationResult(
                    status=PublicationStatus.APPROVAL_REQUIRED, publication_id=package.package_id,
                    last_error="approval_id/approver must be non-empty",
                )

        request_mat = compute_request_material_hash(package, scope_hash, approval)
        pub_id = package.package_id

        # R1-14: post-bind recovery check
        if new.kb_version_id is not None:
            existing_rec = self._journal.get(pub_id)
            if (
                existing_rec is not None
                and existing_rec.phase == PublicationPhase.FINALIZED
                and existing_rec.final_version_id == new.kb_version_id
                and existing_rec.final_snapshot_id == new.snapshot_id
            ):
                return RevisionPublicationResult(
                    status=PublicationStatus.FINALIZED, publication_id=pub_id,
                    final_version_id=new.kb_version_id, final_snapshot_id=new.snapshot_id,
                    idempotent=True,
                )
            if (
                existing_rec is not None
                and existing_rec.phase == PublicationPhase.LIFECYCLE_PUBLISHED
                and existing_rec.final_version_id == new.kb_version_id
                and existing_rec.final_snapshot_id == new.snapshot_id
            ):
                # Crash after bind before journal ack -> finalize idempotently
                existing_rec.phase = PublicationPhase.FINALIZED
                self._journal.update(existing_rec)
                return RevisionPublicationResult(
                    status=PublicationStatus.FINALIZED, publication_id=pub_id,
                    final_version_id=new.kb_version_id, final_snapshot_id=new.snapshot_id,
                    idempotent=True, resumed=True,
                )
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="new source version bound to unexpected KB version",
            )

        # Journal
        existing = self._journal.get(pub_id)
        if existing is not None:
            if existing.request_material_hash != request_mat:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=pub_id,
                    last_error="publication request material conflict",
                )
            if existing.phase == PublicationPhase.FINALIZED:
                return RevisionPublicationResult(
                    status=PublicationStatus.FINALIZED, publication_id=pub_id,
                    final_version_id=existing.final_version_id,
                    final_snapshot_id=existing.final_snapshot_id, idempotent=True,
                )
            record = existing
        else:
            record = RevisionPublicationRecord(
                publication_id=pub_id, package_id=package.package_id,
                request_material_hash=request_mat, phase=PublicationPhase.PREPARED,
                approval_id=approval.approval_id if approval else None,
                trace_id=package.trace_id, provenance_id=package.provenance_id,
            )
            record = self._journal.create(record)

        # Step A: target commit
        if record.phase == PublicationPhase.PREPARED:
            commit_err = await self._run_target_commit(package, target_commit_request, record, new)
            if commit_err is not None:
                return commit_err
            record = self._journal.get(pub_id)

        # Step B: lifecycle
        if record.phase == PublicationPhase.TARGET_PUBLISHED:
            life_err = self._run_lifecycle(package, record, prior, approval, draft)
            if life_err is not None:
                return life_err
            record = self._journal.get(pub_id)

        # Step C: final bind
        if record.phase == PublicationPhase.LIFECYCLE_PUBLISHED:
            bind_err = self._run_final_bind(package, record, new)
            if bind_err is not None:
                return bind_err
            record = self._journal.get(pub_id)

        if record.phase == PublicationPhase.FINALIZED:
            return RevisionPublicationResult(
                status=PublicationStatus.FINALIZED, publication_id=pub_id,
                target_version_id=record.target_version_id,
                target_snapshot_id=record.target_snapshot_id,
                final_version_id=record.final_version_id,
                final_snapshot_id=record.final_snapshot_id,
                lifecycle_id=record.lifecycle_id, idempotent=True,
            )

        return RevisionPublicationResult(
            status=PublicationStatus.FAILED, publication_id=pub_id,
            last_error="publication did not reach FINALIZED",
        )

    async def _run_target_commit(
        self,
        package: RevisionPackage,
        request: CommitRequest,
        record: RevisionPublicationRecord,
        new: Any,
    ) -> Optional[RevisionPublicationResult]:
        if self._commit is None:
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error="document commit coordinator not configured",
            )
        try:
            result = await self._commit.commit(request)
        except Exception as exc:
            record.last_error = f"target commit error: {exc}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )

        status = getattr(result, "status", None)
        status_val = status.value if hasattr(status, "value") else str(status or "").lower()

        if status_val in ("pending_vector", "pending_finalize"):
            record.last_error = f"target commit pending: {status_val}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.TARGET_PENDING, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if status_val not in ("published", "idempotent_hit"):
            record.last_error = f"target commit not publishable: {status_val}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )

        version_id = getattr(result, "version_id", None)
        snapshot_id = getattr(result, "snapshot_id", None)
        if version_id is None or snapshot_id is None:
            record.last_error = "target commit result missing version/snapshot"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )

        # R1-08: full target version/snapshot validation
        ver = self._versions.get_version(version_id)
        if ver is None or not ver.published:
            record.last_error = f"target version {version_id} not published"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if ver.snapshot_id != snapshot_id:
            record.last_error = "target version.snapshot_id != commit result snapshot_id"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        snap = self._versions.get_snapshot(snapshot_id)
        if snap is None:
            record.last_error = f"target snapshot {snapshot_id} not found"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        # Snapshot manifest agrees with new source identity
        if snap.manifest.ref_id != new.ref_id or snap.manifest.source_fingerprint != new.source_fingerprint:
            record.last_error = "target snapshot manifest ref/fingerprint mismatch"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
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
        draft: Any,
    ) -> Optional[RevisionPublicationResult]:
        # Authorized draft
        draft = copy.deepcopy(draft)
        draft.base_version_id = record.target_version_id
        if approval is not None:
            draft.manual_adjudication_required = False
            # KEEP risk_decision = MANUAL_ADJUDICATION_REQUIRED
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
                record.last_error = f"stale base: {msg}"
                self._journal.update(record)
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                    last_error=record.last_error,
                )
            record.last_error = f"lifecycle error: {msg}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.LIFECYCLE_PENDING, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        except Exception as exc:
            record.last_error = f"lifecycle error: {exc}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.LIFECYCLE_PENDING, publication_id=record.publication_id,
                last_error=record.last_error,
            )

        final_version_id = getattr(life_result, "version_id", None)
        final_snapshot_id = getattr(life_result, "snapshot_id", None)

        # Recover snapshot if missing (R1 plan §13)
        if final_version_id is not None and final_snapshot_id is None:
            ver = self._versions.get_version(final_version_id)
            if ver is not None:
                final_snapshot_id = ver.snapshot_id

        if final_version_id is None:
            record.last_error = "lifecycle produced no version"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )

        final_ver = self._versions.get_version(final_version_id)
        if final_ver is None or not final_ver.published:
            record.last_error = f"final version {final_version_id} not published"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if final_ver.prior_version_id != record.target_version_id:
            record.last_error = (
                f"final prior {final_ver.prior_version_id} != target {record.target_version_id}"
            )
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                last_error=record.last_error,
            )

        # R1-09: final snapshot content preservation
        if final_snapshot_id is None:
            final_snapshot_id = final_ver.snapshot_id
        if final_ver.snapshot_id != final_snapshot_id:
            record.last_error = "final version.snapshot_id mismatch"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        final_snap = self._versions.get_snapshot(final_snapshot_id)
        target_snap = self._versions.get_snapshot(record.target_snapshot_id)
        if final_snap is None or target_snap is None:
            record.last_error = "final or target snapshot not found"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        tm, fm = target_snap.manifest, final_snap.manifest
        for field_name in (
            "ref_id", "source_fingerprint", "structural_stage_id",
            "metadata_hash",
        ):
            if getattr(tm, field_name) != getattr(fm, field_name):
                record.last_error = f"final snapshot lost target content: {field_name}"
                self._journal.update(record)
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                    last_error=record.last_error,
                )
        for list_field in (
            "assertion_hashes", "usdo_hashes", "usdo_record_ids",
            "vector_ids", "decision_hashes",
        ):
            if sorted(getattr(tm, list_field) or []) != sorted(getattr(fm, list_field) or []):
                record.last_error = f"final snapshot lost target content: {list_field}"
                self._journal.update(record)
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
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
            self._registry.bind_source_version(
                package.new_source_version_id,
                record.final_version_id,
                record.final_snapshot_id or "",
            )
        except ValueError as exc:
            msg = str(exc)
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
                    status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                    last_error=record.last_error,
                )
            record.last_error = f"bind error: {msg}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )

        record.phase = PublicationPhase.FINALIZED
        try:
            self._journal.update(record)
        except Exception as exc:
            record.last_error = f"journal finalize error: {exc}"
            try:
                self._journal.update(record)
            except Exception:
                pass
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        return None
