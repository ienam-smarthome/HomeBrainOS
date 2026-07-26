from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_index import _device_rows  # noqa: E402
from mcp_client import HubitatMCPClient  # noqa: E402


@pytest.mark.asyncio
async def test_structured_content_wins_over_human_readable_text(monkeypatch):
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

    async def fake_post(_payload):
        return {
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": "1 device found"}],
                "structuredContent": devices,
            },
        }

    client = HubitatMCPClient("http://hubitat.local/mcp")
    client._initialized = True
    monkeypatch.setattr(client, "_post", fake_post)
    try:
        result = await client.call_tool("hub_list_devices", {})
    finally:
        await client.close()

    assert result.text == "1 device found"
    assert result.data["devices"][0]["id"] == "7399"
    assert _device_rows(result.data)[0]["label"] == "Front Door"


@pytest.mark.asyncio
async def test_text_decoded_data_is_retained_without_structured_content(monkeypatch):
    async def fake_post(_payload):
        return {
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": '{"ok":true}'}],
            },
        }

    client = HubitatMCPClient("http://hubitat.local/mcp")
    client._initialized = True
    monkeypatch.setattr(client, "_post", fake_post)
    try:
        result = await client.call_tool("hub_get_info", {})
    finally:
        await client.close()

    assert result.data == {"ok": True}
