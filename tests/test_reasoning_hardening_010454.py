from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import DeviceHistoryService  # noqa: E402
from device_query_service import DeviceQueryService  # noqa: E402
from mcp_client import HubitatMCPClient, MCPToolResult  # noqa: E402
from reasoning_policy import (  # noqa: E402
    CURRENT_TURN_EVIDENCE_RULE,
    DEFAULT_MAX_READ_TOOL_CALLS,
    DEFAULT_MAX_READ_TOOL_ROUNDS,
    FINAL_SYNTHESIS_INSTRUCTION,
    claim_model_tool_call,
    observe_assistant_message,
    prepare_reasoning_turn,
    reasoning_budget_exhausted,
    reasoning_budget_status,
    register_model_tool_execution,
    reset_reasoning_budget,
)


def _call(name: str, arguments: dict | None = None) -> dict:
    return {"function": {"name": name, "arguments": arguments or {}}}


def _claim_one_read(round_index: int) -> None:
    arguments = {"round": round_index}
    observe_assistant_message(
        {"role": "assistant", "content": "", "tool_calls": [_call("reader", arguments)]}
    )
    assert claim_model_tool_call("reader", arguments) == 1
    assert register_model_tool_execution(mutates=False) is True


def test_current_turn_evidence_boundary_replaces_legacy_causal_hunt() -> None:
    reset_reasoning_budget()
    _claim_one_read(1)
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "Why did the light turn on?"},
        {"role": "assistant", "content": "", "tool_calls": [_call("reader", {"round": 1})]},
        {"role": "tool", "tool_name": "reader", "content": '{"result":"on"}'},
        {
            "role": "user",
            "content": "HOST CAUSAL-INVESTIGATION HINT\nSearch every related sensor.",
        },
    ]

    prepared, tools = prepare_reasoning_turn(
        messages,
        [{"type": "function", "function": {"name": "reader"}}],
    )

    assert tools
    rendered = "\n".join(str(item.get("content") or "") for item in prepared)
    assert "HOST CAUSAL-INVESTIGATION HINT" not in rendered
    assert CURRENT_TURN_EVIDENCE_RULE in rendered
    assert "Conversation history is context only" in rendered


def test_read_reasoning_budget_forces_synthesis_after_three_tool_rounds() -> None:
    reset_reasoning_budget()
    for index in range(1, DEFAULT_MAX_READ_TOOL_ROUNDS + 1):
        _claim_one_read(index)

    assert reasoning_budget_exhausted() is True
    status = reasoning_budget_status()
    assert status["toolRounds"] == DEFAULT_MAX_READ_TOOL_ROUNDS
    assert status["readCalls"] == DEFAULT_MAX_READ_TOOL_ROUNDS

    prepared, tools = prepare_reasoning_turn(
        [{"role": "tool", "tool_name": "reader", "content": '{"result":1}'}],
        [{"type": "function", "function": {"name": "reader"}}],
    )
    assert tools == []
    rendered = "\n".join(str(item.get("content") or "") for item in prepared)
    assert FINAL_SYNTHESIS_INSTRUCTION in rendered
    assert "budget is now exhausted" in rendered


def test_read_call_budget_skips_only_additional_reads_not_mutations() -> None:
    reset_reasoning_budget()
    # Stay below the round cap while consuming the call cap from one native round.
    calls = [_call("reader", {"index": index}) for index in range(DEFAULT_MAX_READ_TOOL_CALLS + 1)]
    observe_assistant_message({"role": "assistant", "content": "", "tool_calls": calls})
    for index in range(DEFAULT_MAX_READ_TOOL_CALLS):
        arguments = {"index": index}
        assert claim_model_tool_call("reader", arguments) == len(calls)
        assert register_model_tool_execution(mutates=False) is True
    final_read = {"index": DEFAULT_MAX_READ_TOOL_CALLS}
    assert claim_model_tool_call("reader", final_read) == len(calls)
    assert register_model_tool_execution(mutates=False) is False

    # The budget never blocks a model-emitted mutating action once it reaches the executor.
    observe_assistant_message(
        {"role": "assistant", "content": "", "tool_calls": [_call("writer", {"on": True})]}
    )
    assert claim_model_tool_call("writer", {"on": True}) == 1
    assert register_model_tool_execution(mutates=True) is True
    assert reasoning_budget_exhausted() is False


