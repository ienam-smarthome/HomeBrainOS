"""Native MCP virtual-device creation uses its own direct write contract.

All tests are synthetic: no real Hubitat, HA, OpenWrt or cloud model.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from native_virtual_device_creation_contract import (  # noqa: E402
    requested_virtual_device_type, needs_server_generated_dni,
    virtual_device_creation_error,
)
from confirmed_action_coordinator import ConfirmedActionCoordinator  # noqa: E402
from confirmation_policy import ConfirmationPolicy  # noqa: E402
from confirmation_store import PendingConfirmation  # noqa: E402
from tool_discovery_catalog import ToolDiscoveryCatalog  # noqa: E402
from test_mcp_agent_orchestrator import FakeAI  # noqa: E402


QUESTION = (
    "Create exactly one new disposable MCP-managed Hubitat Virtual Switch "
    "for an isolated Rule Machine scheduling test.\n"
    "Device label: HB BAT Isolated Timer Switch 2026-11-04.\n"
    "Use a server-generated device network ID.\n"
    "Do not yet switch it ON, create a Rule Machine rule, or change OpenWrt."
)
LABEL = "HB BAT Isolated Timer Switch 2026-11-04"
BAD = {
    "tool": "hub_create_device",
    "args": {"deviceTypeId": "Virtual Switch", "label": LABEL, "confirm": True},
}
GOOD = {
    "action": "create", "deviceType": "Virtual Switch", "deviceLabel": LABEL,
}
TOOL = MCPTool(
    "hub_manage_virtual_device", "Create or delete MCP-managed virtual devices",
    {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["create", "delete"]},
        "deviceType": {"type": "string"},
        "deviceLabel": {"type": "string"},
        "confirm": {"type": "boolean"},
    }},
)


class FakeMCP:
    def __init__(self, *, advertise_native=True):
        self.calls = []
        self.advertise_native = advertise_native

    async def list_tools(self):
        base = [
            MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
            MCPTool("hub_manage_devices", "Manage native devices", {"type": "object"}),
            MCPTool("hub_read_devices", "Read devices", {"type": "object"}),
            MCPTool("hub_get_tool_guide", "Read guide", {"type": "object"}),
            MCPTool("hub_read_apps_code", "Read apps/backups", {"type": "object"}),
        ]
        return base + ([TOOL] if self.advertise_native else [])

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        if name == "hub_manage_devices":
            raise AssertionError("Legacy native create must never run")
        if name == "hub_manage_virtual_device":
            assert args["action"] == "create"
            assert args["deviceType"] == "Virtual Switch"
            assert args["deviceLabel"] == LABEL
            assert args["confirm"] is True
            return MCPToolResult(name, args, {}, "", {
                "success": True,
                "device": {
                    "id": "8100", "deviceNetworkId": "mcp-virtual-synthetic",
                    "driverType": "Virtual Switch", "driverNamespace": "hubitat",
                },
            })
        return MCPToolResult(name, args, {}, "", {"success": True})


def test_positive_intent_and_negation_not_misclassified():
    assert requested_virtual_device_type(QUESTION) == "Virtual Switch"
    assert needs_server_generated_dni(QUESTION)
    assert requested_virtual_device_type(
        "Create a Rule Machine rule that turns Virtual Switch off."
    ) is None
    assert requested_virtual_device_type(
        "Do not create a Virtual Switch. List my devices."
    ) is None
    assert requested_virtual_device_type(
        "Check whether a Virtual Switch exists."
    ) is None
    assert requested_virtual_device_type(
        "Create one Virtual Motion Sensor for isolated testing."
    ) == "Virtual Motion Sensor"


def test_schema_guard_refuses_unresolved_string_driver_id_and_wrong_builtin():
    assert "hub_manage_virtual_device" in virtual_device_creation_error(
        "hub_manage_devices", BAD,
    )
    assert "not hub_create_device" in virtual_device_creation_error(
        "hub_manage_devices", BAD,
        requested_type="Virtual Switch",
    )
    assert virtual_device_creation_error(
        "hub_manage_devices",
        {"tool": "hub_create_device", "args": {"deviceTypeId": "123"}},
    ) is None  # legitimate native numeric-id create remains supported
    assert virtual_device_creation_error(
        "hub_manage_devices",
        {"tool": "hub_create_device", "args": {"deviceTypeId": "123"}},
        requested_type="Virtual Switch",
    ) is not None  # user explicitly requested MCP-managed virtual
    assert virtual_device_creation_error(
        "hub_manage_virtual_device",
        {**GOOD, "deviceType": "Virtual Dimmer"},
        requested_type="Virtual Switch",
    ) is not None
    assert virtual_device_creation_error(
        "hub_manage_virtual_device",
        {**GOOD, "deviceNetworkId": "provided-by-model"},
        requested_type="Virtual Switch",
        server_generated_dni=True,
    ) is not None
    assert virtual_device_creation_error(
        "hub_manage_virtual_device", GOOD,
        requested_type="Virtual Switch", server_generated_dni=True,
    ) is None


@pytest.mark.asyncio
async def test_wrong_legacy_create_is_refused_before_confirmation_and_no_remote_write():
    mcp = FakeMCP()
    ai = FakeAI([{
        "message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_manage_devices", "arguments": BAD},
        }]},
    }])
    agent = UnifiedMCPAgent(mcp, "test-key", "gemma4:31b", ai_client=ai)
    result = await agent.process_user_request_result(
        QUESTION, session_id="virtual-bat-wrong"
    )
    assert result.confirmation_required is False
    assert result.confirmation_count == 0
    assert "No Hubitat action was queued or executed" in result.message
    assert "hub_manage_virtual_device" in result.message
    assert "hub_manage_devices" not in [name for name, _ in mcp.calls]
    assert "virtual-bat-wrong" not in agent.confirmations.pending


@pytest.mark.asyncio
async def test_correct_native_creation_is_queued_then_executed_once_on_confirmation():
    mcp = FakeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_manage_virtual_device", "arguments": GOOD},
        }]}},
        {"message": {"role": "assistant", "content": "The create tool returned a result."}},
    ])
    agent = UnifiedMCPAgent(mcp, "test-key", "gemma4:31b", ai_client=ai)
    start = await agent.process_user_request_result(
        QUESTION, session_id="virtual-bat-correct"
    )
    assert start.confirmation_required is True
    assert start.confirmation_count == 1
    assert "hub_manage_virtual_device" in start.message
    assert not any(n == "hub_manage_virtual_device" for n, _ in mcp.calls)
    assert any(
        tool["function"]["name"] == "hub_manage_virtual_device"
        for _url, kwargs in ai.requests
        for tool in (kwargs.get("json") or {}).get("tools", [])
        if isinstance(tool, dict) and "function" in tool
    )
    finish = await agent.process_user_request_result(
        "confirm", session_id="virtual-bat-correct"
    )
    assert finish.confirmation_required is False
    sends = [args for name, args in mcp.calls if name == "hub_manage_virtual_device"]
    assert len(sends) == 1
    assert sends[0]["confirm"] is True
    assert sends[0]["deviceType"] == "Virtual Switch"
    assert "deviceNetworkId" not in sends[0]
    assert all(name != "hub_manage_devices" for name, _ in mcp.calls)
    assert "device ID **8100**" in finish.message
    assert "not yet an independent read-back" in finish.message


def test_partial_native_create_receipt_never_becomes_success_or_retry():
    from tool_executor import ToolExecution
    from tool_registry import ToolEffect
    receipt = MCPToolResult(
        "hub_manage_virtual_device", GOOD, {}, "",
        {"success": True, "partialSuccess": True,
         "device": {"id": "8100", "deviceNetworkId": "mcp-virtual-synthetic"}},
    )
    action = ToolExecution(
        name="hub_manage_virtual_device", arguments=GOOD,
        effect=ToolEffect.SENSITIVE_WRITE,
        success=True, elapsed_ms=3, content="{}", result=receipt,
    )
    answer = ConfirmedActionCoordinator.confirmed_virtual_device_create_report([
        ("hub_manage_virtual_device", GOOD, action),
    ])
    assert "unverified" in answer
    assert "Do not retry" in answer
    assert "candidate device ID 8100" in answer
    assert "created" not in answer


@pytest.mark.asyncio
async def test_missing_native_tool_refuses_before_model_or_any_gateway_call():
    mcp = FakeMCP(advertise_native=False)
    ai = FakeAI([])
    agent = UnifiedMCPAgent(mcp, "test-key", "gemma4:31b", ai_client=ai)
    result = await agent.process_user_request_result(
        QUESTION, session_id="virtual-bat-missing"
    )
    assert "does not expose hub_manage_virtual_device" in result.message
    assert not result.confirmation_required
    assert mcp.calls == []
    assert ai.requests == []


@pytest.mark.asyncio
async def test_replayed_legacy_confirmation_is_revalidated_before_any_write():
    class NeverExecute:
        def __init__(self):
            self.calls = []
        async def execute(self, name, arguments, **kwargs):
            self.calls.append((name, arguments))
            raise AssertionError("The wrong create must not reach an MCP gateway")

    async def no_chat(*args, **kwargs):
        raise AssertionError("No model call on refused confirmation")

    executor = NeverExecute()
    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True),
        executor, no_chat, lambda: None,
    )
    pending = PendingConfirmation(
        expires_at=999,
        actions=[("hub_manage_devices", BAD)],
        messages=[{"role": "user", "content": QUESTION}],
        assistant_message={"role": "assistant", "content": "Please confirm"},
    )
    catalog = ToolDiscoveryCatalog([
        MCPTool("hub_manage_devices", "native tools", {"type": "object"}),
        TOOL,
    ])
    reply = await coordinator.resume(pending, catalog)
    assert "cancelled before any Hubitat write" in reply
    assert "hub_manage_virtual_device" in reply
    assert executor.calls == []
