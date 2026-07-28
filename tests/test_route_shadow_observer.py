from __future__ import annotations

import asyncio
from types import SimpleNamespace

from route_registry import RouteDescriptor, RouteRegistry
from route_shadow_observer import install_route_shadow_observer


class App:
    def __init__(self):
        self.app = SimpleNamespace(get=lambda *args, **kwargs: (lambda fn: fn))

        async def ask(_request):
            return {"route": "actual-route", "message": "ok"}

        self.ask = ask


def test_shadow_observer_records_full_match_set_and_attaches_winner_trace():
    application = App()
    registry = RouteRegistry(
        (
            RouteDescriptor("high", 200, True, lambda q: "power" in q, "high"),
            RouteDescriptor("low", 100, False, lambda q: bool(q), "low"),
        )
    )
    observer = install_route_shadow_observer(application, registry, limit=20)

    answer = asyncio.run(application.ask(SimpleNamespace(query="show power")))

    assert answer["route"] == "actual-route"
    assert answer["message"] == "ok"
    assert answer["routing_trace"]["winning_router"] == "actual-route"
    assert answer["routing_trace"]["selected_by_registry"] == "high"
    assert "Routing decision" in answer["technical"]
    data = observer.response()
    assert data["dispatch_changed"] is False
    assert data["total_queries"] == 1
    assert data["overlap_queries"] == 1
    assert data["recent"][0]["matched_routes"] == ["high", "low"]
    assert data["recent"][0]["selected_by_registry"] == "high"
    assert data["recent"][0]["actual_route"] == "actual-route"
    assert data["capability_count"] == 2
    assert data["capability_safety_counts"] == {
        "read": 2,
        "mutate": 0,
        "destructive": 0,
    }
    assert [item["name"] for item in data["catalogue"]] == ["high", "low"]


def test_entrypoint_installs_shadow_after_final_composition():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py").read_text()
    finalize = source.index("auxiliary_request_layers.finalize()")
    observer = source.index("install_route_shadow_observer(")
    runtime = source.index("install_runtime_route_bridge(_core.application)")
    assert finalize < observer < runtime


def test_shadow_disagreement_uses_declared_runtime_aliases_not_conceptual_name():
    application = App()
    registry = RouteRegistry(
        (
            RouteDescriptor(
                "hub-logs",
                200,
                True,
                lambda _q: True,
                "logs",
                capability_id="diagnostics.hub-logs",
                runtime_routes=("mcp-fast",),
                runtime_intents=("fallback-hub-logs",),
            ),
        )
    )
    observer = install_route_shadow_observer(application, registry, limit=20)

    asyncio.run(application.ask(SimpleNamespace(query="check logs")))

    data = observer.response()
    assert data["comparable_queries"] == 1
    assert data["agreement_queries"] == 0
    assert data["registry_actual_disagreements"] == 1
    assert data["recent"][0]["comparison"] == "disagree"
    assert data["recent"][0]["selected_capability"] == "diagnostics.hub-logs"


def test_shadow_unmapped_capabilities_are_not_false_disagreements():
    application = App()
    registry = RouteRegistry(
        (RouteDescriptor("conceptual", 100, True, lambda _q: True, "test"),)
    )
    observer = install_route_shadow_observer(application, registry, limit=20)

    asyncio.run(application.ask(SimpleNamespace(query="anything")))

    data = observer.response()
    assert data["comparable_queries"] == 0
    assert data["unmapped_queries"] == 1
    assert data["registry_actual_disagreements"] == 0
    assert data["recent"][0]["comparison"] == "unmapped"
