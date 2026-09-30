"""Phase 4.3.2 keyless runner classification tests (no live API)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "integration" / "dsh" / "run_lane325.py"


def _load_classifier():
    spec = importlib.util.spec_from_file_location("run_lane325", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    # Avoid executing main
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_retrieve_marker_cannot_imply_validate_pass():
    mod = _load_classifier()
    out = mod.classify_outputs(
        credential_available=True,
        evidence_stdout="LANE325_DISCOVERY_OK=1\nLANE325_RETRIEVE_TOOLCALL_OK=1\nLANE325_RETRIEVE_RESULT_OK=1\nLANE325_RETRIEVE_IDENTITY_MATCH=1\n",
        evidence_rc=0,
        baseline_stdout="LANE324_BASELINE_TOOLCALL_OK=1\n",
        baseline_rc=0,
    )
    assert out["mounted_dsh_retrieve_evidence_live"] == "PASS"
    assert out["mounted_dsh_validate_retrieved_claims_live"] != "PASS"
    assert out["direct_vs_dsh_policy_match"] != "PASS"
    assert out["classification"] == "B_EVIDENCE_REGRESSION"


def test_missing_identity_marker_identity_not_pass():
    mod = _load_classifier()
    out = mod.classify_outputs(
        credential_available=True,
        evidence_stdout=(
            "LANE325_DISCOVERY_OK=1\n"
            "LANE325_RETRIEVE_TOOLCALL_OK=1\n"
            "LANE325_RETRIEVE_RESULT_OK=1\n"
        ),
        evidence_rc=0,
        baseline_stdout="LANE324_BASELINE_TOOLCALL_OK=1\n",
        baseline_rc=0,
    )
    assert out["direct_vs_dsh_evidence_identity_match"] != "PASS"
    assert out["direct_vs_dsh_policy_match"] != "PASS"


def test_zero_toolcall_with_prereq_is_failed():
    mod = _load_classifier()
    out = mod.classify_outputs(
        credential_available=True,
        evidence_stdout="LANE325_DISCOVERY_OK=1\nLANE325_RETRIEVE_FAILED attempts=3\n",
        evidence_rc=1,
        baseline_stdout="LANE324_BASELINE_TOOLCALL_OK=1\n",
        baseline_rc=0,
    )
    assert out["mounted_dsh_retrieve_evidence_live"] == "FAILED"
    assert out["evidence_live_status"] == "FAILED"
    assert out["classification"] == "B_EVIDENCE_REGRESSION"


def test_no_credential_not_run_env():
    mod = _load_classifier()
    out = mod.classify_outputs(
        credential_available=False,
        evidence_stdout="LANE325_DISCOVERY_OK=1\nLANE325_NO_CREDENTIAL=1\nLANE325_LIVE_NOT_RUN_ENV=1\n",
        evidence_rc=0,
        baseline_stdout="",
        baseline_rc=0,
    )
    assert out["mounted_dsh_tool_discovery"] == "PASS"
    assert out["mounted_dsh_retrieve_evidence_live"] == "NOT_RUN_ENV"
    assert out["mounted_dsh_validate_retrieved_claims_live"] == "NOT_RUN_ENV"
    assert out["classification"] == "NOT_RUN_ENV"


def test_baseline_and_evidence_empty_response_external():
    mod = _load_classifier()
    out = mod.classify_outputs(
        credential_available=True,
        evidence_stdout="LANE325_DISCOVERY_OK=1\nLANE325_RETRIEVE_FAILED attempts=3 types=[\"turn/end\"]\n",
        evidence_rc=1,
        baseline_stdout="AssertionError: expected +0 to be 1\nLANE324_ZERO_TOOLCALL\n",
        baseline_rc=1,
    )
    assert out["external_runtime_unavailable"] is True
    assert out["classification"] == "C_EXTERNAL_RUNTIME_UNAVAILABLE"
    assert out["baseline_control_status"] == "EMPTY_RESPONSE"
    # identity/policy must not be claimed PASS
    assert out["direct_vs_dsh_evidence_identity_match"] == "NOT_RUN_ENV"
    assert out["direct_vs_dsh_policy_match"] == "NOT_RUN_ENV"


def test_full_markers_all_pass():
    mod = _load_classifier()
    stdout = "\n".join(
        [
            "LANE325_DISCOVERY_OK=1",
            "LANE325_RETRIEVE_TOOLCALL_OK=1",
            "LANE325_RETRIEVE_RESULT_OK=1",
            "LANE325_RETRIEVE_IDENTITY_MATCH=1",
            "LANE325_VALIDATE_TOOLCALL_OK=1",
            "LANE325_VALIDATE_RESULT_OK=1",
            "LANE325_VALIDATE_POLICY_MATCH=1",
            "LANE325_LIVE_COMPLETE=1",
            "LANE325_ATTEMPTS retrieve=1 validate=1",
        ]
    )
    out = mod.classify_outputs(
        credential_available=True,
        evidence_stdout=stdout,
        evidence_rc=0,
        baseline_stdout="LANE324_BASELINE_TOOLCALL_OK=1\n",
        baseline_rc=0,
    )
    assert out["mounted_dsh_tool_discovery"] == "PASS"
    assert out["mounted_dsh_retrieve_evidence_live"] == "PASS"
    assert out["mounted_dsh_validate_retrieved_claims_live"] == "PASS"
    assert out["direct_vs_dsh_evidence_identity_match"] == "PASS"
    assert out["direct_vs_dsh_policy_match"] == "PASS"
    assert out["classification"] == "A_PASS"
    assert out["live_attempts"]["retrieve"] == 1


def test_lane325_source_has_no_soft_pass():
    src = (ROOT / "integration" / "dsh" / "lane325_kc_evidence_roundtrip.e2e.ts").read_text(
        encoding="utf-8"
    )
    # Must not return successfully after zero toolcall
    assert "LANE325_LIVE_NO_TOOLCALL" not in src or "throw new Error" in src
    assert "LANE325_DISCOVERY_OK=1" in src
    assert "LANE325_RETRIEVE_IDENTITY_MATCH=1" in src
    assert "LANE325_VALIDATE_POLICY_MATCH=1" in src
    assert "LANE325_LIVE_COMPLETE=1" in src
    assert "throw new Error" in src
