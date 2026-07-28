from __future__ import annotations

from typing import Any, Awaitable, Callable

import request_tracing
from control_focus_octopus_energy import OctopusLiveMeterSummary, is_octopus_energy_query
from device_health_fast_route import is_attention_query, is_device_health_query
from fast_fallback_extended_reads import is_hub_logs_query
from home_priority_insight import WholeHomePriorityInsight, is_home_priority_query
from routing_policy import RouteDecision


TerminalRoute = Callable[[Any], Awaitable[dict[str, Any] | None]]


def configure_device_health_query_classifier() -> None:
    """Add health/attention/priority labels without adding an ask wrapper."""

    original_classifier = request_tracing.classify_query

    def classify_with_late_routes(query: str) -> RouteDecision:
        if is_home_priority_query(query):
            return RouteDecision(
                "home-insight",
                (
                    "deterministic whole-home snapshot gathers confirmed issues first; "
                    "Direct/Hybrid Ollama only ranks and phrases verified evidence"
                ),
            )
        if is_device_health_query(query):
            return RouteDecision(
                "mcp-fast",
                (
                    "authoritative Health Check states plus conservative lastActivity "
                    "classification; event age alone is not treated as a fault"
                ),
            )
        if is_attention_query(query):
            return RouteDecision(
                "mcp-fast",
                "deterministic attention scan over authoritative live Hubitat evidence",
            )
        return original_classifier(query)

    request_tracing.classify_query = classify_with_late_routes


def configure_octopus_query_classifier() -> None:
    """Add Octopus read labels without adding an ask wrapper."""

    original_classifier = request_tracing.classify_query

    def classify_with_octopus(query: str) -> RouteDecision:
        if is_octopus_energy_query(query):
            return RouteDecision(
                "mcp-fast",
                (
                    "Control Focus grouped Octopus whole-house display read; period "
                    "queries select the matching verified display sensor"
                ),
            )
        return original_classifier(query)

    request_tracing.classify_query = classify_with_octopus


def build_device_health_fast_route(application: Any) -> TerminalRoute:
    """Build priority, attention and device-health as one terminal route."""

    priority_service = WholeHomePriorityInsight(
        application,
        application.home_snapshot,
        ai_enabled=application.option_bool("home_snapshot_ai_enabled", True),
        ai_timeout_seconds=float(
            getattr(application, "OPTIONS", {}).get("home_snapshot_ai_timeout_seconds")
            or 20
        ),
    )
    application.home_priority_insight = priority_service

    async def route(request: Any) -> dict[str, Any] | None:
        query = str(getattr(request, "query", "") or "").strip()
        if is_home_priority_query(query):
            answer = dict(await priority_service.answer(query))
            answer.setdefault("version", application.VERSION)
            return answer
        if is_attention_query(query):
            answer = dict(await application.fallback._attention())
            answer["route"] = "mcp-fast"
            answer["model"] = None
            answer["answered_by"] = "Deterministic Hubitat attention classifier"
            answer["selected_tools"] = ["hub_list_devices"]
            return answer
        if is_device_health_query(query):
            answer = dict(await application.fallback._device_health())
            answer["route"] = "mcp-fast"
            answer["model"] = None
            answer["answered_by"] = "Deterministic Hubitat device-health classifier"
            answer["selected_tools"] = ["hub_list_devices"]
            return answer
        return None

    return route


def build_hub_logs_route(application: Any) -> TerminalRoute:
    """Build an authoritative Hubitat log-reading terminal route."""

    async def route(request: Any) -> dict[str, Any] | None:
        query = str(getattr(request, "query", "") or "").strip()
        if not is_hub_logs_query(query):
            return None
        answer = dict(await application.fallback.answer(query))
        if answer.get("intent") != "fallback-hub-logs":
            return None
        answer["route"] = "mcp-fast"
        answer["model"] = None
        answer["answered_by"] = "Deterministic Hubitat log diagnostics"
        answer["selected_tools"] = ["hub_get_logs"]
        answer.setdefault("version", application.VERSION)
        return answer

    return route


def build_control_focus_octopus_energy(application: Any) -> TerminalRoute:
    """Build the authoritative whole-house Octopus read terminal route."""

    service = OctopusLiveMeterSummary(application)
    application.octopus_live_meter_summary = service

    async def route(request: Any) -> dict[str, Any] | None:
        query = str(getattr(request, "query", "") or "").strip()
        if not is_octopus_energy_query(query):
            return None
        answer = dict(await service.answer(query))
        answer.setdefault("version", application.VERSION)
        return answer

    return route


__all__ = [
    "build_control_focus_octopus_energy",
    "build_device_health_fast_route",
    "build_hub_logs_route",
    "configure_device_health_query_classifier",
    "configure_octopus_query_classifier",
]
