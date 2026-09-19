from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from health_audit_service import (  # noqa: E402
    HealthAuditService,
    _device_findings,
    _gateway_arguments,
    _log_findings,
)
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


class _AutomationStatus:
    def __init__(self) -> None:
        self.items = [
            {
                "id": "3992",
                "name": "Auto OFF",
                "display_name": "Auto OFF",
                "type": "app",
                "status": "active",
            },
            {
                "id": "4010",
                "name": "Paused Rule",
                "display_name": "Paused Rule",
                "type": "rule",
                "status": "paused",
            },
            {
                "id": "4020",
                "name": "Disabled Rule",
                "display_name": "Disabled Rule",
                "type": "rule",
                "status": "disabled",
            },
        ]

    async def snapshot(self, *, advisory: bool = False):
        assert advisory is False
        counts = {
            "active": sum(item["status"] == "active" for item in self.items),
            "disabled": sum(item["status"] == "disabled" for item in self.items),
            "paused": sum(item["status"] == "paused" for item in self.items),
            "broken": sum(item["status"] == "broken" for item in self.items),
            "unknown": sum(item["status"] == "unknown" for item in self.items),
        }
        return SimpleNamespace(
            automation_items=list(self.items),
            automation_counts=counts,
        )


class _MCP:
    def __init__(self) -> None:
        self.devices = [
            {
                "id": "hub",
                "label": "Hub Info (C8 Pro)",
                "attributes": {
                    "hubModel": "C-8 Pro",
                    "firmwareVersionString": "2.5.1.140",
                    "hubUpdateStatus": "Current",
                    "freeMemory": 780,
                    "formattedUptime": "3d:04h",
                },
            },
            {
                "id": "door",
                "label": "Fridge Door",
                "attributes": {"battery": 14},
            },
            {
                "id": "vac",
                "label": "Roborock Q7 Max",
                "attributes": {"healthStatus": "offline"},
            },
        ]
        self.log_rows = [
            {
                "level": "WARN",
                "message": "MCP Rule Server device feed omitted 1 device",
            },
            {
                "level": "WARN",
                "message": "MCP Rule Server device feed omitted 1 device",
            },
            {
                "level": "ERROR",
                "message": "Example diagnostic failure",
            },
        ]
        self.calls = []

    async def health(self):
        return {"online": True, "tools": 4}

    async def list_tools(self, refresh=False):
        assert refresh is True
        return [
            MCPTool(
                "hub_read_diagnostics",
                "Read diagnostics",
                {
                    "type": "object",
                    "properties": {
                        "args": {
                            "type": "object",
                            "properties": {
                                "tool": {"type": "string"},
                                "args": {"type": "object"},
                            },
                        }
                    },
                },
            ),
            MCPTool("hub_read_apps_code", "apps", {"type": "object"}),
            MCPTool("hub_read_rules", "rules", {"type": "object"}),
            MCPTool("hub_read_devices", "devices", {"type": "object"}),
        ]

    async def get_cached_devices(self, refresh=False):
        assert refresh is True
        return list(self.devices)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        assert name == "hub_read_diagnostics"
        assert arguments["args"]["tool"] == "hub_get_logs"
        assert arguments["args"]["args"]["since"] == "24h"
        return MCPToolResult(
            name,
            arguments,
            {},
            "",
            {"logs": list(self.log_rows)},
        )


@pytest.mark.asyncio
async def test_health_audit_is_deterministic_persistent_and_problem_first(tmp_path) -> None:
    mcp = _MCP()
    automations = _AutomationStatus()
    service = HealthAuditService(
        mcp,
        automations,
        snapshot_path=tmp_path / "health.json",
        low_battery_threshold=20,
        log_hours=24,
    )

    first = await service.run(reason="manual")

    assert first["status"] == "attention"
    assert first["attention_count"] == 5
    assert first["sections"]["devices"]["low_battery_count"] == 1
    assert first["sections"]["devices"]["offline_count"] == 1
    assert first["sections"]["automations"]["disabled_count"] == 1
    assert first["sections"]["automations"]["attention_count"] == 1
    assert first["sections"]["logs"]["error_group_count"] == 1
    assert first["sections"]["logs"]["warning_group_count"] == 1
    assert first["sections"]["logs"]["warning_groups"][0]["count"] == 2
    assert first["health_hierarchy"]["hub"]["status"] == "healthy"
    assert first["health_hierarchy"]["devices"]["attention_count"] == 2
    assert first["health_hierarchy"]["automations"]["attention_count"] == 1
    assert first["health_hierarchy"]["logs"]["attention_count"] == 2
    assert "Hub healthy" in first["message"]
    assert all(
        "Disabled Rule" not in item["title"]
        for item in first["issues"]
        if item["severity"] in {"critical", "warning"}
    )
    assert service.latest()["checked_at"] == first["checked_at"]
    stored = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))
    assert stored["latest"]["message"].startswith("System check: Attention")

    mcp.devices = [
        mcp.devices[0],
        {"id": "door", "label": "Fridge Door", "attributes": {"battery": 88}},
        {"id": "vac", "label": "Roborock Q7 Max", "attributes": {"healthStatus": "online"}},
    ]
    mcp.log_rows = []
    automations.items = [automations.items[0], automations.items[2]]

    second = await service.run(reason="scheduled")

    assert second["status"] == "healthy"
    assert second["attention_count"] == 0
    assert second["resolved_count"] == 5
    assert second["reason"] == "scheduled"
    assert service.previous()["checked_at"] == first["checked_at"]


