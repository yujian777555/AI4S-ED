"""SI-4-R3 DSH Native Bridge & Truthful Product Qualification tests."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "dsh" / "knowledge-curator"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))


def _run(coro):
    return asyncio.run(coro)


class TestRealDshQualification:
    def test_package_manifest_valid(self):
        pkg = json.loads((PKG / "package.json").read_text(encoding="utf-8-sig"))
        for f in pkg.get("files", []):
            assert (PKG / f).exists(), f"missing: {f}"
        for key, val in pkg.get("exports", {}).items():
            if val.startswith("./"):
                assert (PKG / val[2:]).exists(), f"missing export: {val}"

    def test_pnpm_pack_dry_run_includes_required_files(self):
        result = subprocess.run("pnpm pack --dry-run", cwd=str(PKG), capture_output=True, text=True, timeout=60, shell=True)
        assert result.returncode == 0
        output = result.stdout + result.stderr
        for required in ["cordis.patch.yml", "prompt.md", "tools.yaml", "runtime/bridge-plugin.js"]:
            assert required in output, f"{required} not in pack output"

    def test_bridge_plugin_in_package(self):
        assert (PKG / "runtime" / "bridge-plugin.js").exists()
        text = (PKG / "runtime" / "bridge-plugin.js").read_text(encoding="utf-8-sig")
        assert "curate_and_commit" in text
        assert "revise" in text

    def test_bridge_plugin_registered_in_preset(self):
        text = (PKG / "cordis.patch.yml").read_text(encoding="utf-8-sig")
        assert "bridge" in text.lower() or "curator-bridge" in text.lower() or "bridge-plugin" in text.lower()


class TestMountedSection5:
    def test_mounted_bridge_curate_and_commit(self):
        from system.curator_agent_bridge import CuratorAgentBridge
        from system.workflows.curation_commit import CurationCommitWorkflow
        from system.application_composition import _extract_commit_deps, _validate_commit_deps
        from system.composition import CuratorDependencies, compose_system_runtime
        from knowledge_curator.core.commit import DocumentCommitCoordinator
        from knowledge_curator.schemas.assertions import (
            Assertion, AssertionSet, ClaimType, Confidence, Condition,
            DocumentMetadata, ObjectValue, Provenance, SourceClaimOrigin, Subject, ValueType,
        )
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        curator_raw = bundle["curator"]
        commit_deps = _extract_commit_deps(bundle)
        _validate_commit_deps(commit_deps)
        curator_deps = CuratorDependencies(
            repository=curator_raw["repository"], ontology=curator_raw["ontology"],
            mechanism_validator=curator_raw["mechanism_validator"], provider_identity=curator_raw["provider_identity"],
        )
        system_rt = compose_system_runtime(curator_deps=curator_deps, evidence_deps=None)
        doc_commit = DocumentCommitCoordinator(
            commit_store=commit_deps.commit_store, structural_store=commit_deps.structural_store,
            vector_index=commit_deps.vector_index, usdo_store=commit_deps.usdo_store,
            version_store=commit_deps.version_store,
        )
        workflow = CurationCommitWorkflow(
            curator_runtime=system_rt.curator_runtime, commit_coordinator=doc_commit, provider_identity="dsh-mounted",
        )
        bridge = CuratorAgentBridge(curation_workflow=workflow)

        assertion = Assertion(
            id="AS-001", ref_id="ED-MOUNTED",
            subject=Subject(eddo_class="Membrane", resolved_entity="eddo:membrane:bpm", original_mention="BPM"),
            property="hasEnergyConsumption",
            object=ObjectValue(value=1.42, unit="kWh/m3", value_type=ValueType.NUMBER, uncertainty=0.05),
            conditions=[Condition(eddo_class="Temperature", value=298.15, unit="K")],
            provenance=Provenance(locator="p.1", sentence="energy is 1.42"),
            claim_type=ClaimType.MEASUREMENT, source_claim_origin=SourceClaimOrigin.PRIMARY,
            confidence=Confidence.MEDIUM, quality=0.85,
        )
        assertion_set = AssertionSet(
            ref_id="ED-MOUNTED",
            metadata=DocumentMetadata(title="Mounted Test", authors=["A"], year=2024, source="J", doi="10.0/m", stable_id="ST-M"),
            assertions=[assertion],
        )
        result = _run(bridge.curate_and_commit(
            source_ref_id="ED-MOUNTED", source_fingerprint="fp-mounted-001",
            assertion_set=assertion_set, metadata={}, trace={"trace_id": "tr-mounted"},
        ))
        assert result.commit_attempted is True
        assert result.status == "published"
        assert len(commit_deps.version_store.list_published_versions()) == 1


class TestMountedSection6:
    def test_evidence_derived_claim_content(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {"ok": True, "evidence_bundle": {"evidence_records": [{
                    "chunk_id": "R1-F1", "ref_id": "REF-1", "confidence": "high",
                    "payload_excerpt": "Energy consumption was 1.42 kWh/m3.",
                }], "abstain": {"abstain": False}}}
            if "validate_retrieved_claims" in tool_name:
                claims = args.get("payload", {}).get("claims", [])
                for c in claims:
                    assert "1.42" in c.get("text", "") or "energy" in c.get("text", "").lower()
                return {"ok": True, "claim_results": [{
                    "claim_id": "C1", "claim_text": "Energy consumption was 1.42 kWh/m3.",
                    "policy": {"policy": "factual_allowed", "effective_confidence": "high"},
                    "abstain": {"abstain": False},
                    "resolved_anchors": [{"ref_id": "REF-1", "locator": "p.1", "confidence": "high", "access_pointer": "fixture://REF-1/R1-F1"}],
                }]}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("What is the energy consumption?", CuratorContext()))
        assert result["status"] == "answered"
        assert "1.42" in result.get("answer", "") or "energy" in result.get("answer", "").lower()
        assert len(result.get("claims", [])) > 0

    def test_validation_before_answer(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext
        call_order = []

        async def mock_invoker(tool_name, args):
            call_order.append(tool_name)
            if "retrieve_evidence" in tool_name:
                return {"ok": True, "evidence_bundle": {"evidence_records": [{"chunk_id": "R1-F1", "ref_id": "REF-1", "payload_excerpt": "test"}], "abstain": {"abstain": False}}}
            if "validate_retrieved_claims" in tool_name:
                return {"ok": True, "claim_results": [{"claim_id": "C1", "policy": {"policy": "factual_allowed"}, "abstain": {"abstain": False}, "resolved_anchors": [{"ref_id": "REF-1"}]}]}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("test", CuratorContext()))
        ri = next(i for i, c in enumerate(call_order) if "retrieve_evidence" in c)
        vi = next(i for i, c in enumerate(call_order) if "validate_retrieved_claims" in c)
        assert ri < vi

    def test_unsupported_abstain(self):
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {"ok": True, "evidence_bundle": {"evidence_records": [], "abstain": {"abstain": True, "reasons": ["no_evidence"]}}}
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("unknown", CuratorContext()))
        assert result["status"] == "abstain"


class TestMountedSection7:
    def test_mounted_bridge_revision(self):
        from system.curator_agent_bridge import CuratorAgentBridge
        from system.workflows.revision_publication import RevisionPublicationWorkflow
        from system.revision_application_composition import _extract_revision_deps, _reject_split_brain, _validate_revision_deps
        from system.application_composition import _extract_commit_deps, _validate_commit_deps
        from knowledge_curator.core.commit import DocumentCommitCoordinator
        from knowledge_curator.core.lifecycle import LifecycleRevisionCoordinator
        from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        from knowledge_curator.schemas.source_versions import SourceKind, SourceVersionRecord, VersionRelation, WorkRecord
        from knowledge_curator.schemas.commit import SnapshotManifest
        from knowledge_curator.schemas.version_delta import ContentDeltaPlan, DeltaMode, RevisionPackage
        from knowledge_curator.schemas.commit import CommitRequest, SourceIdentity
        from knowledge_curator.schemas.assertions import Assertion, AssertionSet, ClaimType, Confidence, Condition, DocumentMetadata, ObjectValue, Provenance, SourceClaimOrigin, Subject, ValueType
        from knowledge_curator.schemas.curation import AssertionDecision, CompletenessResult, CompletenessStatus, CurationAction, CurationReport
        from knowledge_curator.core.revision_publication import compute_publication_scope_hash
        from knowledge_curator.schemas.revision_publication import ApprovalDecision, RevisionApproval

        bundle = create_si2b_provider_bundle()
        commit_deps = _extract_commit_deps(bundle)
        _validate_commit_deps(commit_deps)
        _reject_split_brain(bundle)
        rev_deps = _extract_revision_deps(bundle)
        _validate_revision_deps(rev_deps)

        doc_commit = DocumentCommitCoordinator(commit_store=commit_deps.commit_store, structural_store=commit_deps.structural_store, vector_index=commit_deps.vector_index, usdo_store=commit_deps.usdo_store, version_store=commit_deps.version_store)
        lifecycle = LifecycleRevisionCoordinator(lifecycle_store=rev_deps.lifecycle_store, outbox=rev_deps.event_outbox, version_store=commit_deps.version_store)
        publication = RevisionPublicationCoordinator(publication_store=rev_deps.publication_store, source_registry=rev_deps.source_registry, version_store=commit_deps.version_store, lifecycle_coordinator=lifecycle, document_commit_coordinator=doc_commit, document_commit_store=commit_deps.commit_store)
        workflow = RevisionPublicationWorkflow(revision_publication_coordinator=publication)
        bridge = CuratorAgentBridge(revision_workflow=workflow)

        prior_manifest = SnapshotManifest(ref_id="ED-PRIOR", source_fingerprint="fp-prior", assertion_hashes=["h1"], usdo_hashes=["u1"], vector_ids=["v1"], metadata_hash="m1", decision_hashes=["d1"])
        prior_manifest.content_hash = "prior-hash-r3"
        prior_snap = commit_deps.version_store.create_snapshot(prior_manifest)
        prior_ver = commit_deps.version_store.publish_version(prior_snap.snapshot_id)

        rev_deps.source_registry.append_work(WorkRecord(work_id="w1", created_evidence="test"))
        rev_deps.source_registry.append_source_version(SourceVersionRecord(source_version_id="sv-prior", work_id="w1", ref_id="ED-PRIOR", source_fingerprint="fp-prior", source_kind=SourceKind.PREPRINT, relation=VersionRelation.NONE, prior_source_version_id=None))
        rev_deps.source_registry.bind_source_version("sv-prior", prior_ver.version_id, prior_snap.snapshot_id)
        rev_deps.source_registry.append_source_version(SourceVersionRecord(source_version_id="sv-new", work_id="w1", ref_id="ED-NEW", source_fingerprint="fp-new", source_kind=SourceKind.JOURNAL, relation=VersionRelation.PREPRINT_TO_JOURNAL, prior_source_version_id="sv-prior"))

        assertion = Assertion(id="AS-001", ref_id="ED-NEW", subject=Subject(eddo_class="Membrane", resolved_entity="eddo:membrane:bpm", original_mention="BPM"), property="hasEnergyConsumption", object=ObjectValue(value=1.5, unit="kWh/m3", value_type=ValueType.NUMBER, uncertainty=0.05), conditions=[Condition(eddo_class="Temperature", value=298.15, unit="K")], provenance=Provenance(locator="p.1", sentence="energy is 1.5"), claim_type=ClaimType.MEASUREMENT, source_claim_origin=SourceClaimOrigin.PRIMARY, confidence=Confidence.MEDIUM, quality=0.85)
        assertion_set = AssertionSet(ref_id="ED-NEW", metadata=DocumentMetadata(title="Test J", authors=["A"], year=2024, source="J", doi="10.0/j", stable_id="ST-J"), assertions=[assertion])
        report = CurationReport(report_id="r1", source_ref_id="ED-NEW", status="successful", completeness=CompletenessResult(status=CompletenessStatus.OK), decisions=[AssertionDecision(assertion_id="AS-001", action=CurationAction.ACCEPT, confidence=Confidence.MEDIUM, reason="ok")])
        request = CommitRequest(source=SourceIdentity(ref_id="ED-NEW", source_fingerprint="fp-new"), assertion_set=assertion_set, report=report)
        package = RevisionPackage(package_id="pkg-r3", work_id="w1", prior_source_version_id="sv-prior", new_source_version_id="sv-new", relation=VersionRelation.PREPRINT_TO_JOURNAL, prior_ref_id="ED-PRIOR", new_ref_id="ED-NEW", prior_bound_kb_version_id=prior_ver.version_id, content_delta=ContentDeltaPlan(mode=DeltaMode.DELTA_SAFE), target_assertions=[assertion])

        scope_hash = compute_publication_scope_hash(package, request)
        approval = RevisionApproval(approval_id="appr-r3", package_id=package.package_id, scope_hash=scope_hash, decision=ApprovalDecision.APPROVED, approver="test")

        result = _run(bridge.revise(package=package, target_commit_request=request, approval=approval))
        assert result.status == "finalized"
        assert commit_deps.version_store.get_version(prior_ver.version_id) is not None


class TestDirectRegressions:
    def test_mcp_exactly_four(self):
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        from system.composition import compose_system_runtime, CuratorDependencies
        bundle = create_si2b_provider_bundle()
        curator_raw = bundle["curator"]
        deps = CuratorDependencies(repository=curator_raw["repository"], ontology=curator_raw["ontology"], mechanism_validator=curator_raw["mechanism_validator"], provider_identity=curator_raw["provider_identity"])
        rt = compose_system_runtime(curator_deps=deps, evidence_deps=None)
        from knowledge_curator.mcp_server.app import create_mcp_server
        server = create_mcp_server(runtime=rt.curator_runtime, evidence_runtime=rt.evidence_runtime)
        tool_names = set(server._tool_manager._tools.keys()) if hasattr(server, "_tool_manager") else set()
        assert tool_names == {"curate_assertion_set", "knowledge_curator_health", "retrieve_evidence", "validate_retrieved_claims"}
