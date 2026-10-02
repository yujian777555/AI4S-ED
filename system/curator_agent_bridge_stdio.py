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

        assertions.append(Assertion(
            id=a.get("id", ""),
            ref_id=a.get("ref_id", ""),
            subject=Subject(
                eddo_class=subj.get("eddo_class", ""),
                resolved_entity=subj.get("resolved_entity", ""),
                original_mention=subj.get("original_mention", ""),
            ),
            property=a.get("property", ""),
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

    return AssertionSet(
        ref_id=data.get("ref_id", ""),
        metadata=metadata,
        assertions=assertions,
    )


def _hydrate_source_identity(data: dict) -> Any:
    from knowledge_curator.schemas.commit import SourceIdentity
    return SourceIdentity(
        ref_id=data.get("ref_id", ""),
        source_fingerprint=data.get("source_fingerprint", ""),
    )


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
        assertions.append(Assertion(
            id=a.get("id", ""),
            ref_id=a.get("ref_id", ""),
            subject=Subject(eddo_class=subj.get("eddo_class", ""), resolved_entity=subj.get("resolved_entity", ""), original_mention=subj.get("original_mention", "")),
            property=a.get("property", ""),
            object=ObjectValue(value=obj.get("value"), unit=obj.get("unit"), value_type=ValueType.NUMBER, uncertainty=obj.get("uncertainty")),
            conditions=[Condition(eddo_class=c.get("eddo_class", ""), value=c.get("value"), unit=c.get("unit")) for c in (a.get("conditions") or [])],
            provenance=Provenance(locator=prov.get("locator", ""), sentence=prov.get("sentence")) if prov.get("locator") else None,
            claim_type=ClaimType.MEASUREMENT,
            source_claim_origin=SourceClaimOrigin.PRIMARY,
            confidence=Confidence.MEDIUM,
            quality=a.get("quality", 0.5),
        ))

    return RevisionPackage(
        package_id=data.get("package_id", ""),
        work_id=data.get("work_id", ""),
        prior_source_version_id=data.get("prior_source_version_id", ""),
        new_source_version_id=data.get("new_source_version_id", ""),
        relation=relation,
        prior_ref_id=data.get("prior_ref_id", ""),
        new_ref_id=data.get("new_ref_id", ""),
        prior_bound_kb_version_id=data.get("prior_bound_kb_version_id"),
        content_delta=ContentDeltaPlan(mode=DeltaMode.DELTA_SAFE),
        target_assertions=assertions,
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
        decisions.append(AssertionDecision(
            assertion_id=d.get("assertion_id", ""),
            action=action,
            confidence=conf,
            reason=d.get("reason", ""),
        ))

    report = CurationReport(
        report_id=report_raw.get("report_id", ""),
        source_ref_id=report_raw.get("source_ref_id", source.ref_id),
        status=report_raw.get("status", "successful"),
        completeness=CompletenessResult(status=CompletenessStatus.OK),
        decisions=decisions,
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
    return RevisionApproval(
        approval_id=data.get("approval_id", ""),
        package_id=data.get("package_id", ""),
        scope_hash=data.get("scope_hash", ""),
        decision=decision,
        approver=data.get("approver", ""),
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
