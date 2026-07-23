from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from named_app_control import install_named_app_controller, parse_named_app_intent  # noqa: E402


class Result:
    def __init__(self, data, *, is_error=False, text=""):
        self.data = data
        self.is_error = is_error
        self.text = text


class Tool:
    def __init__(self, name):
        self.name = name


class FakeMCP:
    def __init__(self):
        self.disabled = False
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_list_apps":
            return Result(
                {
                    "apps": [
                        {
                            "id": 101,
                            "label": "01. Humidity Controller",
                            "disabled": self.disabled,
                            "status": "disabled" if self.disabled else "active",
                            "type": "Humidity Extraction Controller",
                        }
                    ]
                }
            )
        if name == "hub_set_app_disabled":
            self.disabled = bool(arguments["disabled"])
            return Result({"success": True, "appId": 101, "disabled": self.disabled})
        return Result({}, is_error=True, text="unsupported")

    async def list_tools(self):
        return [Tool("hub_list_apps"), Tool("hub_set_app_disabled")]

    async def gateway_map(self):
        return {}


def make_app():
    async def fallback(_request):
        return {"route": "fallback"}

    return SimpleNamespace(mcp=FakeMCP(), ask=fallback)


def ask(app, query):
    return asyncio.run(app.ask(SimpleNamespace(query=query)))


def test_parser_requires_explicit_app_target():
    assert parse_named_app_intent("disable app Humidity Controller") is not None
    assert parse_named_app_intent("confirm disable app id 101").confirmed is True
    assert parse_named_app_intent("disable bedroom light") is None


def test_list_apps_reports_live_state():
    app = make_app()
    install_named_app_controller(app)
    answer = ask(app, "List Hubitat apps")
    assert answer["route"] == "mcp-app-inventory"
    assert "1 enabled" in answer["message"]


def test_exact_app_write_requires_confirmation():
    app = make_app()
    install_named_app_controller(app)
    answer = ask(app, "disable app 01. Humidity Controller")
    assert answer["route"] == "mcp-app-confirmation"
    assert answer["technical"]["confirmation_required"] is True
    assert [name for name, _ in app.mcp.calls] == ["hub_list_apps"]
    actions = answer["display"]["actions"]
    assert actions[0]["query"] == "confirm disable app id 101"
    assert actions[1]["cancel"] is True


def test_confirmed_disable_writes_and_verifies_response_and_readback():
    app = make_app()
    install_named_app_controller(app)
    answer = ask(app, "confirm disable app id 101")
    assert answer["route"] == "mcp-app-control"
    assert answer["intent"] == "hubitat-app-disable-verified"
    assert answer["technical"]["command_verified"] is True
    assert answer["technical"]["inventory_readback_verified"] is True
    assert answer["technical"]["post_state_verified"] is True
    assert [name for name, _ in app.mcp.calls] == [
        "hub_list_apps",
        "hub_set_app_disabled",
        "hub_list_apps",
    ]


def test_partial_match_offers_clickable_selection_then_confirmation():
    app = make_app()
    install_named_app_controller(app)
    answer = ask(app, "disable app humidity")
    assert answer["route"] == "mcp-app-clarification"
    assert answer["display"]["actions"][0]["query"] == "disable app id 101"
