from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_index import _device_rows  # noqa: E402
from mcp_client import HubitatMCPClient  # noqa: E402


def test_tool_result_prefers_structured_content_when_text_is_also_present():
    client = HubitatMCPClient("http://example.invalid/mcp")
    client._initialized = True

    async def fake_post(payload, allow_empty=False):
        return {
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "result": {
                "content": [{"type": "text", "text": "Found 106 devices."}],
                "structuredContent": {
                    "devices": [
                        {
                            "id": "7399",
                            "label": "Front Door",
                            "room": "Hallway",
                            "currentStates": {"contact": "closed"},
                        }
                    ]
                },
            },
        }

    client._post = fake_post
    result = asyncio.run(client.call_tool("hub_list_devices", {}))

    assert result.text == "Found 106 devices."
    assert isinstance(result.data, dict)
    rows = _device_rows(result.data)
    assert rows[0]["id"] == "7399"
    assert rows[0]["label"] == "Front Door"

    asyncio.run(client.close())
