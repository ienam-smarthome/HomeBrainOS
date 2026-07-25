from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from routing import Route, RouteDecision, RouteRegistry


def route(
    name: str,
    priority: int,
    *,
    matches: bool,
    reason: str | None = None,
) -> Route:
    return Route(
        name=name,
        priority=priority,
        matcher=lambda _query, _context: matches,
        reason=reason or f"{name} matched",
    )


def test_registry_selects_highest_priority_matching_route():
    registry = RouteRegistry(
        [
            route("ai-evidence", 500, matches=True),
            route("entity-read", 850, matches=True),
            route("control", 900, matches=True),
        ]
    )

    decision = registry.decide("test")

    assert decision is not None
    assert decision.route_name == "control"
    assert decision.priority == 900
    assert decision.considered_routes == ("control",)


def test_registry_skips_nonmatching_higher_priority_routes():
    registry = RouteRegistry(
        [
            route("pending-confirmation", 1000, matches=False),
            route("hub-firmware", 950, matches=False),
            route("entity-read", 850, matches=True),
            route("ai-evidence", 500, matches=True),
        ]
    )

    decision = registry.decide("What is the bathroom humidity?")

    assert decision is not None
    assert decision.route_name == "entity-read"
    assert decision.considered_routes == (
        "pending-confirmation",
        "hub-firmware",
        "entity-read",
    )


def test_equal_priorities_preserve_registration_order():
    registry = RouteRegistry()

    registry.register(route("first", 800, matches=True))
    registry.register(route("second", 800, matches=True))

    decision = registry.decide("test")

    assert decision is not None
    assert decision.route_name == "first"


def test_matcher_receives_query_and_context():
    observed = {}

    def matcher(query, context):
        observed["query"] = query
        observed["session_id"] = context["session_id"]
        return context["pending"] is True

    registry = RouteRegistry(
        [
            Route(
                name="pending-confirmation",
                priority=1000,
                matcher=matcher,
                reason="session has a pending confirmation",
            )
        ]
    )

    decision = registry.decide(
        "yes",
        {
            "session_id": "browser-1",
            "pending": True,
        },
    )

    assert decision is not None
    assert observed == {
        "query": "yes",
        "session_id": "browser-1",
    }


def test_no_match_returns_none():
    registry = RouteRegistry(
        [
            route("control", 900, matches=False),
            route("ai-evidence", 500, matches=False),
        ]
    )

    assert registry.decide("unmatched") is None


def test_decision_exposes_existing_trace_field_names():
    decision = RouteDecision(
        route_name="entity-read",
        priority=850,
        reason="authoritative deterministic entity read",
        considered_routes=("control", "entity-read"),
        metadata={"family": "read"},
    )

    assert decision.as_dict() == {
        "route_selected": "entity-read",
        "route_priority": 850,
        "route_reason": "authoritative deterministic entity read",
        "routes_considered": ["control", "entity-read"],
        "route_metadata": {"family": "read"},
    }


def test_registry_rejects_duplicate_route_names():
    registry = RouteRegistry([route("control", 900, matches=True)])

    with pytest.raises(ValueError, match="already registered"):
        registry.register(route("control", 500, matches=True))


def test_registry_can_unregister_route():
    registry = RouteRegistry(
        [
            route("control", 900, matches=True),
            route("ai-evidence", 500, matches=True),
        ]
    )

    assert registry.unregister("control") is True
    assert registry.unregister("missing") is False
    assert registry.decide("test").route_name == "ai-evidence"


def test_registry_description_is_priority_ordered():
    registry = RouteRegistry(
        [
            route("ai-evidence", 500, matches=False),
            route("pending-confirmation", 1000, matches=False),
            route("entity-read", 850, matches=False),
        ]
    )

    assert [item["name"] for item in registry.describe()] == [
        "pending-confirmation",
        "entity-read",
        "ai-evidence",
    ]
