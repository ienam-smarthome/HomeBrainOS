from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import sitecustomize  # noqa: E402
from mcp_client import HubitatMCPClient, MCPToolResult  # noqa: E402
from device_intelligence_index import _device_rows  # noqa: E402


@pytest.mark.asyncio
async def test_structured_content_wins_over_human_readable_text(monkeypatch):
    async def fake_original(self, name, arguments=None):
        devices = {
            "devices": [
                {
                    "id": "7399",
                    "label": "Front Door",
                    "room": "Hallway",
                    "currentStates": {"contact": "closed"},
                }
            ]
        }
        return MCPToolResult(
            name=name,
            arguments=arguments or {},
            raw={"content": [{"type": "text", "text": "1 device found"}], "structuredContent": devices},
            text="1 device found",
            data="1 device found",
            is_error=False,
        )

    monkeypatch.setattr(sitecustomize, "_ORIGINAL_CALL_TOOL", fake_original)
    client = HubitatMCPClient.__new__(HubitatMCPClient)
    result = await sitecustomize._call_tool_with_structured_data(client, "hub_list_devices", {})

    assert result.text == "1 device found"
    assert result.data["devices"][0]["id"] == "7399"
    assert _device_rows(result.data)[0]["label"] == "Front Door"


@pytest.mark.asyncio
async def test_text_decoded_data_is_retained_without_structured_content(monkeypatch):
    async def fake_original(self, name, arguments=None):
        return MCPToolResult(
            name=name,
            arguments=arguments or {},
            raw={"content": [{"type": "text", "text": '{"ok":true}'}]},
            text='{"ok":true}',
            data={"ok": True},
            is_error=False,
        )

    monkeypatch.setattr(sitecustomize, "_ORIGINAL_CALL_TOOL", fake_original)
    client = HubitatMCPClient.__new__(HubitatMCPClient)
    result = await sitecustomize._call_tool_with_structured_data(client, "hub_get_info", {})

    assert result.data == {"ok": True}
