"""Strict DSH tool/call evidence tests (Phase 3.1.1, keyless).

Fixture events use the official DSH 0.1.5rc1 shape:
  {"type": "tool/call", "seq": N, "data": {"name": ..., "callId": ..., "arguments": {...}}}
  {"type": "tool/result", "seq": M, "data": {"name": ..., "sourceEventSeqs": [N], "result": {...}}}
"""

from __future__ import annotations

import json

from integration.dsh.mcp_smoke import (
    EXPECTED_TOOL,
    McpSmokeResult,
    extract_matching_call_events,
    extract_matching_result_events,
    parse_final_response_summary,
    summarize_tool_result_payload,
    summaries_match,
)

CORE_SUMMARY = {"status": "successful", "action": "accept", "confidence": "medium"}


def _tool_result_payload():
    return {
        "ok": True,
        "report": {
            "status": "successful",
            "decisions": [{"action": "accept", "confidence": "medium"}],
        },
    }


def _tool_call_event(seq=5, call_id="c-5", name=None, args=None):
    """Real DSH 0.1.5rc1 tool/call event shape."""
    return {
        "type": "tool/call",
        "seq": seq,
        "time": 1,
        "data": {
            "turn": 1,
            "step": 1,
            "callId": call_id,
            "name": name or EXPECTED_TOOL,
            "arguments": json.dumps(args if args is not None else {"assertion_set": {"ref_id": "X"}}),
        },
    }


def _tool_result_event(seq=6, source_seqs=None, call_id="c-5", payload=None, name="tool"):
    """Real DSH 0.1.5rc1 tool/result event shape."""
    return {
        "type": "tool/result",
        "seq": seq,
        "time": 2,
        "data": {
            "turn": 1,
            "step": 1,
            "message": {
                "source": {"kind": name, "callId": call_id},
                "content": [{"type": "text", "text": json.dumps(payload if payload is not None else _tool_result_payload())}],
                "role": "tool",
                "id": "msg-1",
            },
        },
        "sourceEventSeqs": source_seqs if source_seqs is not None else [seq - 1],
        "surfaceOp": "append",
    }


def test_prompt_text_with_tool_name_is_not_a_call():
    events = [
        {"type": "assistant.message", "seq": 1, "data": {"text": f"please call {EXPECTED_TOOL}"}},
        {"type": "user.message", "seq": 2, "data": {"text": f"Call the tool {EXPECTED_TOOL}"}},
    ]
    assert extract_matching_call_events(events) == []


def test_tool_catalog_entry_is_not_a_call():
    events = [
        {
            "type": "tools.catalog",
            "seq": 1,
            "data": {"tools": [{"name": EXPECTED_TOOL, "description": "curate"}]},
        }
    ]
    assert extract_matching_call_events(events) == []


def test_unrelated_tool_call_does_not_count():
    events = [_tool_call_event(seq=10, call_id="c1", name="mcp__other__tool", args={})]
    assert extract_matching_call_events(events) == []


def test_exact_tool_call_counts_once():
    events = [
        _tool_call_event(seq=3, call_id="call-1", args={"assertion_set": {"ref_id": "ED-2025-0042"}})
    ]
    calls = extract_matching_call_events(events)
    assert len(calls) == 1
    assert calls[0]["seq"] == 3
    assert calls[0]["callId"] == "call-1"
    assert calls[0]["name"] == EXPECTED_TOOL
    assert calls[0]["turn"] == 1
    assert calls[0]["step"] == 1
    assert calls[0]["arguments_fixture_ref_id"] == "ED-2025-0042"
    assert len(calls[0]["arguments_hash"]) == 16


def test_linked_tool_result_pairs_by_source_event_seqs():
    call = _tool_call_event(seq=5, call_id="c-5")
    result = _tool_result_event(seq=6, source_seqs=[5], call_id="c-5")
    calls = extract_matching_call_events([call])
    results = extract_matching_result_events([call, result], calls)
    assert len(calls) == 1
    assert len(results) == 1
    assert results[0]["sourceEventSeqs"] == ["5"]
    assert results[0]["tool_result_summary"]["status"] == "successful"


def test_unlinked_tool_result_is_rejected():
    call = _tool_call_event(seq=5, call_id="c-5")
    orphan = _tool_result_event(seq=9, source_seqs=[99], call_id="c-5")
    calls = extract_matching_call_events([call])
    results = extract_matching_result_events([call, orphan], calls)
    assert results == []


def test_result_from_other_tool_not_paired():
    call = _tool_call_event(seq=5, call_id="c-5")
    other = _tool_result_event(seq=6, source_seqs=[5], call_id="c-5", name="other", payload={"ok": True})
    calls = extract_matching_call_events([call])
    results = extract_matching_result_events([call, other], calls)
    # Linked by sourceEventSeqs; acceptance layer checks summaries match core.
    assert len(results) == 1


def test_direct_core_and_tool_result_mismatch_fails():
    tool_sum = {"status": "successful", "action": "reject", "confidence": "hypothesis"}
    final = {"status": "successful", "action": "accept", "confidence": "medium"}
    assert summaries_match(CORE_SUMMARY, tool_sum, final) is False


def test_tool_result_and_final_mismatch_fails():
    tool_sum = dict(CORE_SUMMARY)
    final = {"status": "successful", "action": "accept", "confidence": "high"}
    assert summaries_match(tool_sum, final, tool_sum) is False


def test_all_three_summaries_match():
    assert summaries_match(CORE_SUMMARY, dict(CORE_SUMMARY), dict(CORE_SUMMARY)) is True


def test_parse_final_response_summary():
    parsed = parse_final_response_summary(
        "status=successful\naction=accept\nconfidence=medium"
    )
    assert parsed == {
        "status": "successful",
        "action": "accept",
        "confidence": "medium",
        "nonempty": True,
    }


def test_artifact_has_no_secret_and_explicit_flags():
    r = McpSmokeResult(credential_available=True, secret_leaked=False)
    payload = r.to_json()
    text = json.dumps(payload)
    assert "credential_available" in payload
    assert "secret_leaked" in payload
    assert payload["secret_leaked"] is False
    assert "sk-" not in text
    assert "secret_present" not in payload
    for key in (
        "matching_call_events",
        "matching_result_events",
        "direct_core_summary",
        "tool_result_summary",
        "final_response_summary",
        "summaries_match",
    ):
        assert key in payload


def test_summarize_tool_result_payload_from_mcp_content_blocks():
    payload = [
        {"type": "text", "text": json.dumps(_tool_result_payload())},
    ]
    summary = summarize_tool_result_payload(payload)
    assert summary["status"] == "successful"
    assert summary["action"] == "accept"
    assert summary["confidence"] == "medium"


def test_summarize_nested_tool_result_block():
    nested = [
        {
            "type": "tool-result",
            "toolCallId": "call-1",
            "content": [
                {"type": "text", "text": json.dumps(_tool_result_payload())}
            ],
            "isError": False,
        }
    ]
    summary = summarize_tool_result_payload(nested)
    assert summary["status"] == "successful"
    assert summary["action"] == "accept"
    assert summary["confidence"] == "medium"
