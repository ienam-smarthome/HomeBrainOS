from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from answer_guard_registry import AnswerGuardRegistry
from home_summary_consistency_guard import build_home_summary_consistency_guard


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def run(coro):
    return asyncio.run(coro)


def test_home_summary_guard_leaves_unrelated_queries_unchanged():
    async def call_tool(name, arguments):
        raise AssertionError("MCP should not be called for unrelated queries")

    application = SimpleNamespace(mcp=SimpleNamespace(call_tool=call_tool))
    guard = build_home_summary_consistency_guard(application)
    original = {"route": "ollama+mcp", "message": "Everything is calm."}

    answer = run(guard(SimpleNamespace(query="List my devices"), original))

    assert answer == original
    assert answer is not original


def test_home_summary_guard_runs_through_registry_once():
    calls = []

    async def call_tool(name, arguments):
        calls.append((name, arguments))
        return SimpleNamespace(
            is_error=False,
            data={
                "devices": [
                    {
                        "label": "Hallway Motion",
                        "currentStates": {"motion": "active"},
                    }
                ]
            },
        )

    async def base(request):
        return {
            "route": "ollama+mcp",
            "message": "No motion is active. Heating is on.",
        }

    application = SimpleNamespace(
        ask=base,
        mcp=SimpleNamespace(call_tool=call_tool),
    )
    registry = AnswerGuardRegistry(application)
    registry.register_guard(
        "home-summary-consistency",
        build_home_summary_consistency_guard(application),
    )
    registry.install()

    answer = run(application.ask(SimpleNamespace(query="What's happening at home?")))

    assert calls == [("hub_list_devices", {})]
    assert "Heating is on." in answer["message"]
    assert "Hallway Motion" in answer["message"]
    assert answer["home_summary_motion_corrected"] is True


def test_public_entrypoint_keeps_home_summary_registry_in_original_position():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    registry_pos = source.index("home_summary_guard_registry = AnswerGuardRegistry")
    thermostat_pos = source.index("thermostat_summary_guard =")
    execution_pos = source.index("answer_guard_registry = AnswerGuardRegistry")

    assert registry_pos < thermostat_pos < execution_pos
    assert "build_home_summary_consistency_guard(_core.application)" in source
    assert "install_home_summary_consistency_guard" not in source
