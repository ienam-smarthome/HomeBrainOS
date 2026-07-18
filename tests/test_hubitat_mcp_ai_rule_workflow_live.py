from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_workflow_live import (  # noqa: E402
    LiveSchemaAutomationRuleWorkflow,
)
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def result(name: str, data: Any, *, error: bool = False, text: str = "") -> MCPToolResult:
    return MCPToolResult(
        name=name,
        arguments={},
        raw=data if isinstance(data, dict) else {"data": data},
        text=text,
        data=data,
        is_error=error,
    )


CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "enabled": {"type": "boolean", "default": True},
        "testRule": {"type": "boolean", "default": False},
        "triggers": {"type": "array"},
        "conditions": {"type": "array"},
        "conditionLogic": {"type": "string"},
        "actions": {"type": "array"},
    },
    "required": ["name", "triggers", "actions"],
}

UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "ruleId": {"type": "string"},
        "enabled": {"type": "boolean"},
    },
    "required": ["ruleId"],
}

TEST_SCHEMA = {
    "type": "object",
    "properties": {"ruleId": {"type": "string"}},
    "required": ["ruleId"],
}


class CurrentMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.rules: list[dict[str, Any]] = []

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool("list_rules", "List rules", {"type": "object", "properties": {}}),
            MCPTool("create_rule", "Create a new automation rule", CREATE_SCHEMA),
            MCPTool("update_rule", "Update or enable/disable a rule", UPDATE_SCHEMA),
            MCPTool(
                "manage_rules_admin",
                "Rule administration gateway. test_rule performs a dry-run.",
                {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                    },
                },
            ),
        ]

    async def gateway_map(self, refresh: bool = False):
        # Current unprefixed tools are not discoverable by the legacy hub_* mapper.
        return {}

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "manage_rules_admin" and not args:
            return result(
                name,
                {
                    "gateway": name,
                    "mode": "catalog",
                    "tools": [
                        {
                            "name": "test_rule",
                            "description": "Test a rule without executing actions (dry run)",
                            "inputSchema": TEST_SCHEMA,
                        }
                    ],
                },
            )
        if name == "manage_rules_admin" and args.get("tool") == "test_rule":
            return result(name, {"success": True, "dryRun": True, "ruleId": args["args"]["ruleId"]})
        if name == "list_rules":
            return result(name, {"rules": list(self.rules)})
        if name == "create_rule":
            created = {
                "id": "9001",
                "name": args["name"],
                "status": "Disabled",
                "enabled": False,
            }
            self.rules.append(created)
            return result(name, {"rule": created})
        if name == "update_rule":
            for rule in self.rules:
                if str(rule["id"]) == str(args["ruleId"]):
                    rule["enabled"] = bool(args["enabled"])
                    rule["status"] = "Active" if args["enabled"] else "Disabled"
            return result(name, {"success": True, "ruleId": args["ruleId"], "enabled": args["enabled"]})
        return result(name, {}, error=True, text=f"Unexpected tool {name}")


class Index:
    def __init__(self, notification_count: int = 1) -> None:
        self.notification_count = notification_count

    async def exact_device(self, label: str):
        if label == "Fridge Door":
            return (
                {
                    "id": "77",
                    "label": "Fridge Door",
                    "room": "Appliances",
                    "capabilities": ["ContactSensor", "Battery"],
                    "currentStates": {"contact": "closed", "battery": 17},
                },
                [],
            )
        return None, []

    async def enriched_devices(self, *, force: bool = False):
        rows = [
            {
                "id": "77",
                "label": "Fridge Door",
                "room": "Appliances",
                "capabilities": ["ContactSensor", "Battery"],
                "currentStates": {"contact": "closed", "battery": 17},
            }
        ]
        for number in range(self.notification_count):
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


def service(notification_count: int = 1):
    client = CurrentMCP()
    app = SimpleNamespace(mcp=client, VERSION="0.4.16-alpha")
    workflow = LiveSchemaAutomationRuleWorkflow(app, Index(notification_count))
    return workflow, client


async def prepare(workflow: LiveSchemaAutomationRuleWorkflow):
    pending = await workflow.store.remember("phone", RECOMMENDATION)
    built = await workflow.handle(SimpleNamespace(session_id="phone"), "build")
    return pending, built


