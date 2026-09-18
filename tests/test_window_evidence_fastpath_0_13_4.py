from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from evidence_ledger import build_current_turn_evidence_ledger  # noqa: E402
from evidence_source_guard import guard_positive_source_attribution  # noqa: E402
from history_result_enrichment import enrich_history_result  # noqa: E402
from history_temporal_analysis import (  # noqa: E402
    history_temporal_evidence_details,
    window_event_evidence,
)
from investigation_policy import uses_known_history_evidence_path  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from synthesis_validator import validate_synthesis  # noqa: E402


WINDOW = {
    "kind": "last_night",
    "label": "last night",
    "start": "2026-09-17T18:00:00+01:00",
    "end": "2026-09-18T08:00:00+01:00",
    "ongoing": False,
}


def _rows() -> list[dict[str, Any]]:
    return [
        {
            "name": "switch",
            "value": "on",
            "description": "later daytime row",
            "date": "2026-09-18T23:55:02.214+01:00",
            "isStateChange": True,
        },
        {
            "name": "command-off",
            "value": None,
            "description": "Command called: off()",
            "date": "2026-09-18T01:45:01.779+01:00",
            "isStateChange": False,
        },
        {
            "name": "command-setLevel",
            "value": None,
            "description": "Command called: setLevel(15)",
            "date": "2026-09-18T01:32:51.812+01:00",
            "isStateChange": False,
        },
        {
            "name": "level",
            "value": "15",
            "description": "Bedroom 3 Light level is 15",
            "date": "2026-09-18T01:32:52.100+01:00",
            "isStateChange": True,
        },
        {
            "name": "command-off",
            "value": None,
            "description": "Command called: off()",
            "date": "2026-09-18T01:30:07.775+01:00",
            "isStateChange": False,
        },
        {
            "name": "command-setLevel",
            "value": None,
            "description": "Command called: setLevel(60)",
            "date": "2026-09-18T00:02:53.900+01:00",
            "isStateChange": False,
        },
        {
            "name": "switch",
            "value": "off",
            "description": "old outside-window row",
            "date": "2026-09-17T12:00:00+01:00",
            "isStateChange": True,
        },
    ]


def _empty_temporal() -> dict[str, Any]:
    return {
        "activeState": "on",
        "inactiveState": "off",
        "intervalCount": 0,
        "totalActiveDuration": "0s",
        "totalActiveSeconds": 0,
        "coverage": "partial",
        "durationReliability": "unverified-event-stream",
        "sourceIntegrityVerified": False,
        "intervals": [],
    }


def test_window_event_evidence_filters_before_latest_event_truncation() -> None:
    rows = window_event_evidence(_rows(), WINDOW)

    assert [row["name"] for row in rows] == [
        "command-setLevel",
        "command-off",
        "command-setLevel",
        "level",
        "command-off",
    ]
    assert all("2026-09-18T23:55" not in str(row["date"]) for row in rows)
    assert all("2026-09-17T12:00" not in str(row["date"]) for row in rows)


def test_history_enrichment_retains_window_commands_with_zero_intervals() -> None:
    result = MCPToolResult(
        "homebrain_device_history",
        {"name": "Bedroom 3 Light"},
        {},
        "",
        {
            "success": True,
            "label": "Bedroom 3 Light",
            "attribute": "switch",
            "timeWindow": WINDOW,
            "temporalAnalysis": _empty_temporal(),
            "events": _rows(),
            "sourceEventCount": len(_rows()),
            "analysisEventCount": 1,
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
        },
    )

    enriched = enrich_history_result("homebrain_device_history", result)
    names = [row["name"] for row in enriched.data["windowEvents"]]

    assert "command-setLevel" in names
    assert "command-off" in names
    assert "later daytime row" not in [
        row.get("description") for row in enriched.data["windowEvents"]
    ]


def test_evidence_receipt_and_ledger_expose_zero_interval_window_rows() -> None:
    data = {
        "label": "Bedroom 3 Light",
        "attribute": "switch",
        "timeWindow": WINDOW,
        "temporalAnalysis": _empty_temporal(),
        "events": _rows(),
        "windowEvents": window_event_evidence(_rows(), WINDOW),
        "sourceEventCount": 39,
        "analysisEventCount": 11,
        "historySourceIntegrity": "unverified",
        "historySourceIntegrityVerified": False,
    }

    details = history_temporal_evidence_details(data)
    assert details is not None
    assert "windowEvents" in details
    assert any(
        row.get("description") == "Command called: off()"
        for row in details["windowEvents"]
    )

    receipt = {
        "tool": "homebrain_device_history",
        "success": True,
        "evidence_kind": "deterministic_device_event_history",
        "summary": "temporal history: intervals=0",
        "details": details,
    }
    brief = build_current_turn_evidence_ledger([receipt])

    assert brief is not None
    assert "0 intervals" in brief
    assert "windowEvents=[" in brief
    assert "command-setLevel" in brief
    assert "command-off" in brief


