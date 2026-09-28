"""Direct MCP server contract tests (no DSH, no API key)."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from knowledge_curator.mcp_server import PUBLIC_TOOL_NAME, create_mcp_server
from knowledge_curator.mcp_server.runtime import create_default_runtime, run_curate
from knowledge_curator.mcp_server.codec import parse_assertion_set, serialize_curation_report
from knowledge_curator.tests.conftest import make_assertion, make_assertion_set


def _fixture_payload() -> dict:
    return {
        "ref_id": "ED-2025-0042",
        "metadata": {
            "title": "Fixture Paper",
            "authors": ["A. Author"],
            "year": 2024,
            "source": "Journal",
            "doi": "10.0000/fixture",
            "stable_id": "ST-FIXTURE",
        },
        "quality_grade": "B",
        "assertions": [
            {
                "id": "AS-001",
                "ref_id": "ED-2025-0042",
                "subject": {
                    "eddo_class": "Membrane",
                    "resolved_entity": "eddo:membrane:nafion117",
                    "original_mention": "Nafion 117",
                },
                "property": "hasEnergyConsumption",
                "object": {
                    "value": 1.42,
                    "unit": "kWh/m3",
                    "value_type": "number",
                    "uncertainty": 0.05,
                },
                "conditions": [
                    {"eddo_class": "Temperature", "value": 298.15, "unit": "K"},
                    {"eddo_class": "FeedNaCl", "value": 0.05, "unit": "mol/L"},
                ],
                "provenance": {"locator": "T12", "sentence": "Table 3 row2"},
                "claim_type": "measurement",
                "source_claim_origin": "primary",
                "confidence": "medium",
                "quality": 0.87,
            }
        ],
    }


def test_tools_list_contains_curate_tool():
    server = create_mcp_server()

    async def _run():
        tools = await server.list_tools()
        return [t.name for t in tools]

    names = anyio.run(_run)
    assert PUBLIC_TOOL_NAME in names


def test_call_tool_matches_direct_core_result():
    payload = _fixture_payload()
    server = create_mcp_server()

    async def _run():
        return await server.call_tool(PUBLIC_TOOL_NAME, {"assertion_set": payload})

    result = anyio.run(_run)
    # CallToolResult exposes content/structuredContent depending on SDK version
    text = ""
    structured = None
    if hasattr(result, "content") and result.content:
        text = " ".join(getattr(c, "text", "") or "" for c in result.content)
    if hasattr(result, "structuredContent"):
        structured = result.structuredContent
    assert structured is not None or text

    # Direct core call
    parsed = parse_assertion_set(payload)
    runtime = create_default_runtime()
    direct = anyio.run(lambda: run_curate(runtime, parsed))
    expected = serialize_curation_report(direct)

    if structured is not None:
        observed_report = structured.get("report") if isinstance(structured, dict) else None
    else:
        import json

        observed = json.loads(text) if text.strip().startswith("{") else None
        observed_report = observed.get("report") if observed else None

    assert observed_report is not None
    assert observed_report["status"] == expected["status"]
    assert observed_report["source_ref_id"] == expected["source_ref_id"]
    assert observed_report["decisions"][0]["action"] == expected["decisions"][0]["action"]
    assert observed_report["decisions"][0]["confidence"] == expected["decisions"][0]["confidence"]


def test_malformed_payload_returns_mcp_is_error():
    """Official mcp 2.2.0: ToolError maps to CallToolResult(is_error=True) on the wire."""
    import pytest
    from mcp.server.mcpserver.exceptions import ToolError

    server = create_mcp_server()

    async def _run():
        return await server.call_tool(PUBLIC_TOOL_NAME, {"assertion_set": {"ref_id": "x"}})

    with pytest.raises(ToolError):
        anyio.run(_run)


def test_invalid_enum_payload_mcp_is_error():
    import pytest
    from mcp.server.mcpserver.exceptions import ToolError

    payload = _fixture_payload()
    payload["assertions"][0]["confidence"] = "not-a-confidence"
    server = create_mcp_server()

    async def _run():
        return await server.call_tool(PUBLIC_TOOL_NAME, {"assertion_set": payload})

    with pytest.raises(ToolError):
        anyio.run(_run)


def test_health_tool_is_diagnostic_only():
    server = create_mcp_server()

    async def _run():
        return await server.call_tool("knowledge_curator_health", {})

    result = anyio.run(_run)
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        assert structured.get("role") == "integration-diagnostic"


def test_stdio_entrypoint_module_exists():
    import knowledge_curator.mcp_server.__main__ as main_mod

    assert hasattr(main_mod, "run_stdio") or callable(main_mod)


def test_stdio_subprocess_lists_and_calls_tool():
    """Start `python -m knowledge_curator.mcp_server` and exercise official stdio MCP."""
    import os
    import sys

    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "knowledge_curator.mcp_server"],
        cwd=str(Path.cwd()),
        env={**os.environ},
    )

    async def _run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = [t.name for t in tools.tools]
                assert "curate_assertion_set" in names
                result = await session.call_tool(
                    "curate_assertion_set",
                    {"assertion_set": _fixture_payload()},
                )
                return result

    result = anyio.run(_run)
    assert result is not None
    if hasattr(result, "isError"):
        assert result.isError is False
