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
    assert len(decision.actions) == 1

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

class WarmInternetIdentityMCP:
    def __init__(self) -> None:
        self.refresh_calls = 0
        self.device_reads: list[str] = []

    def peek_device_identities(self) -> list[dict[str, Any]]:
        return [
            {"id": "8101", "label": "Block Camera-G100-42EA", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8102", "label": "Block Camera-G100-7B37", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8103", "label": "Block Enamul-s-Tab-S9-FE", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8104", "label": "Block Google-Nest-Hub", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8105", "label": "Block Media-Google-Nest-Mini", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "6923", "label": "Block Media-Google-TV-Streamer", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8107", "label": "Block PC-NucBox-M6Ultra", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8108", "label": "Block Tab-S9-FE", "room": "Internet", "capabilities": ["Switch"]},
        ]

    async def get_cached_devices(self) -> list[dict[str, Any]]:
        self.refresh_calls += 1
        raise AssertionError("fresh identity cache should avoid manifest refresh")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        if name == "hub_get_info":
            return result(name, arguments, {"timezone": "Europe/London"})
        if name == "hub_read_devices":
            label_filter = str((arguments.get("args") or {}).get("labelFilter") or "")
            self.device_reads.append(label_filter)
            if label_filter != "Block PC-NucBox-M6Ultra":
                raise AssertionError(f"unexpected target lookup: {label_filter!r}")
            return result(
                name,
                arguments,
                {
                    "success": True,
                    "devices": [
                        {
                            "id": "8107",
                            "label": "Block PC-NucBox-M6Ultra",
                            "name": "Block PC-NucBox-M6Ultra",
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
async def test_relative_block_m6_ultra_pc_matches_compact_reordered_internet_label_from_identity_cache() -> None:
    evidence: list[tuple[Any, ...]] = []
    mcp = WarmInternetIdentityMCP()
    service = RuleAuthoringService(
        mcp,
        lambda *args, **kwargs: evidence.append((args, kwargs)),
        now=lambda: datetime(2026, 10, 3, 10, 0, 0),
    )

    decision = await service.propose(
        "block M6 Ultra PC after 1 minute",
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert decision.handled is True
    assert decision.message is None
    assert decision.target is not None
    assert decision.target["id"] == "8107"
    assert mcp.refresh_calls == 0
    assert mcp.device_reads == ["Block PC-NucBox-M6Ultra"]
    assert decision.actions[0]["args"]["addAction"] == {
        "capability": "runCommand",
        "deviceIds": ["8107"],
        "capabilityFilter": "Switch",
        "command": "off",
    }
    inventory_receipts = [
        item for item in evidence
        if item[0] and item[0][0] == "homebrain_device_inventory"
    ]
    assert inventory_receipts
    assert "identity_source=identity cache" in inventory_receipts[0][1]["summary"]
    assert "source=Internet room local-token match" in inventory_receipts[0][1]["summary"]


@pytest.mark.asyncio
async def test_internet_local_token_match_keeps_two_tab_controls_ambiguous() -> None:
    mcp = WarmInternetIdentityMCP()
    service = RuleAuthoringService(
        mcp,
        lambda *args, **kwargs: None,
        now=lambda: datetime(2026, 10, 3, 10, 0, 0),
    )

    decision = await service.propose(
        "block Tab S9 FE after 1 minute",
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert decision.handled is True
    assert decision.actions == ()
    assert decision.message is not None
    assert "Possible matches" in decision.message
    assert "Block Enamul-s-Tab-S9-FE" in decision.message
    assert "Block Tab-S9-FE" in decision.message
    assert mcp.refresh_calls == 0
    assert mcp.device_reads == []

