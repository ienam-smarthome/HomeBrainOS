from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_subject_prefetch import causal_subject_seed  # noqa: E402
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402


def device(
    device_id: str,
    label: str,
    *,
    room: str = "",
) -> dict:
    return {
        "id": device_id,
        "label": label,
        "name": label,
        "room": room,
        "capabilities": ["Switch", "PowerMeter"],
        "attributes": {"switch": "off", "power": 0},
        "commands": ["on", "off"],
    }


def test_exact_named_switch_causal_subject_is_prefetched() -> None:
    seed = causal_subject_seed(
        "Why did Dehumidifier 2 turn on?",
        [
            device("4222", "Dehumidifier 2"),
            device("5313", "Dehumidifier 1"),
        ],
    )

    assert seed is not None
    assert seed.name == "Dehumidifier 2"
    assert seed.attribute == "switch"
    assert seed.confidence == 1.0


def test_minor_device_typo_is_prefetched_when_unique() -> None:
    seed = causal_subject_seed(
        "Why did dehumidifer 2 turn on?",
        [
            device("4222", "Dehumidifier 2"),
            device("5313", "Dehumidifier 1"),
        ],
    )

    assert seed is not None
    assert seed.name == "Dehumidifier 2"
    assert seed.attribute == "switch"
    assert seed.confidence >= 0.90
    assert seed.matched_text == "dehumidifer 2"


def test_numbered_device_mismatch_does_not_prefetch_wrong_target() -> None:
    seed = causal_subject_seed(
        "Why did Dehumidifier 3 turn on?",
        [
            device("4222", "Dehumidifier 2"),
            device("5313", "Dehumidifier 1"),
        ],
    )

    assert seed is None


def test_generic_or_non_transition_causal_question_stays_model_routed() -> None:
    identities = [device("4222", "Dehumidifier 2")]

    assert causal_subject_seed(
        "Why is Dehumidifier 2 using so much power?",
        identities,
    ) is None
    assert causal_subject_seed(
        "Why is the room humid?",
        identities,
    ) is None


def test_non_switch_device_does_not_take_switch_prefetch_path() -> None:
    seed = causal_subject_seed(
        "Why did Front Door turn on?",
        [{
            "id": "10",
            "label": "Front Door",
            "capabilities": ["ContactSensor"],
            "attributes": {"contact": "closed"},
        }],
    )

    assert seed is None


def test_prefetch_metric_is_supported_and_presented() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_subject_prefetch")
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert snapshot["counters"]["causal_subject_prefetch"] == 1
    assert {
        "label": "Causal subject prefetches",
        "value": "1",
    } in present_request_metrics(snapshot)



class _Response:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "message": {
                "role": "assistant",
                "content": self._content,
            }
        }


class _OneRoundAI:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, _url: str, **kwargs) -> _Response:
        self.requests.append(dict(kwargs))
        return _Response(
            "At 10:07 pm, the strongest initiating-control candidate was "
            "Ikea Rodret (Livingroom) button 2: its physical press immediately "
            "preceded the Dehumidifier 2 on command. The same button/input again "
            "immediately preceded the 10:38 pm off command. The 01. Humidity "
            "Controller reacted after the on command and managed the manual run, "
            "rather than initiating it. This repeated timestamp correlation is "
            "strong provenance, but it does not independently prove the configured "
            "button-to-device mapping or identify who pressed the button."
        )

    async def aclose(self) -> None:
        return None


