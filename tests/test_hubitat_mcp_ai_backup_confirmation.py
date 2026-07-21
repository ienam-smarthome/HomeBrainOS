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

    def __init__(self, *, backup_mode: str = "complete", support_op_token: bool = False) -> None:
        self.backup_mode = backup_mode
        self.support_op_token = support_op_token
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
                        **({"opToken": {"type": "string"}} if self.support_op_token else {}),
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
            assert args == {"scope": "hub_local"}
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
            expected = {
                "confirm": True,
                "bestPracticeKey": "BP-CONFIRM-2401",
            }
            if self.support_op_token:
                assert args.get("opToken", "").startswith("homebrain-backup-")
                expected["opToken"] = args["opToken"]
            assert args == expected
            if self.backup_mode == "timeout":
                raise TimeoutError()
            return result(
                name,
                {
                    "success": True,
                    "fileName": "HomeBrain-2026-07-19.lzf",
                    "status": "complete",
                },
            )
        raise AssertionError(f"Unexpected call {name}: {args}")


class StrictBackupGatewayClient:
    configured = True
    server_info: dict[str, Any] = {}

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self, refresh: bool = False):
        gateway_schema = {
            "type": "object",
            "properties": {
                "tool": {"type": "string"},
                "args": {"type": "object"},
            },
        }
        return [
            MCPTool("hub_manage_backup", "Manage local and cloud backups", gateway_schema),
            MCPTool("hub_read_apps_code", "Read app source code", gateway_schema),
        ]

    async def gateway_map(self, refresh: bool = False):
        # Reproduce the erroneous generic association seen in the live trace.
        return {"hub_list_backups": "hub_read_apps_code"}

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_read_apps_code":
            raise AssertionError("The app-code gateway must never be used for backup listing")
        if name == "hub_manage_backup":
            assert args == {
                "tool": "hub_list_backups",
                "args": {"scope": "hub_local", "limit": 10},
            }
            return result(
                name,
                {
                    "scope": "hub_local",
                    "backups": [
                        {
                            "fileName": "Hubitat_Hub_recent.lzf",
                            "location": "local",
                            "createdEpoch": int(time.time() * 1000) - 5000,
                        }
                    ],
                    "count": 1,
                },
            )
        raise AssertionError(f"Unexpected call {name}: {args}")


def workflow(*, backup_mode: str = "complete"):
    client = ConfirmedBackupClient(backup_mode=backup_mode)
    app = SimpleNamespace(mcp=client, VERSION="0.4.26-alpha")
    return ConfirmedBackupWashingRuleMachineWorkflow(app, object()), client


def test_explicit_backup_forces_new_create_and_uses_schema_idempotency_token():
    client = ConfirmedBackupClient(support_op_token=True)
    app = SimpleNamespace(mcp=client, VERSION="0.10.2")
    service = ConfirmedBackupWashingRuleMachineWorkflow(app, object())

    ok, details = asyncio.run(service._ensure_backup("BP-CONFIRM-2401", force=True))

    assert ok is True
    assert details["created"] is True
    create_calls = [args for name, args in client.calls if name == "hub_create_backup"]
    assert len(create_calls) == 1
    assert create_calls[0]["opToken"].startswith("homebrain-backup-")


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


def test_blank_timeout_is_verified_by_polling_before_rule_writes():
    service, client = workflow(backup_mode="timeout")

    async def verified_poll(delays):
        assert delays == (2.0, 4.0, 6.0)
        return True, [
            {
                "checked": True,
                "recent": True,
                "candidate_count": 1,
                "newest": {"name": "HomeBrain-2026-07-19.lzf", "age_ms": 4000},
            }
        ]

    service._poll_recent_backup = verified_poll
    ok, details = asyncio.run(service._ensure_backup("BP-CONFIRM-2401"))

    assert ok is True
    assert details["created"] is True
    assert details["recent"] is True
    assert details["verified_by"] == "hub_list_backups_after_create"
    assert details["exception_type"] == "TimeoutError"
    assert details["timeout_or_async_response"] is True
    assert len([call for call in client.calls if call[0] == "hub_create_backup"]) == 1


def test_pending_timeout_does_not_launch_duplicate_backup_immediately():
    service, client = workflow(backup_mode="timeout")

    async def not_verified(delays):
        return False, [{"checked": True, "recent": False, "candidate_count": 0}]

    service._poll_recent_backup = not_verified

    first_ok, first = asyncio.run(service._ensure_backup("BP-CONFIRM-2401"))
    second_ok, second = asyncio.run(service._ensure_backup("BP-CONFIRM-2401"))

    assert first_ok is False
    assert first["pending"] is True
    assert first["exception_type"] == "TimeoutError"
    assert "25-second MCP timeout" in first["error"]
    assert second_ok is False
    assert second["pending"] is True
    assert "may still be running" in second["error"]
    assert len([call for call in client.calls if call[0] == "hub_create_backup"]) == 1


def test_backup_listing_rejects_false_app_code_gateway_mapping():
    client = StrictBackupGatewayClient()
    app = SimpleNamespace(mcp=client, VERSION="0.4.26-alpha")
    service = ConfirmedBackupWashingRuleMachineWorkflow(app, object())

    ok, details = asyncio.run(service._recent_listed_backup())

    assert ok is True
    assert details["recent"] is True
    assert details["gateway"] == "hub_manage_backup"
    assert details["request_tool"] == "hub_manage_backup"
    assert details["candidate_count"] == 1
    assert all(name != "hub_read_apps_code" for name, _ in client.calls)


def test_release_metadata_is_0426():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "version: '0.4.26-alpha'" in config
    assert 'RELEASE_VERSION = "0.4.26-alpha"' in entrypoint
    assert "install_confirmed_backup_rule_machine_workflow" in entrypoint
