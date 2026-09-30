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


def _commit_assertion_hash(assertion: Assertion) -> str:
    """Mirror DocumentCommitCoordinator._hash_assertion for manifest agreement checks."""
    return _hash_json(
        {
            "id": assertion.id,
            "ref_id": assertion.ref_id,
            "subject_class": assertion.subject.eddo_class,
            "subject_entity": assertion.subject.resolved_entity,
            "subject_mention": assertion.subject.original_mention,
            "property": assertion.property,
            "value": assertion.object.value,
            "unit": assertion.object.unit,
            "value_type": assertion.object.value_type.value,
            "uncertainty": assertion.object.uncertainty,
            "conditions": [
                {"c": cond.eddo_class, "v": cond.value, "u": cond.unit}
                for cond in assertion.conditions
            ],
            "locator": assertion.provenance.locator if assertion.provenance else None,
            "sentence": assertion.provenance.sentence if assertion.provenance else None,
            "claim_type": assertion.claim_type.value,
            "origin": assertion.source_claim_origin.value,
            "quality": assertion.quality,
        }
    )


def canonical_value(value: Any) -> Any:
    """Typed canonical representation preserving primitive/nested types (R2-02)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [canonical_value(v) for v in value]
    if isinstance(value, tuple):
        return {"__type__": "tuple", "items": [canonical_value(v) for v in value]}
    if isinstance(value, dict):
        return {str(k): canonical_value(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    # Enum or exotic
    if hasattr(value, "value") and hasattr(value, "name"):
        return {"__type__": "enum", "class": type(value).__name__, "value": canonical_value(value.value)}
    return {
        "__type__": f"{type(value).__module__}.{type(value).__qualname__}",
        "repr": repr(value),
    }


def canonical_assertion_material(a: Assertion) -> dict:
    """Canonical publication material for one assertion (R2 typed)."""
    conds = [
        {
            "eddo": c.eddo_class,
            "val": canonical_value(c.value),
            "unit": c.unit,
        }
        for c in (a.conditions or [])
    ]
    conds.sort(key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False, default=str))
    return {
        "id": a.id,
        "ref": a.ref_id,
        "eddo": a.subject.eddo_class,
        "entity": a.subject.resolved_entity,
        "mention": a.subject.original_mention,
        "prop": a.property,
        "val": canonical_value(a.object.value),
        "unit": a.object.unit,
        "vt": a.object.value_type.value,
        "unc": canonical_value(a.object.uncertainty),
        "conds": conds,
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

    def _expected_metadata_hash(self, request: CommitRequest) -> str:
        """Mirror frozen DocumentCommitCoordinator metadata hashing (R2-03)."""
        meta = request.assertion_set.metadata
        return _hash_json(
            {
                "title": meta.title,
                "authors": list(meta.authors),
                "year": meta.year,
                "source": meta.source,
                "doi": meta.doi,
                "stable_id": meta.stable_id,
            }
        )

    def _expected_decision_map(self, request: CommitRequest) -> dict[str, dict]:
        """Derive expected admitted decision material from request.report (R2-04)."""
        out: dict[str, dict] = {}
        for d in getattr(request.report, "decisions", []) or []:
            aid = getattr(d, "assertion_id", None)
            action = getattr(d, "action", None)
            conf = getattr(d, "confidence", None)
            action_val = action.value if hasattr(action, "value") else str(action)
            conf_val = conf.value if hasattr(conf, "value") else str(conf)
            if action_val == "accept":
                vis = "active"
            elif action_val == "downgrade":
                vis = "downgraded"
            else:
                vis = None
            out[aid] = {"action": action_val, "confidence": conf_val, "visibility": vis}
        return out

    def _existing_commit_guard(
        self, package: RevisionPackage, request: CommitRequest
    ) -> Optional[RevisionPublicationResult]:
        """Material-exact existing commit guard (R2). Fail closed on published material drift."""
        if self._commit_store is None:
            return None
        ref_id = request.source.ref_id
        fingerprint = request.source.source_fingerprint
        try:
            existing = self._commit_store.find_by_key(ref_id, fingerprint)
        except Exception as exc:
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=package.package_id,
                last_error=f"commit store inspection failed: {exc}",
            )
        if existing is None:
            return None

        expected_meta_hash = self._expected_metadata_hash(request)
        existing_meta_hash = getattr(existing, "metadata_hash", None)
        if existing_meta_hash and existing_meta_hash != expected_meta_hash:
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                last_error="existing commit metadata_hash mismatch",
            )

        existing_manifest = getattr(existing, "manifest", None)
        if existing_manifest is not None:
            if getattr(existing_manifest, "metadata_hash", None) and existing_manifest.metadata_hash != expected_meta_hash:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="existing manifest metadata_hash mismatch",
                )
            if getattr(existing_manifest, "ref_id", None) and existing_manifest.ref_id != ref_id:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="existing manifest ref_id mismatch",
                )
            if getattr(existing_manifest, "source_fingerprint", None) and existing_manifest.source_fingerprint != fingerprint:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="existing manifest fingerprint mismatch",
                )

        admitted = getattr(existing, "admitted", None) or []
        expected_decisions = self._expected_decision_map(request)
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
            exp = expected_decisions.get(aid)
            if exp is not None:
                item_action = getattr(item, "action", None)
                item_action_val = item_action.value if hasattr(item_action, "value") else str(item_action)
                if item_action_val != exp["action"]:
                    return RevisionPublicationResult(
                        status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                        last_error=f"existing action {item_action_val} != expected {exp['action']} for {aid}",
                    )
                item_conf = getattr(item, "confidence", None)
                item_conf_val = item_conf.value if hasattr(item_conf, "value") else str(item_conf)
                if item_conf_val != exp["confidence"]:
                    return RevisionPublicationResult(
                        status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                        last_error=f"existing confidence {item_conf_val} != expected {exp['confidence']} for {aid}",
                    )
                item_vis = getattr(item, "visibility", None)
                item_vis_val = item_vis.value if hasattr(item_vis, "value") else str(item_vis)
                if exp["visibility"] is not None and item_vis_val != exp["visibility"]:
                    return RevisionPublicationResult(
                        status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                        last_error=f"existing visibility {item_vis_val} != expected {exp['visibility']} for {aid}",
                    )

        phase = getattr(existing, "phase", None)
        phase_val = phase.value if hasattr(phase, "value") else str(phase or "").lower()
        if phase_val == "published":
            # A published exact-replay candidate must carry a complete, request-matching manifest.
            if existing_meta_hash != expected_meta_hash:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="published existing commit missing/mismatched metadata_hash",
                )
            if getattr(existing, "ref_id", ref_id) != ref_id or getattr(existing, "source_fingerprint", fingerprint) != fingerprint:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="published existing commit identity mismatch",
                )
            if existing_manifest is None:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="published existing commit missing manifest",
                )
            if (
                existing_manifest.ref_id != ref_id
                or existing_manifest.source_fingerprint != fingerprint
                or existing_manifest.metadata_hash != expected_meta_hash
            ):
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="published existing manifest identity/metadata mismatch",
                )
            expected_assertion_hashes = sorted(
                _commit_assertion_hash(a) for a in request.assertion_set.assertions
            )
            if sorted(existing_manifest.assertion_hashes or []) != expected_assertion_hashes:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="published existing manifest assertion_hashes mismatch",
                )
            expected_decision_hashes = sorted(
                _hash_json(
                    {
                        "assertion_id": aid,
                        "action": material["action"],
                        "confidence": material["confidence"],
                        "visibility": material["visibility"],
                    }
                )
                for aid, material in expected_decisions.items()
            )
            if sorted(existing_manifest.decision_hashes or []) != expected_decision_hashes:
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="published existing manifest decision_hashes mismatch",
                )
            if not existing_manifest.content_hash or existing_manifest.content_hash != _hash_json(existing_manifest.stable_payload()):
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="published existing manifest content_hash mismatch",
                )
            if admitted_ids != set(target_by_id):
                return RevisionPublicationResult(
                    status=PublicationStatus.CONFLICT, publication_id=package.package_id,
                    last_error="existing commit admitted ID set mismatch",
                )
        elif admitted and admitted_ids != set(target_by_id):
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

        guard_err = self._existing_commit_guard(package, target_commit_request)
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
        is_resumed = False

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
                    idempotent=True, resumed=True,
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
                    final_snapshot_id=existing.final_snapshot_id,
                    idempotent=True, resumed=True,
                )
            record = existing
            is_resumed = True
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
            # R2-06: fresh vs replay result semantics
            return RevisionPublicationResult(
                status=PublicationStatus.FINALIZED, publication_id=pub_id,
                target_version_id=record.target_version_id,
                target_snapshot_id=record.target_snapshot_id,
                final_version_id=record.final_version_id,
                final_snapshot_id=record.final_snapshot_id,
                lifecycle_id=record.lifecycle_id,
                idempotent=is_resumed,
                resumed=is_resumed,
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
        if self._commit_store is None:
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error="document commit store not configured",
            )
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

        # R2-05: strict post-target commit-store agreement.
        # A successful CommitResult is not trusted until the persisted record and
        # its manifest agree with the resolved VersionStore snapshot.
        try:
            store_rec = self._commit_store.find_by_key(new.ref_id, new.source_fingerprint)
        except Exception as exc:
            record.last_error = f"post-commit store read failed: {exc}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if store_rec is None:
            record.last_error = "post-commit store record missing"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.FAILED, publication_id=record.publication_id,
                last_error=record.last_error,
            )

        rec_phase = getattr(store_rec, "phase", None)
        rec_phase_val = rec_phase.value if hasattr(rec_phase, "value") else str(rec_phase or "").lower()
        if rec_phase_val != "published":
            record.last_error = f"post-commit store phase {rec_phase_val} not published"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if getattr(store_rec, "ref_id", None) != new.ref_id:
            record.last_error = "post-commit store ref_id mismatch"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if getattr(store_rec, "source_fingerprint", None) != new.source_fingerprint:
            record.last_error = "post-commit store source_fingerprint mismatch"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if getattr(store_rec, "version_id", None) != version_id:
            record.last_error = f"post-commit store version_id {getattr(store_rec, 'version_id', None)} != result {version_id}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if getattr(store_rec, "snapshot_id", None) != snapshot_id:
            record.last_error = f"post-commit store snapshot_id {getattr(store_rec, 'snapshot_id', None)} != result {snapshot_id}"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                last_error=record.last_error,
            )

        store_manifest = getattr(store_rec, "manifest", None)
        if store_manifest is None:
            record.last_error = "post-commit store manifest missing"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if store_manifest.ref_id != new.ref_id or store_manifest.source_fingerprint != new.source_fingerprint:
            record.last_error = "post-commit store manifest ref/fingerprint mismatch"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        resolved_manifest = snap.manifest
        if (
            not store_manifest.content_hash
            or not resolved_manifest.content_hash
            or store_manifest.content_hash != resolved_manifest.content_hash
        ):
            record.last_error = "post-commit store manifest content_hash mismatch"
            self._journal.update(record)
            return RevisionPublicationResult(
                status=PublicationStatus.CONFLICT, publication_id=record.publication_id,
                last_error=record.last_error,
            )
        if store_manifest.stable_payload() != resolved_manifest.stable_payload():
            record.last_error = "post-commit store manifest payload mismatch"
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
