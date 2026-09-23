from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_subject_prefetch import causal_subject_seed  # noqa: E402
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def _switch_device(device_id: str, label: str, room: str) -> dict:
    return {
        "id": device_id,
        "label": label,
        "name": label,
        "room": room,
        "capabilities": ["Switch"],
        "attributes": {"switch": "off"},
        "commands": ["on", "off"],
    }


IDENTITIES = [
    _switch_device("101", "Bedroom 1 Light", "Bedroom 1"),
    _switch_device("102", "Bedroom2 (MQTT)", "Sockets"),
    _switch_device("103", "Fan Switch (Tuya Local)", "Ventilation"),
]


@pytest.mark.parametrize(
    ("prompt", "expected_name", "expected_transition"),
    [
        ("Why did Bedroom 1 Light turn itself on?", "Bedroom 1 Light", "on"),
        ("Why did Bedroom 1 Light switch itself off?", "Bedroom 1 Light", "off"),
        ("Why did Bedroom2 (MQTT) power itself on?", "Bedroom2 (MQTT)", "on"),
        ("Why did Bedroom2 (MQTT) shut itself off?", "Bedroom2 (MQTT)", "off"),
        ("Why did Fan Switch (Tuya Local) start running?", "Fan Switch (Tuya Local)", "on"),
        ("Why did Fan Switch (Tuya Local) stop running?", "Fan Switch (Tuya Local)", "off"),
        ("Why did Bedroom 1 Light come back on?", "Bedroom 1 Light", "on"),
        ("Why did Bedroom2 (MQTT) go back off?", "Bedroom2 (MQTT)", "off"),
    ],
)
def test_generic_switch_devices_accept_unambiguous_causal_phrases(
    prompt: str,
    expected_name: str,
    expected_transition: str,
) -> None:
    seed = causal_subject_seed(prompt, IDENTITIES)

    assert seed is not None
    assert seed.name == expected_name
    assert seed.attribute == "switch"
    assert seed.transition == expected_transition
    assert seed.target["id"] in {"101", "102", "103"}


@pytest.mark.parametrize(
    "prompt",
    [
        "Why did Fan Switch (Tuya Local) stop responding?",
        "Why did Bedroom 1 Light stop reporting power?",
        "Why did Bedroom2 (MQTT) start updating slowly?",
    ],
)
def test_non_state_start_stop_language_stays_out_of_switch_fastpath(
    prompt: str,
) -> None:
    assert causal_subject_seed(prompt, IDENTITIES) is None


class _GenericSwitchMCP:
    def __init__(
        self,
        device: dict,
        transition: str,
        producer_name: str,
        producer_id: int,
    ) -> None:
        self.device = dict(device)
        self.transition = transition
        self.producer_name = producer_name
        self.producer_id = producer_id
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return [
            MCPTool(
                "hub_read_devices",
                "Read devices. hub_list_device_events.",
                {"type": "object", "properties": {}},
            ),
            MCPTool(
                "hub_read_diagnostics",
                "Read diagnostics. hub_get_logs.",
                {"type": "object", "properties": {}},
            ),
        ]

    async def get_device_identities(self):
        return [dict(self.device)]

    def peek_device_identities(self):
        return [dict(self.device)]

    def peek_cached_devices(self):
        return []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        assert name == "hub_read_devices"
        assert arguments.get("tool") == "hub_list_device_events"

        args = arguments.get("args") or {}
        assert args.get("deviceId") == self.device["id"]
        attribute = args.get("attribute")

        if attribute == "switch":
            events = [
                {
                    "name": "switch",
                    "value": "off",
                    "date": "2026-09-23T08:27:23.601+0100",
                    "isStateChange": True,
                    "type": "digital",
                },
                {
                    "name": "switch",
                    "value": "on",
                    "date": "2026-09-23T06:57:23.391+0100",
                    "isStateChange": True,
                    "type": "digital",
                },
                {
                    "name": "switch",
                    "value": "off",
                    "date": "2026-09-22T22:38:13.489+0100",
                    "isStateChange": True,
                    "type": "digital",
                },
            ]
        elif attribute == f"command-{self.transition}":
            if self.transition == "on":
                date = "2026-09-23T06:57:23.292+0100"
            else:
                date = "2026-09-23T08:27:23.518+0100"
            events = [{
                "name": f"command-{self.transition}",
                "value": None,
                "date": date,
                "description": f"Command called: {self.transition}()",
                "isStateChange": False,
                "type": "command",
                "producedBy": {
                    "name": self.producer_name,
                    "appId": self.producer_id,
                },
            }]
        else:
            raise AssertionError(("unexpected history read", attribute))

        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"events": events, "count": len(events)},
        )


class _NoProvider:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, _url: str, **kwargs):
        self.requests.append(dict(kwargs))
        raise AssertionError("generic switch provenance must not call the provider")

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("device", "prompt", "transition", "producer"),
    [
        (
            _switch_device("101", "Bedroom 1 Light", "Bedroom 1"),
            "Why did Bedroom 1 Light turn itself on?",
            "on",
            "Bedroom 1 button: pushed",
        ),
        (
            _switch_device("102", "Bedroom2 (MQTT)", "Sockets"),
            "Why did Bedroom2 (MQTT) shut itself off?",
            "off",
            "Power Saving Session",
        ),
        (
            _switch_device("103", "Fan Switch (Tuya Local)", "Ventilation"),
            "Why did Fan Switch (Tuya Local) start running?",
            "on",
            "Ventilation Fan Controller",
        ),
    ],
)
async def test_generic_switch_categories_use_same_zero_model_provenance_path(
    device: dict,
    prompt: str,
    transition: str,
    producer: str,
) -> None:
    mcp = _GenericSwitchMCP(device, transition, producer, 9001)
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result(prompt)

    counters = outcome.metrics["counters"]
    assert ai.requests == []
    assert counters.get("model_rounds", 0) == 0
    assert counters["causal_subject_prefetch"] == 1
    assert counters["causal_command_producer_reads"] == 1
    assert counters["causal_command_producer_provenance"] == 1
    assert counters["causal_deterministic_finalization"] == 1
    assert counters["tool_calls"] == 3
    assert counters.get("causal_native_log_reads", 0) == 0

    assert device["label"] in outcome.message
    assert producer in outcome.message
    assert f"{transition.upper()} command" in outcome.message

    attributes = [
        arguments.get("args", {}).get("attribute")
        for name, arguments in mcp.calls
        if name == "hub_read_devices"
        and arguments.get("tool") == "hub_list_device_events"
    ]
    assert set(attributes) == {"switch", f"command-{transition}"}
    assert len(attributes) == 2
    assert not any(
        name == "hub_read_diagnostics"
        for name, _arguments in mcp.calls
    )
