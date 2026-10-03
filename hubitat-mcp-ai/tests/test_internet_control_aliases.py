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


def result(name: str, arguments: dict[str, Any], data: Any) -> MCPToolResult:
    return MCPToolResult(name=name, arguments=arguments, raw={}, text="", data=data, is_error=False)


ADB = {
    "id": "7000",
    "label": "Google TV Streamer (ADB)",
    "roomName": "Living Room",
    "commands": ["on", "off"],
    "capabilities": ["Switch"],
}
CONTROL = {
    "id": "6923",
    "label": "Block Media-Google-TV-Streamer",
    "commands": ["on", "off"],
    "capabilities": ["Switch"],
}


class FakeMCP:
    async def get_cached_devices(self):
        return [dict(ADB), dict(CONTROL)]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        if name == "hub_read_devices":
            label = str(arguments.get("args", {}).get("labelFilter") or "")
            devices = [dict(CONTROL)] if label == CONTROL["label"] else []
            return result(name, arguments, {"success": True, "devices": devices})
        if name == "hub_read_rules":
            return result(name, arguments, {"success": True, "rules": []})
        raise AssertionError((name, arguments))


@pytest.mark.asyncio
async def test_explicit_alias_extends_internet_scope_without_room_membership() -> None:
    service = RuleAuthoringService(
        FakeMCP(),
        lambda *_args, **_kwargs: None,
        now=lambda: datetime(2026, 10, 3, 8, 0, 0),
        internet_control_aliases='{"Google TV":"Block Media-Google-TV-Streamer"}',
    )
    decision = await service.propose(
        "block Google TV after 1 minute",
        available_gateways={RULE_MACHINE_GATEWAY},
    )
    assert decision.handled is True
    assert decision.message is None
    assert decision.target["id"] == "6923"
    assert decision.actions[0]["args"]["addAction"]["deviceIds"] == ["6923"]
    assert decision.actions[0]["args"]["addAction"]["command"] == "off"


@pytest.mark.asyncio
async def test_missing_alias_does_not_guess_from_block_prefix() -> None:
    service = RuleAuthoringService(
        FakeMCP(),
        lambda *_args, **_kwargs: None,
        now=lambda: datetime(2026, 10, 3, 8, 0, 0),
    )
    decision = await service.propose(
        "block Google TV after 1 minute",
        available_gateways={RULE_MACHINE_GATEWAY},
    )
    assert decision.handled is True
    assert decision.actions == ()
    assert "configured Internet aliases" in str(decision.message)
