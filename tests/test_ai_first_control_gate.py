from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_agent_gate import (  # noqa: E402
    install_control_agent_gate,
    is_exact_fast_control,
)


def test_exact_fast_control_is_intentionally_tiny():
    assert is_exact_fast_control("turn on the hallway light")
    assert is_exact_fast_control("switch the hallway light off")
    assert is_exact_fast_control("set the living room light to 35%")

    assert not is_exact_fast_control("turn on whichever hallway lights are off")
    assert not is_exact_fast_control("make the hallway warmer")
    assert not is_exact_fast_control("set heating in the hallway to 20 degrees")
    assert not is_exact_fast_control("turn on the light near the sofa")


class FakePending:
    async def get(self, _session_id):
        return None


class FakeContexts:
    @staticmethod
    def session_id(_request):
        return "test-session"


class FakeControlAgent:
    pending = FakePending()
    contexts = FakeContexts()


class FakeOllama:
    def __init__(self):
        self.calls = []

    async def answer_with_planner(self, query, history):
        self.calls.append((query, history))
        return {"success": True, "message": "Done", "tools_used": [{"name": "hub_command_device"}]}


class FakeApplication:
    VERSION = "test"
    OPTIONS = {"ai_first_control_timeout_seconds": 5}

    def __init__(self):
        self.ollama = FakeOllama()
        self.calls = []

        async def initial_ask(request):
            self.calls.append(("control", request.query))
            return {
                "success": True,
                "route": "control-agent+mcp",
                "tools_used": [{"name": "hub_call_device_command", "success": True}],
            }

        self.ask = initial_ask

    @staticmethod
    def option_bool(_name, default=False):
        return default


def request(query):
    return SimpleNamespace(query=query, history=[])


def test_non_trivial_control_uses_terminal_control_agent():
    application = FakeApplication()

    async def legacy_ask(req):
        application.calls.append(("legacy", req.query))
        return {"success": True, "route": "legacy"}

    install_control_agent_gate(application, FakeControlAgent(), legacy_ask)
    query = "turn on the hallway light near the stairs"
    answer = asyncio.run(application.ask(request(query)))

    assert answer["route"] == "control-agent+mcp"
    assert not application.ollama.calls
    assert application.calls == [("control", query)]


def test_exact_control_keeps_fast_verified_path():
    application = FakeApplication()

    async def legacy_ask(req):
        application.calls.append(("legacy", req.query))
        return {"success": True, "route": "legacy"}

    install_control_agent_gate(application, FakeControlAgent(), legacy_ask)
    answer = asyncio.run(application.ask(request("turn on the hallway light")))

    assert answer["route"] == "control-agent+mcp"
    assert not application.ollama.calls
    assert application.calls == [("control", "turn on the hallway light")]


def test_control_agent_does_not_depend_on_ai_tool_planner():
    application = FakeApplication()

    async def fail(_query, _history):
        raise TimeoutError("planner unavailable")

    application.ollama.answer_with_planner = fail

    async def legacy_ask(req):
        application.calls.append(("legacy", req.query))
        return {"success": True, "route": "legacy"}

    install_control_agent_gate(application, FakeControlAgent(), legacy_ask)
    query = "turn on the hallway light near the stairs"
    answer = asyncio.run(application.ask(request(query)))

    assert answer["route"] == "control-agent+mcp"
    assert "ai_first_control_fallback" not in answer
    assert not application.ollama.calls
    assert application.calls == [("control", query)]
