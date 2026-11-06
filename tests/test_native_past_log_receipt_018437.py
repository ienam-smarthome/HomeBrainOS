"""Regression: native historic MCP messages become bounded privacy-safe receipts.

Synthetic fixtures only; not evidence that 5 Nov 2026 logs still exist on a hub.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from evidence_recorder import EvidenceRecorder  # noqa: E402
from evidence_ledger import build_current_turn_evidence_ledger  # noqa: E402
from hub_incident_ai import (  # noqa: E402
    guard_unresolved_causal_publication, read_only_log_receipt_summary,
)
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from native_past_log_receipt import native_past_log_receipt  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from tool_registry import ToolEffect  # noqa: E402


def native_row(kind: str, ident: int, time: str, body: str) -> dict:
    return {
        "name": "Example",
        "level": "info",
        "time": time,
        "type": "app" if kind == "app" else "dev",
        "message": f"{kind}|{ident}|Example|{body}",
    }


def args(mode="past", **kwargs):
    return {"tool": "hub_get_logs", "args": {
        "mode": mode, "since": "2026-11-05T16:00:00Z",
        "until": "2026-11-05T17:00:00Z", **kwargs,
    }}


def past_data():
    return {
        "mode": "past", "total": 130, "matched": 3, "count": 3,
        "entries": [
            native_row("app", 4151, "2026-11-05 16:21:19.123", "PRIVATE password=secret"),
            native_row("dev", 7828, "2026-11-05 16:35:02", "sensitive device message"),
            {"name": "unknown", "type": "app",
             "time": "2026-11-05 16:48:01",
             "message": "no source id; cannot prove app identity"},
        ],
        "nextCursor": "page-2-secret-do-not-expose",
        "truncated": False,
    }


def test_proof_is_typed_and_does_not_publish_raw_message_or_cursor():
    payload = native_past_log_receipt("hub_read_diagnostics", args(), past_data())
    assert payload is not None
    assert list(payload) == ["nativePastLog"]
    info = payload["nativePastLog"]
    assert info["returnedRowsInspected"] == 3
    assert info["timestampedRows"] == 3
    assert info["timestampedMessageRows"] == 3
    assert info["appMessageRowsWithVerifiedSourceId"] == 1
    assert info["deviceMessageRowsWithVerifiedSourceId"] == 1
    assert info["appSourceIds"] == ["4151"]
    assert info["deviceSourceIds"] == ["7828"]
    assert info["timeBasis"] == "hub_local_source_time_not_utc_verified"
    assert info["hasNextCursor"] is True
    assert info["completeHistoricalCoverageVerified"] is False
    assert info["matchedRowsReported"] == 3
    serialized = json.dumps(payload)
    for forbidden in ("password", "secret", "PRIVATE", "sensitive",
                      "page-2", "16:21:19.123"):
        assert forbidden not in serialized


def test_mode_and_source_response_must_both_be_past_and_contain_rows():
    assert native_past_log_receipt("hub_read_diagnostics", args("apps"), past_data()) is None
    assert native_past_log_receipt("hub_read_diagnostics", args(), {"mode": "apps", "entries": []}) is None
    assert native_past_log_receipt("hub_read_devices", {"tool": "hub_list_devices"},
                                  past_data()) is None
    assert native_past_log_receipt("hub_get_logs",
                                  {"mode": "past"}, {"mode": "past"}) is None
    assert native_past_log_receipt("hub_get_logs", {"mode": "past"},
                                  {"mode": "past", "entries": []}) is not None


def test_malformed_clock_wrong_type_and_empty_message_cannot_prove_app_rows():
    data = {"mode": "past", "entries": [
        native_row("app", 123, "2026-11-05 99:99:99", "invalid clock"),
        {"time": "2026-11-05 16:10:00", "type": "dev",
         "message": "app|123|Example|wrong kind"},
        {"time": "2026-11-05 16:11:00", "type": "app",
         "message": "app|123|Example|valid app"},
        {"time": "2026-11-05 16:12:00", "type": "app", "message": ""},
        {"time": "2026-11-05T16:13:00Z", "type": "app",
         "message": "app|123|Example|offset source is not a local date field"},
    ]}
    projection = native_past_log_receipt("hub_get_logs", {"mode": "past"}, data)
    assert projection["nativePastLog"]["appMessageRowsWithVerifiedSourceId"] == 1
    assert projection["nativePastLog"]["timestampedMessageRows"] == 2
    assert projection["nativePastLog"]["requestDateBounded"] is False


def test_capped_native_page_never_certifies_complete_history():
    entries = [native_row("app", 11, "2026-11-05 16:00:00", "private")]
    data = {"mode": "past", "entries": entries * 201}
    info = native_past_log_receipt("hub_get_logs", {"mode": "past"}, data)["nativePastLog"]
    assert info["returnedRowsInspected"] == 200
    assert info["returnedRowsCapped"] is True
    assert info["appMessageRowsWithVerifiedSourceId"] == 200
    assert info["completeHistoricalCoverageVerified"] is False


def test_actual_native_receipt_counts_bounded_app_rows_without_claiming_full_coverage():
    projection = native_past_log_receipt("hub_read_diagnostics", args(), past_data())
    receipt = {
        "sub_tool": "hub_get_logs", "success": True,
        "supports_live_claim": True, "mutates": False,
        "arguments": args(), "details": projection,
    }
    coverage = read_only_log_receipt_summary([receipt])
    assert coverage["verified_bounded_app_message_rows"] == 1
    assert coverage["verified_native_past_pages"] == 1
    assert coverage["returned_timestamped_past_messages"] == 3
    assert coverage["past_pages_with_more"] == 1
    assert coverage["complete_historical_app_log_coverage"] is False
    for altered in (
        {**receipt, "success": False},
        {**receipt, "supports_live_claim": False},
        {**receipt, "mutates": True},
        {**receipt, "arguments": args("apps")},
        {**receipt, "arguments": args(since="", until="")},
    ):
        assert read_only_log_receipt_summary(
            [altered]
        )["verified_bounded_app_message_rows"] == 0


def test_guard_preserves_actual_page_counts_but_no_private_text_or_invented_cause():
    projected = native_past_log_receipt("hub_read_diagnostics", args(), past_data())
    evidence = [{
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": True, "supports_live_claim": True, "mutates": False,
        "arguments": args(), "details": projected,
    }]
    response = {
        "message": "The app caused the reboot; password=private-text",
        "outcome_presentation": {"value": "unresolved"},
        "investigation_coverage": {"hypothesisComparisons": [
            {"candidate": "an app issue", "discriminator_verified": False},
        ]},
        "evidence": evidence,
    }
    verified = guard_unresolved_causal_publication(response)
    assert "3 timestamped messages" in verified["message"]
    assert "1 app messages with source IDs" in verified["message"]
    assert "Pagination or truncation requires further reads" in verified["message"]
    assert "underlying cause" in verified["message"]
    assert "password" not in verified["message"]
    assert "PRIVATE" not in str(verified["causal_read_source_coverage"])


class FakeMCP:
    def __init__(self, data):
        self.data = data

    async def call_tool(self, name, arguments):
        return MCPToolResult(name, arguments, {}, "", self.data)


@pytest.mark.asyncio
async def test_tool_executor_retains_projection_not_messages_in_evidence():
    evidence = EvidenceRecorder()
    executor = ToolExecutor(FakeMCP(past_data()), evidence)
    token = evidence.begin()
    try:
        result = await executor.execute(
            "hub_read_diagnostics", args(),
            tool=MCPTool("hub_read_diagnostics", "Read diagnostics", {},
                         annotations={"effect": ToolEffect.READ.value}),
        )
        receipt = evidence.receipts()[0]
    finally:
        evidence.reset(token)
    assert result.success is True
    assert receipt["success"] is True
    assert receipt["details"]["nativePastLog"]["appMessageRowsWithVerifiedSourceId"] == 1
    assert "secret" not in json.dumps(receipt)
    # Preserve original data for the model under existing privacy controls.
    assert "PRIVATE password=secret" in result.content


def test_final_synthesis_brief_keeps_distinct_past_log_pages_without_message_text():
    data = past_data()
    first_projection = native_past_log_receipt("hub_read_diagnostics", args(), data)
    next_args = args(cursor="page-2-secret-do-not-expose")
    second = {"mode": "past", "entries": [
        native_row("app", 900, "2026-11-05 16:40:01", "PRIVATE ROW TWO")
    ]}
    second_projection = native_past_log_receipt("hub_read_diagnostics", next_args, second)
    logs = [
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
         "success": True, "mutates": False, "arguments": params,
         "details": projection, "summary": "native log read"}
        for params, projection in (
            (args(), first_projection), (next_args, second_projection)
        )
    ]
    history = {
        "tool": "homebrain_device_history", "success": True, "mutates": False,
        "arguments": {"deviceId": "7828"}, "summary": "bounded device history",
        "details": {"label": "Example", "attribute": "switch"},
    }
    brief = build_current_turn_evidence_ledger([history, *logs])
    assert brief is not None
    assert brief.count("CHECKED native past-log page") == 2
    assert "3 timestamped message rows returned" in brief
    assert "1 timestamped message rows returned" in brief
    assert "more pages indicated" in brief
    assert "PRIVATE" not in brief
    assert "page-2-secret" not in brief
