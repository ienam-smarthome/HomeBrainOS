from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from named_app_control import install_named_app_controller, parse_app_write_intent  # noqa: E402


def result(name, data, *, error=False):
    return MCPToolResult(name=name, arguments={}, raw={}, text="", data=data, is_error=error)


class FakeMCP:
    def __init__(self):
        self.disabled = False
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            MCPTool("hub_list_apps", "", {}),
            MCPTool("hub_set_app_disabled", "", {}),
        ]

    async def gateway_map(self, refresh=False):
        return {}

    async def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if name == "hub_list_apps":
            return result(name, {"apps": [{"id": 51, "label": "01. Humidity Controller", "disabled": self.disabled, "status": "disabled" if self.disabled else "active", "type": "user"}]})
        if name == "hub_set_app_disabled":
            self.disabled = bool(arguments["disabled"])
            return result(name, {"success": True, "appId": arguments["appId"], "disabled": self.disabled})
        raise AssertionError(name)


def build_app():
    async def fallback(_request):
        return {"route": "fallback"}

    return SimpleNamespace(mcp=FakeMCP(), ask=fallback)


def ask(app, query):
    return asyncio.run(app.ask(SimpleNamespace(query=query)))


def test_parser_supports_confirmed_exact_app_id():
    intent = parse_app_write_intent("confirm disable app id 51")
    assert intent is not None
    assert intent.action == "disable"
    assert intent.confirmed is True


def test_list_apps_reports_enabled_and_disabled_counts():
    app = build_app()
    install_named_app_controller(app)
    answer = ask(app, "List Hubitat apps")
    assert answer["route"] == "mcp-app-inventory"
    assert "1 enabled" in answer["message"]
    assert "0 disabled" in answer["message"]


def test_exact_app_write_requires_clickable_confirmation():
    app = build_app()
    install_named_app_controller(app)
    answer = ask(app, "disable 01. Humidity Controller")
    assert answer["route"] == "mcp-app-confirmation"
    assert app.mcp.calls == [("hub_list_apps", {})]
    assert answer["display"]["actions"][0]["query"] == "confirm disable app id 51"
    assert answer["display"]["actions"][1]["cancel"] is True


def test_confirmed_disable_writes_and_verifies_response_and_inventory():
    app = build_app()
    install_named_app_controller(app)
    answer = ask(app, "confirm disable app id 51")
    assert answer["route"] == "mcp-app-control"
    assert answer["intent"] == "hubitat-app-disable-verified"
    assert answer["technical"]["command_verified"] is True
    assert answer["technical"]["inventory_readback_verified"] is True
    assert app.mcp.calls == [
        ("hub_list_apps", {}),
        ("hub_set_app_disabled", {"appId": 51, "disabled": True}),
        ("hub_list_apps", {}),
    ]


def test_confirmed_enable_restores_a_disabled_app():
    app = build_app()
    app.mcp.disabled = True
    install_named_app_controller(app)
    answer = ask(app, "confirm enable app id 51")
    assert answer["intent"] == "hubitat-app-enable-verified"
    assert app.mcp.disabled is False
    assert answer["technical"]["post_state_verified"] is True


def test_partial_match_offers_selection_without_writing():
    app = build_app()
    install_named_app_controller(app)
    answer = ask(app, "disable humidity")
    assert answer["route"] == "mcp-app-clarification"
    assert answer["display"]["actions"][0]["query"] == "disable app id 51"
    assert not any(name == "hub_set_app_disabled" for name, _ in app.mcp.calls)
