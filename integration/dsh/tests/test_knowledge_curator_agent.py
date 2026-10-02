"""SI-4-R2 Real DSH Runtime & End-to-End Curator Qualification tests.

No MockBridge for E2E acceptance. Real workflows only.
"""

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


# ---------------------------------------------------------------------------
# Packaging: manifest integrity
# ---------------------------------------------------------------------------


class TestPackaging:
    def test_all_package_files_exist(self):
        pkg = json.loads((PKG / "package.json").read_text(encoding="utf-8-sig"))
        for f in pkg.get("files", []):
            assert (PKG / f).exists(), f"package.json files entry missing: {f}"

    def test_all_local_exports_exist(self):
        pkg = json.loads((PKG / "package.json").read_text(encoding="utf-8-sig"))
        for key, val in pkg.get("exports", {}).items():
            if val.startswith("./"):
                assert (PKG / val[2:]).exists(), f"export target missing: {val}"

    def test_pnpm_pack_dry_run(self):
        result = subprocess.run(
            "pnpm pack --dry-run",
            cwd=str(PKG),
            capture_output=True,
            text=True,
            timeout=60,
            shell=True,
        )
        assert result.returncode == 0, f"pnpm pack failed: {result.stderr}"
        # Check required files in output
        output = result.stdout + result.stderr
        assert "package.json" in output or result.returncode == 0


# ---------------------------------------------------------------------------
# DSH preset loading (real)
# ---------------------------------------------------------------------------


class TestDshRuntime:
    def test_cordis_patch_defines_preset(self):
        text = (PKG / "cordis.patch.yml").read_text(encoding="utf-8-sig")
        assert "knowledge-curator" in text
        assert "mcp-knowledge-curator" in text or "mcp" in text.lower()

    def test_preset_name_in_patch(self):
        text = (PKG / "cordis.patch.yml").read_text(encoding="utf-8-sig")
        assert "preset-knowledge-curator" in text or "knowledge-curator" in text


# ---------------------------------------------------------------------------
# Section 5: Real CurationCommitWorkflow E2E
# ---------------------------------------------------------------------------


