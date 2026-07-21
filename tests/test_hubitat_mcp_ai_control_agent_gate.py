from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_agent_gate import (  # noqa: E402
    install_control_agent_gate,
    is_explicit_named_multi_control,
)


def request(query: str):
    return SimpleNamespace(query=query, session_id="gate", history=[])


def test_simple_named_conjunction_is_reserved_for_verified_multi_control():
    assert is_explicit_named_multi_control("turn on fan switch and fan boost") is True
    assert is_explicit_named_multi_control("turn off lamp one, lamp two") is True


def test_contextual_or_conditional_conjunction_is_not_bypassed():
    assert is_explicit_named_multi_control("turn on both living room lights") is False
    assert is_explicit_named_multi_control("turn on fan switch and fan boost if humid") is False
    assert is_explicit_named_multi_control("turn off all lights and sockets") is False


def test_non_control_read_bypasses_control_graph_and_direct_named_multi_uses_legacy():
    legacy_queries: list[str] = []
    agent_queries: list[str] = []

    async def legacy_ask(value: Any):
        legacy_queries.append(value.query)
        return {"success": True, "route": "legacy", "message": "legacy"}

    async def control_agent_ask(value: Any):
        agent_queries.append(value.query)
        return {"success": True, "route": "control-agent", "message": "agent"}

    class Pending:
        async def get(self, _session_id: str):
            return None

    control_agent = SimpleNamespace(
        pending=Pending(),
        contexts=SimpleNamespace(session_id=lambda _request: "gate"),
    )
    application = SimpleNamespace(ask=control_agent_ask)
    install_control_agent_gate(application, control_agent, legacy_ask)

    weather = asyncio.run(application.ask(request("what is the weather?")))
    multi = asyncio.run(application.ask(request("turn on fan switch and fan boost")))
    contextual = asyncio.run(application.ask(request("turn off the other one")))

    assert weather["route"] == "legacy"
    assert multi["route"] == "legacy"
    assert multi["control_agent_bypass"] == "verified-named-multi-control"
    assert contextual["route"] == "control-agent"
    assert legacy_queries == [
        "what is the weather?",
        "turn on fan switch and fan boost",
    ]
    assert agent_queries == ["turn off the other one"]


def test_pending_confirmation_reaches_control_agent_even_for_yes_or_number():
    agent_queries: list[str] = []

    async def legacy_ask(_value: Any):
        raise AssertionError("Pending reply must not reach the legacy route")

    async def control_agent_ask(value: Any):
        agent_queries.append(value.query)
        return {"success": True, "route": "control-agent-confirmation"}

    class Pending:
        async def get(self, _session_id: str):
            return object()

    control_agent = SimpleNamespace(
        pending=Pending(),
        contexts=SimpleNamespace(session_id=lambda _request: "gate"),
    )
    application = SimpleNamespace(ask=control_agent_ask)
    install_control_agent_gate(application, control_agent, legacy_ask)

    answer = asyncio.run(application.ask(request("2")))

    assert answer["route"] == "control-agent-confirmation"
    assert agent_queries == ["2"]


def test_pronoun_follow_up_returns_to_the_same_control_agent():
    agent_queries: list[str] = []
    legacy_queries: list[str] = []

    async def legacy_ask(value: Any):
        legacy_queries.append(value.query)
        return {"success": True, "route": "legacy"}

    async def control_agent_ask(value: Any):
        agent_queries.append(value.query)
        return {"success": True, "route": "control-agent"}

    class Pending:
        async def get(self, _session_id: str):
            return None

    control_agent = SimpleNamespace(
        pending=Pending(),
        contexts=SimpleNamespace(session_id=lambda _request: "gate"),
    )
    application = SimpleNamespace(ask=control_agent_ask)
    install_control_agent_gate(application, control_agent, legacy_ask)

    answer = asyncio.run(application.ask(request("turn it off")))

    assert answer["route"] == "control-agent"
    assert agent_queries == ["turn it off"]
    assert legacy_queries == []


def test_release_installs_control_agent_gate():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "from control_agent_gate import install_control_agent_gate" in entrypoint
    assert "legacy_control_ask = application.ask" in entrypoint
    assert "install_control_agent_gate(application, control_agent, legacy_control_ask)" in entrypoint
