"""Phase 4.3.1 keyless DSH preset / fixture-switch regression tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_preset_persona_mentions_evidence_tools():
    preset = (ROOT / "dsh" / "knowledge-curator" / "cordis.patch.yml").read_text(
        encoding="utf-8"
    )
    assert "retrieve_evidence" in preset
    assert "validate_retrieved_claims" in preset
    # Still the same preset id — no new Agent.
    assert "id: knowledge-curator" in preset
    assert "knowledge-curator-rag" not in preset
    assert "knowledge-curator-v2" not in preset


def test_preset_still_uses_stdio_mcp_server():
    preset = (ROOT / "dsh" / "knowledge-curator" / "cordis.patch.yml").read_text(
        encoding="utf-8"
    )
    assert "knowledge_curator.mcp_server" in preset
    assert "@deepseek-ai/dsh-mcp-client" in preset


def test_lane325_e2e_exists_and_binds_preset():
    lane = ROOT / "integration" / "dsh" / "lane325_kc_evidence_roundtrip.e2e.ts"
    assert lane.exists()
    text = lane.read_text(encoding="utf-8")
    assert "agentPreset" in text
    assert "knowledge-curator" in text
    assert "agentPresets.mount" in text
    assert "mcp__knowledge_curator__retrieve_evidence" in text
    assert "mcp__knowledge_curator__validate_retrieved_claims" in text
    assert "KC_EVIDENCE_INTEGRATION_FIXTURE" in text


def test_app_py_utf8_clean():
    src = (ROOT / "knowledge_curator" / "mcp_server" / "app.py").read_text(
        encoding="utf-8"
    )
    for bad in ("搂", "鈥", "撀"):
        assert bad not in src
    assert "§5.1" in src


def test_no_new_agent_preset_dirs():
    dsh_dir = ROOT / "dsh"
    names = [p.name for p in dsh_dir.iterdir() if p.is_dir()]
    assert names == ["knowledge-curator"], names
