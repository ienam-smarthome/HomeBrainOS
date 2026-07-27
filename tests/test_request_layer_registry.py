from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from request_composition import (  # noqa: E402
    classify_ask_layer,
    install_ask_layer_tracking,
)
from request_tracing import _performance  # noqa: E402


def _tracked_application():
    application = ModuleType("test_request_application")

    async def base_ask(request):
        return {"success": True, "route": "base", "message": request.query}

    application.ask = base_ask
    registry = install_ask_layer_tracking(application)
    return application, registry


def test_assignment_tracker_records_delegation_and_terminal_answer_layer():
    application, registry = _tracked_application()
    previous = application.ask

    async def delegated(request, next_handler=previous):
        return await next_handler(request)

    application.ask = delegated
    delegated_record = registry.records()[-1]
    previous = application.ask

    async def terminal(request, next_handler=previous):
        if request.query == "stop":
            return {"success": True, "route": "terminal", "message": "stopped"}
        return await next_handler(request)

    application.ask = terminal
    terminal_record = registry.records()[-1]

    delegated_answer = asyncio.run(
        application.ask(SimpleNamespace(query="continue"))
    )
    terminal_answer = asyncio.run(
        application.ask(SimpleNamespace(query="stop"))
    )

    assert delegated_answer["answering_layer"] == "base-application-route"
    assert delegated_answer["ask_layers_traversed"] == [
        terminal_record.name,
        delegated_record.name,
        "base-application-route",
    ]
    assert terminal_answer["answering_layer"] == terminal_record.name
    assert terminal_answer["ask_layers_traversed"] == [terminal_record.name]
    assert registry.response()["count"] == 3


def test_layer_tiers_preserve_the_documented_safety_boundaries():
    assert (
        classify_ask_layer(
            "hub_firmware_update_workflow",
            "install_hub_firmware_update_workflow",
        )
        == "safety-critical-write"
    )
    assert (
        classify_ask_layer(
            "home_summary_consistency_guard",
            "install_home_summary_consistency_guard",
        )
        == "answer-guard"
    )
    assert (
        classify_ask_layer(
            "automation_recommendation",
            "install_automation_recommendation_terminal_route",
        )
        == "terminal-route"
    )
    assert (
        classify_ask_layer(
            "semantic_home_query_router",
            "install_semantic_home_query_router",
        )
        == "semantic-evidence"
    )


def test_request_performance_exposes_answering_layer():
    performance = _performance(
        {
            "trace_id": "trace",
            "route_selected": "semantic",
            "route_reason": "test",
            "mcp_events": [],
        },
        {
            "route": "fallback",
            "answering_layer": "base-application-route",
            "answering_layer_tier": "deterministic-fast-read",
            "ask_layers_traversed": ["outer", "base-application-route"],
        },
    )

    assert performance["answering_layer"] == "base-application-route"
    assert performance["answering_layer_tier"] == "deterministic-fast-read"
    assert performance["ask_layer_count"] == 2


def test_tracking_is_installed_before_the_maintained_request_layers():
    source = (APP_DIR / "entrypoint_core.py").read_text(encoding="utf-8")

    tracker = source.index("ask_layer_registry = install_ask_layer_tracking")
    first_layer = source.index("install_fastpath_ai_handoff(application)")
    tracing = source.index("request_traces = install_request_tracing")

    assert tracker < first_layer < tracing
    assert '"/api/request-layers"' in (
        APP_DIR / "request_tracing.py"
    ).read_text(encoding="utf-8")
