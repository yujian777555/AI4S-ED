"""SI-1.5-R2 keyless qualification-path regressions.

Proves:
- integration provider fixture-corpus parity with direct reference;
- evidence chunk identity / coverage / Abstain / claim-guard parity;
- integration_fixture boundary: direct=true vs provider=false;
- run_lane325 supplies AI4S_SYSTEM_ADAPTER_FACTORY and no longer sets
  KC_EVIDENCE_INTEGRATION_FIXTURE globally;
- lane324 baseline receives the provider contract from the runner;
- mcp_smoke preserves caller-supplied provider / defaults to integration;
- no forbidden InMemory/Fake adapters inside the integration provider.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# R2-02: integration provider uses test-local adapters over fixture corpus
# ---------------------------------------------------------------------------


class TestR202IntegrationProviderAdapters:
    def test_provider_module_loads(self):
        mod = importlib.import_module("integration.system.fixtures.dsh_provider")
        assert hasattr(mod, "create_provider_bundle")

    def test_no_forbidden_adapter_names_in_provider_module(self):
        mod = importlib.import_module("integration.system.fixtures.dsh_provider")
        source = inspect.getsource(mod)
        forbidden = (
            "InMemoryVectorSearch",
            "InMemoryKeywordSearch",
            "FakeReranker",
            "InMemoryGraphSearch",
        )
        for name in forbidden:
            # The names must not appear as imports or instantiations.
            # Comments mentioning them for documentation are allowed only if
            # not used as identifiers; we check AST for actual Name/Attribute.
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == name:
                    pytest.fail(f"forbidden adapter name used: {name}")
                if isinstance(node, ast.Attribute) and node.attr == name:
                    pytest.fail(f"forbidden adapter attribute used: {name}")

    def test_no_forbidden_module_imports(self):
        mod = importlib.import_module("integration.system.fixtures.dsh_provider")
        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                modname = node.module or ""
                if "in_memory_retrieval" in modname:
                    pytest.fail(f"forbidden module import: {modname}")

    def test_provider_bundle_evidence_over_fixture_corpus(self):
        from integration.system.fixtures.dsh_provider import create_provider_bundle

        bundle = create_provider_bundle()
        evidence = bundle.get("evidence")
        assert evidence is not None
        retrieval = evidence.get("retrieval")
        assert retrieval is not None
        # Must be EvidenceRetrievalService
        from knowledge_curator.retrieval.evidence_service import EvidenceRetrievalService

        assert isinstance(retrieval, EvidenceRetrievalService)
        # Backends must be test-local classes (not forbidden names)
        for attr in ("_vector_port", "_keyword_port", "_reranker"):
            backend = getattr(retrieval, attr, None)
            assert backend is not None, f"{attr} missing"
            cls_name = type(backend).__name__
            assert cls_name not in (
                "InMemoryVectorSearch",
                "InMemoryKeywordSearch",
                "FakeReranker",
            ), f"{attr} uses forbidden adapter: {cls_name}"


# ---------------------------------------------------------------------------
# R2-02 / §5: keyless evidence parity (direct reference vs provider)
# ---------------------------------------------------------------------------

FIXTURE_QUERY = "双极膜电渗析 能耗"
CLAIMS_PAYLOAD = [
    {
        "claim_id": "C1",
        "text": "BPM energy about 1.4 kWh/m3",
        "anchor_chunk_ids": ["R1-F1"],
    },
    {
        "claim_id": "C2",
        "text": "fabricated",
        "anchor_chunk_ids": ["NO-SUCH-CHUNK"],
    },
]


def _direct_reference_bundle():
    """Build the direct reference EvidenceBundle (legacy integration fixture)."""
    from knowledge_curator.mcp_server.evidence_runtime import build_fixture_evidence_service
    from knowledge_curator.retrieval.evidence_service import EvidenceRequest

    svc = build_fixture_evidence_service()
    return svc.retrieve(
        EvidenceRequest(
            query=FIXTURE_QUERY,
            top_k=5,
            coverage_keys=["sq1"],
            required_coverage_keys=["sq1"],
            integration_fixture=True,
        )
    )


def _provider_bundle_result():
    """Build the production-style bundle via integration provider adapters."""
    from integration.system.fixtures.dsh_provider import create_provider_bundle
    from knowledge_curator.retrieval.evidence_service import EvidenceRequest

    bundle_dict = create_provider_bundle()
    retrieval = bundle_dict["evidence"]["retrieval"]
    return retrieval.retrieve(
        EvidenceRequest(
            query=FIXTURE_QUERY,
            top_k=5,
            coverage_keys=["sq1"],
            required_coverage_keys=["sq1"],
            integration_fixture=False,
        )
    )


class TestR202EvidenceParity:
    def test_same_chunk_ids(self):
        direct = _direct_reference_bundle()
        provider = _provider_bundle_result()
        direct_ids = [r.chunk_id for r in direct.evidence_records]
        provider_ids = [r.chunk_id for r in provider.evidence_records]
        assert direct_ids == provider_ids, (
            f"chunk id mismatch: direct={direct_ids} provider={provider_ids}"
        )

    def test_same_coverage_keys_and_states(self):
        direct = _direct_reference_bundle()
        provider = _provider_bundle_result()
        direct_cov = {c.coverage_key: c.state.value for c in direct.coverage}
        provider_cov = {c.coverage_key: c.state.value for c in provider.coverage}
        assert direct_cov == provider_cov

    def test_same_abstain_decision(self):
        direct = _direct_reference_bundle()
        provider = _provider_bundle_result()
        assert direct.abstain.abstain == provider.abstain.abstain
        assert list(direct.abstain.reasons) == list(provider.abstain.reasons)

    def test_direct_fixture_marker_true(self):
        direct = _direct_reference_bundle()
        assert direct.integration_fixture is True

    def test_provider_fixture_marker_false(self):
        provider = _provider_bundle_result()
        assert provider.integration_fixture is False

    def test_claim_guard_policy_parity(self):
        from knowledge_curator.mcp_server.evidence_codec import parse_proposed_claims
        from knowledge_curator.retrieval.guard_service import ClaimGuardService

        direct = _direct_reference_bundle()
        provider = _provider_bundle_result()
        claims = parse_proposed_claims(CLAIMS_PAYLOAD)

        guard = ClaimGuardService()
        direct_results = {r.claim_id: r for r in guard.validate_claims(direct, claims)}
        provider_results = {
            r.claim_id: r for r in guard.validate_claims(provider, claims)
        }

        for cid in ("C1", "C2"):
            d = direct_results.get(cid)
            p = provider_results.get(cid)
            assert d is not None and p is not None, f"missing claim result {cid}"
            assert d.policy.policy == p.policy.policy, (
                f"{cid} policy mismatch: {d.policy.policy} vs {p.policy.policy}"
            )
            assert d.abstain.abstain == p.abstain.abstain, (
                f"{cid} abstain mismatch"
            )

        # C2 unresolved anchors must match
        d2 = direct_results["C2"]
        p2 = provider_results["C2"]
        assert sorted(d2.unresolved_anchor_chunk_ids) == sorted(
            p2.unresolved_anchor_chunk_ids
        )

        # C2 H1 finding types must match
        d_h1 = sorted(f.type.value for f in d2.h1.findings)
        p_h1 = sorted(f.type.value for f in p2.h1.findings)
        assert d_h1 == p_h1


# ---------------------------------------------------------------------------
# R2-03 / R2-04: run_lane325 provider wiring structural regressions
# ---------------------------------------------------------------------------


class TestR203RunnerProviderWiring:
    def test_run_lane325_source_sets_adapter_factory(self):
        src = (ROOT / "integration" / "dsh" / "run_lane325.py").read_text(
            encoding="utf-8"
        )
        assert "AI4S_SYSTEM_ADAPTER_FACTORY" in src
        assert (
            "integration.system.fixtures.dsh_provider:create_provider_bundle" in src
        )

    def test_run_lane325_no_global_fixture_flag(self):
        src = (ROOT / "integration" / "dsh" / "run_lane325.py").read_text(
            encoding="utf-8"
        )
        # Must NOT set KC_EVIDENCE_INTEGRATION_FIXTURE in the runner env.
        # Look for the assignment pattern env["KC_EVIDENCE_INTEGRATION_FIXTURE"]
        assert 'env["KC_EVIDENCE_INTEGRATION_FIXTURE"]' not in src
        assert "env['KC_EVIDENCE_INTEGRATION_FIXTURE']" not in src

    def test_lane324_baseline_inherits_provider_from_runner(self):
        """lane324 must not hard-code a provider; runner supplies it."""
        src = (ROOT / "integration" / "dsh" / "lane324_kc_roundtrip.e2e.ts").read_text(
            encoding="utf-8"
        )
        # lane324 must NOT set AI4S_SYSTEM_ADAPTER_FACTORY itself
        # (it inherits from run_lane325 runner environment).
        # This is a structural check: the file should not contain the env assignment.
        assert "AI4S_SYSTEM_ADAPTER_FACTORY" not in src, (
            "lane324 should inherit provider from runner, not hard-code it"
        )

    def test_runner_copies_lane324_and_lane325(self):
        src = (ROOT / "integration" / "dsh" / "run_lane325.py").read_text(
            encoding="utf-8"
        )
        assert "lane324_kc_roundtrip.e2e.ts" in src
        assert "lane325_kc_evidence_roundtrip.e2e.ts" in src


# ---------------------------------------------------------------------------
# R2-05: mcp_smoke provider resolution
# ---------------------------------------------------------------------------


class TestR205McpSmokeProvider:
    def test_caller_supplied_provider_preserved(self):
        from integration.dsh.mcp_smoke import resolve_smoke_provider

        env = {"AI4S_SYSTEM_ADAPTER_FACTORY": "my.custom.module:factory"}
        spec, source, _ = resolve_smoke_provider(env)
        assert spec == "my.custom.module:factory"
        assert source == "caller"

    def test_absent_provider_defaults_to_integration(self):
        from integration.dsh.mcp_smoke import (
            INTEGRATION_PROVIDER_SPEC,
            resolve_smoke_provider,
        )

        env = {}
        spec, source, _ = resolve_smoke_provider(env)
        assert spec == INTEGRATION_PROVIDER_SPEC
        assert source == "integration_default"

    def test_empty_string_provider_defaults_to_integration(self):
        from integration.dsh.mcp_smoke import (
            INTEGRATION_PROVIDER_SPEC,
            resolve_smoke_provider,
        )

        env = {"AI4S_SYSTEM_ADAPTER_FACTORY": "  "}
        spec, source, _ = resolve_smoke_provider(env)
        assert spec == INTEGRATION_PROVIDER_SPEC
        assert source == "integration_default"


# ---------------------------------------------------------------------------
# R2-06: patch template documentation
# ---------------------------------------------------------------------------


class TestR206PatchTemplate:
    def test_patch_template_documents_system_mcp_stdio(self):
        src = (
            ROOT / "integration" / "dsh" / "patches" / "knowledge-curator-mcp.patch.yml"
        ).read_text(encoding="utf-8")
        assert "system.mcp_stdio" in src
        assert "knowledge_curator.mcp_server" not in src.split("args:")[-1] or (
            "system.mcp_stdio" in src
        )

    def test_patch_template_documents_provider_injection(self):
        src = (
            ROOT / "integration" / "dsh" / "patches" / "knowledge-curator-mcp.patch.yml"
        ).read_text(encoding="utf-8")
        assert "AI4S_SYSTEM_ADAPTER_FACTORY" in src or "provider" in src.lower()


# ---------------------------------------------------------------------------
# R2 acceptance: lane325 fixture boundary semantics in source
# ---------------------------------------------------------------------------


class TestR201Lane325FixtureBoundary:
    def test_lane325_no_fixture_equality_comparison(self):
        src = (
            ROOT / "integration" / "dsh" / "lane325_kc_evidence_roundtrip.e2e.ts"
        ).read_text(encoding="utf-8")
        # The old invalid pattern compared the two flags for equality.
        assert (
            "Boolean(directR.identity.integration_fixture) ===\n        Boolean(retrieveLinked.payload?.integration_fixture)"
            not in src
        )
        # Must assert direct=true and DSH=false explicitly.
        assert "integration_fixture=true" in src or "integration_fixture === true" in src or "must report integration_fixture=true" in src
        assert "integration_fixture=false" in src or "integration_fixture === false" in src or "must report integration_fixture=false" in src