def test_gateway_arguments_follow_nested_diagnostics_schema() -> None:
    nested = MCPTool(
        "hub_read_diagnostics",
        "",
        {
            "type": "object",
            "properties": {"args": {"type": "object"}},
        },
    )
    direct = MCPTool(
        "hub_read_diagnostics",
        "",
        {
            "type": "object",
            "properties": {"tool": {"type": "string"}, "args": {"type": "object"}},
        },
    )

    assert _gateway_arguments(nested, "hub_get_logs", {"limit": 10}) == {
        "args": {"tool": "hub_get_logs", "args": {"limit": 10}}
    }
    assert _gateway_arguments(direct, "hub_get_logs", {"limit": 10}) == {
        "tool": "hub_get_logs",
        "args": {"limit": 10},
    }


def test_log_findings_group_recurring_warnings() -> None:
    section, issues = _log_findings(
        [
            {"level": "WARN", "message": "Query Status failed at 09:59:28"},
            {"level": "WARN", "message": "Query Status failed at 10:01:02"},
            {"level": "INFO", "message": "normal event"},
        ]
    )

    assert section["warning_group_count"] == 1
    assert section["warning_groups"][0]["count"] == 2
    assert len(issues) == 1
    assert issues[0]["count"] == 2


def test_stale_analysis_is_conservative_and_clusters_mqtt_telemetry() -> None:
    now = datetime(2026, 9, 19, 9, 0, tzinfo=timezone.utc)
    devices = [
        *[
            {
                "id": f"mqtt-{index}",
                "label": f"Bedroom {index} (MQTT)",
                "deviceType": "Tasmota MQTT power meter",
                "capabilities": ["PowerMeter", "EnergyMeter", "Switch"],
                "attributes": {"power": 0, "switch": "on"},
                "lastActivity": f"2026-09-17T08:0{index}:00+00:00",
            }
            for index in range(1, 4)
        ],
        {
            "id": "button",
            "label": "Aqara Mini Switch",
            "capabilities": ["PushableButton"],
            "attributes": {"pushed": 1},
            "lastActivity": "2026-09-10T08:00:00+00:00",
        },
        {
            "id": "battery-meter",
            "label": "Bedroom Battery Meter",
            "capabilities": ["TemperatureMeasurement", "Battery"],
            "attributes": {"temperature": 21.5, "battery": 82},
            "lastActivity": "2026-09-10T08:00:00+00:00",
        },
        {
            "id": "motion",
            "label": "Hallway Motion",
            "capabilities": ["MotionSensor"],
            "attributes": {"motion": "active"},
            "lastActivity": "2026-09-19T04:00:00+00:00",
        },
        {
            "id": "presence",
            "label": "Bedroom 1 FP300",
            "capabilities": ["PresenceSensor"],
            "attributes": {"presence": "present"},
            "lastActivity": "2026-09-10T08:00:00+00:00",
        },
        {
            "id": "never",
            "label": "New temperature sensor",
            "capabilities": ["TemperatureMeasurement"],
            "attributes": {},
            "lastActivity": None,
        },
    ]

    section, issues = _device_findings(
        devices,
        low_battery_threshold=20,
        stale_hours=24,
        cluster_minutes=15,
        motion_active_hours=2,
        now=now,
    )

    assert section["suspicious_stale_count"] == 3
    assert section["stale_cluster_count"] == 1
    assert section["stale_clusters"][0]["subsystem"] == "MQTT"
    assert section["stale_clusters"][0]["count"] == 3
    assert section["motion_active_too_long"][0]["label"] == "Hallway Motion"
    assert section["occupied_long"][0]["label"] == "Bedroom 1 FP300"
    assert section["never_reported"][0]["label"] == "New temperature sensor"
    assert any(row["label"] == "Aqara Mini Switch" for row in section["passive_quiet"])
    assert any(row["label"] == "Bedroom Battery Meter" for row in section["passive_quiet"])
    assert any(item["category"] == "device-stale-cluster" for item in issues)
    assert not any(item["category"] == "device-stale" for item in issues)
    assert any(item["category"] == "device-motion-active" for item in issues)
    assert not any(item["category"] == "device-never-reported" for item in issues)
    assert not any("FP300" in item["title"] and item["severity"] == "warning" for item in issues)


def test_log_fingerprint_removes_volatile_ids_and_groups_vrb_warning() -> None:
    section, issues = _log_findings(
        [
            {
                "level": "WARN",
                "timestamp": "2026-09-19T08:00:00Z",
                "message": (
                    "MCP Rule Server - Visual Rule Builder feed missing 1/358 devices "
                    "requestId=ffbd1db2-54e0-4a4f-9df8-b389bb392f65"
                ),
            },
            {
                "level": "WARN",
                "timestamp": "2026-09-19T08:05:00Z",
                "message": (
                    "MCP Rule Server - Visual Rule Builder feed missing 1/358 devices "
                    "requestId=8ccbe3d8-35a3-48d0-b052-d5dd027e41a1"
                ),
            },
        ]
    )

    assert section["warning_group_count"] == 1
    group = section["warning_groups"][0]
    assert group["count"] == 2
    assert group["source"] == "MCP Rule Server"
    assert group["summary"] == "VRB feed missing 1/358 devices."
    assert group["first_seen"] == "2026-09-19T08:00:00+00:00"
    assert group["last_seen"] == "2026-09-19T08:05:00+00:00"
    assert issues[0]["title"] == "MCP Rule Server"
    assert issues[0]["count"] == 2
