"""Live DSH MCP bridge smoke with strict tool/call evidence (Phase 3.1.1).

Only structurally matched DSH session events count as tool evidence:

    event["type"] == "tool/call" and event["data"]["name"] == EXPECTED_TOOL

String occurrences in prompts/catalog are NOT evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
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


# ---------------------------------------------------------------------------
# Strict DSH session event parsing (0.1.5rc1)
# ---------------------------------------------------------------------------

def _event_type(event: Any) -> str:
    if not isinstance(event, dict):
        return ""
    for key in ("type", "event", "kind"):
        val = event.get(key)
        if isinstance(val, str):
            return val
    return ""


def _event_data(event: Any) -> dict:
    if not isinstance(event, dict):
        return {}
    data = event.get("data")
    if isinstance(data, dict):
        return data
    # Some events flatten fields at top level.
    return event


def extract_matching_call_events(events: list[Any], expected_tool: str = EXPECTED_TOOL) -> list[dict[str, Any]]:
    """Return sanitized evidence only for exact tool/call events of expected_tool.

    DSH 0.1.5rc1 shape:
      {"type":"tool/call","seq":N,"data":{"turn":T,"step":S,"callId":"...","name":"...","arguments":"<json str>"}}
    """
    matches: list[dict[str, Any]] = []
    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        if _event_type(event) != "tool/call":
            continue
        data = _event_data(event)
        name = data.get("name") or data.get("tool") or data.get("toolName")
        if name != expected_tool:
            continue
        raw_args = data.get("arguments") or data.get("args") or data.get("input") or {}
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args) if raw_args.strip() else {}
            except Exception:
                args = {}
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            args = {}
        fixture_ref = None
        nested = args.get("assertion_set") if isinstance(args, dict) else None
        if isinstance(nested, dict):
            fixture_ref = nested.get("ref_id")
        matches.append(
            {
                "seq": event.get("seq", data.get("seq", idx)),
                "callId": data.get("callId") or data.get("call_id") or data.get("id"),
                "name": name,
                "turn": data.get("turn", event.get("turn")),
                "step": data.get("step", event.get("step")),
                "arguments_hash": hashlib.sha256(
                    json.dumps(args, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
                ).hexdigest()[:16],
                "arguments_fixture_ref_id": fixture_ref,
            }
        )
    return matches


def extract_matching_result_events(
    events: list[Any],
    call_events: list[dict[str, Any]],
    expected_tool: str = EXPECTED_TOOL,
) -> list[dict[str, Any]]:
    """Return tool/result events linked to matching calls via sourceEventSeqs.

    DSH 0.1.5rc1 shape:
      {"type":"tool/result","seq":M,"sourceEventSeqs":[N],
       "data":{"turn":T,"step":S,"message":{"source":{"kind":"...","callId":"..."},
       "content":[{...}],"role":"tool","id":"..."}}}
    """
    call_seqs = {str(c.get("seq")) for c in call_events}
    call_ids = {c.get("callId") for c in call_events if c.get("callId")}
    results: list[dict[str, Any]] = []
    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        if _event_type(event) != "tool/result":
            continue
        data = _event_data(event)
        source_seqs = event.get("sourceEventSeqs") or data.get("sourceEventSeqs") or []
        if isinstance(source_seqs, (int, str)):
            source_seqs = [source_seqs]
        if not isinstance(source_seqs, (list, tuple, set)):
            source_seqs = []
        source_set = {str(s) for s in source_seqs}
        linked = source_set & call_seqs
        message = data.get("message") if isinstance(data.get("message"), dict) else {}
        source = message.get("source") if isinstance(message.get("source"), dict) else {}
        call_id = source.get("callId") or data.get("callId")
        # Plan §2: require sourceEventSeqs to contain the call seq.
        # Only fall back to callId when sourceEventSeqs is absent entirely.
        if source_seqs:
            if not linked:
                continue
        elif call_id not in call_ids:
            continue
        content = message.get("content") if isinstance(message.get("content"), list) else data.get("content")
        payload = content
        summary = summarize_tool_result_payload(payload)
        result_name = (
            source.get("kind")
            or message.get("name")
            or data.get("name")
            or expected_tool
        )
        # Prefer expected tool name for acceptance when call was matched
        display_name = expected_tool if linked or call_id in call_ids else result_name
        results.append(
            {
                "seq": event.get("seq", data.get("seq", idx)),
                "sourceEventSeqs": sorted(linked) if linked else [],
                "callId": call_id,
                "name": display_name,
                "isError": bool(data.get("isError") or event.get("isError") or False),
                "tool_result_summary": summary,
            }
        )
    return results


def summarize_tool_result_payload(payload: Any) -> dict[str, Any]:
    """Extract status/action/confidence from an MCP curate result payload.

    Handles DSH 0.1.5rc1 nesting:
      [{"type":"tool-result","toolCallId":"...","content":[{"type":"text","text":"<json>"}]}]
    """
    obj: Any = payload
    if isinstance(payload, str):
        try:
            obj = json.loads(payload)
        except Exception:
            return {"raw_snippet": payload[:200]}
    if isinstance(obj, list):
        texts = []
        structured = None
        for item in obj:
            if isinstance(item, dict):
                # Nested tool-result block
                if "content" in item and isinstance(item["content"], list):
                    for sub in item["content"]:
                        if isinstance(sub, dict) and "text" in sub:
                            texts.append(str(sub["text"]))
                    if isinstance(item.get("structuredContent"), (dict, list)):
                        structured = item["structuredContent"]
                if "text" in item:
                    texts.append(str(item["text"]))
                if "structuredContent" in item and isinstance(item["structuredContent"], (dict, list)):
                    structured = item["structuredContent"]
            elif isinstance(item, str):
                texts.append(item)
        if structured is not None:
            obj = structured
        else:
            joined = "\n".join(texts)
            parsed = None
            for candidate in (joined, joined.strip(), joined.strip().strip("`")):
                if not candidate:
                    continue
                try:
                    parsed = json.loads(candidate)
                    break
                except Exception:
                    continue
            if parsed is None:
                m = re.search(r"\{.*\}", joined, re.DOTALL)
                if m:
                    try:
                        parsed = json.loads(m.group(0))
                    except Exception:
                        parsed = None
            obj = parsed if parsed is not None else {"raw_snippet": joined[:200]}
    if not isinstance(obj, dict):
        return {"raw_snippet": str(obj)[:200]}

    report = obj.get("report") if isinstance(obj.get("report"), dict) else obj
    status = report.get("status")
    action = None
    confidence = None
    decisions = report.get("decisions")
    if isinstance(decisions, list) and decisions:
        first = decisions[0]
        if isinstance(first, dict):
            action = first.get("action")
            confidence = first.get("confidence")
    return {
        "status": status,
        "action": action,
        "confidence": confidence,
        "ok": obj.get("ok"),
    }


def parse_final_response_summary(final_response: str) -> dict[str, Any]:
    """Parse the required three-line final answer."""
    text = final_response or ""
    status = action = confidence = None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"(status|action|confidence)\s*[=:]\s*(\S+)", line, re.IGNORECASE)
        if not m:
            continue
        key, val = m.group(1).lower(), m.group(2)
        if key == "status":
            status = val
        elif key == "action":
            action = val
        else:
            confidence = val
    return {"status": status, "action": action, "confidence": confidence, "nonempty": bool(text.strip())}


def summaries_match(a: dict, b: dict, c: dict) -> bool:
    keys = ("status", "action", "confidence")
    vals = []
    for s in (a, b, c):
        if not isinstance(s, dict):
            return False
        vals.append(tuple(s.get(k) for k in keys))
    return vals[0] == vals[1] == vals[2]


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
    matching_tool_result_count: int = 0
    matching_call_events: list[dict[str, Any]] = field(default_factory=list)
    matching_result_events: list[dict[str, Any]] = field(default_factory=list)
    direct_core_summary: dict[str, Any] = field(default_factory=dict)
    tool_result_summary: dict[str, Any] = field(default_factory=dict)
    final_response_summary: dict[str, Any] = field(default_factory=dict)
    summaries_match: bool = False
    final_response_nonempty: bool = False
    finish_reason: str = ""
    live_test_passed: bool = False
    credential_available: bool = False
    secret_leaked: bool = False
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
            "matching_tool_result_count": self.matching_tool_result_count,
            "matching_call_events": self.matching_call_events,
            "matching_result_events": self.matching_result_events,
            "direct_core_summary": self.direct_core_summary,
            "tool_result_summary": self.tool_result_summary,
            "final_response_summary": self.final_response_summary,
            "summaries_match": self.summaries_match,
            "final_response_nonempty": self.final_response_nonempty,
            "finish_reason": self.finish_reason,
            "live_test_passed": self.live_test_passed,
            "credential_available": self.credential_available,
            "secret_leaked": self.secret_leaked,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _ver(pkg: str) -> str:
    try:
        import importlib.metadata as md

        return md.version(pkg)
    except Exception:
        return "unknown"


def compute_direct_core_summary() -> dict[str, Any]:
    import anyio

    from knowledge_curator.mcp_server.codec import parse_assertion_set, serialize_curation_report
    from knowledge_curator.mcp_server.runtime import create_default_runtime, run_curate

    parsed = parse_assertion_set(FIXTURE)
    report = anyio.run(lambda: run_curate(create_default_runtime(), parsed))
    exp = serialize_curation_report(report)
    return {
        "status": exp["status"],
        "action": exp["decisions"][0]["action"],
        "confidence": exp["decisions"][0]["confidence"],
    }


def run_live_mcp_bridge() -> McpSmokeResult:
    result = McpSmokeResult(
        dsh_sdk_version=_ver("deepseek-harness-sdk"),
        dsh_runtime_version=_ver("deepseek-harness-runtime-bin"),
        mcp_sdk_version=_ver("mcp"),
        model=os.environ.get("DSH_MODEL", "deepseek-chat"),
        credential_available=bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()),
        secret_leaked=False,
    )
    result.warnings.append(
        f"DSH target {result.dsh_sdk_version} vs reviewed 0.2.0-rc.1 (CG-015)"
    )

    if not result.credential_available:
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
        max_tokens=2500,
        patches=(str(patch_path),),
        request_timeout_seconds=180.0,
    )

    session_id = f"ai4s-ed-mcp-{uuid.uuid4().hex[:8]}"
    try:
        with DeepSeekHarness(harness_config) as harness:
            run = harness.run(PROMPT, session_id=session_id)

            # Strict structural evidence only
            calls = extract_matching_call_events(run.events)
            results = extract_matching_result_events(run.events, calls)
            result.matching_call_events = calls
            result.matching_result_events = results
            result.tool_call_count = len(calls)
            result.matching_tool_result_count = len(results)
            result.tool_called = len(calls) >= 1
            result.tool_discovered = len(calls) >= 1  # discovery proven by real call

            result.finish_reason = run.finish_reason or ""
            final = (run.final_response or "").strip()
            result.final_response_nonempty = bool(final)
            result.final_response_summary = parse_final_response_summary(final)

            # Tool result summary from paired event
            if results:
                result.tool_result_summary = results[0].get("tool_result_summary") or {}
            else:
                result.errors.append("no linked tool/result event for expected tool")

            if not calls:
                result.errors.append("no exact tool/call event for expected tool")
    except Exception as exc:
        result.errors.append(f"live MCP bridge failed: {type(exc).__name__}: {exc}")
        return result

    try:
        result.direct_core_summary = compute_direct_core_summary()
    except Exception as exc:
        result.errors.append(f"direct core summary failed: {exc}")
        return result

    result.summaries_match = summaries_match(
        result.direct_core_summary,
        result.tool_result_summary,
        result.final_response_summary,
    )
    if result.direct_core_summary and result.tool_result_summary:
        if not summaries_match(result.direct_core_summary, result.tool_result_summary, result.direct_core_summary):
            result.errors.append("direct core != tool result")
    if result.tool_result_summary and result.final_response_summary:
        if not summaries_match(result.tool_result_summary, result.final_response_summary, result.tool_result_summary):
            result.errors.append("tool result != final response")

    result.live_test_passed = bool(
        result.tool_call_count >= 1
        and result.matching_tool_result_count >= 1
        and result.summaries_match
        and result.final_response_nonempty
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
