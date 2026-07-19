from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_workflow_washing_final import (  # noqa: E402
    FinalWashingRuleMachineWorkflow,
)
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def result(name: str, data: Any, *, error: bool = False, text: str = "") -> MCPToolResult:
    return MCPToolResult(
        name=name,
        arguments={},
        raw={"isError": error},
        text=text,
        data=data,
        is_error=error,
    )


class BackupListClient:
    configured = True
    server_info: dict[str, Any] = {}

    def __init__(self, *, age_hours: float) -> None:
        self.age_hours = age_hours
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool(
                "hub_manage_backup",
                "List, restore and delete backups.",
                {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                    },
                },
            )
        ]

    async def gateway_map(self, refresh: bool = False):
        return {"hub_list_backups": "hub_manage_backup"}

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_get_info":
            return result(name, {"lastBackupEpoch": None})
        if name == "hub_manage_backup" and not args:
            return result(
                name,
                {
                    "gateway": name,
                    "mode": "catalog",
                    "tools": [
                        {
                            "name": "hub_list_backups",
                            "description": "List local or cloud hub backups.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "scope": {
                                        "type": "string",
                                        "enum": ["source", "hub_local", "hub_cloud", "hub"],
                                    },
                                    "limit": {"type": "integer"},
                                },
                            },
                        }
                    ],
                },
            )
        if name == "hub_manage_backup" and args.get("tool") == "hub_list_backups":
            created_epoch = int((time.time() - self.age_hours * 3600) * 1000)
            return result(
                name,
                {
                    "scope": "hub_local",
                    "backups": [
                        {
                            "fileName": "Hubitat_Hub_recent.lzf",
                            "location": "local",
                            "createdEpoch": created_epoch,
                        }
                    ],
                    "count": 1,
                },
            )
        raise AssertionError(f"Unexpected call {name}: {args}")


def workflow(age_hours: float):
    client = BackupListClient(age_hours=age_hours)
    app = SimpleNamespace(mcp=client, VERSION="0.4.23-alpha")
    return FinalWashingRuleMachineWorkflow(app, object()), client


def test_recent_local_backup_satisfies_preflight_without_create_tool():
    service, client = workflow(2)

    ok, details = asyncio.run(service._ensure_backup("BP-RECENT-1234"))

    assert ok is True
    assert details["created"] is False
    assert details["recent"] is True
    assert details["verified_by"] == "hub_list_backups"
    list_call = next(
        args
        for name, args in client.calls
        if name == "hub_manage_backup" and args.get("tool") == "hub_list_backups"
    )
    assert list_call["args"]["scope"] == "hub_local"
    assert not [
        args
        for _, args in client.calls
        if args.get("tool") == "hub_create_backup"
    ]


def test_stale_backup_and_missing_core_create_tool_returns_exact_override_guidance():
    service, _ = workflow(30)

    ok, details = asyncio.run(service._ensure_backup("BP-STALE-1234"))

    assert ok is False
    assert "separate core tool" in details["error"]
    assert "Per-tool Overrides" in details["error"]
    assert "Reset all overrides" in details["error"]
    listed = details["listed_backup_check"]
    assert listed["candidate_count"] == 1
    assert listed["newest"]["age_ms"] >= 24 * 60 * 60 * 1000


def test_today_date_only_hubitat_filename_is_accepted_as_recent():
    service, _ = workflow(30)
    today = time.strftime("%Y-%m-%d")
    item = {
        "fileName": f"Hubitat_Hub_{today}~2.5.1.125.lzf",
        "location": "local",
    }

    from automation_rule_workflow_washing_final import _backup_timestamp_ms

    now_ms = int(time.time() * 1000)
    parsed = _backup_timestamp_ms(item, now_ms)

    assert parsed is not None
    assert 0 <= now_ms - parsed < 24 * 60 * 60 * 1000
