from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_workflow_release import (  # noqa: E402
    ReleaseAutomationRuleWorkflow,
)
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def result(name: str, data: Any, *, error: bool = False) -> MCPToolResult:
    return MCPToolResult(
        name=name,
        arguments={},
        raw=data if isinstance(data, dict) else {"data": data},
        text="",
        data=data,
        is_error=error,
    )


class Client:
    def __init__(self) -> None:
        self.invalidations: list[str] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool("list_rules", "List rules", {"type": "object", "properties": {}}),
            MCPTool(
                "create_rule",
                "Create rule",
                {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "enabled": {"type": "boolean"},
                        "triggers": {"type": "array"},
                        "actions": {"type": "array"},
                    },
                    "required": ["name", "triggers", "actions"],
                },
            ),
        ]

    async def gateway_map(self, refresh: bool = False):
        return {}

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "list_rules":
            return result(name, {"rules": []})
        if name == "create_rule":
            return result(
                name,
                {
                    "rule": {
                        "id": "1",
                        "name": args["name"],
                        "enabled": False,
                        "status": "Disabled",
                    }
                },
            )
        return result(name, {})

    async def invalidate(self, category: str):
        self.invalidations.append(category)
        return 0


class Index:
    def __init__(self, include_notifier: bool) -> None:
        self.include_notifier = include_notifier

    async def exact_device(self, label: str):
        return (
            {
                "id": "77",
                "label": "Fridge Door",
                "room": "Appliances",
                "capabilities": ["ContactSensor"],
                "currentStates": {"contact": "closed"},
            },
            [],
        )

    async def enriched_devices(self, *, force: bool = False):
        rows = [
            {
                "id": "77",
                "label": "Fridge Door",
                "room": "Appliances",
                "capabilities": ["ContactSensor"],
                "currentStates": {"contact": "closed"},
            }
        ]
        if self.include_notifier:
            rows.append(
                {
                    "id": "800",
                    "label": "Enamul Phone",
                    "capabilities": ["Notification"],
                    "supportedCommands": ["deviceNotification"],
                }
            )
        return rows


RECOMMENDATION = {
    "type": "cold-storage-door",
    "title": "Fridge Door left-open alert",
    "room": "Appliances",
    "devices": ["Fridge Door"],
    "trigger": "Trigger when Fridge Door remains open for 2 minutes.",
    "action": "Send a high-priority phone notification and repeat once after 5 minutes if it is still open.",
    "safeguard": "Cancel all pending alerts immediately when the contact closes.",
    "reason": "Prevent food warming.",
}


def workflow(include_notifier: bool):
    client = Client()
    app = SimpleNamespace(mcp=client, VERSION="0.4.16-alpha")
    return ReleaseAutomationRuleWorkflow(app, Index(include_notifier)), client


def test_recommendation_wording_is_aligned_with_supported_notification_action():
    service, _ = workflow(include_notifier=True)
    answer = {
        "recommendation": dict(RECOMMENDATION),
        "message": RECOMMENDATION["action"],
        "display": {
            "summary": RECOMMENDATION["action"],
            "items": [
                {"title": "Action", "subtitle": RECOMMENDATION["action"]},
                {"title": "Safeguard", "subtitle": RECOMMENDATION["safeguard"]},
            ],
            "note": "Review only",
        },
    }

    asyncio.run(service.remember_answer("phone", answer))

    assert "selected Hubitat Notification device" in answer["recommendation"]["action"]
    assert "high-priority" not in answer["message"]
    assert answer["display"]["actions"][0]["query"] == "Build this rule"


def test_missing_notification_reason_is_visible_in_main_summary():
    service, _ = workflow(include_notifier=False)

    async def run():
        await service.store.remember("phone", RECOMMENDATION)
        return await service.handle(SimpleNamespace(session_id="phone"), "build")

    answer = asyncio.run(run())

    assert answer["write_ready"] is False
    assert "No selected Notification-capable device" in answer["display"]["summary"]
    assert "No selected Notification-capable device" in answer["display"]["note"]


def test_successful_create_invalidates_rule_catalogue():
    service, client = workflow(include_notifier=True)

    async def run():
        await service.store.remember("phone", RECOMMENDATION)
        await service.handle(SimpleNamespace(session_id="phone"), "build")
        return await service.handle(SimpleNamespace(session_id="phone"), "create")

    answer = asyncio.run(run())

    assert answer["success"] is True
    assert "catalog" in client.invalidations
