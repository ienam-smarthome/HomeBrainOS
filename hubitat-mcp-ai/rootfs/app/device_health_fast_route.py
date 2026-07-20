from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

import request_tracing
from home_priority_insight import WholeHomePriorityInsight, is_home_priority_query
from routing_policy import RouteDecision


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_DEVICE_HEALTH_QUERY = re.compile(
    r"^(?:please\s+)?(?:"
    r"(?:are\s+(?:there\s+)?any|do\s+i\s+have)\s+(?:devices?\s+)?(?:that\s+are\s+)?"
    r"(?:offline|stale|offline\s+(?:or|and)\s+stale|stale\s+(?:or|and)\s+offline)"
    r"|(?:which|what|show|list|find|get|check)\s+(?:devices?\s+)?(?:are\s+|that\s+are\s+)?"
    r"(?:offline|stale|offline\s+(?:or|and)\s+stale|stale\s+(?:or|and)\s+offline)"
    r"|(?:device|devices)\s+health(?:\s+status)?"
    r"|(?:offline|stale)\s+devices?"
    r")[?.!]*$",
    re.IGNORECASE,
)


def is_device_health_query(query: str) -> bool:
    text = re.sub(r"\s+", " ", str(query or "").strip())
    return bool(_DEVICE_HEALTH_QUERY.match(text))


def install_device_health_fast_route(application: Any) -> AskHandler:
    """Install late authoritative health and whole-home priority routes.

    This wrapper is installed after semantic and Control Agent routes but before
    request tracing. Whole-home insight questions therefore cannot be swallowed by
    the broad semantic-comparison gate merely because they contain words such as
    ``most`` or ``important``. Device-health questions remain deterministic.
    """

    original_ask: AskHandler = application.ask
    original_classifier = request_tracing.classify_query
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
        return original_classifier(query)

    request_tracing.classify_query = classify_with_late_routes

    async def ask_with_late_routes(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        if is_home_priority_query(query):
            answer = dict(await priority_service.answer(query))
            answer.setdefault("version", application.VERSION)
            return answer
        if not is_device_health_query(query):
            return await original_ask(request)

        answer = dict(await application.fallback._device_health())
        answer["route"] = "mcp-fast"
        answer["model"] = None
        answer["answered_by"] = "Deterministic Hubitat device-health classifier"
        answer["selected_tools"] = ["hub_list_devices"]
        return answer

    application.ask = ask_with_late_routes
    return original_ask


__all__ = [
    "install_device_health_fast_route",
    "is_device_health_query",
    "is_home_priority_query",
]
