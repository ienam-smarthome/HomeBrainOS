from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

import request_tracing
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
    """Install a deterministic route for offline/stale health questions.

    The wrapper is installed after semantic and Control Agent routes but before
    request tracing. It therefore avoids Cloud synthesis while keeping the final
    trace accurate. The request-tracing module imports ``classify_query`` by name,
    so its module global is patched explicitly with a narrow health-query override.
    """

    original_ask: AskHandler = application.ask
    original_classifier = request_tracing.classify_query

    def classify_with_device_health(query: str) -> RouteDecision:
        if is_device_health_query(query):
            return RouteDecision(
                "mcp-fast",
                (
                    "authoritative Health Check states plus conservative lastActivity "
                    "classification; event age alone is not treated as a fault"
                ),
            )
        return original_classifier(query)

    request_tracing.classify_query = classify_with_device_health

    async def ask_with_device_health(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        if not is_device_health_query(query):
            return await original_ask(request)

        answer = dict(await application.fallback._device_health())
        answer["route"] = "mcp-fast"
        answer["model"] = None
        answer["answered_by"] = "Deterministic Hubitat device-health classifier"
        answer["selected_tools"] = ["hub_list_devices"]
        return answer

    application.ask = ask_with_device_health
    return original_ask


__all__ = ["install_device_health_fast_route", "is_device_health_query"]
