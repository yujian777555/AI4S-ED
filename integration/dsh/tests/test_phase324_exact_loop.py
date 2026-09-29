"""Phase 3.2.4 keyless regression tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_no_null_session_probe():
    """Prevent null/undefined sessionId being treated as a real session probe."""
    for fp in (ROOT / "integration" / "dsh").rglob("*.ts"):
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if "sessionId" in line and "null" in line and "P2" in line:
                if "real" not in line.lower() and "assert" not in line:
                    raise AssertionError(f"null sessionId probe in {fp}: {line.strip()[:80]}")


def test_no_hardcoded_empty_tool_history():
    for fp in (ROOT / "integration" / "dsh").rglob("*.ts"):
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if re.search(r"toolHistory\s*=\s*\[\]", line):
                raise AssertionError(f"hardcoded empty toolHistory in {fp}")


def test_marker_probe_requires_isAgentLoopRequest():
    for fp in (ROOT / "integration" / "dsh").rglob("lane324*.ts"):
        text = fp.read_text(encoding="utf-8", errors="ignore")
        if "markAgentLoopRequest" in text and "isAgentLoopRequest" not in text:
            raise AssertionError(f"marker probe without isAgentLoopRequest check in {fp}")


def test_artifact_cg015_and_abc():
    artifact = ROOT / "results" / "phase-03-2-4-exact-loop-request.json"
    if not artifact.exists():
        return
    data = json.loads(artifact.read_text(encoding="utf-8"))
    if data.get("cg015") == "CLOSED":
        assert data.get("kc_roundtrip", {}).get("abc_match") is True
        assert data.get("kc_roundtrip", {}).get("tool_call_count", 0) >= 1


def test_secret_redaction():
    artifact = ROOT / "results" / "phase-03-2-4-exact-loop-request.json"
    if not artifact.exists():
        return
    text = artifact.read_text(encoding="utf-8")
    assert "sk-" not in text
    assert "Authorization" not in text