class _PrefetchMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.identity = device("4222", "Dehumidifier 2")

    async def list_tools(self):
        return [
            MCPTool(
                "hub_read_devices",
                "Read devices. hub_list_devices and hub_list_device_events.",
                {"type": "object", "properties": {}},
            ),
            MCPTool(
                "hub_read_diagnostics",
                "Read diagnostics. hub_get_logs.",
                {"type": "object", "properties": {}},
            ),
        ]

    async def get_device_identities(self):
        return [dict(self.identity), device("5313", "Dehumidifier 1")]

    def peek_device_identities(self):
        return [dict(self.identity), device("5313", "Dehumidifier 1")]

    def peek_cached_devices(self):
        return []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        args = arguments.get("args") or {}

        if name == "hub_read_devices" and operation == "hub_list_devices":
            assert args["labelFilter"] == "Dehumidifier 2"
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"devices": [dict(self.identity)]},
            )

        if name == "hub_read_devices" and operation == "hub_list_device_events":
            assert args["deviceId"] == "4222"
            assert args["attribute"] == "switch"
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "events": [
                        {
                            "name": "switch",
                            "value": "off",
                            "description": "switch attribute updated",
                            "date": "2026-09-22T22:38:13.489+0100",
                            "isStateChange": True,
                        },
                        {
                            "name": "switch",
                            "value": "on",
                            "description": "switch attribute updated",
                            "date": "2026-09-22T22:07:37.107+0100",
                            "isStateChange": True,
                        },
                    ],
                    "count": 2,
                },
            )

        if name == "hub_read_diagnostics" and operation == "hub_get_logs":
            since = str(args.get("since") or "")
            if since.startswith("2026-09-22T21:07:27"):
                rows = [
                    {
                        "date": "2026-09-22 22:07:37.195",
                        "level": "INFO",
                        "message": (
                            "app|3995|01. Humidity Controller|01. Humidity Controller: "
                            "Unit 2 manual: will turn OFF after 90 min"
                        ),
                    },
                    {
                        "date": "2026-09-22 22:07:37.159",
                        "level": "INFO",
                        "message": (
                            "app|3995|01. Humidity Controller|01. Humidity Controller: "
                            "DEV LOCK set [unit2]: manual for 5430s (manual run)"
                        ),
                    },
                    {
                        "date": "2026-09-22 22:07:37.002",
                        "level": "INFO",
                        "message": (
                            "dev|4222|Dehumidifier 2|Dehumidifier 2 turn on command"
                        ),
                    },
                    {
                        "date": "2026-09-22 22:07:36.926",
                        "level": "INFO",
                        "message": (
                            "dev|7129|Ikea Rodret (Livingroom)|Ikea Rodret "
                            "(Livingroom) button 2 (Off) was pushed [physical]"
                        ),
                    },
                ]
            elif since.startswith("2026-09-22T21:38:03"):
                rows = [
                    {
                        "date": "2026-09-22 22:38:13.552",
                        "level": "INFO",
                        "message": (
                            "app|3995|01. Humidity Controller|01. Humidity Controller: "
                            "DEV LOCK cleared [unit2] (manual run cancelled by user)"
                        ),
                    },
                    {
                        "date": "2026-09-22 22:38:13.354",
                        "level": "INFO",
                        "message": (
                            "dev|4222|Dehumidifier 2|Dehumidifier 2 turn off command"
                        ),
                    },
                    {
                        "date": "2026-09-22 22:38:13.248",
                        "level": "INFO",
                        "message": (
                            "dev|7129|Ikea Rodret (Livingroom)|Ikea Rodret "
                            "(Livingroom) button 2 (Off) was pushed [physical]"
                        ),
                    },
                ]
            else:
                raise AssertionError(("unexpected log window", arguments))
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"logs": rows, "count": len(rows)},
            )

        raise AssertionError((name, arguments))


@pytest.mark.asyncio
async def test_strong_causal_prefetch_reaches_final_reasoning_in_one_model_round():
    mcp = _PrefetchMCP()
    ai = _OneRoundAI()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result(
        "Why did dehumidifer 2 turn on?"
    )

    assert outcome.version if hasattr(outcome, "version") else True
    assert len(ai.requests) == 1
    assert outcome.metrics["counters"]["model_rounds"] == 1
    assert outcome.metrics["counters"]["causal_subject_prefetch"] == 1
    assert outcome.metrics["counters"]["causal_native_log_reads"] == 2
    assert outcome.metrics["counters"]["causal_native_log_correlations"] == 2
    assert outcome.metrics["counters"]["causal_repeated_controller_pattern"] == 1
    assert outcome.metrics["counters"]["investigative_finalization"] == 1
    assert "causal_room_plan" not in outcome.metrics["counters"]
    assert "causal_location_read" not in outcome.metrics["counters"]
    assert "causal_completion_retry" not in outcome.metrics["counters"]
    assert "Ikea Rodret" in outcome.message

    history_calls = [
        arguments
        for name, arguments in mcp.calls
        if name == "hub_read_devices"
        and arguments.get("tool") == "hub_list_device_events"
    ]
    assert len(history_calls) == 1
    assert history_calls[0]["args"]["attribute"] == "switch"
    assert history_calls[0]["args"]["hoursBack"] == 168

    log_calls = [
        arguments
        for name, arguments in mcp.calls
        if name == "hub_read_diagnostics"
        and arguments.get("tool") == "hub_get_logs"
    ]
    assert len(log_calls) == 2
    assert {
        call["args"]["since"]
        for call in log_calls
    } == {
        "2026-09-22T21:07:27.107000Z",
        "2026-09-22T21:38:03.489000Z",
    }


@pytest.mark.asyncio
async def test_causal_prefetch_rollback_keeps_model_tool_selection_path():
    mcp = _PrefetchMCP()
    ai = _OneRoundAI()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
        causal_subject_prefetch_enabled=False,
        max_tool_rounds=1,
    )

    outcome = await agent.process_user_request_result(
        "Why did dehumidifer 2 turn on?"
    )

    # With prefetch disabled, the first provider response contains no tool call,
    # so the ordinary grounding path cannot invent live evidence.
    assert len(ai.requests) >= 1
    assert outcome.metrics["counters"].get("causal_subject_prefetch", 0) == 0
