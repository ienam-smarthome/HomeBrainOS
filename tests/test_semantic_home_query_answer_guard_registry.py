from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from answer_guard_registry import AnswerGuardRegistry
from semantic_home_query_registry import build_semantic_home_query_terminal_route


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def run(coro):
    return asyncio.run(coro)


def test_semantic_home_query_route_returns_none_for_write_passthrough():
    class Broker:
        async def collect(self, limit):
            raise AssertionError("write-like passthrough must not collect evidence")

    app = SimpleNamespace(
        semantic_home_evidence_broker=Broker(),
        ollama=SimpleNamespace(),
    )
    route = build_semantic_home_query_terminal_route(app)

    assert run(route(SimpleNamespace(query="turn off the kitchen light"))) is None


def test_semantic_home_summary_runs_as_registry_terminal_route():
    class Response:
        def __init__(self, content):
            self._content = content

        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": self._content}}

    class Client:
        calls = 0

        async def post(self, url, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return Response('{"intent":"home_summary"}')
            return Response("Everything looks calm at home.")

    class Broker:
        async def collect(self, limit):
            assert limit == 20
            return {
                "success": True,
                "data": {"lights": {"on_count": 0}, "contacts": {"open_count": 0}},
                "tools_used": ["home_snapshot"],
            }

    app = SimpleNamespace(
        semantic_home_evidence_broker=Broker(),
        ollama=SimpleNamespace(
            _http=Client(),
            planner_model="test-model",
            cloud_model="test-model",
            model="test-model",
            base_url="http://ollama",
            keep_alive="30m",
        ),
    )
    registry = AnswerGuardRegistry(SimpleNamespace(ask=None))
    registry._application.ask = lambda request: None
    registry.register_terminal_route(
        "semantic-home-query",
        build_semantic_home_query_terminal_route(app),
    )
    handler = registry.install()

    answer = run(handler(SimpleNamespace(query="what is happening at home?")))

    assert answer["route"] == "ai-semantic-home-evidence"
    assert answer["intent"] == "home-summary"
    assert answer["tools_used"] == ["home_snapshot"]


def test_public_entrypoint_uses_semantic_home_query_registry_at_same_position():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "from semantic_home_query_registry import build_semantic_home_query_terminal_route" in source
    assert 'register_terminal_route(\n    "semantic-home-query",' in source
    assert '"semantic-home-query-registry",\n    semantic_home_query_registry.install,' in source
    assert "install_semantic_home_query_router" not in source
    assert source.index("semantic-home-summary") < source.index("semantic-home-query-registry")
    assert source.index("semantic-home-query-registry") < source.index("home-summary-guard-registry")
