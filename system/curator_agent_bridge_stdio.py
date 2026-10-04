"""SI-4-R4 Production bridge entrypoint for DSH Knowledge Curator Agent.

Usage: python -m system.curator_agent_bridge_stdio <action>

stdin: JSON request
stdout: JSON response
stderr: diagnostics

Actions:
  curate_and_commit -- Section 5 curation + commit
  revise -- Section 7 revision publication

Reads AI4S_SYSTEM_ADAPTER_FACTORY for provider composition.
Never imports integration test fixtures.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Optional


def _hydrate_assertion_set(data: dict) -> Any:
    """Hydrate JSON dict into frozen AssertionSet type."""
    from knowledge_curator.schemas.assertions import (
        Assertion, AssertionSet, ClaimType, Confidence, Condition,
        DocumentMetadata, ObjectValue, Provenance, SourceClaimOrigin,
        Subject, ValueType,
    )

    meta_raw = data.get("metadata") or {}
    metadata = DocumentMetadata(
        title=meta_raw.get("title", ""),
        authors=meta_raw.get("authors", []),
        year=meta_raw.get("year"),
        source=meta_raw.get("source", ""),
        doi=meta_raw.get("doi"),
        stable_id=meta_raw.get("stable_id"),
    )

    assertions = []
    for a in data.get("assertions") or []:
        subj = a.get("subject") or {}
        obj = a.get("object") or {}
        prov = a.get("provenance") or {}
        cond_raw = a.get("conditions") or []
        conditions = [
            Condition(eddo_class=c.get("eddo_class", ""), value=c.get("value"), unit=c.get("unit"))
            for c in cond_raw
        ]
        vt = obj.get("value_type")
        if vt is None:
            raise ValueError("object.value_type is required")
        try:
            value_type = ValueType(vt)
        except ValueError:
            raise ValueError(f"invalid value_type: {vt}")

        ct = a.get("claim_type")
        if ct is None:
            raise ValueError("claim_type is required")
        try:
            claim_type = ClaimType(ct)
        except ValueError:
            raise ValueError(f"invalid claim_type: {ct}")

        sco = a.get("source_claim_origin")
        if sco is None:
            raise ValueError("source_claim_origin is required")
        try:
            origin = SourceClaimOrigin(sco)
        except ValueError:
            raise ValueError(f"invalid source_claim_origin: {sco}")

        conf = a.get("confidence")
        if conf is None:
            raise ValueError("confidence is required")
        try:
            confidence = Confidence(conf)
        except ValueError:
            raise ValueError(f"invalid confidence: {conf}")

        aid = a.get("id")
        if not aid:
            raise ValueError("assertion.id is required")
        aref = a.get("ref_id")
        if not aref:
            raise ValueError("assertion.ref_id is required")
        prop = a.get("property")
        if not prop:
            raise ValueError("assertion.property is required")

        assertions.append(Assertion(
            id=aid,
            ref_id=aref,
            subject=Subject(
                eddo_class=subj.get("eddo_class", ""),
                resolved_entity=subj.get("resolved_entity", ""),
                original_mention=subj.get("original_mention", ""),
            ),
            property=prop,
            object=ObjectValue(
                value=obj.get("value"),
                unit=obj.get("unit"),
                value_type=value_type,
                uncertainty=obj.get("uncertainty"),
            ),
            conditions=conditions,
            provenance=Provenance(locator=prov.get("locator", ""), sentence=prov.get("sentence")) if prov.get("locator") else None,
            claim_type=claim_type,
            source_claim_origin=origin,
            confidence=confidence,
            quality=a.get("quality", 0.5),
        ))

    ref = data.get("ref_id")
    if not ref:
        raise ValueError("assertion_set.ref_id is required")
    return AssertionSet(
        ref_id=ref,
        metadata=metadata,
        assertions=assertions,
    )


def _hydrate_source_identity(data: dict) -> Any:
    from knowledge_curator.schemas.commit import SourceIdentity
    ref = data.get("ref_id")
    fp = data.get("source_fingerprint")
    if not ref:
        raise ValueError("source.ref_id is required")
    if not fp:
        raise ValueError("source.source_fingerprint is required")
    return SourceIdentity(ref_id=ref, source_fingerprint=fp)


def _hydrate_revision_package(data: dict) -> Any:
    from knowledge_curator.schemas.version_delta import ContentDeltaPlan, DeltaMode, RevisionPackage
    from knowledge_curator.schemas.source_versions import VersionRelation

    rel_str = data.get("relation")
    if not rel_str:
        raise ValueError("relation is required")
    try:
        relation = VersionRelation(rel_str)
    except ValueError:
        raise ValueError(f"invalid relation: {rel_str}")

    assertions = []
    for a in data.get("target_assertions") or []:
        from knowledge_curator.schemas.assertions import (
            Assertion, ClaimType, Confidence, Condition, ObjectValue,
            Provenance, SourceClaimOrigin, Subject, ValueType,
        )
        subj = a.get("subject") or {}
        obj = a.get("object") or {}
        prov = a.get("provenance") or {}
        # R6: strict hydration - no fabricated enum defaults
        vt = obj.get("value_type")
        if not vt:
            raise ValueError("target assertion object.value_type is required")
        try:
            value_type = ValueType(vt)
        except ValueError:
            raise ValueError(f"invalid value_type: {vt}")

        ct = a.get("claim_type")
        if not ct:
            raise ValueError("target assertion claim_type is required")
        try:
            claim_type = ClaimType(ct)
        except ValueError:
            raise ValueError(f"invalid claim_type: {ct}")

        sco = a.get("source_claim_origin")
        if not sco:
            raise ValueError("target assertion source_claim_origin is required")
        try:
            origin = SourceClaimOrigin(sco)
        except ValueError:
            raise ValueError(f"invalid source_claim_origin: {sco}")

        conf = a.get("confidence")
        if not conf:
            raise ValueError("target assertion confidence is required")
        try:
            confidence = Confidence(conf)
        except ValueError:
            raise ValueError(f"invalid confidence: {conf}")

        aid = a.get("id")
        if not aid:
            raise ValueError("target assertion id is required")
        aref = a.get("ref_id")
        if not aref:
            raise ValueError("target assertion ref_id is required")
        prop = a.get("property")
        if not prop:
            raise ValueError("target assertion property is required")

        assertions.append(Assertion(
            id=aid,
            ref_id=aref,
            subject=Subject(eddo_class=subj.get("eddo_class", ""), resolved_entity=subj.get("resolved_entity", ""), original_mention=subj.get("original_mention", "")),
            property=prop,
            object=ObjectValue(value=obj.get("value"), unit=obj.get("unit"), value_type=value_type, uncertainty=obj.get("uncertainty")),
            conditions=[Condition(eddo_class=c.get("eddo_class", ""), value=c.get("value"), unit=c.get("unit")) for c in (a.get("conditions") or [])],
            provenance=Provenance(locator=prov.get("locator", ""), sentence=prov.get("sentence")) if prov.get("locator") else None,
            claim_type=claim_type,
            source_claim_origin=origin,
            confidence=confidence,
            quality=a.get("quality", 0.5),
        ))

    # R6: strict required fields
    for field in ("package_id", "work_id", "prior_source_version_id", "new_source_version_id", "prior_ref_id", "new_ref_id"):
        if not data.get(field):
            raise ValueError(f"package.{field} is required")

    # R7: hydrate content_delta from input
    cd_raw = data.get("content_delta") or {}
    cd_mode_str = cd_raw.get("mode", "delta_safe")
    try:
        cd_mode = DeltaMode(cd_mode_str)
    except ValueError:
        raise ValueError(f"invalid content_delta.mode: {cd_mode_str}")

    content_delta = ContentDeltaPlan(
        mode=cd_mode,
        unchanged_pairs=[_hydrate_aligned_pair(x) for x in (cd_raw.get("unchanged_pairs") or [])],
        modified_pairs=[_hydrate_aligned_pair(x) for x in (cd_raw.get("modified_pairs") or [])],
        added_unit_ids=cd_raw.get("added_unit_ids") or [],
        removed_unit_ids=cd_raw.get("removed_unit_ids") or [],
        extraction_unit_ids=cd_raw.get("extraction_unit_ids") or [],
        diagnostics=cd_raw.get("diagnostics") or {},
    )

    # R7: preserve non-default revision fields
    return RevisionPackage(
        package_id=data["package_id"],
        work_id=data["work_id"],
        prior_source_version_id=data["prior_source_version_id"],
        new_source_version_id=data["new_source_version_id"],
        relation=relation,
        prior_ref_id=data["prior_ref_id"],
        new_ref_id=data["new_ref_id"],
        prior_bound_kb_version_id=data.get("prior_bound_kb_version_id"),
        content_delta=content_delta,
        target_assertions=assertions,
        supersede_actions=data.get("supersede_actions") or {},
        archive_actions=data.get("archive_actions") or [],
        added_assertion_ids=data.get("added_assertion_ids") or [],
        carried_records=[_hydrate_carried_record(x) for x in (data.get("carried_records") or [])],
        transitions=[_hydrate_transition(x) for x in (data.get("transitions") or [])],
        requires_manual_review=data.get("requires_manual_review", False),
        lifecycle_reason=data.get("lifecycle_reason", ""),
        trace_id=data.get("trace_id", ""),
        provenance_id=data.get("provenance_id", ""),
        diagnostics=data.get("diagnostics") or {},
    )


def _hydrate_commit_request(data: dict) -> Any:
    from knowledge_curator.schemas.commit import CommitRequest
    from knowledge_curator.schemas.curation import (
        AssertionDecision, CompletenessResult, CompletenessStatus,
        CurationAction, CurationReport,
    )
    from knowledge_curator.schemas.assertions import Confidence

    source = _hydrate_source_identity(data.get("source") or {})
    assertion_set = _hydrate_assertion_set(data.get("assertion_set") or {})

    report_raw = data.get("report") or {}
    decisions = []
    for d in report_raw.get("decisions") or []:
        action_str = d.get("action")
        if not action_str:
            raise ValueError("decision.action is required")
        try:
            action = CurationAction(action_str)
        except ValueError:
            raise ValueError(f"invalid curation action: {action_str}")
        conf_str = d.get("confidence")
        if not conf_str:
            raise ValueError("decision.confidence is required")
        try:
            conf = Confidence(conf_str)
        except ValueError:
            raise ValueError(f"invalid confidence: {conf_str}")
        aid = d.get("assertion_id")
        if not aid:
            raise ValueError("decision.assertion_id is required")
        reason = d.get("reason")
        if not reason:
            raise ValueError("decision.reason is required")
        decisions.append(AssertionDecision(
            assertion_id=aid,
            action=action,
            confidence=conf,
            reason=reason,
        ))

    # R7: faithful CompletenessResult hydration
    comp_raw = report_raw.get("completeness") or {}
    comp_status_str = comp_raw.get("status")
    if not comp_status_str:
        raise ValueError("report.completeness.status is required")
    try:
        comp_status = CompletenessStatus(comp_status_str)
    except ValueError:
        raise ValueError(f"invalid completeness status: {comp_status_str}")

    # Hydrate CompletenessIssue list
    from knowledge_curator.schemas.curation import CompletenessIssue
    issues = []
    for issue_raw in comp_raw.get("issues") or []:
        if not issue_raw.get("code"):
            raise ValueError("completeness issue.code is required")
        issues.append(CompletenessIssue(
            code=issue_raw["code"],
            message=issue_raw.get("message", ""),
            assertion_ids=issue_raw.get("assertion_ids") or [],
        ))

    # R9: safety fields must be explicitly provided (no permissive defaults)
    def _require_bool(data, field, ctx):
        if field not in data:
            raise ValueError(f"{ctx}.{field} is required")
        v = data[field]
        if not isinstance(v, bool):
            raise ValueError(f"{ctx}.{field} must be bool, got {type(v).__name__}")
        return v

    def _require_nonneg_int(data, field, ctx):
        if field not in data:
            raise ValueError(f"{ctx}.{field} is required")
        v = data[field]
        if not isinstance(v, int) or v < 0:
            raise ValueError(f"{ctx}.{field} must be non-negative int")
        return v

    metadata_valid = _require_bool(comp_raw, "metadata_valid", "completeness")
    assertion_count = _require_nonneg_int(comp_raw, "assertion_count", "completeness")
    allows_formal_curation = _require_bool(comp_raw, "allows_formal_curation", "completeness")
    requires_manual_review = _require_bool(comp_raw, "requires_manual_review", "completeness")
    requires_return_upstream = _require_bool(comp_raw, "requires_return_upstream", "completeness")
    returned_upstream_count = _require_nonneg_int(report_raw, "returned_upstream_count", "report")

    completeness = CompletenessResult(
        status=comp_status,
        issues=issues,
        metadata_valid=metadata_valid,
        assertion_count=assertion_count,
        allows_formal_curation=allows_formal_curation,
        requires_manual_review=requires_manual_review,
        requires_return_upstream=requires_return_upstream,
    )

    report_id = report_raw.get("report_id")
    if not report_id:
        raise ValueError("report.report_id is required")
    report_status = report_raw.get("status")
    if not report_status:
        raise ValueError("report.status is required")

    report = CurationReport(
        report_id=report_id,
        source_ref_id=report_raw.get("source_ref_id", source.ref_id),
        status=report_status,
        completeness=completeness,
        decisions=decisions,
        returned_upstream_count=returned_upstream_count,
        accepted_count=report_raw.get("accepted_count", 0),
        downgraded_count=report_raw.get("downgraded_count", 0),
        rejected_count=report_raw.get("rejected_count", 0),
        pending_count=report_raw.get("pending_count", 0),
        superseded_count=report_raw.get("superseded_count", 0),
        warnings=report_raw.get("warnings") or [],
    )

    return CommitRequest(source=source, assertion_set=assertion_set, report=report)


def _hydrate_approval(data: Optional[dict]) -> Optional[Any]:
    if not data:
        return None
    from knowledge_curator.schemas.revision_publication import ApprovalDecision, RevisionApproval
    dec_str = data.get("decision")
    if not dec_str:
        raise ValueError("approval.decision is required")
    try:
        decision = ApprovalDecision(dec_str)
    except ValueError:
        raise ValueError(f"invalid approval decision: {dec_str}")
    for field in ("approval_id", "package_id", "scope_hash", "approver"):
        if not data.get(field):
            raise ValueError(f"approval.{field} is required")

    return RevisionApproval(
        approval_id=data["approval_id"],
        package_id=data["package_id"],
        scope_hash=data["scope_hash"],
        decision=decision,
        approver=data["approver"],
    )


def _hydrate_aligned_pair(data: dict):
    from knowledge_curator.schemas.version_delta import AlignedPair, DeltaCategory
    prior = data.get("prior_unit_id")
    new = data.get("new_unit_id")
    cat_raw = data.get("category")
    if not prior:
        raise ValueError("aligned_pair.prior_unit_id is required")
    if not new:
        raise ValueError("aligned_pair.new_unit_id is required")
    if not cat_raw:
        raise ValueError("aligned_pair.category is required")
    try:
        category = DeltaCategory(cat_raw)
    except ValueError:
        raise ValueError(f"invalid DeltaCategory: {cat_raw}")
    return AlignedPair(prior_unit_id=prior, new_unit_id=new, category=category)


def _hydrate_carried_record(data: dict):
    from knowledge_curator.schemas.version_delta import CarriedAssertionRecord
    old_id = data.get("old_assertion_id")
    carried_id = data.get("carried_assertion_id")
    unit_id = data.get("unit_id")
    if not old_id:
        raise ValueError("carried_record.old_assertion_id is required")
    if not carried_id:
        raise ValueError("carried_record.carried_assertion_id is required")
    if not unit_id:
        raise ValueError("carried_record.unit_id is required")
    return CarriedAssertionRecord(
        old_assertion_id=old_id,
        carried_assertion_id=carried_id,
        unit_id=unit_id,
    )


def _hydrate_transition(data: dict):
    from knowledge_curator.schemas.version_delta import AssertionTransition, TransitionAction
    action_raw = data.get("action")
    slot_key = data.get("slot_key")
    reason = data.get("reason")
    if not action_raw:
        raise ValueError("transition.action is required")
    if not slot_key:
        raise ValueError("transition.slot_key is required")
    if not reason:
        raise ValueError("transition.reason is required")
    try:
        action = TransitionAction(action_raw)
    except ValueError:
        raise ValueError(f"invalid TransitionAction: {action_raw}")
    return AssertionTransition(
        action=action,
        old_assertion_id=data.get("old_assertion_id"),
        new_assertion_id=data.get("new_assertion_id"),
        slot_key=slot_key,
        reason=reason,
    )


def _build_bridge():
    """Build CuratorAgentBridge using deployment provider factory."""
    from system.provider_loader import load_provider_bundle
    from system.curator_agent_bridge import CuratorAgentBridge

    bundle = load_provider_bundle()  # reads AI4S_SYSTEM_ADAPTER_FACTORY

    # Compose curation workflow
    from system.application_composition import _extract_commit_deps, _validate_commit_deps
    from system.composition import CuratorDependencies, compose_system_runtime
    from system.workflows.curation_commit import CurationCommitWorkflow
    from knowledge_curator.core.commit import DocumentCommitCoordinator

    curator_raw = bundle.get("curator") if isinstance(bundle, dict) else getattr(bundle, "curator", None)
    if curator_raw is None:
        raise RuntimeError("provider bundle missing curator")

    if isinstance(curator_raw, dict):
        curator_deps = CuratorDependencies(
            repository=curator_raw.get("repository"),
            ontology=curator_raw.get("ontology"),
            mechanism_validator=curator_raw.get("mechanism_validator"),
            provider_identity=str(curator_raw.get("provider_identity", "external")),
        )
    else:
        curator_deps = CuratorDependencies(
            repository=getattr(curator_raw, "repository", None),
            ontology=getattr(curator_raw, "ontology", None),
            mechanism_validator=getattr(curator_raw, "mechanism_validator", None),
            provider_identity=str(getattr(curator_raw, "provider_identity", "external")),
        )
    system_rt = compose_system_runtime(curator_deps=curator_deps, evidence_deps=None)

    commit_deps = _extract_commit_deps(bundle)
    _validate_commit_deps(commit_deps)
    doc_commit = DocumentCommitCoordinator(
        commit_store=commit_deps.commit_store,
        structural_store=commit_deps.structural_store,
        vector_index=commit_deps.vector_index,
        usdo_store=commit_deps.usdo_store,
        version_store=commit_deps.version_store,
    )
    curation_workflow = CurationCommitWorkflow(
        curator_runtime=system_rt.curator_runtime,
        commit_coordinator=doc_commit,
        provider_identity=commit_deps.provider_identity,
    )

    # Compose revision workflow (R5: required for full agent)
    revision_raw = bundle.get("revision") if isinstance(bundle, dict) else getattr(bundle, "revision", None)
    if revision_raw is None:
        raise RuntimeError("provider bundle missing revision capability; required for Knowledge Curator Agent")
    revision_workflow = None
    if revision_raw is not None:
        from system.revision_application_composition import (
            _extract_revision_deps, _reject_split_brain, _validate_revision_deps,
        )
        from system.workflows.revision_publication import RevisionPublicationWorkflow
        from knowledge_curator.core.lifecycle import LifecycleRevisionCoordinator
        from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator

        _reject_split_brain(bundle)
        rev_deps = _extract_revision_deps(bundle)
        _validate_revision_deps(rev_deps)

        lifecycle = LifecycleRevisionCoordinator(
            lifecycle_store=rev_deps.lifecycle_store,
            outbox=rev_deps.event_outbox,
            version_store=commit_deps.version_store,
        )
        publication = RevisionPublicationCoordinator(
            publication_store=rev_deps.publication_store,
            source_registry=rev_deps.source_registry,
            version_store=commit_deps.version_store,
            lifecycle_coordinator=lifecycle,
            document_commit_coordinator=doc_commit,
            document_commit_store=commit_deps.commit_store,
        )
        revision_workflow = RevisionPublicationWorkflow(
            revision_publication_coordinator=publication,
            provider_identity=rev_deps.provider_identity,
        )

    return CuratorAgentBridge(
        curation_workflow=curation_workflow,
        revision_workflow=revision_workflow,
    )


def main() -> int:
    import asyncio

    action = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        print(f'R9R1 FULL PAYLOAD: {json.dumps(payload, ensure_ascii=False)[:2000]}', file=sys.stderr)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid JSON: {exc}"}))
        return 1

    try:
        bridge = _build_bridge()
    except Exception as exc:
        print(json.dumps({"error": f"provider/composition failed: {exc}"}))
        return 1

    try:
        if action == "curate_and_commit":
            # R6: validate required fields
            if not payload.get("source_ref_id"):
                raise ValueError("source_ref_id is required")
            if not payload.get("source_fingerprint"):
                raise ValueError("source_fingerprint is required")
            result = asyncio.run(bridge.curate_and_commit(
                source_ref_id=payload.get("source_ref_id", ""),
                source_fingerprint=payload.get("source_fingerprint", ""),
                assertion_set=_hydrate_assertion_set(payload.get("assertion_set") or {}),
                metadata=payload.get("metadata") or {},
                trace=payload.get("trace") or {},
            ))
            print(json.dumps({
                "status": result.status,
                "commit_attempted": result.commit_attempted,
                "blocked_reason": result.blocked_reason,
            }))
        elif action == "revise":
            import sys as _s
            _pkg = payload.get("package") or {}
            print(f"R9R1 DEBUG package.prior_bound_kb_version_id={_pkg.get('prior_bound_kb_version_id')}", file=_s.stderr)
            print(f"R9R1 DEBUG package.target_assertions[0].confidence={(_pkg.get('target_assertions') or [{}])[0].get('confidence')}", file=_s.stderr)
            _req = payload.get("target_commit_request") or {}
            _as = (_req.get('assertion_set') or {}).get('assertions') or [{}]
            print(f"R9R1 DEBUG request.assertions[0].confidence={_as[0].get('confidence')}", file=_s.stderr)
            package = _hydrate_revision_package(payload.get("package") or {})
            request = _hydrate_commit_request(payload.get("target_commit_request") or {})
            approval = _hydrate_approval(payload.get("approval"))
            result = asyncio.run(bridge.revise(
                package=package,
                target_commit_request=request,
                approval=approval,
            ))
            print(json.dumps({
                "status": result.status,
                "error": result.error,
            }))
        else:
            print(json.dumps({"error": f"unknown action: {action}"}))
            return 1
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

