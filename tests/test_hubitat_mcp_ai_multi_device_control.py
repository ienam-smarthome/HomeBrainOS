from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import MethodType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_multi_control import (  # noqa: E402
    FastFallbackRouter,
    split_explicit_control_targets,
)
from mcp_client import MCPToolResult  # noqa: E402
from routing_policy import classify_query  # noqa: E402


def result(data: Any) -> MCPToolResult:
    return MCPToolResult(
        name="hub_list_devices",
        arguments={},
        raw={},
        text="",
        data=data,
        is_error=False,
    )


def test_explicit_fan_switch_and_boost_routes_to_verified_fast_path():
    decision = classify_query("turn on fan switch and fan boost")

    assert decision.route == "mcp-fast"
    assert "multiple explicit" in decision.reason
    assert split_explicit_control_targets("fan switch and fan boost") == [
        "fan switch",
        "fan boost",
    ]


def test_conditional_multi_control_stays_on_planner_route():
    decision = classify_query(
        "turn on fan switch and fan boost if bathroom humidity is high"
    )

    assert decision.route == "ollama-planner"
    assert split_explicit_control_targets(
        "fan switch and fan boost if bathroom humidity is high"
    ) is None


def test_all_named_targets_are_resolved_before_group_control_runs():
    service = object.__new__(FastFallbackRouter)
    devices = [
        {"id": 101, "label": "Fan Switch", "currentStates": {"switch": "off"}},
        {"id": 102, "label": "Fan Boost", "currentStates": {"switch": "off"}},
    ]
    calls: list[tuple[str, Any]] = []

    async def fake_live(self, capability=None):
        calls.append(("read", capability))
        return result({"devices": devices})

    async def fake_group(self, requested_name, action, selected, initial_result):
        calls.append(
            (
                "group",
                {
                    "requested_name": requested_name,
                    "action": action,
                    "ids": [item["id"] for item in selected],
                },
            )
        )
        return {
            "success": True,
            "intent": "fallback-device-group-control-confirmed",
            "message": "Both devices confirmed on.",
            "display": {"note": "old note"},
        }

    service._live_devices = MethodType(fake_live, service)
    service._device_rows = MethodType(lambda self, value: list(value["devices"]), service)
    service._control_group = MethodType(fake_group, service)

    answer = asyncio.run(
        service._control_device("fan switch and fan boost", "on")
    )

    assert answer["success"] is True
    assert answer["intent"] == "fallback-named-multi-control-confirmed"
    assert answer["resolved_targets"] == [
        {"id": 101, "label": "Fan Switch"},
        {"id": 102, "label": "Fan Boost"},
    ]
    assert calls == [
        ("read", "Switch"),
        (
            "group",
            {
                "requested_name": "Fan Switch and Fan Boost",
                "action": "on",
                "ids": [101, 102],
            },
        ),
    ]
    assert "exact-matched" in answer["display"]["note"]


def test_unresolved_second_target_sends_no_commands():
    service = object.__new__(FastFallbackRouter)
    devices = [
        {"id": 101, "label": "Fan Switch", "currentStates": {"switch": "off"}},
    ]
    group_calls = 0

    async def fake_live(self, capability=None):
        return result({"devices": devices})

    async def forbidden_group(self, requested_name, action, selected, initial_result):
        nonlocal group_calls
        group_calls += 1
        raise AssertionError("No device command should be sent")

    service._live_devices = MethodType(fake_live, service)
    service._device_rows = MethodType(lambda self, value: list(value["devices"]), service)
    service._control_group = MethodType(forbidden_group, service)

    answer = asyncio.run(
        service._control_device("fan switch and missing boost", "on")
    )

    assert answer["success"] is False
    assert answer["intent"] == "fallback-named-multi-control-unresolved"
    assert "No devices were changed" in answer["message"]
    assert group_calls == 0
    assert answer["requested_targets"] == ["fan switch", "missing boost"]


def test_release_uses_multi_control_router():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "version: '0.4.32-alpha'" in config
    assert 'PREVIOUS_RELEASE_VERSION = "0.4.31-alpha"' in entrypoint
    assert 'RELEASE_VERSION = "0.4.32-alpha"' in entrypoint
    assert "from fast_fallback_multi_control import FastFallbackRouter" in entrypoint