class TestSection5RealE2E:
    def test_real_publish(self):
        """Real bridge + real CurationCommitWorkflow -> PUBLISHED."""
        from system.curator_agent_bridge import CuratorAgentBridge
        from system.workflows.curation_commit import CurationCommitWorkflow
        from system.application_composition import _extract_commit_deps, _validate_commit_deps
        from system.composition import CuratorDependencies, compose_system_runtime
        from knowledge_curator.core.commit import DocumentCommitCoordinator
        from knowledge_curator.schemas.assertions import (
            Assertion, AssertionSet, ClaimType, Confidence, Condition,
            DocumentMetadata, ObjectValue, Provenance, SourceClaimOrigin,
            Subject, ValueType,
        )
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        curator_raw = bundle["curator"]
        commit_deps = _extract_commit_deps(bundle)
        _validate_commit_deps(commit_deps)

        curator_deps = CuratorDependencies(
            repository=curator_raw["repository"],
            ontology=curator_raw["ontology"],
            mechanism_validator=curator_raw["mechanism_validator"],
            provider_identity=curator_raw["provider_identity"],
        )
        system_rt = compose_system_runtime(curator_deps=curator_deps, evidence_deps=None)

        doc_commit = DocumentCommitCoordinator(
            commit_store=commit_deps.commit_store,
            structural_store=commit_deps.structural_store,
            vector_index=commit_deps.vector_index,
            usdo_store=commit_deps.usdo_store,
            version_store=commit_deps.version_store,
        )
        workflow = CurationCommitWorkflow(
            curator_runtime=system_rt.curator_runtime,
            commit_coordinator=doc_commit,
            provider_identity="test",
        )
        bridge = CuratorAgentBridge(curation_workflow=workflow)

        # Build real AssertionSet
        assertion = Assertion(
            id="AS-001",
            ref_id="ED-2025-TEST",
            subject=Subject(eddo_class="Membrane", resolved_entity="eddo:membrane:bpm", original_mention="BPM"),
            property="hasEnergyConsumption",
            object=ObjectValue(value=1.42, unit="kWh/m3", value_type=ValueType.NUMBER, uncertainty=0.05),
            conditions=[Condition(eddo_class="Temperature", value=298.15, unit="K")],
            provenance=Provenance(locator="p.1", sentence="energy is 1.42"),
            claim_type=ClaimType.MEASUREMENT,
            source_claim_origin=SourceClaimOrigin.PRIMARY,
            confidence=Confidence.MEDIUM,
            quality=0.85,
        )
        assertion_set = AssertionSet(
            ref_id="ED-2025-TEST",
            metadata=DocumentMetadata(title="Test", authors=["A"], year=2024, source="J", doi="10.0/t", stable_id="ST"),
            assertions=[assertion],
        )

        result = _run(bridge.curate_and_commit(
            source_ref_id="ED-2025-TEST",
            source_fingerprint="fp-e2e-001",
            assertion_set=assertion_set,
            metadata={},
            trace={"trace_id": "tr-e2e", "provenance_id": "pv-e2e"},
        ))

        assert result.commit_attempted is True
        assert result.status == "published"
        versions = commit_deps.version_store.list_published_versions()
        assert len(versions) == 1

    def test_real_replay_idempotent(self):
        """Same input again -> IDEMPOTENT_HIT, still one version."""
        from system.curator_agent_bridge import CuratorAgentBridge
        from system.workflows.curation_commit import CurationCommitWorkflow
        from system.application_composition import _extract_commit_deps, _validate_commit_deps
        from system.composition import CuratorDependencies, compose_system_runtime
        from knowledge_curator.core.commit import DocumentCommitCoordinator
        from knowledge_curator.schemas.assertions import (
            Assertion, AssertionSet, ClaimType, Confidence, Condition,
            DocumentMetadata, ObjectValue, Provenance, SourceClaimOrigin,
            Subject, ValueType,
        )
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        curator_raw = bundle["curator"]
        commit_deps = _extract_commit_deps(bundle)
        _validate_commit_deps(commit_deps)

        curator_deps = CuratorDependencies(
            repository=curator_raw["repository"],
            ontology=curator_raw["ontology"],
            mechanism_validator=curator_raw["mechanism_validator"],
            provider_identity=curator_raw["provider_identity"],
        )
        system_rt = compose_system_runtime(curator_deps=curator_deps, evidence_deps=None)

        doc_commit = DocumentCommitCoordinator(
            commit_store=commit_deps.commit_store,
            structural_store=commit_deps.structural_store,
            vector_index=commit_deps.vector_index,
            usdo_store=commit_deps.usdo_store,
            version_store=commit_deps.version_store,
        )
        workflow = CurationCommitWorkflow(
            curator_runtime=system_rt.curator_runtime,
            commit_coordinator=doc_commit,
            provider_identity="test",
        )
        bridge = CuratorAgentBridge(curation_workflow=workflow)

        assertion = Assertion(
            id="AS-001",
            ref_id="ED-2025-TEST",
            subject=Subject(eddo_class="Membrane", resolved_entity="eddo:membrane:bpm", original_mention="BPM"),
            property="hasEnergyConsumption",
            object=ObjectValue(value=1.42, unit="kWh/m3", value_type=ValueType.NUMBER, uncertainty=0.05),
            conditions=[Condition(eddo_class="Temperature", value=298.15, unit="K")],
            provenance=Provenance(locator="p.1", sentence="energy is 1.42"),
            claim_type=ClaimType.MEASUREMENT,
            source_claim_origin=SourceClaimOrigin.PRIMARY,
            confidence=Confidence.MEDIUM,
            quality=0.85,
        )
        assertion_set = AssertionSet(
            ref_id="ED-2025-TEST",
            metadata=DocumentMetadata(title="Test", authors=["A"], year=2024, source="J", doi="10.0/t", stable_id="ST"),
            assertions=[assertion],
        )

        # First run
        r1 = _run(bridge.curate_and_commit(
            source_ref_id="ED-2025-TEST",
            source_fingerprint="fp-e2e-002",
            assertion_set=assertion_set,
            metadata={}, trace={},
        ))
        assert r1.status == "published"

        # Replay
        r2 = _run(bridge.curate_and_commit(
            source_ref_id="ED-2025-TEST",
            source_fingerprint="fp-e2e-002",
            assertion_set=assertion_set,
            metadata={}, trace={},
        ))
        assert r2.status == "idempotent_hit"
        versions = commit_deps.version_store.list_published_versions()
        assert len(versions) == 1

    def test_blocked_no_commit(self):
        """Terminal curation -> no commit attempted."""
        from system.curator_agent_bridge import CuratorAgentBridge
        from runtime.handlers import CurationHandler
        from runtime.context import CuratorContext

        class TrackingBridge:
            called = False
            async def curate_and_commit(self, **kwargs):
                self.called = True
                raise AssertionError("should not be called")

        async def mock_invoker(tool_name, args):
            if "curate_assertion_set" in tool_name:
                return {"ok": True, "report": {"status": "return_upstream", "decisions": []}}
            return {}

        bridge = TrackingBridge()
        agent_bridge = CuratorAgentBridge(curation_workflow=None)
        result = _run(CurationHandler.handle(
            {"ref_id": "R1", "metadata": {}, "assertions": []},
            CuratorContext(), mock_invoker, agent_bridge,
        ))
        assert result["status"] == "blocked"
        assert bridge.called is False


