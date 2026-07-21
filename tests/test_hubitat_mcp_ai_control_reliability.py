from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_confirmation import install_control_confirmation  # noqa: E402
from control_language import canonicalise_basic_control, install_control_language  # noqa: E402
from fast_fallback_verified import FastFallbackRouter  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def request(query: str, session_id: str = "browser-1"):
    return SimpleNamespace(query=query, session_id=session_id, history=[])


def test_basic_control_language_corrects_only_action_word_of():
    control = canonicalise_basic_control("turn of livingroom light 2")
    assert control is not None
    assert control.action == "off"
    assert control.target == "livingroom light 2"
    assert control.canonical_query == "turn off livingroom light 2"
    assert control.correction == "of→off"

    assert canonicalise_basic_control("show status of livingroom light 2") is None


def test_control_language_wrapper_sends_canonical_query_to_router():
    async def scenario():
        calls = []
        app = SimpleNamespace()

        async def ask(req):
            calls.append(req.query)
            return {"success": True, "message": "done"}

        app.ask = ask
        install_control_language(app)
        answer = await app.ask(request("switch bedroom light of"))
        return calls, answer

    calls, answer = asyncio.run(scenario())
    assert calls == ["turn off bedroom light"]
    assert answer["control_language_correction"] == "of→off"


def test_single_device_confirmation_accepts_yes_and_preserves_off_action():
    async def scenario():
        calls = []
        app = SimpleNamespace()

        async def ask(req):
            calls.append(req.query)
            if req.query == "turn off dehum 2":
                return {
                    "success": False,
                    "intent": "fallback-device-confirmation-required",
                    "confirmation_required": True,
                    "alternatives": ["Dehumidifier 2"],
                    "confirmation": {
                        "action": "off",
                        "requested_name": "dehum 2",
                        "candidates": ["Dehumidifier 2"],
                    },
                    "message": "old prompt",
                }
            return {
                "success": True,
                "intent": "fallback-device-control-confirmed",
                "message": "Dehumidifier 2 turned off.",
            }

        app.ask = ask
        install_control_confirmation(app, ttl_seconds=120)
        prompt = await app.ask(request("turn off dehum 2"))
        confirmed = await app.ask(request("yes"))
        return calls, prompt, confirmed

    calls, prompt, confirmed = asyncio.run(scenario())
    assert "Reply Yes to turn it off" in prompt["message"]
    assert "turn it on" not in prompt["message"]
    assert prompt["route"] == "mcp-confirmation"
    assert calls == ["turn off dehum 2", "turn off Dehumidifier 2"]
    assert confirmed["confirmation_follow_up"] is True
    assert confirmed["confirmed_candidate"] == "Dehumidifier 2"


def test_no_cancels_pending_confirmation_without_sending_command():
    async def scenario():
        calls = []
        app = SimpleNamespace()

        async def ask(req):
            calls.append(req.query)
            return {
                "success": False,
                "confirmation_required": True,
                "alternatives": ["Dehumidifier 2"],
                "confirmation": {
                    "action": "off",
                    "requested_name": "dehum 2",
                    "candidates": ["Dehumidifier 2"],
                },
            }

        app.ask = ask
        install_control_confirmation(app)
        await app.ask(request("turn off dehum 2"))
        cancelled = await app.ask(request("no"))
        return calls, cancelled

    calls, cancelled = asyncio.run(scenario())
    assert calls == ["turn off dehum 2"]
    assert cancelled["intent"] == "control-confirmation-cancelled"
    assert "No device command was sent" in cancelled["message"]


