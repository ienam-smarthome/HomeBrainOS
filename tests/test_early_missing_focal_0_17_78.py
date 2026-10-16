"""The 0.17.77 live question had no word 'deep', yet spent five model rounds.

Historical focal source retrieval is an evidence requirement, independent of
a model-effort label. This test exercises the production agent with a recorded
missing-history command source and a zero-row native historical window.
"""
from __future__ import annotations

from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from homebrain_agent import UnifiedMCPAgent
from mcp_client import MCPTool, MCPToolResult
from mcp_skill_guidance import wants_deep_investigation
from test_skill_missing_focal_0_17_76 import _evicted


REAL_QUESTION = (
    "Why did Livingroom Light 1 turn ON at 19:55 on 14 October 2026? "
    "Retrieve the exact historical ON/OFF events, preceding commands and "
    "command-producer logs. Explain the most likely cause using verified "
    "evidence, and identify any missing historical records. Read-only."
)


class NeverCallAI:
    calls = 0

    async def post(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("model ran before missing historical source was checked")

    async def aclose(self):
        pass


class HistoricalMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [
            MCPTool("hub_read_devices", "Read Hubitat device events", {"type": "object", "properties": {}}),
            MCPTool("hub_read_diagnostics", "Read device and app logs", {"type": "object", "properties": {}}),
        ]

    async def get_device_identities(self):
        return [{
            "id": "7805", "label": "Livingroom Light 1",
            "name": "Livingroom Light 1", "room": "Living Room",
            "capabilities": ["Switch"], "commands": ["on", "off"],
            "attributes": {"switch": "on"},
        }]

    def peek_device_identities(self):
        return []

    def peek_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        op = arguments.get("tool")
        args = arguments.get("args") or {}
        if name == "hub_read_devices" and op == "hub_list_device_events":
            assert args.get("deviceId") == "7805"
            assert args.get("attribute") == "switch"
            assert "since" in args and "until" in args
            data = {"source": "device", "device": "Livingroom Light 1",
                    "deviceId": "7805", "sinceMode": "explicit",
                    "events": [], "count": 0}
            return MCPToolResult(name, arguments, {}, "ok", data)
        if name == "hub_read_diagnostics" and op == "hub_get_logs":
            assert str(args.get("appId")) == "4129"
            assert args["since"].startswith("2026-10-14T18:54:")
            return MCPToolResult(name, arguments, {}, "ok",
                                 {"logs": [], "count": 0})
        raise AssertionError((name, arguments))


@pytest.mark.asyncio
async def test_non_deep_dated_incident_runs_exact_reads_before_any_model(monkeypatch):
    assert not wants_deep_investigation(REAL_QUESTION)
    mcp = HistoricalMCP()
    ai = NeverCallAI()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)
    observed_at_model = []

    async def model_response(messages, schemas):
        observed_at_model.append([(name, args["tool"]) for name, args in mcp.calls])
        return {"content": (
            "SenseCap D1 Settings issued the recorded command, but the exact "
            "historical physical ON and initiator remain unverified. Producer "
            "logs returned 0 record(s)."), "tool_calls": []}

    monkeypatch.setattr(agent.transport, "chat", model_response)

    async def recorded_prefetch(self, *_args, **_kwargs):
        for row in _evicted():
            # The small source fixture historically stores the leaf name in
            # sub_tool; production receipts carry the full gateway operation.
            # Normalize into the real recorder contract before injecting.
            args = row.get("arguments") or {}
            if row.get("sub_tool") and "tool" not in args:
                args = {"tool": row["sub_tool"], "args": args.get("args") or args}
            self.evidence.record(
                row["tool"], args,
                success=True, elapsed_ms=0,
                summary=str(row.get("summary") or "verified"),
                supports_live_claim=True,
                evidence_kind=str(row.get("evidence_kind") or "tool_result"),
                mutates=False, effect="read",
                details=row.get("details"),
            )
        return "partial", "livingroomlight1", "on"

    monkeypatch.setattr(
        UnifiedMCPAgent, "_prefetch_explicit_causal_subject", recorded_prefetch,
    )
    outcome = await agent.process_user_request_result(REAL_QUESTION)
    counters = outcome.metrics["counters"]

    assert observed_at_model
    assert observed_at_model[0] == [
        ("hub_read_devices", "hub_list_device_events"),
        ("hub_read_diagnostics", "hub_get_logs"),
    ]
    assert counters["investigation_read_reflection"] == 1
    assert counters["skills_focal_state_window"] == 1
    assert counters["skills_focal_producer_logs"] == 1
    assert "Historical verification boundary" in outcome.message
    assert "returned 0 record(s)" in outcome.message
    assert "initiated outside Hubitat" not in outcome.message
    assert [
        (name, args["tool"]) for name, args in mcp.calls
    ] == [
        ("hub_read_devices", "hub_list_device_events"),
        ("hub_read_diagnostics", "hub_get_logs"),
    ]
