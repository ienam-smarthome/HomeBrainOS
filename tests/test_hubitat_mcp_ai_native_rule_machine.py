from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_workflow_native_rm import (  # noqa: E402
    NativeRuleMachineAutomationWorkflow,
    _native_rule_plan,
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


class Index:
    def __init__(self, notifications: int = 1) -> None:
        self.notifications = notifications

    async def enriched_devices(self, force: bool = False):
        rows = [
            {
                "id": "77",
                "label": "Fridge Door",
                "room": "Appliances",
                "capabilities": ["ContactSensor", "Battery"],
                "currentStates": {"contact": "closed", "battery": 17},
            }
        ]
        for number in range(self.notifications):
            rows.append(
                {
                    "id": str(800 + number),
                    "label": "Enamul Phone" if number == 0 else f"Phone {number + 1}",
                    "room": "Mobile",
                    "capabilities": ["Notification"],
                    "supportedCommands": [{"name": "deviceNotification"}],
                    "currentStates": {},
                }
            )
        return rows


class CurrentMCP:
    configured = True
    server_info: dict[str, Any] = {}

    def __init__(self, *, backup_ok: bool = True) -> None:
        self.backup_ok = backup_ok
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.created = False

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool(
                "hub_set_rule",
                "Create or edit a native Rule Machine rule",
                {
                    "type": "object",
                    "properties": {
                        "appId": {"type": "integer"},
                        "name": {"type": "string"},
                        "addTriggers": {"type": "array"},
                        "addActions": {"type": "array"},
                        "confirm": {"type": "boolean"},
                        "opToken": {"type": "string"},
                        "bestPracticeKey": {"type": "string"},
                    },
                    "required": ["confirm"],
                },
            ),
            MCPTool(
                "hub_set_rule_paused",
                "Pause or resume a native Rule Machine rule",
                {
                    "type": "object",
                    "properties": {
                        "ruleId": {"type": "integer"},
                        "paused": {"type": "boolean"},
                        "bestPracticeKey": {"type": "string"},
                    },
                    "required": ["ruleId", "paused"],
                },
            ),
            MCPTool("hub_list_rules", "List Rule Machine rules", {"type": "object", "properties": {}}),
            MCPTool(
                "hub_get_tool_guide",
                "Read MCP guidance",
                {"type": "object", "properties": {"section": {"type": "string"}}},
            ),
            MCPTool(
                "hub_create_backup",
                "Create a hub database backup",
                {"type": "object", "properties": {"bestPracticeKey": {"type": "string"}}},
            ),
            MCPTool("hub_get_info", "Get hub information", {"type": "object", "properties": {}}),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_list_rules":
            rules = [{"id": 901, "label": "Fridge Door left-open alert"}] if self.created else []
            return result(name, {"rules": rules})
        if name == "hub_get_tool_guide":
            return result(name, {"section": "best practice", "bestPracticeKey": "BP-READY-1234"})
        if name == "hub_get_info":
            return result(name, {"writeEnabled": True, "lastBackupEpoch": None})
        if name == "hub_create_backup":
            if not self.backup_ok:
                return result(name, {"success": False, "error": "Backup failed"}, error=True, text="Backup failed")
            return result(name, {"success": True, "fileName": "backup.lzf"})
        if name == "hub_set_rule" and "appId" not in args:
            self.created = True
            return result(name, {"success": True, "appId": 901, "ruleId": 901, "name": args.get("name")})
        if name == "hub_set_rule" and args.get("appId") == 901:
            return result(
                name,
                {
                    "success": True,
                    "partial": False,
                    "partialTriggers": [],
                    "partialActions": [],
                    "health": {"ok": True},
                },
            )
        if name == "hub_set_rule_paused":
            return result(name, {"success": True, "ruleId": 901, "paused": args.get("paused")})
        raise AssertionError(f"Unexpected call {name}: {args}")


RECOMMENDATION = {
    "type": "cold-storage-door",
    "title": "Fridge Door left-open alert",
    "room": "Appliances",
    "devices": ["Fridge Door"],
    "trigger": "Trigger when Fridge Door remains open for 2 minutes.",
    "action": "Send a phone notification and repeat once after 5 minutes if it remains open.",
    "safeguard": "Cancel the pending repeat when Fridge Door closes.",
    "reason": "Prevent food warming and wasted energy.",
}


def service(*, notifications: int = 1, backup_ok: bool = True):
    client = CurrentMCP(backup_ok=backup_ok)
    app = SimpleNamespace(mcp=client, VERSION="0.4.19-alpha")
    workflow = NativeRuleMachineAutomationWorkflow(app, Index(notifications))
    return workflow, client


async def build(workflow: NativeRuleMachineAutomationWorkflow):
    pending = await workflow.store.remember("phone", RECOMMENDATION)
    answer = await workflow.handle(SimpleNamespace(session_id="phone"), "build")
    return pending, answer


def test_native_plan_matches_current_rm_schema():
    draft = {
        "type": "cold-storage-door",
        "devices": [
            {"id": "77", "label": "Fridge Door", "attributes": {"contact": "closed"}},
            {"id": "800", "label": "Enamul Phone", "attributes": {}},
        ],
        "notification_candidates": [{"id": "800", "label": "Enamul Phone"}],
        "unresolved": [],
    }
    plan, error = _native_rule_plan(draft)

    assert error is None
    assert plan["triggers"] == [
        {
            "capability": "Contact",
            "deviceIds": [77],
            "state": "open",
            "andStays": {"seconds": 120},
        },
        {"capability": "Contact", "deviceIds": [77], "state": "closed"},
    ]
    assert plan["actions"][0]["capability"] == "ifThen"
    assert plan["actions"][1] == {"capability": "cancelDelay"}
    assert {"capability": "delay", "seconds": 300, "cancelable": True} in plan["actions"]
    notifications = [item for item in plan["actions"] if item.get("capability") == "notification"]
    assert len(notifications) == 2
    assert all(item["deviceIds"] == [800] for item in notifications)


def test_native_create_orders_backup_shell_pause_populate_and_pause_recheck():
    workflow, client = service()

    async def run():
        pending, built = await build(workflow)
        created = await workflow.handle(SimpleNamespace(session_id="phone"), "create")
        return pending, built, created

    pending, built, created = asyncio.run(run())

    assert built["write_ready"] is True
    assert pending.create_tool.name == "hub_set_rule"
    assert created["success"] is True
    assert created["created_rule"]["status"] == "Paused"
    names = [name for name, _ in client.calls]
    backup_index = names.index("hub_create_backup")
    shell_index = next(
        index
        for index, (name, args) in enumerate(client.calls)
        if name == "hub_set_rule" and "appId" not in args
    )
    pause_indices = [
        index for index, (name, _) in enumerate(client.calls) if name == "hub_set_rule_paused"
    ]
    populate_index = next(
        index
        for index, (name, args) in enumerate(client.calls)
        if name == "hub_set_rule" and args.get("appId") == 901
    )
    assert backup_index < shell_index < pause_indices[0] < populate_index < pause_indices[-1]

    shell_args = client.calls[shell_index][1]
    assert "addTriggers" not in shell_args
    assert "addActions" not in shell_args
    assert shell_args["confirm"] is True
    assert shell_args["bestPracticeKey"] == "BP-READY-1234"

    populate_args = client.calls[populate_index][1]
    assert populate_args["appId"] == 901
    assert populate_args["confirm"] is True
    assert populate_args["bestPracticeKey"] == "BP-READY-1234"
    assert len(populate_args["addTriggers"]) == 2
    assert len(populate_args["addActions"]) == 9

    actions = created["display"]["actions"]
    assert actions == [
        {"label": "Enable rule", "query": "Enable this rule", "tone": "danger", "icon": "▶️"}
    ]
    assert "dry-run" in created["display"]["note"].lower()


def test_enable_and_pause_use_native_pause_tool_only():
    workflow, client = service()

    async def run():
        await build(workflow)
        await workflow.handle(SimpleNamespace(session_id="phone"), "create")
        enabled = await workflow.handle(SimpleNamespace(session_id="phone"), "enable")
        paused = await workflow.handle(SimpleNamespace(session_id="phone"), "pause")
        return enabled, paused

    enabled, paused = asyncio.run(run())
    pause_calls = [args for name, args in client.calls if name == "hub_set_rule_paused"]

    assert enabled["intent"] == "automation-rule-enabled"
    assert paused["intent"] == "automation-rule-paused"
    assert pause_calls[-2]["paused"] is False
    assert pause_calls[-1]["paused"] is True
    assert all(name != "hub_call_rule" for name, _ in client.calls)


def test_missing_notification_device_blocks_before_any_write():
    workflow, client = service(notifications=0)

    async def run():
        _, built = await build(workflow)
        return built

    built = asyncio.run(run())

    assert built["write_ready"] is False
    assert "Notification-capable" in built["message"]
    assert not [name for name, _ in client.calls if name in {"hub_create_backup", "hub_set_rule"}]


def test_backup_failure_blocks_before_rule_shell():
    workflow, client = service(backup_ok=False)

    async def run():
        await build(workflow)
        return await workflow.handle(SimpleNamespace(session_id="phone"), "create")

    answer = asyncio.run(run())

    assert answer["success"] is False
    assert answer["intent"] == "automation-rule-backup-required"
    assert not [
        args
        for name, args in client.calls
        if name == "hub_set_rule" and "appId" not in args
    ]


def test_native_run_is_not_misrepresented_as_dry_run():
    workflow, _ = service()

    async def run():
        await build(workflow)
        await workflow.handle(SimpleNamespace(session_id="phone"), "create")
        return await workflow.handle(SimpleNamespace(session_id="phone"), "test")

    answer = asyncio.run(run())
    assert answer["success"] is False
    assert "does not expose a genuine" in answer["message"]


def test_release_metadata_is_0419():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "version: '0.4.19-alpha'" in config
    assert 'RELEASE_VERSION = "0.4.19-alpha"' in entrypoint
    assert "install_native_rule_machine_workflow" in entrypoint
