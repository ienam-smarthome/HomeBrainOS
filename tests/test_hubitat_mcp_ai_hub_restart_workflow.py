from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from hub_restart_workflow import install_hub_restart_workflow  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from automation_recommendation_webui import install_automation_recommendation_webui  # noqa: E402
from webui_homebrain import render_homebrain_page  # noqa: E402


def request(query: str, session_id: str = "browser-1"):
    return SimpleNamespace(query=query, session_id=session_id, history=[])


class FakeMCP:
    def __init__(self, *, error: bool = False) -> None:
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        self.calls.append((name, arguments))
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="Admin writes disabled" if self.error else "Restart accepted",
            data={},
            is_error=self.error,
        )


def make_application(*, error: bool = False):
    fallback_calls: list[str] = []

    async def fallback(value: Any):
        fallback_calls.append(value.query)
        return {"success": True, "route": "fallback"}

    application = SimpleNamespace(ask=fallback, mcp=FakeMCP(error=error))
    install_hub_restart_workflow(application)
    return application, fallback_calls


def test_restart_requires_a_separate_same_session_yes_then_calls_confirmed_tool_once():
    async def scenario():
        application, fallback_calls = make_application()
        prompt = await application.ask(request("restart the hub"))
        confirmed = await application.ask(request("yes"))
        return application, fallback_calls, prompt, confirmed

    application, fallback_calls, prompt, confirmed = asyncio.run(scenario())
    assert prompt["confirmation_required"] is True
    assert prompt["intent"] == "hub-restart-confirmation-required"
    assert prompt["message"].startswith("Do you want to restart the Hubitat hub now?")
    assert prompt["display"]["title"] == "Restart the Hubitat hub now?"
    assert prompt["display"]["actions"] == [
        {
            "label": "Yes — restart hub",
            "query": "Yes",
            "tone": "danger",
            "icon": "🔄",
        },
        {
            "label": "No — cancel",
            "query": "No",
            "tone": "secondary",
            "icon": "✖️",
        },
    ]
    assert application.mcp.calls == [("hub_reboot", {"confirm": True})]
    assert confirmed["success"] is True
    assert confirmed["intent"] == "hub-restart-requested"
    assert fallback_calls == []


def test_restart_no_cancels_and_unrelated_session_yes_does_not_execute():
    async def scenario():
        application, fallback_calls = make_application()
        await application.ask(request("please reboot my Hubitat hub"))
        unrelated = await application.ask(request("yes", session_id="browser-2"))
        cancelled = await application.ask(request("no"))
        return application, fallback_calls, unrelated, cancelled

    application, fallback_calls, unrelated, cancelled = asyncio.run(scenario())
    assert unrelated["route"] == "fallback"
    assert cancelled["intent"] == "hub-restart-cancelled"
    assert application.mcp.calls == []
    assert fallback_calls == ["yes"]


def test_rejected_restart_reports_failure_without_retry():
    async def scenario():
        application, _ = make_application(error=True)
        await application.ask(request("reboot hub"))
        answer = await application.ask(request("confirm"))
        return application, answer

    application, answer = asyncio.run(scenario())
    assert answer["success"] is False
    assert answer["intent"] == "hub-restart-failed"
    assert "Admin writes disabled" in answer["message"]
    assert application.mcp.calls == [("hub_reboot", {"confirm": True})]


def test_release_installs_restart_workflow_outside_ai_routes():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    assert "from hub_restart_workflow import install_hub_restart_workflow" in entrypoint
    assert "hub_restart_workflow = install_hub_restart_workflow(" in entrypoint
    assert entrypoint.index("install_unified_mcp_agent_orchestrator") < entrypoint.index(
        "hub_restart_workflow = install_hub_restart_workflow("
    )


def test_display_items_with_queries_are_clickable_and_keyboard_accessible():
    class Module:
        @staticmethod
        def patch_page(page: str) -> str:
            return page

    install_automation_recommendation_webui(Module)
    page = Module.patch_page(render_homebrain_page("HomeBrain", "test"))

    assert ".result-item.clickable" in page
    assert "row.setAttribute('role','button')" in page
    assert "row.setAttribute('aria-label'" in page
    assert "row.onkeydown" in page
    assert "submit(query)" in page
