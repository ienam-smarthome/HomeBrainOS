from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import webui  # noqa: E402
from dashboard_api import DashboardSnapshot  # noqa: E402
from dashboard_health_tile import install_dashboard_health_tile  # noqa: E402


class FakeIndex:
    def __init__(self) -> None:
        self.calls = 0

    async def dashboard_metrics(self, *, force: bool = False) -> dict[str, Any]:
        self.calls += 1
        return {
            "success": True,
            "lights_on": 4,
            "switches_on": 15,
            "motion_active": 2,
            "low_batteries": 1,
            "selected_devices": 106,
            "updated_at": 123.0,
            "index_age_seconds": 0.1,
        }


class FakeHealthFallback:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []

    async def answer(self, query: str) -> dict[str, Any]:
        self.calls.append(query)
        if self.fail:
            raise RuntimeError("live health scan failed")
        return {
            "success": True,
            "offline_count": 3,
            "stale_telemetry_count": 1,
            "quiet_timestamp_count": 7,
            "display": {
                "metrics": [
                    {"label": "Offline", "value": "3"},
                    {"label": "Stale telemetry", "value": "1"},
                    {"label": "Quiet timestamps", "value": "7"},
                ]
            },
        }


def test_dashboard_replaces_visible_switch_count_with_authoritative_health_total():
    index = FakeIndex()
    fallback = FakeHealthFallback()
    snapshot = DashboardSnapshot(fallback, ttl_seconds=30, device_index=index)

    first = asyncio.run(snapshot.get())
    second = asyncio.run(snapshot.get())

    assert first["lights_on"] == 4
    # Retained for backwards-compatible API consumers, but no longer displayed.
    assert first["switches_on"] == 15
    assert first["health_issues"] == 4
    assert first["offline_devices"] == 3
    assert first["stale_telemetry"] == 1
    assert first["quiet_timestamps"] == 7
    assert first["health_success"] is True
    assert first["health_source"] == "authoritative-device-health"
    assert second == first
    assert index.calls == 1
    assert fallback.calls == ["Are any devices offline or stale?"]


def test_dashboard_remains_available_when_health_scan_fails():
    snapshot = DashboardSnapshot(
        FakeHealthFallback(fail=True),
        ttl_seconds=30,
        device_index=FakeIndex(),
    )

    value = asyncio.run(snapshot.get())

    assert value["success"] is True
    assert value["lights_on"] == 4
    assert value["health_success"] is False
    assert value["health_issues"] is None
    assert value["offline_devices"] is None
    assert value["stale_telemetry"] is None
    assert "live health scan failed" in value["health_error"]


def test_rendered_dashboard_has_health_tile_not_switch_tile():
    old_summary = webui.NEW_SUMMARY
    old_status = webui.NEW_STATUS_FUNCTION
    try:
        install_dashboard_health_tile(webui)
        page = webui.render_page("Hubitat MCP AI", "0.5.9")
    finally:
        webui.NEW_SUMMARY = old_summary
        webui.NEW_STATUS_FUNCTION = old_status

    assert 'id="dashHealth"' in page
    assert 'id="dashHealthDetail"' in page
    assert 'id="healthSummary"' in page
    assert 'data-q="Are any devices offline or stale?"' in page
    assert ">Offline / stale<" in page
    assert ">Switches on<" not in page
    assert 'id="dashSwitches"' not in page
    assert "dash.health_issues" in page
    assert "dash.offline_devices" in page
    assert "dash.stale_telemetry" in page
    assert "classList.toggle('warning',Number(dash.health_issues)>0)" in page


def test_release_wires_health_tile_before_dashboard_requests():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")

    assert "from dashboard_health_tile import install_dashboard_health_tile" in entrypoint
    assert entrypoint.index("install_dashboard_health_tile()") < entrypoint.index(
        "dashboard_snapshot = install_dashboard_api("
    )
    assert 'RELEASE_VERSION = "0.5.9"' in entrypoint
    assert 'version: "0.5.9"' in config
