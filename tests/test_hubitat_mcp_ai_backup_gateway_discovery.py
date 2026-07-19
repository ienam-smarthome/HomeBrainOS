from __future__ import annotations

import asyncio
import sys
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


class CatalogueOnlyBackupClient:
    configured = True
    server_info: dict[str, Any] = {}

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self, refresh: bool = False):
        # Legacy compatibility fixture: a compact gateway catalogue contains the
        # create tool even though the visible description does not enumerate it.
        return [
            MCPTool(
                "hub_manage_system",
                "Administrative maintenance gateway.",
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
        return {}

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_get_info":
            return result(name, {"lastBackupEpoch": None})
        if name == "hub_manage_system" and not args:
            return result(
                name,
                {
                    "gateway": name,
                    "mode": "catalog",
                    "tools": [
                        {
                            "name": "hub_create_backup",
                            "description": "Create a hub database backup.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "bestPracticeKey": {"type": "string"}
                                },
                            },
                        }
                    ],
                },
            )
        if name == "hub_manage_system" and args.get("tool") == "hub_create_backup":
            return result(
                name,
                {
                    "success": True,
                    "fileName": "homebrain-test-backup.lzf",
                },
            )
        raise AssertionError(f"Unexpected call {name}: {args}")


def workflow():
    client = CatalogueOnlyBackupClient()
    app = SimpleNamespace(mcp=client, VERSION="0.4.23-alpha")
    return FinalWashingRuleMachineWorkflow(app, object()), client


def test_backup_tool_is_found_by_probing_live_gateway_catalogue():
    service, client = workflow()

    tool = asyncio.run(service._find_tool({"hub_create_backup", "create_backup"}, refresh=True))

    assert tool is not None
    assert tool.name == "hub_create_backup"
    assert tool.gateway == "hub_manage_system"
    assert ("hub_manage_system", {}) in client.calls


def test_backup_preflight_invokes_catalogue_only_tool_through_gateway():
    service, client = workflow()

    ok, details = asyncio.run(service._ensure_backup("BP-BACKUP-1234"))

    assert ok is True
    assert details["created"] is True
    assert details["recent"] is True
    assert details["tool"] == "hub_create_backup"
    assert details["gateway"] == "hub_manage_system"
    invocation = next(
        args
        for name, args in client.calls
        if name == "hub_manage_system" and args.get("tool") == "hub_create_backup"
    )
    assert invocation["args"]["bestPracticeKey"] == "BP-BACKUP-1234"


def test_release_metadata_is_0423():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "version: '0.4.23-alpha'" in config
    assert 'RELEASE_VERSION = "0.4.23-alpha"' in entrypoint
    assert "install_final_washing_rule_machine_workflow" in entrypoint
