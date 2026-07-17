from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import fast_fallback_release as release_module  # noqa: E402
from fast_fallback_release import FastFallbackRouter  # noqa: E402
from hub_metric_formatting import format_database_size  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from routing_policy import classify_query  # noqa: E402
from webui import render_page  # noqa: E402


class FakeHubMCP:
    async def call_tool(self, name, arguments):
        assert name == "hub_get_info"
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={
                "name": "Hub C8 Pro",
                "firmwareVersion": "2.5.1.130",
                "localIP": "192.168.1.239",
                "freeMemoryKB": "999137",
                "internalTempCelsius": "48.7",
                # Current Hubitat firmware returns an MB-sized value through the
                # legacy databaseSizeKB MCP field.
                "databaseSizeKB": "194",
                "uptimeFormatted": "0d 7h 14m",
                "safeMode": False,
                "mcpDeviceCount": 105,
                "mcpRuleCount": 0,
            },
            is_error=False,
        )


def test_find_devices_listed_under_apps_uses_mcp_fast():
    decision = classify_query("Find devices listed under Apps")
    assert decision.route == "mcp-fast"
    assert FastFallbackRouter._room_candidate("Find devices listed under Apps") == "Apps"


def test_database_size_handles_current_and_legacy_hubitat_units():
    assert format_database_size("194") == "194 MB"
    assert format_database_size("198656") == "194 MB"
    assert format_database_size("194 MB") == "194 MB"
    assert format_database_size("198656 KB") == "194.0 MB"


def test_hub_health_includes_cpu_percentage_and_correct_database(monkeypatch):
    async def fake_cpu(_local_ip, *, timeout_seconds):
        return {
            "available": True,
            "mode": "percent",
            "value": "23.75%",
            "percent": 23.75,
        }

    monkeypatch.setattr(release_module, "probe_hub_cpu", fake_cpu)
    answer = asyncio.run(
        FastFallbackRouter(
            FakeHubMCP(),
            cpu_probe_enabled=True,
            cpu_probe_timeout_seconds=3,
        )._hub_info()
    )

    metrics = {
        item["label"]: item["value"]
        for item in answer["display"]["metrics"]
    }
    assert metrics["CPU load"] == "23.75%"
    assert answer["display"]["note"] == "Database: 194 MB"
    assert "Database size is 194 MB." in answer["message"]


def test_lights_and_low_battery_actions_are_not_duplicated():
    page = render_page("Hubitat MCP AI", "0.3.2-alpha")
    # Each action remains available once through its live summary tile, but the
    # duplicate shortcut-row buttons are removed.
    assert page.count('data-q="Which lights are on?"') == 1
    assert page.count('data-q="Which batteries are low?"') == 1
    assert ">💡 Lights</button>" not in page
    assert ">🪫 Low batteries</button>" not in page
