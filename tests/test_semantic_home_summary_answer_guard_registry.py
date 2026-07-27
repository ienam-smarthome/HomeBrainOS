from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from answer_guard_registry import AnswerGuardRegistry
from semantic_home_summary_registry import build_semantic_home_summary_terminal_route


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def run(coro):
    return asyncio.run(coro)


class Broker:
    async def collect(self, limit=20):
        return {
            "success": True,
            "data": {
                "mode": "Home",
                "motion": {"active_count": 0, "active": []},
                "contacts": {"open_count": 0, "open": []},
                "lights": {"on_count": 0, "on": []},
                "low_batteries": {"count": 0, "items": []},
                "heating": [],
            },
            "required_facts": [],
            "tools_used": ["home_snapshot"],
        }


class Snapshot:
    pass


def _application():
    async def base(request):
        return {"message": f"base:{request.query}"}

    app = SimpleNamespace(
        ask=base,
        ollama=SimpleNamespace(cloud_model="", model=""),
    )
    return app


def test_exact_home_summary_query_returns_terminal_answer(monkeypatch):
    app = _application()
    route = build_semantic_home_summary_terminal_route(app, Snapshot())
    monkeypatch.setattr(app.semantic_home_evidence_broker, "collect", Broker().collect)

    answer = run(route(SimpleNamespace(query="What is happening at home?")))

    assert answer is not None
    assert answer["route"] == "ai-semantic-home-evidence"
    assert answer["intent"] == "home-summary"
    assert answer["message"] == "It's Home mode. No motion sensors are currently active."


def test_unmatched_query_delegates_through_registry(monkeypatch):
    app = _application()
    route = build_semantic_home_summary_terminal_route(app, Snapshot())
    monkeypatch.setattr(app.semantic_home_evidence_broker, "collect", Broker().collect)
    registry = AnswerGuardRegistry(app)
    registry.register_terminal_route("semantic-home-summary", route)
    handler = registry.install()

    answer = run(handler(SimpleNamespace(query="Is the kitchen light on?")))

    assert answer == {"message": "base:Is the kitchen light on?"}


def test_entrypoint_uses_summary_terminal_route_before_semantic_query_route():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "build_semantic_home_summary_terminal_route" in source
    assert '"semantic-home-summary-registry"' in source
    assert "install_semantic_home_summary_agent" not in source
    assert source.index("semantic-home-summary-registry") < source.index(
        "semantic-home-query-registry"
    )
