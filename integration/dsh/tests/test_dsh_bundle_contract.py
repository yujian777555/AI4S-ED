"""Product DSH bundle contract tests (Phase 3.2, keyless).

Inspect dsh/knowledge-curator product bundle only.
The global registry fixture is integration/qualif only and must not live here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

BUNDLE_DIR = Path("dsh/knowledge-curator")
PACKAGE_JSON = BUNDLE_DIR / "package.json"
PATCH_YML = BUNDLE_DIR / "cordis.patch.yml"
README_MD = BUNDLE_DIR / "README.md"


def _patch_text() -> str:
    return PATCH_YML.read_text(encoding="utf-8")


def _package() -> dict:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def test_package_json_shape():
    pkg = _package()
    assert pkg["name"] == "@ai4s-ed/knowledge-curator-dsh"
    assert pkg["private"] is True
    assert pkg["type"] == "module"
    assert pkg["dsh"]["bundle"]["patch"] == "./cordis.patch.yml"


def test_exactly_one_agent_preset():
    text = _patch_text()
    presets = re.findall(r"@deepseek-ai/dsh-agent-preset(?!\-)", text)
    # Only the agent-preset package name (not agent-preset-registry)
    assert text.count("name: '@deepseek-ai/dsh-agent-preset'") == 1
    assert "config:\n        id: knowledge-curator" in text or "id: knowledge-curator" in text
    assert "lit_researcher" not in text or "Do not act as lit_researcher" in text


def test_no_other_agent_presets():
    text = _patch_text()
    # No other preset ids besides knowledge-curator
    ids = re.findall(r"config:\s*\n\s*id:\s*(\S+)", text)
    # Only expect knowledge-curator as preset id (mcp row uses serverName)
    assert "knowledge-curator" in text
    for other in ("orchestrator", "proposer", "critic", "lit_researcher", "ra-de"):
        assert f"id: {other}" not in text


def test_product_bundle_has_no_global_registry():
    # Ignore comment lines; only active config rows matter.
    active = "\n".join(
        line for line in _patch_text().splitlines() if not line.strip().startswith("#")
    )
    assert "agent-preset-registry" not in active
    pkg = json.dumps(_package())
    assert "agent-preset-registry" not in pkg


def test_persona_present_and_boundary_safe():
    text = _patch_text()
    assert "@deepseek-ai/dsh-persona" in text
    assert "knowledge_curator" in text
    for role in (
        "lit_researcher",
        "orchestrator",
        "proposer",
        "critic",
        "mechanism validator",
        "evaluation scheduler",
    ):
        assert role in text  # persona must tell model NOT to act as these
    assert "Do not invent scientific facts" in text
    # §6/§7 not claimed
    assert "Abstain" not in text
    assert "retrieval" not in text.lower() or "Do not" in text


def test_mcp_child_config():
    text = _patch_text()
    assert "@deepseek-ai/dsh-mcp-client" in text
    assert "serverName: knowledge_curator" in text
    assert "transport: stdio" in text
    assert "system.mcp_stdio" in text
    assert "failOnStartupError: true" in text
    assert "toolCallTimeoutMs" in text


def test_no_hardcoded_user_paths():
    text = _patch_text()
    assert "C:\\Users" not in text
    assert "/home/" not in text
    assert "/Users/" not in text
    assert "AI4S_KC_PYTHON" in text  # env-backed
    assert "AI4S_KC_WORKSPACE" in text


def test_no_api_key_or_secret():
    text = _patch_text()
    pkg = json.dumps(_package())
    assert "sk-" not in text
    assert "DEEPSEEK_API_KEY" not in text
    assert "sk-" not in pkg


def test_no_six_or_seven_tools():
    text = _patch_text()
    for tool in (
        "search_evidence",
        "get_citation",
        "abstain",
        "revise_assertion",
        "watchdog",
    ):
        assert tool not in text


def test_expected_public_mcp_tool_documented():
    readme = README_MD.read_text(encoding="utf-8")
    assert "mcp__knowledge_curator__curate_assertion_set" in readme
    assert "agent-preset-registry" in readme  # documents the boundary


def test_registry_fixture_is_outside_product_bundle():
    fixture = Path("integration/dsh/fixtures/knowledge-curator-qualification.patch.yml")
    assert fixture.exists()
    ftext = fixture.read_text(encoding="utf-8")
    assert "agent-preset-registry" in ftext
    assert "TEST / QUALIFICATION ONLY" in ftext
    # Product bundle must not contain the fixture
    assert "qualification" not in _patch_text()
