from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_workflow_backup_filename_safe import (  # noqa: E402
    FilenameSafeBackupWashingRuleMachineWorkflow,
    _hubitat_backup_filename_date,
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


class OldestFirstBackupClient:
    configured = True
    server_info: dict[str, Any] = {}

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool(
                "hub_manage_backup",
                "Backup management gateway",
                {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                    },
                },
            )
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        assert name == "hub_manage_backup"
        assert args.get("tool") == "hub_list_backups"
        assert args.get("args", {}).get("scope") == "hub_local"
        assert args.get("args", {}).get("limit") == 100

        today = datetime.now().astimezone().date()
        rows = []
        for offset in range(20, 5, -1):
            old_date = today - timedelta(days=offset)
            rows.append(
                {
                    "fileName": f"{old_date.isoformat()}~2.5.1.131.lzf",
                    "location": "local",
                }
            )
        rows.append(
            {
                "fileName": (
                    f"Hub_C8_Pro_{today.isoformat()}~2.5.1.131~manual.lzf"
                ),
                "location": "local",
            }
        )
        return result(name, {"backups": rows})


class HubInfoFallbackClient(OldestFirstBackupClient):
    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_get_info":
            return result(
                name,
                {
                    "hub": {
                        "backups": {
                            "lastBackupEpoch": int(time.time() * 1000) - 5 * 60 * 1000
                        }
                    }
                },
            )

        assert name == "hub_manage_backup"
        assert args.get("tool") == "hub_list_backups"
        old_date = datetime.now().astimezone().date() - timedelta(days=2)
        return result(
            name,
            {
                "backups": [
                    {
                        "fileName": f"{old_date.isoformat()}~2.5.1.131.lzf",
                        "location": "local",
                    }
                ]
            },
        )


def workflow(client: Any | None = None):
    client = client or OldestFirstBackupClient()
    app = SimpleNamespace(mcp=client, VERSION="test")
    return FilenameSafeBackupWashingRuleMachineWorkflow(app, object()), client


def test_exact_user_backup_filename_date_is_recognised():
    parsed = _hubitat_backup_filename_date(
        "Hub_C8_Pro_2026-07-19~2.5.1.131~manual.lzf"
    )

    assert parsed is not None
    assert parsed.isoformat() == "2026-07-19"


def test_newest_manual_backup_after_first_ten_is_still_verified():
    service, client = workflow()

    ok, details = asyncio.run(service._recent_listed_backup())

    assert ok is True
    assert details["recent"] is True
    assert details["strict_gateway"] is True
    assert details["gateway"] == "hub_manage_backup"
    assert details["request_tool"] == "hub_manage_backup"
    assert details["requested_limit"] == 100
    assert details["candidate_count"] >= 1
    assert details["newest"]["timestamp_source"] == "filename_today"
    assert details["newest"]["name"].startswith("Hub_C8_Pro_")
    assert details["filename_today_matches"] == [details["newest"]["name"]]
    assert len(client.calls) == 1


def test_recent_last_backup_epoch_is_accepted_when_list_omits_new_file():
    service, client = workflow(HubInfoFallbackClient())

    ok, details = asyncio.run(service._ensure_backup("BP-READY"))

    assert ok is True
    assert details["recent"] is True
    assert details["created"] is False
    assert details["verified_by"] == "hub_get_info_lastBackupEpoch"
    assert details["hub_info_backup_check"]["epoch_found"] is True
    assert details["hub_info_backup_check"]["age_ms"] < 10 * 60 * 1000
    assert [name for name, _ in client.calls] == [
        "hub_manage_backup",
        "hub_get_info",
    ]


def test_release_keeps_guarded_rule_repair_and_safe_webui_installers():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "install_repair_id_safe_rule_machine_workflow" in entrypoint
    assert "install_clipboard_safe_webui" in entrypoint
    assert "install_http_safe_webui" in entrypoint