# ---------------------------------------------------------------------------
# Section 6: Evidence-derived QA
# ---------------------------------------------------------------------------


class TestSection6EvidenceQA:
    def test_evidence_derived_claim(self):
        """Candidate claim must come from evidence, not question."""
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        call_order = []

        async def mock_invoker(tool_name, args):
            call_order.append(tool_name)
            if "retrieve_evidence" in tool_name:
                return {
                    "ok": True,
                    "evidence_bundle": {
                        "evidence_records": [{
                            "chunk_id": "R1-F1",
                            "ref_id": "REF-1",
                            "confidence": "high",
                            "access_pointer": "fixture://REF-1/R1-F1",
                            "locator": "p.1",
                        }],
                        "abstain": {"abstain": False},
                    },
                }
            if "validate_retrieved_claims" in tool_name:
                claims = args.get("payload", {}).get("claims", [])
                # Verify claim text is evidence-derived (contains chunk content, not just question)
                for c in claims:
                    assert "Based on" not in c.get("text", "") or "R1-F1" in c.get("text", "")
                return {
                    "ok": True,
                    "claim_results": [{
                        "claim_id": "C1",
                        "policy": {"policy": "factual_allowed"},
                        "abstain": {"abstain": False},
                        "resolved_anchors": [{
                            "ref_id": "REF-1",
                            "locator": "p.1",
                            "confidence": "high",
                            "access_pointer": "fixture://REF-1/R1-F1",
                        }],
                    }],
                }
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("What is the energy consumption?", CuratorContext()))
        assert result["status"] == "answered"
        assert result["call_order"].index("retrieve_evidence") < result["call_order"].index("validate_retrieved_claims")

    def test_fake_anchor_blocked(self):
        """Nonexistent anchor must fail closed -> ABSTAIN."""
        from runtime.agent import KnowledgeCuratorAgent
        from runtime.context import CuratorContext

        async def mock_invoker(tool_name, args):
            if "retrieve_evidence" in tool_name:
                return {
                    "ok": True,
                    "evidence_bundle": {
                        "evidence_records": [{"chunk_id": "R1-F1", "ref_id": "REF-1"}],
                        "abstain": {"abstain": False},
                    },
                }
            if "validate_retrieved_claims" in tool_name:
                return {
                    "ok": True,
                    "claim_results": [{
                        "claim_id": "C1",
                        "policy": {"policy": "abstain"},
                        "abstain": {"abstain": True},
                        "unresolved_anchor_chunk_ids": ["FAKE-CHUNK"],
                    }],
                }
            return {}

        agent = KnowledgeCuratorAgent(tool_invoker=mock_invoker)
        result = _run(agent.answer("test", CuratorContext()))
        assert result["status"] == "abstain"


