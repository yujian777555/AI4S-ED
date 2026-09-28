"""Live DSH MCP bridge smoke (Phase 3.1).

Requires DEEPSEEK_API_KEY. Uses official DeepSeekHarness + runtime patch.
Does not call DeepSeek HTTP directly. No secrets in output.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from integration.dsh.mcp_patch import build_patch, expected_public_tool_name

REVIEWED_DSH_REVISION = "4878cdabd87d4041bdaff61d04c966883b9fd07a"
EXPECTED_TOOL = expected_public_tool_name()

FIXTURE = {
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

PROMPT = (
    f"Call the tool {EXPECTED_TOOL} with this assertion_set. "
    "Then reply with exactly three lines:\n"
    "status=<value>\n"
    "action=<first decision action>\n"
    "confidence=<first decision confidence>\n"
    f"assertion_set={json.dumps(FIXTURE, ensure_ascii=False, separators=(',', ':'))}"
)


@dataclass
class McpSmokeResult:
    dsh_sdk_version: str = ""
    dsh_runtime_version: str = ""
    mcp_sdk_version: str = ""
    profile: str = "sdk-minimal"
    provider: str = "deepseek-official"
    model: str = ""
    public_tool_name: str = EXPECTED_TOOL
    tool_discovered: bool = False
    tool_called: bool = False
    tool_call_count: int = 0
    expected_result_summary: dict[str, Any] = field(default_factory=dict)
    observed_result_summary: dict[str, Any] = field(default_factory=dict)
    final_response_nonempty: bool = False
    finish_reason: str = ""
    live_test_passed: bool = False
    secret_present: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "dsh_sdk_version": self.dsh_sdk_version,
            "dsh_runtime_version": self.dsh_runtime_version,
            "mcp_sdk_version": self.mcp_sdk_version,
            "profile": self.profile,
            "provider": self.provider,
            "model": self.model,
            "public_tool_name": self.public_tool_name,
            "tool_discovered": self.tool_discovered,
            "tool_called": self.tool_called,
            "tool_call_count": self.tool_call_count,
            "expected_result_summary": self.expected_result_summary,
            "observed_result_summary": self.observed_result_summary,
            "final_response_nonempty": self.final_response_nonempty,
            "finish_reason": self.finish_reason,
            "live_test_passed": self.live_test_passed,
            "secret_present": self.secret_present,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _ver(pkg: str) -> str:
    try:
        import importlib.metadata as md

        return md.version(pkg)
    except Exception:
        return "unknown"


def _scan_events_for_tools(events: list, notifications: list) -> tuple[bool, int, list[str]]:
    """Walk DSH RunResult events/notifications for MCP tool evidence."""
    discovered = False
    count = 0
    names: list[str] = []

    def walk(node: Any) -> None:
        nonlocal discovered, count
        if isinstance(node, dict):
            for k, v in node.items():
                lk = str(k).lower()
                sv = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
                if "tool" in lk or (isinstance(v, str) and EXPECTED_TOOL in v):
                    if EXPECTED_TOOL in sv or EXPECTED_TOOL in str(v):
                        discovered = True
                        names.append(str(v)[:200])
                if lk in {"name", "tool_name", "tool", "toolName"} and isinstance(v, str):
                    if "curate" in v or "knowledge_curator" in v or v.startswith("mcp__"):
                        discovered = True
                        names.append(v)
                if lk in {"method"} and isinstance(v, str) and "tool" in v.lower():
                    count += 1
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            if EXPECTED_TOOL in node:
                discovered = True
                names.append(node[:200])

    walk(events)
    walk(notifications)

    # Count explicit tool/call mentions
    blob = json.dumps({"e": events, "n": notifications}, ensure_ascii=False, default=str)
    count = max(count, blob.count("tool/call") + blob.count("tools/call"))
    if EXPECTED_TOOL in blob:
        discovered = True
        count = max(count, blob.count(EXPECTED_TOOL) // 2)
    return discovered, count, names


def run_live_mcp_bridge() -> McpSmokeResult:
    result = McpSmokeResult(
        dsh_sdk_version=_ver("deepseek-harness-sdk"),
        dsh_runtime_version=_ver("deepseek-harness-runtime-bin"),
        mcp_sdk_version=_ver("mcp"),
        model=os.environ.get("DSH_MODEL", "deepseek-chat"),
        secret_present=bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()),
    )
    result.warnings.append(
        f"DSH target {result.dsh_sdk_version} vs reviewed 0.2.0-rc.1 (CG-015)"
    )

    if not result.secret_present:
        result.errors.append("LIVE_SMOKE_NOT_RUN_NO_SECRET")
        return result

    from integration.dsh.config import load_config

    try:
        config = load_config()
    except Exception as exc:
        result.errors.append(f"config error: {exc}")
        return result

    patch = build_patch(python_executable=sys.executable, workspace=str(Path.cwd()))
    patch_path = Path(tempfile.gettempdir()) / f"ai4s-ed-mcp-{uuid.uuid4().hex[:8]}.patch.json"
    patch_path.write_text(json.dumps(patch, indent=2), encoding="utf-8")

    try:
        from deepseek_harness import DeepSeekHarness, DeepSeekHarnessConfig
    except Exception as exc:
        result.errors.append(f"DSH SDK import failed: {exc}")
        return result

    harness_config = DeepSeekHarnessConfig(
        provider=config.provider,
        model=result.model,
        profile="sdk-minimal",
        dsh_home=config.dsh_home,
        cwd=config.workspace,
        max_tokens=1200,
        patches=(str(patch_path),),
        request_timeout_seconds=180.0,
    )

    session_id = f"ai4s-ed-mcp-{uuid.uuid4().hex[:8]}"
    try:
        with DeepSeekHarness(harness_config) as harness:
            run = harness.run(PROMPT, session_id=session_id)
            discovered, count, names = _scan_events_for_tools(
                run.events, [n.model_dump() if hasattr(n, "model_dump") else n for n in run.notifications]
            )
            result.tool_discovered = discovered
            result.tool_call_count = count
            result.tool_called = count >= 1 and discovered
            result.finish_reason = run.finish_reason or ""
            final = (run.final_response or "").strip()
            result.final_response_nonempty = bool(final)
            result.observed_result_summary = {
                "finish_reason": result.finish_reason,
                "final_snippet": final[:300],
                "tool_name_hits": names[:5],
            }
    except Exception as exc:
        result.errors.append(f"live MCP bridge failed: {type(exc).__name__}: {exc}")
        return result

    # Expected deterministic summary from core
    try:
        from knowledge_curator.mcp_server.codec import parse_assertion_set, serialize_curation_report
        from knowledge_curator.mcp_server.runtime import create_default_runtime, run_curate
        import anyio

        parsed = parse_assertion_set(FIXTURE)
        direct = anyio.run(lambda: run_curate(create_default_runtime(), parsed))
        exp = serialize_curation_report(direct)
        result.expected_result_summary = {
            "status": exp["status"],
            "action": exp["decisions"][0]["action"],
            "confidence": exp["decisions"][0]["confidence"],
        }
        obs_final = result.observed_result_summary.get("final_snippet", "")
        if result.expected_result_summary["action"] in obs_final or result.expected_result_summary["confidence"] in obs_final:
            result.observed_result_summary["matches_expected"] = True
        else:
            result.observed_result_summary["matches_expected"] = False
            result.warnings.append("final response does not explicitly quote expected action/confidence")
    except Exception as exc:
        result.warnings.append(f"expected summary unavailable: {exc}")

    result.live_test_passed = bool(
        result.tool_discovered
        and result.tool_called
        and result.final_response_nonempty
        and result.finish_reason in {"completed", "stop", "completed_successfully", ""}
        and not result.errors
    )
    return result


def write_result(path: Path, result: McpSmokeResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    r = run_live_mcp_bridge()
    write_result(Path("results/phase-03-1-dsh-mcp-smoke.json"), r)
    print(json.dumps(r.to_json(), indent=2, ensure_ascii=False))
    sys.exit(0 if r.live_test_passed else 1)
