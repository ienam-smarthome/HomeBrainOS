"""Cross-device contract tests for the direct MCP virtual-device creator.

No test contacts the live Hubitat hub; all mutating calls are fake.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent, _explicit_mutation_request  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from test_mcp_agent_orchestrator import FakeAI  # noqa: E402
from tool_registry import (  # noqa: E402
    requests_virtual_device_creation,
    virtual_device_creation_proposal_error,
)


class VirtualMCP:
    def __init__(self, *, direct_available=True):
        self.calls = []
        self.direct_available = direct_available

    async def list_tools(self):
        tools = [
            MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
            MCPTool("hub_manage_devices", "Generic native device creation", {
                "type": "object",
                "properties": {"tool": {"type": "string"}, "args": {"type": "object"}},
            }),
        ]
        if self.direct_available:
            tools.append(MCPTool(
                "hub_manage_virtual_device", "Create managed virtual device", {
                    "type": "object",
                    "properties": {
                        "deviceType": {"type": "string"},
                        "label": {"type": "string"},
                        "confirm": {"type": "boolean"},
                    },
                    "required": ["deviceType", "label"],
                },
            ))
        return tools

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            # Worst-case fuzzy search advertises the WRONG generic gateway.
            return MCPToolResult(name, arguments, {}, "", {
                "results": [{"tool": "hub_create_device", "gateway": "hub_manage_devices"}]
            })
        return MCPToolResult(
            name, arguments, {}, "", {"success": True, "deviceId": "test-1"},
        )


@pytest.mark.parametrize("device_type", [
    "Virtual Switch", "Virtual Button", "Virtual Contact", "Virtual Sensor",
])
def test_virtual_type_labels_are_not_native_driver_ids(device_type):
    rejected = virtual_device_creation_proposal_error(
        "hub_manage_devices", {
            "tool": "hub_create_device",
            "args": {"deviceTypeId": device_type, "label": "Temporary test"},
        },
    )
    assert rejected is not None
    assert "hub_manage_virtual_device" in rejected
    assert "No action was queued or executed" in rejected
    assert virtual_device_creation_proposal_error(
        "hub_manage_devices", {
            "tool": "hub_create_device",
            "args": {"deviceTypeId": "1234", "label": "Other device"},
        },
    ) is None
    assert virtual_device_creation_proposal_error(
        "hub_manage_virtual_device", {
            "deviceType": device_type, "label": "Temporary test",
        },
    ) is None


def test_authority_is_separate_from_virtual_device_capability_recognition():
    prompt = "Create one disposable Hubitat Virtual Switch for a scheduling test"
    assert requests_virtual_device_creation(prompt)
    assert _explicit_mutation_request(prompt)
    forbidden = "Do not create any Virtual Switch. Explain the options only."
    assert not _explicit_mutation_request(forbidden)
    assert not requests_virtual_device_creation(
        "Why did my existing virtual switch turn off?"
    )


@pytest.mark.asyncio
async def test_installed_direct_creator_is_exposed_despite_wrong_fuzzy_gateway():
    mcp = VirtualMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_manage_virtual_device", "arguments": {
                "deviceType": "Virtual Switch",
                "label": "Temporary creation-contract test",
            }}
        }]}},
        {"message": {"role": "assistant", "content": "The test creation was reported."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)
    prompt = "Create a new disposable Hubitat Virtual Switch"
    first = await agent.process_user_request_result(prompt, session_id="create-test")
    assert first.confirmation_required is True
    assert first.confirmation_count == 1
    assert not any(name.startswith("hub_manage_") for name, _ in mcp.calls)
    seen = [t["function"]["name"] for t in ai.requests[0][1]["json"]["tools"]]
    assert "hub_manage_virtual_device" in seen
    assert "VIRTUAL DEVICE TOOL CONTRACT" in str(
        ai.requests[0][1]["json"]["messages"]
    )
    second = await agent.process_user_request_result("confirm", session_id="create-test")
    assert second.confirmation_required is False
    creates = [(name, args) for name, args in mcp.calls
               if name == "hub_manage_virtual_device"]
    assert len(creates) == 1
    assert creates[0][1]["deviceType"] == "Virtual Switch"
    assert creates[0][1]["confirm"] is True
    assert not any(name == "hub_manage_devices" for name, _ in mcp.calls)


@pytest.mark.asyncio
async def test_bad_generic_virtual_driver_is_never_queued_or_sent():
    mcp = VirtualMCP()
    bad_call = {"message": {"role": "assistant", "tool_calls": [{
        "function": {"name": "hub_manage_devices", "arguments": {
            "tool": "hub_create_device", "args": {
                "deviceTypeId": "Virtual Switch", "label": "Temporary test",
            }
        }}
    }]}}
    ai = FakeAI([bad_call, bad_call])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)
    outcome = await agent.process_user_request_result(
        "Create a new disposable Hubitat Virtual Switch",
        session_id="bad-generic",
    )
    assert outcome.confirmation_required is False
    assert "No Hubitat action was queued or executed" in outcome.message
    assert "native deviceTypeId" in outcome.message
    assert not any(name.startswith("hub_manage_") for name, _ in mcp.calls)


@pytest.mark.asyncio
async def test_missing_direct_creator_is_not_invented_or_auto_created():
    mcp = VirtualMCP(direct_available=False)
    ai = FakeAI([{"message": {"role": "assistant", "content":
        "The direct tool is unavailable; no virtual device was created."}}] * 9)
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)
    outcome = await agent.process_user_request_result(
        "Create a new disposable Hubitat Virtual Switch",
        session_id="missing-direct",
    )
    assert outcome.confirmation_required is False
    assert "hub_manage_virtual_device" not in str(
        ai.requests[0][1]["json"]["tools"]
    )
    assert not any(name.startswith("hub_manage_") for name, _ in mcp.calls)