def test_current_create_rule_schema_builds_exact_disabled_fridge_rule():
    workflow, client = service()

    async def run():
        pending, built = await prepare(workflow)
        created = await workflow.handle(SimpleNamespace(session_id="phone"), "create")
        return pending, built, created

    pending, built, created = asyncio.run(run())

    assert built["write_ready"] is True
    assert built["rule_draft"]["enabled"] is False
    assert pending.create_tool.name == "create_rule"
    create_calls = [args for name, args in client.calls if name == "create_rule"]
    assert len(create_calls) == 1
    args = create_calls[0]
    assert args["enabled"] is False
    assert args["testRule"] is False
    assert args["triggers"] == [
        {
            "type": "device_event",
            "deviceId": "77",
            "attribute": "contact",
            "value": "open",
            "duration": 120,
        },
        {
            "type": "device_event",
            "deviceId": "77",
            "attribute": "contact",
            "value": "closed",
        },
    ]
    outer = args["actions"][0]
    assert outer["type"] == "if_then_else"
    assert outer["thenActions"] == [
        {"type": "cancel_delayed", "delayId": "homebrain-fridge-door-repeat"}
    ]
    notification = outer["elseActions"][0]
    assert notification == {
        "type": "send_notification",
        "deviceId": "800",
        "message": "Fridge Door has been open for 2 minutes.",
    }
    assert created["intent"] == "automation-rule-created"
    assert "enabled=false" in created["message"]


def test_current_gateway_test_rule_is_a_dry_run_without_actions():
    workflow, client = service()

    async def run():
        await prepare(workflow)
        await workflow.handle(SimpleNamespace(session_id="phone"), "create")
        return await workflow.handle(SimpleNamespace(session_id="phone"), "test")

    answer = asyncio.run(run())

    gateway_calls = [args for name, args in client.calls if name == "manage_rules_admin" and args]
    assert gateway_calls == [{"tool": "test_rule", "args": {"ruleId": "9001"}}]
    assert answer["success"] is True
    assert answer["intent"] == "automation-rule-tested"
    assert "without executing its actions" in answer["message"]
    assert "dry-run only" in answer["display"]["note"].lower()


def test_current_update_rule_enables_and_disables_separately():
    workflow, client = service()

    async def run():
        await prepare(workflow)
        await workflow.handle(SimpleNamespace(session_id="phone"), "create")
        enabled = await workflow.handle(SimpleNamespace(session_id="phone"), "enable")
        disabled = await workflow.handle(SimpleNamespace(session_id="phone"), "pause")
        return enabled, disabled

    enabled, disabled = asyncio.run(run())

    update_calls = [args for name, args in client.calls if name == "update_rule"]
    assert update_calls == [
        {"ruleId": "9001", "enabled": True},
        {"ruleId": "9001", "enabled": False},
    ]
    assert enabled["intent"] == "automation-rule-enabled"
    assert disabled["intent"] == "automation-rule-paused"


def test_missing_notification_device_blocks_create_instead_of_inventing_recipient():
    workflow, client = service(notification_count=0)

    async def run():
        _, built = await prepare(workflow)
        create = await workflow.handle(SimpleNamespace(session_id="phone"), "create")
        return built, create

    built, create = asyncio.run(run())

    assert built["write_ready"] is False
    assert "No selected Notification-capable device" in built["message"]
    assert all(item["query"] != "Create this rule" for item in built["display"]["actions"])
    assert create["success"] is False
    assert [name for name, _ in client.calls if name == "create_rule"] == []


def test_multiple_notification_devices_block_recipient_guessing():
    workflow, client = service(notification_count=2)

    async def run():
        _, built = await prepare(workflow)
        return built

    built = asyncio.run(run())

    assert built["write_ready"] is False
    assert "will not guess the recipient" in built["message"]
    assert "Enamul Phone" in built["message"]
    assert "Phone 2" in built["message"]
    assert [name for name, _ in client.calls if name == "create_rule"] == []


def test_build_performs_no_rule_write():
    workflow, client = service()

    async def run():
        _, built = await prepare(workflow)
        return built

    built = asyncio.run(run())

    assert built["intent"] == "automation-rule-draft"
    assert not [
        name
        for name, _ in client.calls
        if name in {"create_rule", "update_rule", "test_rule"}
    ]
