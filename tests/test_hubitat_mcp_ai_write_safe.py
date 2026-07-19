from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_workflow_live import LiveRuleTool  # noqa: E402
from automation_rule_workflow_write_safe import (  # noqa: E402
    WriteSafeBackupWashingRuleMachineWorkflow,
)
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def result(name: str, data: Any) -> MCPToolResult:
    return MCPToolResult(
        name=name,
        arguments={},
        raw={},
        text="",
        data=data,
        is_error=False,
    )


class GatewayFailsDirectWorks:
    configured = True

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool("hub_set_rule", "Native Rule Machine write", {"type": "object"}),
            MCPTool(
                "hub_manage_rule_machine",
                "Rule Machine gateway",
                {"type": "object", "properties": {"tool": {}, "args": {}}},
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_manage_rule_machine":
            raise RuntimeError("MCP HTTP 500: Internal Server Error")
        if name == "hub_set_rule":
            return result(name, {"success": True, "ruleId": 901})
        raise AssertionError(name)


class AllRoutesFail(GatewayFailsDirectWorks):
    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        raise RuntimeError(f"MCP HTTP 500 from {name}: Internal Server Error")


def workflow(client: Any) -> WriteSafeBackupWashingRuleMachineWorkflow:
    app = SimpleNamespace(mcp=client, VERSION="0.4.29-alpha")
    return WriteSafeBackupWashingRuleMachineWorkflow(app, object())


def test_gateway_http_500_retries_same_idempotent_write_directly():
    client = GatewayFailsDirectWorks()
    service = workflow(client)
    tool = LiveRuleTool(
        name="hub_set_rule",
        description="Native Rule Machine write",
        schema={"type": "object"},
        gateway="hub_manage_rule_machine",
    )
    args = {
        "name": "Washing machine finished notification",
        "confirm": True,
        "opToken": "homebrain-fixed-token",
        "bestPracticeKey": "secret-key",
    }

    value = asyncio.run(service._call_rule_tool(tool, args))

    assert value.is_error is False
    assert value.data["success"] is True
    assert [name for name, _ in client.calls] == [
        "hub_manage_rule_machine",
        "hub_set_rule",
    ]
    assert client.calls[1][1]["opToken"] == "homebrain-fixed-token"
    assert value.raw["homebrain_write_route_recovery"]["recovered_via"] == "hub_set_rule"


def test_all_http_routes_fail_as_structured_tool_error_not_exception():
    client = AllRoutesFail()
    service = workflow(client)
    tool = LiveRuleTool(
        name="hub_set_rule",
        description="Native Rule Machine write",
        schema={"type": "object"},
        gateway="hub_manage_rule_machine",
    )

    value = asyncio.run(
        service._call_rule_tool(
            tool,
            {
                "name": "Washing machine finished notification",
                "confirm": True,
                "opToken": "homebrain-fixed-token",
                "bestPracticeKey": "secret-key",
            },
        )
    )

    assert value.is_error is True
    assert value.data["success"] is False
    assert value.data["writeTool"] == "hub_set_rule"
    assert value.data["alternateRouteAttempted"] is True
    assert len(value.data["attempts"]) == 2
    assert value.data["arguments"]["bestPracticeKey"] == "<present>"
    assert "Internal Server Error" in value.text
