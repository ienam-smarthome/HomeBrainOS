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


def test_shadow_observer_records_full_match_set_without_changing_answer():
    application = App()
    registry = RouteRegistry(
        (
            RouteDescriptor("high", 200, True, lambda q: "power" in q, "high"),
            RouteDescriptor("low", 100, False, lambda q: bool(q), "low"),
        )
    )
    observer = install_route_shadow_observer(application, registry, limit=20)

    answer = asyncio.run(application.ask(SimpleNamespace(query="show power")))

    assert answer == {"route": "actual-route", "message": "ok"}
    data = observer.response()
    assert data["dispatch_changed"] is False
    assert data["total_queries"] == 1
    assert data["overlap_queries"] == 1
    assert data["recent"][0]["matched_routes"] == ["high", "low"]
    assert data["recent"][0]["selected_by_registry"] == "high"
    assert data["recent"][0]["actual_route"] == "actual-route"


def test_entrypoint_installs_shadow_after_final_composition():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py").read_text()
    finalize = source.index("auxiliary_request_layers.finalize()")
    observer = source.index("install_route_shadow_observer(")
    runtime = source.index("install_runtime_route_bridge(_core.application)")
    assert finalize < observer < runtime
