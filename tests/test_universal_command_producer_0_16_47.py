from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_subject_prefetch import (  # noqa: E402
    causal_subject_history_arguments,
    causal_subject_seed,
)
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def _microwave() -> dict:
    return {
        "id": "7124",
        "label": "Microwave (MQTT)",
        "name": "Microwave (MQTT)",
        "room": "Appliances",
        "capabilities": ["Switch", "PowerMeter"],
        "attributes": {"switch": "on", "power": 22},
        "commands": ["on", "off"],
    }


def _door() -> dict:
    return {
        "id": "7400",
        "label": "Microwave Door",
        "name": "Microwave Door",
        "room": "Appliances",
        "capabilities": ["ContactSensor"],
        "attributes": {"contact": "closed"},
        "commands": [],
    }


def _meter() -> dict:
    return {
        "id": "7401",
        "label": "Microwave Meter",
        "name": "Microwave Meter",
        "room": "Appliances",
        "capabilities": ["PowerMeter"],
        "attributes": {"power": 22},
        "commands": [],
    }


def test_parenthetical_transport_suffix_is_safe_causal_subject_alias() -> None:
    seed = causal_subject_seed(
        "Why did Microwave turn on?",
        [_microwave(), _door(), _meter()],
    )

    assert seed is not None
    assert seed.name == "Microwave (MQTT)"
    assert seed.transition == "on"
    assert seed.confidence == 1.0
    assert seed.target["id"] == "7124"


def test_model_resolved_subject_history_is_enriched_with_command_provenance() -> None:
    normalized = causal_subject_history_arguments(
        "Why did Microwave turn on?",
        {
            "name": "Microwave (MQTT)",
            "limit": 3,
        },
    )

    assert normalized == {
        "name": "Microwave (MQTT)",
        "attribute": "switch",
        "limit": 3,
        "_include_command_provenance": True,
        "_causal_transition": "on",
        "_causal_correlation_history": True,
    }

    unrelated = causal_subject_history_arguments(
        "Why did Microwave turn on?",
        {
            "name": "Microwave Door",
            "attribute": "contact",
            "limit": 3,
        },
    )
    assert unrelated == {
        "name": "Microwave Door",
        "attribute": "contact",
        "limit": 3,
    }


class _NoProvider:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, _url: str, **kwargs):
        self.requests.append(dict(kwargs))
        raise AssertionError("provider must not be called for command-producer proof")

    async def aclose(self) -> None:
        return None


class _MicrowaveMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return [
            MCPTool(
                "hub_read_devices",
                "Read devices. hub_list_device_events.",
                {"type": "object", "properties": {}},
            )
        ]

    async def get_device_identities(self):
        return [_microwave(), _door(), _meter()]

    def peek_device_identities(self):
        return [_microwave(), _door(), _meter()]

    def peek_cached_devices(self):
        return []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        assert name == "hub_read_devices"
        assert arguments.get("tool") == "hub_list_device_events"
        args = arguments.get("args") or {}
        assert args.get("deviceId") == "7124"

        attribute = args.get("attribute")
        if attribute == "switch":
            events = [
                {
                    "name": "switch",
                    "value": "on",
                    "descriptionText": "Switch is on",
                    "date": "2026-09-25T21:12:06.469+0100",
                    "isStateChange": True,
                    "type": "digital",
                },
                {
                    "name": "switch",
                    "value": "off",
                    "descriptionText": "Switch is off",
                    "date": "2026-09-25T20:17:38.671+0100",
                    "isStateChange": True,
                    "type": "digital",
                },
                {
                    "name": "switch",
                    "value": "on",
                    "descriptionText": "Switch is on",
                    "date": "2026-09-25T20:15:09.500+0100",
                    "isStateChange": True,
                    "type": "digital",
                },
            ]
        elif attribute == "command-on":
            events = [
                {
                    "name": "command-on",
                    "value": None,
                    "descriptionText": "Command called: on()",
                    "date": "2026-09-25T21:12:06.394+0100",
                    "isStateChange": False,
                    "type": "command",
                    "producedBy": {
                        "label": "Appliance: Microwave ON/OFF",
                        "id": "3090",
                        "type": "app",
                    },
                }
            ]
        else:
            raise AssertionError(("unexpected attribute", attribute))

        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"events": events, "count": len(events)},
        )


@pytest.mark.asyncio
async def test_microwave_command_producer_finalizes_before_logs_or_model() -> None:
    mcp = _MicrowaveMCP()
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result(
        "Why did Microwave turn on?"
    )

    counters = outcome.metrics["counters"]
    assert ai.requests == []
    assert counters.get("model_rounds", 0) == 0
    assert counters["causal_subject_prefetch"] == 1
    assert counters["causal_command_producer_reads"] == 1
    assert counters["causal_command_producer_provenance"] == 1
    assert counters["causal_deterministic_finalization"] == 1
    assert counters["investigative_finalization"] == 1
    assert counters.get("causal_native_log_reads", 0) == 0
    assert counters.get("causal_room_plan", 0) == 0
    assert counters.get("causal_location_read", 0) == 0

    assert outcome.message.startswith("**Cause:**")
    assert "Appliance: Microwave ON/OFF issued the ON command" in outcome.message
    assert "Microwave (MQTT)" in outcome.message
    assert "75 ms later" in outcome.message
    assert "current ON interval is still open" in outcome.message

    event_attributes = [
        arguments["args"].get("attribute")
        for name, arguments in mcp.calls
        if name == "hub_read_devices"
        and arguments.get("tool") == "hub_list_device_events"
    ]
    assert event_attributes == ["switch", "command-on"]

    history_receipts = [
        receipt
        for receipt in outcome.evidence
        if receipt.get("tool") == "homebrain_device_history"
    ]
    assert len(history_receipts) == 1
    assert history_receipts[0]["arguments"] == {
        "name": "Microwave (MQTT)",
        "attribute": "switch",
        "limit": 3,
    }
