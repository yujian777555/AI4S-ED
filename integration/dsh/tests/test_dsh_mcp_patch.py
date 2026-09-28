"""DSH MCP patch shape tests (keyless)."""

from __future__ import annotations

import sys

from integration.dsh.mcp_patch import (
    DSH_TARGET_VERSION,
    PLUGIN_NAME,
    ROW_ID,
    SERVER_NAME,
    build_patch,
    expected_public_tool_name,
)


def test_patch_targets_015rc1():
    assert DSH_TARGET_VERSION == "0.1.5rc1"


def test_patch_shape_and_no_committed_absolute_path():
    patch = build_patch(python_executable="/runtime/injected/python", workspace="/runtime/ws")
    assert isinstance(patch, list) and len(patch) == 1
    rows = patch[0]["insert"]
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == ROW_ID
    assert row["name"] == PLUGIN_NAME
    cfg = row["config"]
    assert cfg["serverName"] == SERVER_NAME
    assert cfg["transport"] == "stdio"
    assert cfg["command"] == "/runtime/injected/python"
    assert cfg["args"] == ["-m", "knowledge_curator.mcp_server"]
    assert cfg["failOnStartupError"] is True
    assert cfg["toolCallTimeoutMs"] >= 1000


def test_default_patch_uses_current_interpreter():
    patch = build_patch()
    assert patch[0]["insert"][0]["config"]["command"] == sys.executable


def test_template_file_has_no_machine_specific_python_path():
    from pathlib import Path

    tpl = Path("integration/dsh/patches/knowledge-curator-mcp.patch.yml")
    text = tpl.read_text(encoding="utf-8")
    assert "C:\\Users" not in text
    assert "/Users/" not in text
    assert "ai4s-ed" in text or "knowledge_curator" in text


def test_public_tool_name_is_dsh_mcp_style():
    name = expected_public_tool_name()
    assert name == "mcp__knowledge_curator__curate_assertion_set"
