"""Phase SI-1.5-R1: real stdio subprocess MCP acceptance test.

Launches `python -m system.mcp_stdio` as a real subprocess via MCP stdio
transport, exactly as DSH does. No DeepSeek API key required.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp", reason="mcp SDK required for stdio subprocess test")

ROOT = Path(__file__).resolve().parents[3]


def _run_mcp_subprocess(env_extra: dict, call_tool: str = "knowledge_curator_health", call_args: dict | None = None):
    """Start system.mcp_stdio via MCP stdio client and run one tool call."""
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = {**os.environ, **env_extra}
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "system.mcp_stdio"],
        cwd=str(ROOT),
        env=env,
    )

    async def _run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = [t.name for t in tools.tools]
                result = await session.call_tool(call_tool, call_args or {})
                return names, result

    return anyio.run(_run)


def _parse_result(result) -> dict:
    structured = getattr(result, "structuredContent", None) or {}
    if not structured and getattr(result, "content", None):
        text = " ".join(getattr(c, "text", "") or "" for c in result.content)
        structured = json.loads(text) if text.strip().startswith("{") else {}
    return structured


PROVIDER = "integration.system.fixtures.dsh_provider:create_provider_bundle"
PROVIDER_NO_EVIDENCE = "integration.system.fixtures.dsh_provider:create_provider_bundle_no_evidence"


def test_real_stdio_valid_provider_exact_four_tools():
    names, _ = _run_mcp_subprocess(
        {"AI4S_SYSTEM_ADAPTER_FACTORY": PROVIDER},
        call_tool="knowledge_curator_health",
    )
    assert sorted(names) == sorted(
        [
            "curate_assertion_set",
            "knowledge_curator_health",
            "retrieve_evidence",
            "validate_retrieved_claims",
        ]
    )


def test_real_stdio_health_provider_identity():
    _, result = _run_mcp_subprocess(
        {"AI4S_SYSTEM_ADAPTER_FACTORY": PROVIDER},
        call_tool="knowledge_curator_health",
    )
    structured = _parse_result(result)
    assert "integration-test-provider" in str(structured.get("adapters", ""))
    assert structured.get("retrieval_available") is True


def test_real_stdio_curation_round_trip():
    assertion_set = {
        "ref_id": "R1",
        "metadata": {"title": "T", "authors": ["A"], "year": 2024, "source": "S"},
        "assertions": [
            {
                "id": "A1",
                "ref_id": "R1",
                "subject": {"eddo_class": "M", "resolved_entity": "E", "original_mention": "E"},
                "property": "P",
                "object": {"value": 1.0, "unit": "u", "value_type": "number"},
                "conditions": [],
                "provenance": {"locator": "p.1"},
                "claim_type": "measurement",
                "source_claim_origin": "primary",
                "confidence": "high",
                "quality": 0.9,
            }
        ],
        "quality_grade": "B",
    }
    _, result = _run_mcp_subprocess(
        {"AI4S_SYSTEM_ADAPTER_FACTORY": PROVIDER},
        call_tool="curate_assertion_set",
        call_args={"assertion_set": assertion_set},
    )
    structured = _parse_result(result)
    assert structured.get("ok") is True
    assert "report" in structured


def test_real_stdio_missing_provider_fails_closed():
    import subprocess

    env = {k: v for k, v in os.environ.items() if k != "AI4S_SYSTEM_ADAPTER_FACTORY"}
    proc = subprocess.run(
        [sys.executable, "-m", "system.mcp_stdio"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode != 0
    # Must not silently start an integration runtime
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert "provider" in combined.lower() or "failed" in combined.lower()


def test_real_stdio_evidence_unavailable_when_omitted():
    _, result = _run_mcp_subprocess(
        {"AI4S_SYSTEM_ADAPTER_FACTORY": PROVIDER_NO_EVIDENCE},
        call_tool="retrieve_evidence",
        call_args={"request": {"query": "test"}},
    )
    structured = _parse_result(result)
    assert structured.get("ok") is False
    assert structured.get("error") == "retrieval_unavailable"


def test_real_stdio_fixture_env_cannot_bypass():
    """KC_EVIDENCE_INTEGRATION_FIXTURE=1 does not enable evidence without provider."""
    _, result = _run_mcp_subprocess(
        {
            "AI4S_SYSTEM_ADAPTER_FACTORY": PROVIDER_NO_EVIDENCE,
            "KC_EVIDENCE_INTEGRATION_FIXTURE": "1",
        },
        call_tool="retrieve_evidence",
        call_args={"request": {"query": "test"}},
    )
    structured = _parse_result(result)
    assert structured.get("ok") is False
    assert structured.get("error") == "retrieval_unavailable"
