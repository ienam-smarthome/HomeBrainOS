from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)
sys.path.insert(0, str(APP_DIR))

import mcp_agent_orchestrator as orchestrator


class Request:
    query = "How much power is unaccounted for?"
    history = []
    session_id = "test"


def test_power_accounting_uses_specific_orchestrator_label(monkeypatch):
    async def terminal(_application, _query):
        return {
            "success": True,
            "route": "mcp-power-accounting",
            "intent": "verified-power-accounting",
            "message": "Power accounting result",
        }

    monkeypatch.setattr(
        orchestrator,
        "_answer_terminal_entity_read",
        terminal,
    )
    monkeypatch.setattr(
        orchestrator,
        "should_use_unified_agent",
        lambda _query: True,
    )

    async def original(_request):
        raise AssertionError(
            "The original route must not run"
        )

    application = SimpleNamespace(
        ask=original,
        VERSION="0.10.119",
    )

    orchestrator.install_unified_mcp_agent_orchestrator(
        application
    )

    answer = asyncio.run(
        application.ask(Request())
    )

    assert answer["route"] == "mcp-power-accounting"
    assert answer["agent_orchestrator"] == (
        "deterministic-power-accounting"
    )


def test_normal_entity_read_keeps_entity_label(monkeypatch):
    async def terminal(_application, _query):
        return {
            "success": True,
            "route": "mcp-fast",
            "intent": "device-attribute-read",
            "message": "Fridge is 97 W.",
        }

    monkeypatch.setattr(
        orchestrator,
        "_answer_terminal_entity_read",
        terminal,
    )
    monkeypatch.setattr(
        orchestrator,
        "should_use_unified_agent",
        lambda _query: True,
    )

    async def original(_request):
        raise AssertionError(
            "The original route must not run"
        )

    application = SimpleNamespace(
        ask=original,
        VERSION="0.10.119",
    )

    orchestrator.install_unified_mcp_agent_orchestrator(
        application
    )

    answer = asyncio.run(
        application.ask(Request())
    )

    assert answer["agent_orchestrator"] == (
        "deterministic-entity-read"
    )
