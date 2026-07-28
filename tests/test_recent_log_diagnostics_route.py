from __future__ import annotations

import asyncio
from types import SimpleNamespace

from recent_log_diagnostics_route import (
    build_recent_log_diagnostics_terminal_route,
    is_recent_log_diagnostics_query,
)


class TraceStore:
    def __init__(self, rows):
        self.rows = rows

    def recent(self):
        return list(self.rows)


def test_log_diagnostics_query_matches_domain_not_home_attention():
    assert is_recent_log_diagnostics_query("Check HomeBrain logs for any issues")
    assert is_recent_log_diagnostics_query("Review HomeBrain errors")
    assert is_recent_log_diagnostics_query("Show request diagnostics")
    assert is_recent_log_diagnostics_query("Inspect assistant warnings")
    assert not is_recent_log_diagnostics_query("Check logs for any issues")
    assert not is_recent_log_diagnostics_query("Check the home for any issues")


def test_log_diagnostics_reports_bounded_request_errors_without_claiming_supervisor_logs():
    route = build_recent_log_diagnostics_terminal_route(
        SimpleNamespace(VERSION="0.10.188"),
        TraceStore(
            [
                {
                    "query": "show power devices",
                    "final_route": "server-error",
                    "exception_type": "AttributeError",
                    "error": "str has no attribute get",
                },
                {"query": "lights on", "final_route": "mcp-fast"},
            ]
        ),
    )

    answer = asyncio.run(
        route(SimpleNamespace(query="Check HomeBrain request diagnostics"))
    )

    assert answer is not None
    assert answer["route"] == "homebrain-recent-request-diagnostics"
    assert answer["error_count"] == 1
    assert answer["model"] is None
    assert "last 2 recorded HomeBrain requests" in answer["message"]
    assert "Supervisor" not in answer["message"].split(".")[0]
    assert '"supervisor_logs_checked": false' in answer["technical"].lower()


def test_log_diagnostics_falls_through_for_household_attention_query():
    route = build_recent_log_diagnostics_terminal_route(
        SimpleNamespace(VERSION="test"),
        TraceStore([]),
    )

    answer = asyncio.run(route(SimpleNamespace(query="What needs attention at home?")))

    assert answer is None


def test_log_diagnostics_falls_through_for_ambiguous_bare_log_query():
    route = build_recent_log_diagnostics_terminal_route(
        SimpleNamespace(VERSION="test"),
        TraceStore([]),
    )

    answer = asyncio.run(route(SimpleNamespace(query="Check logs for any issues")))

    assert answer is None
