from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_workflow_washing import (  # noqa: E402
    WashingRuleMachineWorkflow,
    _washing_rule_plan,
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


class WashingIndex:
    def __init__(self, *, notifications: int = 1) -> None:
        self.notifications = notifications

    def rows(self):
        values = [
            {
                "id": "94",
                "label": "Washing Machine (MQTT)",
                "room": "Appliances",
                "capabilities": ["PowerMeter", "EnergyMeter", "Switch"],
                "currentStates": {"power": 3.8, "energy": 94.753, "switch": "on"},
            }
        ]
        for number in range(self.notifications):
            values.append(
                {
                    "id": str(800 + number),
                    "label": "SM-S938B" if number == 0 else f"Phone {number + 1}",
                    "room": "Mobile",
                    "capabilities": ["Notification"],
                    "supportedCommands": [{"name": "deviceNotification"}],
                    "currentStates": {},
                }
            )
        return values

    async def exact_device(self, label: str):
        matches = [item for item in self.rows() if item["label"] == label]
        return (matches[0], []) if len(matches) == 1 else (None, [item["label"] for item in matches])

    async def enriched_devices(self, force: bool = False):
        return self.rows()

    async def summary_devices(self, force: bool = False):
        return self.rows()


class WashingMCP:
    configured = True
    server_info: dict[str, Any] = {}

    def __init__(self, *, local_variable_ok: bool = True) -> None:
        self.local_variable_ok = local_variable_ok
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
                        "addLocalVariable": {"type": "object"},
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
                {"type": "object", "properties": {"bestPracticeKey": {"type": "string"}},
            ),
            MCPTool("hub_get_info", "Get hub information", {"type": "object", "properties": {}}),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_list_rules":
            rules = [{"id": 902, "label": "Washing machine finished notification"}] if self.created else []
            return result(name, {"rules": rules})
        if name == "hub_get_tool_guide":
            return result(name, {"bestPracticeKey": "BP-WASH-1234"})
        if name == "hub_get_info":
            return result(name, {"writeEnabled": True, "lastBackupEpoch": None})
        if name == "hub_create_backup":
            return result(name, {"success": True, "fileName": "backup.lzf"})
        if name == "hub_set_rule_paused":
            return result(name, {"success": True, "ruleId": 902, "paused": args.get("paused")})
        if name == "hub_set_rule" and "appId" not in args:
            self.created = True
            return result(name, {"success": True, "appId": 902, "ruleId": 902, "name": args.get("name")})
        if name == "hub_set_rule" and "addLocalVariable" in args:
            if not self.local_variable_ok:
                return result(
                    name,
                    {"success": False, "partial": True, "error": "Local variable did not bake"},
                    error=True,
                    text="Local variable did not bake",
                )
            return result(
                name,
                {
                    "success": True,
                    "partial": False,
                    "variableNotLive": False,
                    "localVariable": args["addLocalVariable"],
                    "health": {"ok": True},
                },
            )
        if name == "hub_set_rule" and "addTriggers" in args:
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
        raise AssertionError(f"Unexpected call {name}: {args}")


RECOMMENDATION = {
    "type": "washing-complete",
    "title": "Washing machine finished notification",
    "room": "Appliances",
    "devices": ["Washing Machine (MQTT)"],
    "trigger": "Arm above 10 W, then trigger below 5 W for 3 minutes.",
    "action": "Send a phone notification that the washing cycle has finished.",
    "safeguard": "Only notify after a genuine cycle crossed the running threshold.",
    "reason": "Avoid repeatedly checking the washing machine.",
}


def service(*, notifications: int = 1, local_variable_ok: bool = True):
    client = WashingMCP(local_variable_ok=local_variable_ok)
    app = SimpleNamespace(mcp=client, VERSION="0.4.21-alpha")
    workflow = WashingRuleMachineWorkflow(app, WashingIndex(notifications=notifications))
    return workflow, client


async def build(workflow: WashingRuleMachineWorkflow):
    pending = await workflow.store.remember("washing", RECOMMENDATION)
    answer = await workflow.handle(SimpleNamespace(session_id="washing"), "build")
    return pending, answer


def test_washing_plan_uses_two_thresholds_and_cycle_arm_variable():
    draft = {
        "type": "washing-complete",
        "washing_power_device": {
            "id": "94",
            "label": "Washing Machine (MQTT)",
            "attributes": {"power": 3.8},
        },
        "devices": [],
        "notification_candidates": [{"id": "800", "label": "SM-S938B"}],
        "unresolved": [],
    }

    plan, error = _washing_rule_plan(draft)

    assert error is None
    assert plan["local_variables"] == [{"name": "cycleArmed", "type": "Number", "value": 0}]
    assert plan["triggers"] == [
        {"capability": "Power", "deviceIds": [94], "comparator": ">", "value": 10},
        {
            "capability": "Power",
            "deviceIds": [94],
            "comparator": "<",
            "value": 5,
            "andStays": {"seconds": 180},
        },
    ]
    assert [item["capability"] for item in plan["actions"]] == [
        "ifThen",
        "setLocalVariable",
        "elseIf",
        "notification",
        "setLocalVariable",
        "endIf",
    ]
    assert plan["actions"][1] == {
        "capability": "setLocalVariable",
        "variable": "cycleArmed",
        "value": 1,
    }
    assert plan["actions"][4] == {
        "capability": "setLocalVariable",
        "variable": "cycleArmed",
        "value": 0,
    }
    assert plan["actions"][3]["deviceIds"] == [800]


def test_washing_build_is_ready_with_power_meter_and_one_notification_device():
    workflow, _ = service()

    async def run():
        return await build(workflow)

    pending, answer = asyncio.run(run())

    assert answer["write_ready"] is True
    assert pending.create_tool.name == "hub_set_rule"
    assert pending.draft["type"] == "washing-complete"
    assert pending.draft["washing_power_device"]["id"] == "94"
    assert pending.draft["notification_candidates"][0]["id"] == "800"
    assert pending.draft["unresolved"] == []


def test_washing_create_orders_backup_shell_pause_local_pause_populate_pause():
    workflow, client = service()

    async def run():
        pending, built = await build(workflow)
        created = await workflow.handle(SimpleNamespace(session_id="washing"), "create")
        return pending, built, created

    pending, built, created = asyncio.run(run())

    assert built["write_ready"] is True
    assert pending.create_tool.name == "hub_set_rule"
    assert created["success"] is True
    assert created["created_rule"]["status"] == "Paused"
    assert created["created_rule"]["local_variable_count"] == 1
    assert created["created_rule"]["trigger_count"] == 2
    assert created["created_rule"]["action_count"] == 6

    backup_index = next(i for i, (name, _) in enumerate(client.calls) if name == "hub_create_backup")
    shell_index = next(
        i
        for i, (name, args) in enumerate(client.calls)
        if name == "hub_set_rule" and "appId" not in args
    )
    pause_indices = [
        i for i, (name, _) in enumerate(client.calls) if name == "hub_set_rule_paused"
    ]
    local_index = next(
        i
        for i, (name, args) in enumerate(client.calls)
        if name == "hub_set_rule" and "addLocalVariable" in args
    )
    populate_index = next(
        i
        for i, (name, args) in enumerate(client.calls)
        if name == "hub_set_rule" and "addTriggers" in args
    )

    assert backup_index < shell_index < pause_indices[0] < local_index < pause_indices[1] < populate_index < pause_indices[-1]

    local_args = client.calls[local_index][1]
    assert local_args["addLocalVariable"] == {
        "name": "cycleArmed",
        "type": "Number",
        "value": 0,
    }
    assert local_args["bestPracticeKey"] == "BP-WASH-1234"

    populate_args = client.calls[populate_index][1]
    assert len(populate_args["addTriggers"]) == 2
    assert len(populate_args["addActions"]) == 6
    assert populate_args["bestPracticeKey"] == "BP-WASH-1234"


def test_local_variable_failure_blocks_triggers_and_actions_and_leaves_rule_paused():
    workflow, client = service(local_variable_ok=False)

    async def run():
        await build(workflow)
        return await workflow.handle(SimpleNamespace(session_id="washing"), "create")

    answer = asyncio.run(run())

    assert answer["success"] is False
    assert answer["intent"] == "automation-rule-create-partial"
    assert "cycle-arm variable" in answer["message"]
    assert not [
        args
        for name, args in client.calls
        if name == "hub_set_rule" and "addTriggers" in args
    ]
    pause_calls = [args for name, args in client.calls if name == "hub_set_rule_paused"]
    assert pause_calls and all(args["paused"] is True for args in pause_calls)


def test_missing_notification_device_blocks_before_any_write():
    workflow, client = service(notifications=0)

    async def run():
        _, built = await build(workflow)
        return built

    built = asyncio.run(run())

    assert built["write_ready"] is False
    assert "Notification-capable" in built["message"]
    assert not [name for name, _ in client.calls if name in {"hub_create_backup", "hub_set_rule"}]
