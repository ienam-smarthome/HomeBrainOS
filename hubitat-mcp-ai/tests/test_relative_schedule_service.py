from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPToolResult
from rule_authoring_service import RULE_MACHINE_GATEWAY, RuleAuthoringService


TARGET = "Block Media-Google-TV-Streamer"
ADB_TARGET = "Google TV Streamer (ADB)"


def result(name: str, arguments: dict[str, Any], data: Any) -> MCPToolResult:
    return MCPToolResult(
        name=name,
        arguments=arguments,
        raw={},
        text="",
        data=data,
        is_error=False,
    )


class FakeMCP:
    async def get_device_identities(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "7000",
                "label": ADB_TARGET,
                "name": ADB_TARGET,
                "room": "Living Room",
                "capabilities": ["Switch"],
            },
            {
                "id": "6923",
                "label": TARGET,
                "name": TARGET,
                "room": "Internet",
                "capabilities": ["Switch"],
            },
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        if name == "hub_read_devices":
            label_filter = str((arguments.get("args") or {}).get("labelFilter") or "")
            if label_filter != TARGET:
                raise AssertionError(
                    f"Internet schedule must re-read the scoped control surface, got {label_filter!r}"
                )
            return result(
                name,
                arguments,
                {
                    "success": True,
                    "devices": [
                        {
                            "id": "6923",
                            "label": TARGET,
                            "name": TARGET,
                            "room": "Internet",
                            "capabilities": ["Switch"],
                            "commands": ["on", "off"],
                        }
                    ],
                },
            )
        if name == "hub_read_rules":
            return result(name, arguments, {"success": True, "rules": []})
        raise AssertionError(f"Unexpected tool: {name} {arguments}")


@pytest.mark.asyncio
async def test_relative_block_schedule_uses_internet_group_and_real_switch_off() -> None:
    evidence: list[tuple[Any, ...]] = []
    service = RuleAuthoringService(
        FakeMCP(),
        lambda *args, **kwargs: evidence.append((args, kwargs)),
        now=lambda: datetime(2026, 10, 2, 22, 25, 12),
    )

    decision = await service.propose(
        "block Google TV after 1 minute",
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert decision.handled is True
    assert decision.message is None
    assert decision.target is not None
    assert decision.target["id"] == "6923"
    assert decision.rule_names == (
        "Block Media Google TV Streamer (One-time 2026-10-02 22:26)",
    )
    assert len(decision.actions) == 2

    create = decision.actions[0]
    payload = create["args"]
    assert payload["addTrigger"] == {
        "capability": "Certain Time (and optional date)",
        "time": "A specific time",
        "atTime": "2026-10-02T22:26:12",
    }
    assert payload["addAction"] == {
        "capability": "runCommand",
        "deviceIds": ["6923"],
        "capabilityFilter": "Switch",
        "command": "off",
    }
    assert payload["addAction"].get("minutes") is None

    pause = decision.actions[1]["args"]["addAction"]
    assert pause["capability"] == "pauseRule"

    inventory_receipts = [
        item for item in evidence
        if item[0] and item[0][0] == "homebrain_device_inventory"
    ]
    assert inventory_receipts
    assert inventory_receipts[0][0][1] == {"group": "Internet"}


@pytest.mark.asyncio
async def test_relative_allow_schedule_uses_real_switch_on() -> None:
    service = RuleAuthoringService(
        FakeMCP(),
        lambda *args, **kwargs: None,
        now=lambda: datetime(2026, 10, 2, 22, 25, 12),
    )

    decision = await service.propose(
        "allow internet for Google TV after 1 minute",
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert decision.handled is True
    assert decision.message is None
    assert decision.target is not None
    assert decision.target["id"] == "6923"
    assert decision.actions[0]["args"]["addAction"] == {
        "capability": "runCommand",
        "deviceIds": ["6923"],
        "capabilityFilter": "Switch",
        "command": "on",
    }
