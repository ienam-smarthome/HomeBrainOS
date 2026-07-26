from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from named_app_control import install_named_app_controller, parse_app_intent  # noqa: E402


class Result:
    def __init__(self, data, *, is_error=False, text=""):
        self.data = data
        self.is_error = is_error
        self.text = text


class FakeMCP:
    def __init__(self):
        self.calls = []
        self.disabled = False

    async def list_tools(self):
        return [SimpleNamespace(name="hub_list_apps"), SimpleNamespace(name="hub_set_app_disabled")]

    async def gateway_map(self):
        return {}

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
                        },
                        {
                            "id": 202,
                            "label": "Battery Monitor",
                            "disabled": True,
                            "status": "disabled",
                            "type": "Battery Monitor 2.0",
                        },
                    ]
                }
            )
        if name == "hub_set_app_disabled":
            self.disabled = bool(arguments["disabled"])
            return Result({"success": True, "appId": arguments["appId"], "disabled": self.disabled})
        raise AssertionError(name)


def make_app(mcp=None):
    async def fallback(_request):
        return {"route": "fallback"}

    app = SimpleNamespace(mcp=mcp or FakeMCP(), ask=fallback)
    install_named_app_controller(app)
    return app


def test_parser_requires_app_word_for_writes():
    assert parse_app_intent("disable bedroom light") is None
    assert parse_app_intent("disable Humidity Controller app") is not None
    assert parse_app_intent("confirm disable app id 101").confirmed is True
    assert parse_app_intent("list disabled apps").state_filter == "disabled"


def test_list_disabled_apps_is_read_only():
    app = make_app()
    answer = asyncio.run(app.ask(SimpleNamespace(query="List disabled apps")))
    assert answer["route"] == "mcp-app-inventory"
    assert "1 apps returned" in answer["message"]
    assert [name for name, _ in app.mcp.calls] == ["hub_list_apps"]


def test_exact_app_requires_confirmation_before_write():
    app = make_app()
    answer = asyncio.run(app.ask(SimpleNamespace(query="Disable Humidity Controller app")))
    assert answer["route"] == "mcp-app-confirmation"
    assert answer["display"]["actions"][0]["query"] == "confirm disable app id 101"
    assert [name for name, _ in app.mcp.calls] == ["hub_list_apps"]


def test_confirmed_app_disable_writes_exact_id_and_verifies():
    app = make_app()
    answer = asyncio.run(app.ask(SimpleNamespace(query="confirm disable app id 101")))
    assert answer["route"] == "mcp-app-control"
    assert answer["success"] is True
    technical = answer["technical"]
    if isinstance(technical, str):
        technical = json.loads(technical)
    assert technical["post_state_verified"] is True
    assert technical["arguments"] == {"appId": 101, "disabled": True}
    assert [name for name, _ in app.mcp.calls] == [
        "hub_list_apps",
        "hub_set_app_disabled",
        "hub_list_apps",
    ]


def test_confirmed_app_disable_uses_inventory_readback_when_write_omits_state():
    class ReadbackMCP(FakeMCP):
        async def call_tool(self, name, arguments):
            if name == "hub_set_app_disabled":
                self.calls.append((name, arguments))
                self.disabled = bool(arguments["disabled"])
                return Result({"success": True, "appId": arguments["appId"]})
            return await super().call_tool(name, arguments)

    app = make_app(ReadbackMCP())
    answer = asyncio.run(app.ask(SimpleNamespace(query="confirm disable app id 101")))
    technical = answer["technical"]
    if isinstance(technical, str):
        technical = json.loads(technical)

    assert answer["intent"] == "app-disable-verified"
    assert technical["command_verified"] is False
    assert technical["inventory_readback_verified"] is True
    assert technical["verification_source"] == "hub_list_apps read-back"
    assert technical["verification_outcome"] == "completed"


def test_confirmed_app_disable_remains_accepted_when_state_is_unavailable():
    class AcceptedMCP(FakeMCP):
        async def call_tool(self, name, arguments):
            if name == "hub_set_app_disabled":
                self.calls.append((name, arguments))
                return Result({"success": True, "appId": arguments["appId"]})
            return await super().call_tool(name, arguments)

    app = make_app(AcceptedMCP())
    answer = asyncio.run(app.ask(SimpleNamespace(query="confirm disable app id 101")))
    technical = answer["technical"]
    if isinstance(technical, str):
        technical = json.loads(technical)

    assert answer["intent"] == "app-disable-accepted"
    assert technical["post_state_verified"] is False
    assert technical["verification_source"] is None
    assert technical["verification_outcome"] == "sent"


def test_partial_match_returns_clickable_selection_without_write():
    app = make_app()
    answer = asyncio.run(app.ask(SimpleNamespace(query="Disable Humidity app")))
    assert answer["route"] == "mcp-app-clarification"
    assert answer["display"]["actions"][0]["query"] == "disable app id 101"
    assert [name for name, _ in app.mcp.calls] == ["hub_list_apps"]
