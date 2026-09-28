"""MCP application: official MCPServer exposing curate_assertion_set.

Thin adapter over existing KnowledgeCurator core. No §5 logic duplication.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer

from knowledge_curator.mcp_server.codec import CodecError, parse_assertion_set, serialize_curation_report
from knowledge_curator.mcp_server.runtime import CuratorRuntime, create_default_runtime, run_curate

PUBLIC_TOOL_NAME = "curate_assertion_set"
HEALTH_TOOL_NAME = "knowledge_curator_health"


def create_mcp_server(runtime: CuratorRuntime | None = None) -> MCPServer:
    """Build the knowledge_curator MCP server around an optional runtime."""
    rt = runtime or create_default_runtime()
    server = MCPServer(
        name="knowledge_curator",
        version="0.1.0",
        instructions=(
            "Deterministic knowledge curation tools for AI4S-ED. "
            "Business logic lives in KnowledgeCurator core."
        ),
    )

    @server.tool(
        name=PUBLIC_TOOL_NAME,
        description=(
            "Curate one AssertionSet through KnowledgeCurator §5.1–§5.3 "
            "(completeness, conflict, quality, decision) and return a CurationReport."
        ),
    )
    async def curate_assertion_set(assertion_set: dict[str, Any]) -> dict[str, Any]:
        try:
            parsed = parse_assertion_set(assertion_set)
        except CodecError as exc:
            return {
                "ok": False,
                "error": {"type": "CodecError", "message": str(exc)},
            }
        except Exception as exc:  # noqa: BLE001 — structured tool failure
            return {
                "ok": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }

        report = await run_curate(rt, parsed)
        return {
            "ok": True,
            "report": serialize_curation_report(report),
        }

    @server.tool(
        name=HEALTH_TOOL_NAME,
        description="Integration diagnostic only — not a scientific business API.",
    )
    async def knowledge_curator_health() -> dict[str, Any]:
        return {
            "ok": True,
            "role": "integration-diagnostic",
            "core": "KnowledgeCurator",
            "adapters": rt.adapter_note,
            "public_business_tool": PUBLIC_TOOL_NAME,
        }

    return server


def run_stdio() -> None:
    """Entry for `python -m knowledge_curator.mcp_server` (official stdio transport)."""
    server = create_mcp_server()
    # Official MCP SDK stdio runner. Not hand-written JSON-RPC.
    import anyio

    anyio.run(server.run_stdio_async)
