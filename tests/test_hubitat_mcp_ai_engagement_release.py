from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_webui import patch_page  # noqa: E402
from device_presentation import device_icon  # noqa: E402
from fast_fallback_engagement import (  # noqa: E402
    FastFallbackRouter,
    _ROOM_LIST_QUERY,
)
from mcp_client import MCPToolResult  # noqa: E402
from ollama_engagement import (  # noqa: E402
    _AI_INSIGHT_QUERY,
    install_ollama_engagement,
    install_ollama_help_terminal_route,
)
from webui import render_page  # noqa: E402


def _result(data: Any) -> MCPToolResult:
    return MCPToolResult(
        name="hub_list_rooms",
        arguments={},
        raw={},
        text="",
        data=data,
        is_error=False,
    )


def test_device_inventory_icons_are_specific_to_live_device_type():
    samples = [
        ({"label": "Shower Light"}, {"switch": "off"}, "💡"),
        ({"label": "Bedroom 1 FP300 battery"}, {"battery": 100}, "🔋"),
        ({"label": "Aqara Light Sensor T1"}, {"illuminance": 12}, "☀️"),
        ({"label": "Bedroom 1 FP300 Humidity"}, {"humidity": 46}, "💧"),
        ({"label": "Bedroom 1 Meter"}, {"temperature": 22.5}, "🌡️"),
        ({"label": "Bedroom 3 Presence Sensor"}, {"presence": "present"}, "📍"),
        ({"label": "Bedroom 1 FP300"}, {"motion": "active"}, "🏃"),
        ({"label": "Hub Info (C8 Pro)"}, {"temperature": 44.7}, "🧠"),
        ({"label": "TV"}, {"switch": "on", "power": 75}, "⚡"),
        ({"label": "Bedroom 1 socket"}, {"switch": "off", "power": 0}, "🔌"),
    ]

    assert [device_icon(item, attrs) for item, attrs, _ in samples] == [
        expected for _, _, expected in samples
    ]


def test_show_rooms_is_a_direct_room_inventory_query():
    assert _ROOM_LIST_QUERY.match("show rooms")
    assert _ROOM_LIST_QUERY.match("List my Hubitat rooms")
    assert _ROOM_LIST_QUERY.match("show all rooms and device counts")


def test_room_inventory_executes_hidden_room_tool_and_presents_cards():
    router = object.__new__(FastFallbackRouter)
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def execute(primary: str, gateway: str, arguments: dict[str, Any]):
        calls.append((primary, gateway, arguments))
        return _result(
            {
                "rooms": [
                    {"id": "1", "name": "Bathroom", "deviceCount": 4},
                    {"id": "2", "name": "Bedroom 1", "deviceCount": 7},
                ]
            }
        )

    router._execute_catalog_tool = execute  # type: ignore[method-assign]
    answer = asyncio.run(router._rooms_inventory())

    assert calls == [("hub_list_rooms", "hub_read_rooms", {})]
    assert answer["success"] is True
    assert answer["intent"] == "fallback-rooms"
    assert answer["display"]["title"] == "Hubitat rooms"
    assert [item["title"] for item in answer["display"]["items"]] == [
        "Bathroom",
        "Bedroom 1",
    ]
    assert "Call again with tool=" not in answer["message"]


def test_ai_insight_button_query_is_recognised():
    assert _AI_INSIGHT_QUERY.match("What looks unusual at home right now?")
    assert _AI_INSIGHT_QUERY.match("Analyse my home now")
    assert _AI_INSIGHT_QUERY.match("Give me an AI home insight")


def test_ollama_guide_insight_and_explicit_override():
    calls: list[tuple[str, Any]] = []

    async def original_ask(request: Any) -> dict[str, Any]:
        calls.append(("fallback", request.query))
        return {"success": True, "route": "mcp-fast", "message": "Fallback"}

    class FakeOllama:
        async def answer(self, query: str, history: list[dict[str, str]]):
            calls.append(("ollama", (query, history)))
            return {
                "success": True,
                "route": "ollama+mcp",
                "message": "AI answer",
                "model": "qwen3.5:9b",
            }

    class FakeSnapshot:
        async def answer(self, query: str):
            calls.append(("snapshot", query))
            return {
                "success": True,
                "route": "ollama+snapshot",
                "message": "Home insight",
            }

    application = SimpleNamespace(
        ask=original_ask,
        ollama=FakeOllama(),
        OPTIONS={
            "ollama_model": "qwen3.5:9b",
            "ollama_agent_timeout_seconds": 60,
        },
        VERSION="0.4.8-alpha",
    )
    install_ollama_engagement(application, FakeSnapshot())

    guide = asyncio.run(
        application.ask(SimpleNamespace(query="What can Ollama help with?", history=[]))
    )
    insight = asyncio.run(
        application.ask(
            SimpleNamespace(
                query="What looks unusual at home right now?",
                history=[],
            )
        )
    )
    forced = asyncio.run(
        application.ask(
            SimpleNamespace(
                query="Ask Ollama: compare the bedroom temperatures",
                history=[SimpleNamespace(role="user", content="Previous question")],
            )
        )
    )

    assert guide["intent"] == "ollama-question-guide"
    assert guide["display"]["title"] == "What Ollama answers"
    assert insight["route"] == "ollama+snapshot"
    assert insight["engagement_mode"] == "ai-home-insight"
    assert forced["route"] == "ollama+mcp"
    assert forced["forced_ollama"] is True
    assert forced["resolved_query"] == "compare the bedroom temperatures"
    assert ("snapshot", "What looks unusual at home right now?") in calls
    assert any(
        kind == "ollama" and value[0] == "compare the bedroom temperatures"
        for kind, value in calls
    )


def test_question_guide_is_terminal_outside_unified_agent():
    calls: list[str] = []

    async def unified_agent(_request: Any):
        calls.append("unified-agent")
        raise TimeoutError("planner must not run for the static question guide")

    application = SimpleNamespace(
        ask=unified_agent,
        OPTIONS={"ollama_model": "gemma4:31b-cloud"},
        VERSION="test",
    )
    install_ollama_help_terminal_route(application)

    answer = asyncio.run(
        application.ask(SimpleNamespace(query="What can Ollama help with?", history=[]))
    )

    assert calls == []
    assert answer["success"] is True
    assert answer["route"] == "system"
    assert answer["intent"] == "ollama-question-guide"
    assert answer["model"] is None
    assert answer["answered_by"] == "HomeBrain AI question guide"


def test_webui_exposes_ai_shortcuts_and_friendly_route_labels():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.8-alpha"))

    assert "AI home insight" in page
    assert "AI question guide" in page
    assert "Ask Hubitat, or start with Ask Ollama:" in page
    assert page.count("function routeLabel(route)") == 1
    assert "Ollama + Hubitat" in page
    assert "Hubitat live" in page


def test_webui_renderer_keeps_question_status_and_cannot_blank_on_route_label():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.8-alpha"))

    route_helper = page.index("function routeLabel(route)")
    answer_renderer = page.index("function showAnswer(answer)")

    assert route_helper < answer_renderer
    assert "typeof routeLabel==='function'" in page
    assert "Asked: '+query" in page
    assert "Asked: '+asked" in page
    assert "Contacting Hubitat…" in page
    assert "Working on: '+query" not in page
    assert "function itemList(items)" in page
    assert "function showAnswer(answer){clearOutput();const asked=" in page