def test_positive_log_attribution_is_corrected_when_only_device_history_was_read() -> None:
    evidence = [{
        "tool": "homebrain_device_history",
        "success": True,
        "evidence_kind": "deterministic_device_event_history",
        "details": {
            "label": "Bedroom 3 Light",
            "attribute": "switch",
            "temporalAnalysis": _empty_temporal(),
        },
    }]
    draft = "The logs show several setLevel and off commands during the night."

    corrected, changed = guard_positive_source_attribution(draft, evidence)

    assert changed is True
    assert "recorded device-event rows show" in corrected
    assert "logs show" not in corrected.casefold()

    validated, issues = validate_synthesis(draft, evidence, causal=True)
    assert "positive_source_attribution" in issues
    assert "recorded device-event rows show" in validated


def test_positive_log_attribution_is_preserved_when_native_logs_were_checked() -> None:
    evidence = [
        {
            "tool": "homebrain_device_history",
            "success": True,
            "details": {"temporalAnalysis": _empty_temporal()},
        },
        {
            "tool": "hub_read_diagnostics",
            "sub_tool": "hub_get_logs",
            "success": True,
            "summary": "native logs checked",
        },
    ]

    draft = "The logs show an off command."
    corrected, changed = guard_positive_source_attribution(draft, evidence)

    assert changed is False
    assert corrected == draft


def test_known_history_path_skips_only_implicit_provenance_discovery() -> None:
    assert uses_known_history_evidence_path(
        "Why was Bedroom 3 Light on during the night?"
    ) is True
    assert uses_known_history_evidence_path(
        "Why was Bedroom 3 Light on? Check the logs."
    ) is False
    assert uses_known_history_evidence_path(
        "Which automation caused Bedroom 3 Light to turn on?"
    ) is False
    assert uses_known_history_evidence_path("Turn on Bedroom 3 Light") is False


class _PromptMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self):
        return [
            MCPTool("hub_search_tools", "search tools", {"type": "object"}),
            MCPTool("hub_read_apps_code", "read apps", {"type": "object"}),
        ]

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_read_apps_code":
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {"apps": [{"id": "1", "label": "Lighting Auto OFF"}]},
            )
        raise AssertionError((name, arguments))


@pytest.mark.asyncio
async def test_generic_causal_history_system_prompt_does_not_preload_app_manifest() -> None:
    mcp = _PromptMCP()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=object(),
        require_sensitive_confirmation=False,
    )

    await agent._system_prompt(
        "Why was Bedroom 3 Light on during the night?",
        conversation_history=[],
    )

    assert mcp.calls == []


class _HistoryMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self):
        return [
            MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
            MCPTool("hub_read_devices", "Read devices", {"type": "object"}),
        ]

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            return MCPToolResult(name, arguments, {}, "", {"results": []})
        if name == "hub_read_devices":
            operation = arguments.get("tool")
            if operation == "hub_list_devices":
                return MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {
                        "devices": [{
                            "id": "7841",
                            "name": "Bedroom 3 Light",
                            "label": "Bedroom 3 Light",
                            "room": "Bedroom 3",
                            "capabilities": ["Switch"],
                            "attributes": {"switch": "off"},
                            "commands": ["on", "off"],
                        }]
                    },
                )
            if operation == "hub_list_device_events":
                return MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {
                        "events": [{
                            "name": "switch",
                            "value": "off",
                            "description": "Bedroom 3 Light switch is off",
                            "date": "2026-09-18T01:45:02+01:00",
                            "isStateChange": True,
                        }]
                    },
                )
        raise AssertionError((name, arguments))


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _FakeAI:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return _FakeResponse(next(self.responses))

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_generic_causal_history_does_not_run_initial_fuzzy_discovery() -> None:
    mcp = _HistoryMCP()
    ai = _FakeAI([
        {
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "function": {
                        "name": "homebrain_device_history",
                        "arguments": {
                            "name": "Bedroom 3 Light",
                            "attribute": "switch",
                        },
                    }
                }],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": (
                    "No bounded on interval was established from the current "
                    "recorded rows."
                ),
            }
        },
    ])
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result(
        "Why did Bedroom 3 Light turn on?"
    )

    assert "No bounded on interval" in outcome.message
    assert all(name != "hub_search_tools" for name, _args in mcp.calls)
    assert all(name != "hub_read_apps_code" for name, _args in mcp.calls)
