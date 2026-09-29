"""Build the DSH 0.1.5rc1 MCP client patch without committing machine-specific paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

PLUGIN_NAME = "@deepseek-ai/dsh-mcp-client"
ROW_ID = "mcp-knowledge-curator"
SERVER_NAME = "knowledge_curator"
TOOL_CALL_TIMEOUT_MS = 60000
DSH_TARGET_VERSION = "0.1.5rc1"


def build_patch(
    *,
    python_executable: str | None = None,
    workspace: str | None = None,
    timeout_ms: int = TOOL_CALL_TIMEOUT_MS,
) -> list[dict[str, Any]]:
    """Return a DSH patch list that inserts the knowledge_curator MCP client.

    DSH 0.1.5rc1 requires a top-level YAML/JSON array of loader patch entries.
    Absolute interpreter/workspace paths are injected at runtime from the
    current environment — never hard-coded in the committed template.
    """
    py = python_executable or sys.executable
    cwd = workspace or os.environ.get('AI4S_KC_WORKSPACE') or str(Path.cwd())
    return [
        {
            "insert": [
                {
                    "id": ROW_ID,
                    "name": PLUGIN_NAME,
                    "config": {
                        "serverName": SERVER_NAME,
                        "transport": "stdio",
                        "command": py,
                        "args": ["-m", "knowledge_curator.mcp_server"],
                        "cwd": cwd,
                        "failOnStartupError": True,
                        "toolCallTimeoutMs": timeout_ms,
                    },
                }
            ]
        }
    ]


def expected_public_tool_name() -> str:
    """DSH registers MCP tools as mcp__<serverName>__<tool>."""
    from knowledge_curator.mcp_server import PUBLIC_TOOL_NAME

    return f"mcp__{SERVER_NAME}__{PUBLIC_TOOL_NAME}"
