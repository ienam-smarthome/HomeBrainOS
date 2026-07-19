from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_workflow_backup_confirmed import (  # noqa: E402
    ConfirmedBackupWashingRuleMachineWorkflow,
    _acknowledgment_key,
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


class ConfirmedBackupClient:
    configured = True
    server_info: dict[str, Any] = {}

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool(
                "hub_list_backups",
                "List backups",
                {
                    "type": "object",
                    "properties": {
                        "scope": {"type": "string"},
                    },
                },
            ),
            MCPTool(
                "hub_get_tool_guide",
                "Read MCP guide",
                {
                    "type": "object",
                    "properties": {
                        "section": {"type": "string"},
                    },
                },
            ),
            MCPTool(
                "hub_create_backup",
                "Create full hub backup",
                {
                    "type": "object",
                    "properties": {
                        "confirm": {"type": "boolean"},
                        "bestPracticeKey": {"type": "string"},
                    },
                    "required": ["confirm"],
                },
            ),
        ]

    async def gateway_map(self, refresh: bool = False):
        return {}

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_list_backups":
            assert args.get("scope") == "hub_local"
            return result(name, {"backups": [], "count": 0})
        if name == "hub_get_tool_guide":
            section = args.get("section")
            if section == "best_practice_reference":
                return result(name, {"section": section, "text": "Read this guide before writes."})
            if section == "backup":
                return result(
                    name,
                    {
                        "section": section,
                        "text": "**Acknowledgment key:** `BP-CONFIRM-2401`",
                    },
                )
            raise AssertionError(f"Unexpected guide section: {section}")
        if name == "hub_create_backup":
            assert args == {
                "confirm": True,
                "bestPracticeKey": "BP-CONFIRM-2401",
            }
            return result(
                name,
                {
                    "success": True,
                    "fileName": "HomeBrain-2026-07-19.lzf",
                    "status": "complete",
                },
            )
        raise AssertionError(f"Unexpected call {name}: {args}")


def workflow():
    client = ConfirmedBackupClient()
    app = SimpleNamespace(mcp=client, VERSION="0.4.24-alpha")
    return ConfirmedBackupWashingRuleMachineWorkflow(app, object()), client


def test_acknowledgment_parser_accepts_markdown_backup_guide_wording():
    assert (
        _acknowledgment_key("**Acknowledgment key:** `BP-CONFIRM-2401`")
        == "BP-CONFIRM-2401"
    )


def test_backup_preflight_reads_fallback_guide_and_sends_confirm_true():
    service, client = workflow()

    async def run():
        key = await service._read_best_practice_key()
        ok, details = await service._ensure_backup(key)
        return key, ok, details

    key, ok, details = asyncio.run(run())

    assert key == "BP-CONFIRM-2401"
    assert ok is True
    assert details["created"] is True
    assert details["recent"] is True
    assert details["confirm_sent"] is True
    assert details["best_practice_key_found"] is True
    assert (
        "hub_create_backup",
        {"confirm": True, "bestPracticeKey": "BP-CONFIRM-2401"},
    ) in client.calls


def test_release_metadata_is_0424():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "version: '0.4.24-alpha'" in config
    assert 'RELEASE_VERSION = "0.4.24-alpha"' in entrypoint
    assert "install_confirmed_backup_rule_machine_workflow" in entrypoint
