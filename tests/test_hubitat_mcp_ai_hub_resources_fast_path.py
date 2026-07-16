from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_device_health import FastFallbackRouter  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from routing import is_fast_path_query  # noqa: E402


class FakeMCP:
    async def call_tool(self, name, arguments):
        assert name == "hub_get_info"
        assert arguments == {}
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={
                "name": "Hub C8 Pro",
                "firmwareVersion": "2.5.1.128",
                "freeMemoryKB": "941568",
                "internalTempCelsius": "48",
                "databaseSizeKB": "149",
                "uptimeFormatted": "16h 30m",
            },
            is_error=False,
        )


def test_show_hub_cpu_and_free_memory_is_fast_path():
    assert is_fast_path_query("Show hub CPU and free memory") is True
    assert is_fast_path_query("Show hub resources") is True
    assert is_fast_path_query("How much free memory does the hub have?") is True


def test_hub_resources_returns_focused_mcp_answer():
    answer = asyncio.run(
        FastFallbackRouter(FakeMCP()).answer("Show hub CPU and free memory")
    )

    assert answer["success"] is True
    assert answer["intent"] == "fallback-hub-resources"
    assert answer["display"]["kind"] == "hub-resources"
    metrics = {
        item["label"]: item["value"]
        for item in answer["display"]["metrics"]
    }
    assert metrics["Free memory"] == "919.5 MB"
    assert metrics["Temperature"] == "48°C"
    assert metrics["Database"] == "0.1 MB"
    assert metrics["CPU load"] == "Not exposed"
    assert "does not expose CPU load" in answer["message"]
    assert "free memory is 919.5 MB" in answer["message"]