def test_multiple_candidates_require_number_not_yes():
    async def scenario():
        calls = []
        app = SimpleNamespace()

        async def ask(req):
            calls.append(req.query)
            if req.query == "turn off hallway light":
                return {
                    "success": False,
                    "confirmation_required": True,
                    "alternatives": ["Hallway Light 1", "Hallway Light 2"],
                    "confirmation": {
                        "action": "off",
                        "requested_name": "hallway light",
                        "candidates": ["Hallway Light 1", "Hallway Light 2"],
                    },
                }
            return {"success": True, "message": req.query}

        app.ask = ask
        install_control_confirmation(app)
        prompt = await app.ask(request("turn off hallway light"))
        yes = await app.ask(request("yes"))
        selected = await app.ask(request("2"))
        return calls, prompt, yes, selected

    calls, prompt, yes, selected = asyncio.run(scenario())
    assert "1. Hallway Light 1" in prompt["message"]
    assert [item["query"] for item in prompt["display"]["items"]] == [
        "turn off Hallway Light 1",
        "turn off Hallway Light 2",
    ]
    assert yes["intent"] == "control-confirmation-choice-required"
    assert calls == ["turn off hallway light", "turn off Hallway Light 2"]
    assert selected["confirmed_candidate"] == "Hallway Light 2"


class FreshReadClient:
    configured = True
    server_info = {"name": "Hubitat MCP", "version": "3.4.1"}

    def __init__(self) -> None:
        self.invalidations = 0
        self.reads = 0
        self.command_calls = 0
        self.cached: MCPToolResult | None = None
        self.reported_states = ["on", "on", "off"]
        self.tools = [
            MCPTool("hub_list_devices", "List devices", {"type": "object", "properties": {}}),
            MCPTool(
                "hub_call_device_command",
                "Call command",
                {
                    "type": "object",
                    "properties": {
                        "deviceId": {"type": "string"},
                        "command": {"type": "string"},
                        "params": {"type": "array"},
                    },
                },
            ),
        ]

    async def list_tools(self, refresh: bool = False):
        return list(self.tools)

    async def get_tool(self, name: str):
        return next((item for item in self.tools if item.name == name), None)

    async def invalidate(self, category: str = "all"):
        assert category == "devices"
        self.invalidations += 1
        self.cached = None
        return 1

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        arguments = arguments or {}
        if name == "hub_call_device_command":
            self.command_calls += 1
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={"success": True, "command": arguments.get("command")},
                is_error=False,
            )
        assert name == "hub_list_devices"
        if self.cached is not None:
            return self.cached
        index = min(self.reads, len(self.reported_states) - 1)
        state = self.reported_states[index]
        self.reads += 1
        self.cached = MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={
                "devices": [
                    {
                        "id": "22",
                        "name": "Dehumidifier 2",
                        "label": "Dehumidifier 2",
                        "room": "Livingroom",
                        "currentStates": {"switch": state},
                    }
                ]
            },
            is_error=False,
        )
        return self.cached


def test_verified_control_invalidates_before_every_state_read():
    async def scenario():
        client = FreshReadClient()
        router = FastFallbackRouter(
            client,
            control_verification_timeout_seconds=3,
            control_verification_initial_delay_seconds=0.05,
        )
        answer = await router._control_device("Dehumidifier 2", "off")
        return client, answer

    client, answer = asyncio.run(scenario())
    assert client.command_calls == 1
    assert client.reads == 3
    assert client.invalidations >= 3
    assert answer["confirmed"] is True
    assert answer["initial_state"] == "on"
    assert answer["verified_state"] == "off"
    assert answer["intent"] == "fallback-device-control-confirmed"
    assert len(answer["verification_attempts"]) == 2


def test_fresh_preflight_prevents_false_already_on_result():
    async def scenario():
        client = FreshReadClient()
        # Simulate an old cached "on" result while the next authoritative read is off.
        client.cached = MCPToolResult(
            name="hub_list_devices",
            arguments={},
            raw={},
            text="",
            data={"devices": [{"id": "22", "label": "Dehumidifier 2", "currentStates": {"switch": "on"}}]},
            is_error=False,
        )
        client.reported_states = ["off"]
        router = FastFallbackRouter(client)
        answer = await router._control_device("Dehumidifier 2", "off")
        return client, answer

    client, answer = asyncio.run(scenario())
    assert client.invalidations >= 1
    assert client.command_calls == 0
    assert answer["intent"] == "fallback-device-already-set"
    assert answer["message"] == "Dehumidifier 2 is already off."
