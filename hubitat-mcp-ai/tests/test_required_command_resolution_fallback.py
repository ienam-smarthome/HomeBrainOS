from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_query_service import DeviceQueryService
from mcp_client import MCPToolResult


ADB = {
    "id": "7000",
    "label": "Google TV Streamer (ADB)",
    "name": "Google TV Streamer (ADB)",
    "room": "Living Room",
    "capabilities": ["Switch"],
    "commands": ["on", "off"],
}

BLOCKER = {
    "id": "6923",
    "label": "Block Media-Google-TV-Streamer",
    "name": "Block Media-Google-TV-Streamer",
    "room": "Internet",
    "capabilities": ["Switch"],
    "commands": ["on", "off", "blockInternet", "allowInternet"],
}


class FakeMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        self.calls.append((name, arguments))
        assert name == "hub_read_devices"
        assert arguments["tool"] == "hub_list_devices"
        assert arguments["args"]["labelFilter"] == "Google-TV-Streamer"
        data = {"success": True, "devices": [ADB]}
        return MCPToolResult(name, arguments, {}, json.dumps(data), data)

    def peek_device_identities(self) -> list[dict[str, Any]]:
        return [ADB, BLOCKER]


@pytest.mark.asyncio
async def test_required_command_broadens_past_exact_incapable_label_match() -> None:
    mcp = FakeMCP()
    evidence: list[tuple[Any, ...]] = []
    service = DeviceQueryService(
        mcp,
        lambda *args, **kwargs: evidence.append((args, kwargs)),
    )

    result = await service.resolve_device({
        "name": "Google-TV-Streamer",
        "required_command": "blockInternet",
    })

    assert result.is_error is False
    assert result.data["matched"] is True
    assert result.data["deviceId"] == "6923"
    assert result.data["label"] == "Block Media-Google-TV-Streamer"
    assert result.data["attempts"] == [
        {"source": "label_filter", "count": 1},
        {"source": "authoritative_identity_fuzzy", "count": 1},
    ]
    assert len(mcp.calls) == 1


@pytest.mark.asyncio
async def test_without_required_command_exact_name_behavior_is_unchanged() -> None:
    mcp = FakeMCP()
    service = DeviceQueryService(mcp, lambda *args, **kwargs: None)

    result = await service.resolve_device({"name": "Google-TV-Streamer"})

    assert result.is_error is False
    assert result.data["matched"] is True
    assert result.data["deviceId"] == "7000"
    assert result.data["label"] == "Google TV Streamer (ADB)"
    assert result.data["attempts"] == [{"source": "label_filter", "count": 1}]