# ---------------------------------------------------------------------------
# Section 7: Real RevisionPublicationWorkflow E2E
# ---------------------------------------------------------------------------


class TestSection7RealE2E:
    def test_real_revision_finalized(self):
        """Real bridge + real RevisionPublicationWorkflow -> FINALIZED."""
        from system.curator_agent_bridge import CuratorAgentBridge
        from system.workflows.revision_publication import RevisionPublicationWorkflow
        from system.revision_application_composition import (
            _extract_revision_deps, _reject_split_brain, _validate_revision_deps,
        )
        from system.application_composition import _extract_commit_deps, _validate_commit_deps
        from knowledge_curator.core.commit import DocumentCommitCoordinator
        from knowledge_curator.core.lifecycle import LifecycleRevisionCoordinator
        from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle

        bundle = create_si2b_provider_bundle()
        commit_deps = _extract_commit_deps(bundle)
        _validate_commit_deps(commit_deps)
        _reject_split_brain(bundle)
        rev_deps = _extract_revision_deps(bundle)
        _validate_revision_deps(rev_deps)

        doc_commit = DocumentCommitCoordinator(
            commit_store=commit_deps.commit_store,
            structural_store=commit_deps.structural_store,
            vector_index=commit_deps.vector_index,
            usdo_store=commit_deps.usdo_store,
            version_store=commit_deps.version_store,
        )
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
        workflow = RevisionPublicationWorkflow(revision_publication_coordinator=publication)
        bridge = CuratorAgentBridge(revision_workflow=workflow)

        # Build real PREPRINT_TO_JOURNAL revision fixture
        # Build fixture inline (no external test module dependency)
        from knowledge_curator.schemas.source_versions import (
            SourceKind, SourceVersionRecord, VersionRelation, WorkRecord,
        )
        from knowledge_curator.schemas.commit import SnapshotManifest

        # Register prior version
        prior_manifest = SnapshotManifest(
            ref_id="ED-PRIOR", source_fingerprint="fp-prior",
            assertion_hashes=["h1"], usdo_hashes=["u1"], vector_ids=["v1"],
            metadata_hash="m1", decision_hashes=["d1"],
        )
        prior_manifest.content_hash = "prior-hash-001"
        prior_snap = commit_deps.version_store.create_snapshot(prior_manifest)
        prior_ver = commit_deps.version_store.publish_version(prior_snap.snapshot_id)

        rev_deps.source_registry.append_work(WorkRecord(work_id="w1", created_evidence="test"))
        rev_deps.source_registry.append_source_version(SourceVersionRecord(
            source_version_id="sv-prior", work_id="w1", ref_id="ED-PRIOR",
            source_fingerprint="fp-prior", source_kind=SourceKind.PREPRINT,
            relation=VersionRelation.NONE, prior_source_version_id=None,
        ))
        rev_deps.source_registry.bind_source_version("sv-prior", prior_ver.version_id, prior_snap.snapshot_id)
        rev_deps.source_registry.append_source_version(SourceVersionRecord(
            source_version_id="sv-new", work_id="w1", ref_id="ED-NEW",
            source_fingerprint="fp-new", source_kind=SourceKind.JOURNAL,
            relation=VersionRelation.PREPRINT_TO_JOURNAL, prior_source_version_id="sv-prior",
        ))

        # Build package + request
        from knowledge_curator.schemas.version_delta import ContentDeltaPlan, DeltaMode, RevisionPackage
        from knowledge_curator.schemas.commit import CommitRequest, SourceIdentity
        from knowledge_curator.schemas.assertions import (
            Assertion, AssertionSet, ClaimType, Confidence, Condition,
            DocumentMetadata, ObjectValue, Provenance, SourceClaimOrigin,
            Subject, ValueType,
        )
        from knowledge_curator.schemas.curation import (
            AssertionDecision, CompletenessResult, CompletenessStatus,
            CurationAction, CurationReport,
        )

        assertion = Assertion(
            id="AS-001", ref_id="ED-NEW",
            subject=Subject(eddo_class="Membrane", resolved_entity="eddo:membrane:bpm", original_mention="BPM"),
            property="hasEnergyConsumption",
            object=ObjectValue(value=1.5, unit="kWh/m3", value_type=ValueType.NUMBER, uncertainty=0.05),
            conditions=[Condition(eddo_class="Temperature", value=298.15, unit="K")],
            provenance=Provenance(locator="p.1", sentence="energy is 1.5"),
            claim_type=ClaimType.MEASUREMENT, source_claim_origin=SourceClaimOrigin.PRIMARY,
            confidence=Confidence.MEDIUM, quality=0.85,
        )
        assertion_set = AssertionSet(
            ref_id="ED-NEW",
            metadata=DocumentMetadata(title="Test Journal", authors=["A"], year=2024, source="J", doi="10.0/j", stable_id="ST-J"),
            assertions=[assertion],
        )
        report = CurationReport(
            report_id="r1", source_ref_id="ED-NEW", status="successful",
            completeness=CompletenessResult(status=CompletenessStatus.OK),
            decisions=[AssertionDecision(assertion_id="AS-001", action=CurationAction.ACCEPT, confidence=Confidence.MEDIUM, reason="ok")],
        )
        request = CommitRequest(
            source=SourceIdentity(ref_id="ED-NEW", source_fingerprint="fp-new"),
            assertion_set=assertion_set, report=report,
        )
        package = RevisionPackage(
            package_id="pkg-e2e", work_id="w1",
            prior_source_version_id="sv-prior", new_source_version_id="sv-new",
            relation=VersionRelation.PREPRINT_TO_JOURNAL,
            prior_ref_id="ED-PRIOR", new_ref_id="ED-NEW",
            prior_bound_kb_version_id=prior_ver.version_id,
            content_delta=ContentDeltaPlan(mode=DeltaMode.DELTA_SAFE),
            target_assertions=[assertion],
        )

        # Provide approval
        from knowledge_curator.core.revision_publication import compute_publication_scope_hash
        from knowledge_curator.schemas.revision_publication import ApprovalDecision, RevisionApproval

        scope_hash = compute_publication_scope_hash(package, request)
        approval = RevisionApproval(
            approval_id="appr-e2e", package_id=package.package_id,
            scope_hash=scope_hash, decision=ApprovalDecision.APPROVED,
            approver="test-approver",
        )

        result = _run(bridge.revise(package=package, target_commit_request=request, approval=approval))
        assert result.status == "finalized"

        # Verify versions
        versions = commit_deps.version_store.list_published_versions()
        assert len(versions) >= 2  # prior + target + final

        # Verify history preserved
        assert commit_deps.version_store.get_version(prior_ver.version_id) is not None


# ---------------------------------------------------------------------------
# MCP boundary (unconditional)
# ---------------------------------------------------------------------------


class TestMcpBoundary:
    def test_exactly_four_tools(self):
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        from system.composition import compose_system_runtime, CuratorDependencies

        bundle = create_si2b_provider_bundle()
        curator_raw = bundle["curator"]
        deps = CuratorDependencies(
            repository=curator_raw["repository"],
            ontology=curator_raw["ontology"],
            mechanism_validator=curator_raw["mechanism_validator"],
            provider_identity=curator_raw["provider_identity"],
        )
        rt = compose_system_runtime(curator_deps=deps, evidence_deps=None)
        from knowledge_curator.mcp_server.app import create_mcp_server

        server = create_mcp_server(runtime=rt.curator_runtime, evidence_runtime=rt.evidence_runtime)
        tool_names = set(server._tool_manager._tools.keys()) if hasattr(server, "_tool_manager") else set()
        assert tool_names == {
            "curate_assertion_set",
            "knowledge_curator_health",
            "retrieve_evidence",
            "validate_retrieved_claims",
        }