class HistoryResolutionMCP:
    def __init__(self, *, broad_candidates: list[dict] | None = None):
        self.broad_candidates = list(broad_candidates or [])
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        assert name == "hub_read_devices"
        assert arguments.get("tool") == "hub_list_devices"
        label_filter = str((arguments.get("args") or {}).get("labelFilter") or "")
        devices = self.broad_candidates if label_filter.casefold() == "fan" else []
        data = {"devices": devices}
        return MCPToolResult(name, arguments, {}, json.dumps(data), data)


def _fan(device_id: str, label: str) -> dict:
    return {
        "id": device_id,
        "label": label,
        "name": label,
        "room": "Bathroom",
        "capabilities": ["Switch"],
        "attributes": {"switch": "off"},
        "commands": ["on", "off"],
    }


@pytest.mark.asyncio
async def test_history_resolution_uses_one_bounded_broader_lookup_for_exact_miss() -> None:
    mcp = HistoryResolutionMCP(
        broad_candidates=[_fan("1", "Fan Switch"), _fan("2", "Fan Boost")]
    )
    evidence = []
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: evidence.append((args, kwargs)))

    result = await service.history({"name": "bathroom fan", "hours_back": 24})

    assert result.is_error is True
    assert result.data["error"] == "device is ambiguous"
    assert result.data["fallbackLookup"] == "fan"
    assert set(result.data["alternatives"]) == {"Fan Switch", "Fan Boost"}
    filters = [
        (arguments.get("args") or {}).get("labelFilter")
        for name, arguments in mcp.calls
        if name == "hub_read_devices"
    ]
    assert filters == ["bathroom fan", "fan"]
    assert not any(
        (arguments.get("tool") == "hub_list_device_events")
        for _name, arguments in mcp.calls
    )


@pytest.mark.asyncio
async def test_history_resolution_reports_missing_not_ambiguous_when_no_candidate_exists() -> None:
    mcp = HistoryResolutionMCP(broad_candidates=[])
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({"name": "bathroom fan", "hours_back": 24})

    assert result.is_error is True
    assert result.data["error"] == "device not found"
    assert result.data["alternatives"] == []


class ContextPowerMCP(HubitatMCPClient):
    def __init__(self):
        super().__init__("http://hubitat.invalid/mcp")
        self.remote_calls: list[tuple[str, dict]] = []

    async def get_live_context(self):
        return {
            "devices": [
                {
                    "id": "1",
                    "label": "Freezer (MQTT)",
                    "room": "Appliances",
                    "attributes": {"power": 75},
                },
                {
                    "id": "2",
                    "label": "Computer",
                    "room": "Bedroom 3",
                    "attributes": {"power": 47},
                },
            ],
            "totalDevices": 2,
            "idsComplete": True,
            "truncated": False,
            "partial": False,
        }

    async def call_tool(self, name: str, arguments: dict):
        self.remote_calls.append((name, arguments))
        raise AssertionError("numeric power query should not request full hub_list_devices")

    async def get_cached_devices(self):
        return []


@pytest.mark.asyncio
async def test_numeric_power_query_uses_bulk_live_context_instead_of_full_inventory() -> None:
    mcp = ContextPowerMCP()
    receipts = []
    service = DeviceQueryService(mcp, lambda *args, **kwargs: receipts.append((args, kwargs)))
    try:
        result = await service.query_devices(
            {"attribute": "power", "operation": "top", "limit": 2}
        )
    finally:
        await mcp.close()

    assert result.is_error is False
    assert [row["label"] for row in result.data["results"]] == [
        "Freezer (MQTT)",
        "Computer",
    ]
    assert result.data["results"][0]["value"] == 75
    assert mcp.remote_calls == []
    assert receipts
    source_arguments = receipts[0][0][1]
    assert source_arguments["resource"] == "hubitat://context"
    assert source_arguments["required_attributes"] == ["power"]
