from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_agent_combined_level import install_combined_level_intent  # noqa: E402
from control_agent_gate import install_control_agent_gate  # noqa: E402


class Pending:
    async def get(self, _session_id: str):
        return None


class Contexts:
    @staticmethod
    def session_id(_request: Any) -> str:
        return "agent-first-test"


class ControlAgent:
    pending = Pending()
    contexts = Contexts()


def request(query: str):
    return SimpleNamespace(query=query, session_id="agent-first-test", history=[])


def test_natural_control_reaches_control_agent_before_legacy_answer_route():
    install_combined_level_intent()
    calls: list[str] = []

    async def control_ask(req: Any):
        calls.append("control")
        return {"success": True, "route": "control-agent", "query": req.query}

    async def legacy_ask(req: Any):
        calls.append("legacy")
        return {"success": True, "route": "ollama+mcp", "query": req.query}

    application = SimpleNamespace(ask=control_ask)
    install_control_agent_gate(application, ControlAgent(), legacy_ask)

    answer = asyncio.run(
        application.ask(request("Put bedroom one light at about thirty percent."))
    )

    assert answer["route"] == "control-agent"
    assert calls == ["control"]


def test_read_question_stays_outside_control_agent():
    install_combined_level_intent()
    calls: list[str] = []

    async def control_ask(_req: Any):
        calls.append("control")
        return {"route": "control-agent"}

    async def legacy_ask(_req: Any):
        calls.append("legacy")
        return {"route": "mcp-fast"}

    application = SimpleNamespace(ask=control_ask)
    install_control_agent_gate(application, ControlAgent(), legacy_ask)

    answer = asyncio.run(application.ask(request("What lights are on?")))

    assert answer["route"] == "mcp-fast"
    assert calls == ["legacy"]


def test_proven_named_multi_control_keeps_existing_atomic_path():
    install_combined_level_intent()
    calls: list[str] = []

    async def control_ask(_req: Any):
        calls.append("control")
        return {"route": "control-agent"}

    async def legacy_ask(_req: Any):
        calls.append("legacy")
        return {"route": "mcp-fast"}

    application = SimpleNamespace(ask=control_ask)
    install_control_agent_gate(application, ControlAgent(), legacy_ask)

    answer = asyncio.run(
        application.ask(request("turn on Fan Switch and Fan Boost"))
    )

    assert answer["route"] == "mcp-fast"
    assert answer["control_agent_bypass"] == "verified-named-multi-control"
    assert calls == ["legacy"]
