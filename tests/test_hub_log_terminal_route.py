from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from final_read_terminal_routes import build_hub_logs_route


class Fallback:
    def __init__(self):
        self.queries = []

    async def answer(self, query):
        self.queries.append(query)
        return {
            "success": True,
            "route": "mcp-fast",
            "intent": "fallback-hub-logs",
            "message": "No matching recent hub log entries were returned.",
            "model": None,
        }


def test_bare_log_issue_query_reads_hub_logs_before_semantic_attention():
    fallback = Fallback()
    route = build_hub_logs_route(
        SimpleNamespace(fallback=fallback, VERSION="test")
    )

    answer = asyncio.run(route(SimpleNamespace(query="Check logs for any issues")))

    assert answer is not None
    assert fallback.queries == ["Check logs for any issues"]
    assert answer["intent"] == "fallback-hub-logs"
    assert answer["selected_tools"] == ["hub_get_logs"]
    assert answer["answered_by"] == "Deterministic Hubitat log diagnostics"


def test_natural_log_issue_purpose_clause_still_reads_hub_logs():
    fallback = Fallback()
    route = build_hub_logs_route(
        SimpleNamespace(fallback=fallback, VERSION="test")
    )

    queries = (
        "Check logs to see if there are any issues",
        "Review the hub logs to check whether there are warnings",
        "Inspect logs and see if there are any errors",
    )
    for query in queries:
        answer = asyncio.run(route(SimpleNamespace(query=query)))
        assert answer is not None, query
        assert answer["intent"] == "fallback-hub-logs", query
        assert answer["selected_tools"] == ["hub_get_logs"], query

    assert fallback.queries == list(queries)


def test_homebrain_request_diagnostics_remain_separate():
    fallback = Fallback()
    route = build_hub_logs_route(
        SimpleNamespace(fallback=fallback, VERSION="test")
    )

    answer = asyncio.run(
        route(SimpleNamespace(query="Check HomeBrain request diagnostics"))
    )

    assert answer is None
    assert fallback.queries == []


def test_public_entrypoint_registers_hub_logs_in_outer_read_registry():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"
    ).read_text(encoding="utf-8")

    assert source.index('"hub-logs"') < source.index('"device-health-fast-route"')
    assert source.index('"hub-logs"') > source.index('"semantic-home-query"')
