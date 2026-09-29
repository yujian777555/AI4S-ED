"""Phase 3.2.2 keyless tests: harness portability, lane status, CG-015 rule."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INTEGRATION = ROOT / "integration" / "dsh"


def test_no_machine_absolute_paths_in_harness():
    for fp in list(INTEGRATION.rglob("*.ts")) + list(INTEGRATION.rglob("*.py")):
        if "tests" in fp.parts and fp.name.startswith("test_"):
            continue
        text = fp.read_text(encoding="utf-8", errors="ignore")
        # Assertion strings that CHECK for absence are allowed
        for line in text.splitlines():
            if "assert" in line or "expect" in line or "not in" in line:
                continue
            if re.search(r"C:/Users|C:\\\\Users|于舰", line):
                raise AssertionError(f"machine path in {fp}: {line.strip()[:80]}")


def test_no_node_execpath_as_python_fallback():
    for fp in INTEGRATION.rglob("*.ts"):
        text = fp.read_text(encoding="utf-8", errors="ignore")
        if "process.execPath" in text and "AI4S_KC_PYTHON" in text:
            for line in text.splitlines():
                if "process.execPath" in line and "??" in line and "PYTHON" in line:
                    raise AssertionError(f"invalid Node-as-Python fallback in {fp}")
                if "process.execPath" in line and "not a valid fallback" in line:
                    continue  # fail-fast message is OK


def test_lane_status_schema():
    artifact = ROOT / "results" / "phase-03-2-2-dsh-live-isolation.json"
    if not artifact.exists():
        return  # artifact written at end of live run
    data = json.loads(artifact.read_text(encoding="utf-8"))
    for lane in (
        "lane_a_upstream_adapter",
        "lane_b_scaffold_direct_llm",
        "lane_c_baseline_agent",
        "lane_d_kc_plain_agent",
        "lane_e_kc_tool_roundtrip",
    ):
        assert lane in data
        assert data[lane] in ("PASS", "FAILED", "NOT_RUN")
    assert "blocking_layer" in data


def test_cg015_close_rule():
    artifact = ROOT / "results" / "phase-03-2-2-dsh-live-isolation.json"
    if not artifact.exists():
        return
    data = json.loads(artifact.read_text(encoding="utf-8"))
    lanes = [
        data.get("lane_a_upstream_adapter"),
        data.get("lane_b_scaffold_direct_llm"),
        data.get("lane_c_baseline_agent"),
        data.get("lane_d_kc_plain_agent"),
        data.get("lane_e_kc_tool_roundtrip"),
    ]
    if data.get("cg015") == "CLOSED":
        assert all(x == "PASS" for x in lanes)
        assert data.get("abc_match") is True


def test_secret_redaction_in_artifact():
    artifact = ROOT / "results" / "phase-03-2-2-dsh-live-isolation.json"
    if not artifact.exists():
        return
    text = artifact.read_text(encoding="utf-8")
    assert "sk-" not in text
    assert "DEEPSEEK_API_KEY=" not in text
    assert "Authorization" not in text
