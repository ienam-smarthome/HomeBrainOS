from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from semantic_metric_comparison import _SPECS, format_measurement


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
TerminalRoute = Callable[[Any], Awaitable[dict[str, Any] | None]]
_NON_ROOM_CLIMATE_TERMS = (
    "appliance",
    "appliances",
    "fridge",
    "freezer",
    "refrigerator",
    "hub info",
    "hubitat",
    "weather",
    "open-meteo",
    "bridge",
    "life360",
)


def _normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower()).strip(" .!?")


def _metric_request(query: str) -> tuple[str, str] | None:
    q = _normalise(query)
    if not q or q.startswith("why "):
        return None

    metric = ""
    if any(term in q for term in ("humidity", "humid", "damp", "moisture")):
        metric = "humidity"
    elif any(term in q for term in ("temperature", "temp", "warmest", "hottest", "coldest", "coolest")):
        metric = "temperature"
    if not metric:
        return None

    if any(term in q for term in ("highest", "most ", "warmest", "hottest")):
        return metric, "max"
    if any(term in q for term in ("lowest", "least ", "coldest", "coolest")):
        return metric, "min"
    return None


def _is_room_climate_reading(reading: dict[str, Any]) -> bool:
    device = str(reading.get("label") or reading.get("device") or "").strip()
    room = str(reading.get("room") or "").strip()
    haystack = f"{device} {room}".lower()
    return bool(room) and not any(term in haystack for term in _NON_ROOM_CLIMATE_TERMS)


def select_metric_extreme(
    readings: list[dict[str, Any]],
    *,
    metric: str,
    direction: str,
) -> dict[str, Any] | None:
    valid: list[dict[str, Any]] = []
    for raw in readings:
        if not isinstance(raw, dict) or raw.get("aggregate") is True:
            continue
        if not _is_room_climate_reading(raw):
            continue
        try:
            value = float(raw.get("value"))
        except (TypeError, ValueError):
            continue
        if metric == "humidity" and not 0 <= value <= 100:
            continue
        if metric == "temperature" and not -40 <= value <= 80:
            continue
        item = dict(raw)
        item["value"] = value
        valid.append(item)

    if not valid:
        return None
    chooser = max if direction == "max" else min
    return chooser(valid, key=lambda item: float(item["value"]))


def build_climate_metric_extrema_route(
    metric_executor: Any,
) -> TerminalRoute:
    """Build the registry terminal route for authoritative climate extrema reads."""

    async def climate_metric_route(request: Any) -> dict[str, Any] | None:
        query = str(getattr(request, "query", "") or "").strip()
        requested = _metric_request(query)
        if requested is None:
            return None

        metric, direction = requested
        spec = _SPECS.get(metric)
        if spec is None:
            return None

        try:
            result = await metric_executor._fresh_capability_result(spec)
            rows = metric_executor.router._device_rows(result.data)
            readings = metric_executor._measurement_rows(rows, spec)
            selected = select_metric_extreme(
                readings,
                metric=metric,
                direction=direction,
            )
        except Exception:
            return None

        if selected is None:
            return {
                "success": False,
                "route": "mcp-fast",
                "intent": f"climate-{metric}-extreme",
                "message": f"No valid live room {metric} readings are currently available.",
                "answered_by": "Deterministic climate measurement reader",
            }

        value = float(selected["value"])
        formatted = format_measurement(spec, value)
        device = str(selected.get("label") or selected.get("device") or "sensor").strip()
        room = str(selected.get("room") or "").strip()
        direction_word = "highest" if direction == "max" else "lowest"

        message = (
            f"{room} has the {direction_word} {metric} reading at {formatted}, "
            f"reported by {device}."
        )

        return {
            "success": True,
            "route": "mcp-fast",
            "intent": f"climate-{metric}-extreme",
            "message": message,
            "metric": metric,
            "direction": direction,
            "reading": {
                "device": device,
                "room": room,
                "value": value,
                "formatted": formatted,
                "attribute": selected.get("source_attribute"),
            },
            "answered_by": "Deterministic climate measurement reader",
        }

    return climate_metric_route


def install_climate_metric_extrema_route(
    application: Any,
    metric_executor: Any,
) -> AskHandler:
    """Compatibility installer for the registry-compatible terminal route."""

    original_ask: AskHandler = application.ask
    terminal_route = build_climate_metric_extrema_route(metric_executor)

    async def climate_metric_ask(request: Any) -> dict[str, Any]:
        answer = await terminal_route(request)
        if answer is not None:
            return answer
        return await original_ask(request)

    application.ask = climate_metric_ask
    application.climate_metric_extrema_route = climate_metric_ask
    return climate_metric_ask


__all__ = [
    "build_climate_metric_extrema_route",
    "install_climate_metric_extrema_route",
    "select_metric_extreme",
]
