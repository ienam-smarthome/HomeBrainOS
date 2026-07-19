from __future__ import annotations

import asyncio
import sys
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


def workflow():
    client = OldestFirstBackupClient()
    app = SimpleNamespace(mcp=client, VERSION="0.4.27-alpha")
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


def test_release_metadata_is_0427():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "version: '0.4.27-alpha'" in config
    assert 'RELEASE_VERSION = "0.4.27-alpha"' in entrypoint
    assert "install_filename_safe_backup_rule_machine_workflow" in entrypoint
