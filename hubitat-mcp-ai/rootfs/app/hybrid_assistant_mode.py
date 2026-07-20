from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

import ai_evidence_planner as planner_module
import request_tracing
from control_agent_intent import is_control_candidate
from control_focus_mode import ControlFocusMode, is_control_followup, is_power_summary_query
from control_focus_power_summary_safe import install_control_focus_power_summary_safe
from device_health_fast_route import is_device_health_query
from fallback_router import _device_id, _label
from presenter import display_payload, normalise_text, safe_debug
from routing_policy import RouteDecision, classify_query, normalise
from semantic_metric_comparison_live import _merge_rows


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_READ_PREFIXES = (
    "show ",
    "list ",
    "display ",
    "get ",
    "check ",
    "tell me ",
    "give me ",
    "what ",
    "what's ",
    "whats ",
    "which ",
    "why ",
    "how ",
    "is ",
    "are ",
    "do ",
    "does ",
    "should ",
    "could ",
)
_AUTOMATION_WRITE_TERMS = (
    "create automation",
    "create rule",
    "modify rule",
    "change rule",
    "delete rule",
    "repair rule",
)
_OCTOPUS_PREFIX = "octopus live meter display"
_PERIOD_ORDER = (
    "power",
    "today",
    "yesterday",
    "week",
    "month",
    "rates compact",
    "previous rate",
    "standing charge",
)
_PERIOD_LABELS = {
    "power": "Whole-house power",
    "today": "Today",
    "yesterday": "Yesterday",
    "week": "This week",
    "month": "This month",
    "rates compact": "Current rates",
    "previous rate": "Previous rate",
    "standing charge": "Standing charge",
}


def _query(value: Any) -> str:
    return normalise(str(value or "")).strip(" .!?")


def is_direct_control_query(query: str) -> bool:
    """Return true only for action-shaped controls, not read verbs such as show/list."""

    q = _query(query)
    if not q:
        return False
    if is_control_followup(q):
        return True
    if q.startswith(_READ_PREFIXES):
        return False
    return bool(is_control_candidate(q))


def is_octopus_energy_query(query: str) -> bool:
    q = _query(query)
    if not q:
        return False
    if "octopus" in q and any(
        term in q for term in ("meter", "display", "power", "energy", "usage", "cost", "rate", "charge")
    ):
        return True
    period = any(term in q for term in ("today", "yesterday", "this week", "week", "this month", "month"))
    energy = any(
        term in q
        for term in (
            "total power consumption",
            "total energy consumption",
            "energy consumption",
            "electricity consumption",
            "electricity usage",
            "energy usage",
            "energy used",
            "power used",
            "energy cost",
            "electricity cost",
        )
    )
    if period and energy:
        return True
    whole_house = any(term in q for term in ("whole house", "whole-house", "overall", "home meter"))
    return whole_house and any(term in q for term in ("meter", "power", "energy", "electricity"))


def is_hybrid_ai_query(query: str) -> bool:
    """Use AI for every non-fast read instead of blocking or fuzzy device matching."""

    q = _query(query)
    if not q or is_direct_control_query(q) or is_device_health_query(q):
        return False
    if any(term in q for term in _AUTOMATION_WRITE_TERMS):
        return False
    if is_power_summary_query(q) or is_octopus_energy_query(q):
        return False
    decision = classify_query(q)
    return decision.route != "mcp-fast"


def install_hybrid_assistant_query_policy() -> None:
    """Make the Evidence Planner the universal fallback after proven fast routes."""

    planner_module.is_ai_evidence_query = is_hybrid_ai_query


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _device_rows(value: Any) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in _walk(value):
        if not isinstance(item, dict):
            continue
        label = _label(item)
        device_id = _device_id(item)
        if device_id is None or not label:
            continue
        if not normalise(label).startswith(_OCTOPUS_PREFIX):
            continue
        rows[str(device_id)] = item
    return list(rows.values())


def _state_values(item: dict[str, Any]) -> list[tuple[str, Any]]:
    values: list[tuple[str, Any]] = []
    for container_name in ("currentStates", "attributes", "state", "states"):
        container = item.get(container_name)
        if isinstance(container, dict):
            for key, raw in container.items():
                if isinstance(raw, dict):
                    raw = raw.get("currentValue", raw.get("value", raw.get("state", raw.get("text"))))
                values.append((str(key), raw))
        elif isinstance(container, list):
            for entry in container:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name") or entry.get("attribute") or entry.get("key") or "value"
                raw = entry.get("currentValue", entry.get("value", entry.get("state", entry.get("text"))))
                values.append((str(name), raw))
    for key in ("currentValue", "value", "display", "html", "text", "descriptionText"):
        if item.get(key) not in (None, ""):
            values.append((key, item.get(key)))
    return values


def _display_value(item: dict[str, Any]) -> str | None:
    preferred = (
        "display",
        "html",
        "text",
        "value",
        "currentvalue",
        "power",
        "energy",
        "cost",
        "rate",
        "state",
    )
    candidates: list[tuple[int, str]] = []
    for name, raw in _state_values(item):
        if raw in (None, ""):
            continue
        text = normalise_text(raw)
        if not text or text.lower() in {"available", "unknown", "unavailable", "none", "null"}:
            continue
        lowered = normalise(name).replace(" ", "")
        score = next((100 - index for index, key in enumerate(preferred) if key in lowered), 10)
        candidates.append((score, text[:800]))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: (-pair[0], len(pair[1])))
    return candidates[0][1]


def _period_for_label(label: str) -> str:
    suffix = normalise(label)
    if suffix.startswith(_OCTOPUS_PREFIX):
        suffix = suffix[len(_OCTOPUS_PREFIX) :].strip()
    return suffix or "display"


def _requested_periods(query: str) -> tuple[str, ...]:
    q = _query(query)
    requested: list[str] = []
    if "yesterday" in q:
        requested.append("yesterday")
    if "today" in q:
        requested.append("today")
    if "week" in q:
        requested.append("week")
    if "month" in q:
        requested.append("month")
    if any(term in q for term in ("right now", "current power", "live power", "whole house power")):
        requested.append("power")
    return tuple(dict.fromkeys(requested))


class OctopusEnergySummary:
    def __init__(self, application: Any) -> None:
        self.application = application

    async def _read(self, *, detailed: bool) -> Any:
        desired = {
            "detailed": detailed,
            "format": "detailed" if detailed else "summary",
            "labelFilter": "Octopus Live Meter Display",
        }
        supported = getattr(self.application.mcp, "supported_arguments", None)
        args = await supported("hub_list_devices", desired) if callable(supported) else desired
        return await self.application.mcp.call_tool("hub_list_devices", args)

    async def answer(self, query: str) -> dict[str, Any]:
        invalidate = getattr(self.application.mcp, "invalidate", None)
        if callable(invalidate):
            try:
                await invalidate("devices")
            except Exception:
                pass

        summary = await self._read(detailed=False)
        detailed = await self._read(detailed=True)
        summary_rows = _device_rows(summary.data) if not summary.is_error else []
        detailed_rows = _device_rows(detailed.data) if not detailed.is_error else []
        rows = _merge_rows(detailed_rows, summary_rows)
        rows = [item for item in rows if normalise(_label(item)).startswith(_OCTOPUS_PREFIX)]

        requested = _requested_periods(query)
        prepared: list[dict[str, Any]] = []
        for item in rows:
            period = _period_for_label(_label(item))
            if requested and not any(period == wanted or period.startswith(wanted) for wanted in requested):
                continue
            prepared.append(
                {
                    "id": str(_device_id(item) or ""),
                    "label": _label(item),
                    "period": period,
                    "title": _PERIOD_LABELS.get(period, period.title()),
                    "value": _display_value(item),
                    "room": item.get("room"),
                    "lastActivity": item.get("lastActivity"),
                }
            )

        order = {name: index for index, name in enumerate(_PERIOD_ORDER)}
        prepared.sort(key=lambda item: (order.get(str(item.get("period")), 99), str(item.get("label")).lower()))
        available = [item for item in prepared if item.get("value")]

        if available:
            message = "Octopus whole-house energy readings:\n" + "\n".join(
                f"- {item['title']}: {item['value']}" for item in available
            )
        elif prepared:
            message = (
                "The Octopus Live Meter display devices were found, but their current display values "
                "were not returned by the selected-device read."
            )
        else:
            message = "No selected Octopus Live Meter display devices matched this request."

        items = [
            {
                "icon": "⚡" if item.get("period") == "power" else "📊",
                "title": item.get("title"),
                "value": item.get("value") or "No live value",
                "subtitle": item.get("label"),
            }
            for item in prepared
        ]
        display = display_payload(
            "octopus-energy-summary",
            "Octopus whole-house energy",
            subtitle=f"{len(available)} live display reading{'s' if len(available) != 1 else ''}",
            metrics=[
                {"label": "Displays found", "value": str(len(rows)), "icon": "📟"},
                {"label": "Values read", "value": str(len(available)), "icon": "📡"},
            ],
            items=items,
            note="These are the authoritative Octopus display sensors selected in Hubitat.",
        )
        display["summary"] = message
        return {
            "success": bool(available),
            "route": "mcp-octopus-energy",
            "intent": "verified-octopus-energy-summary",
            "message": message,
            "display": display,
            "octopus_readings": prepared,
            "answered_by": "Deterministic Octopus whole-house display reader",
            "selected_tools": ["hub_list_devices"],
            "model": None,
            "technical": safe_debug(
                {
                    "query": query,
                    "requested_periods": requested,
                    "summary_error": summary.text if summary.is_error else None,
                    "detailed_error": detailed.text if detailed.is_error else None,
                    "readings": prepared,
                }
            ),
        }


def install_hybrid_verified_read_routes(application: Any, metric_executor: Any) -> dict[str, Any]:
    """Install fast verified reads outside optional restricted Control Focus mode."""

    install_control_focus_power_summary_safe()
    power_service = ControlFocusMode(
        application,
        metric_executor,
        enabled=False,
        allow_verified_reads=True,
    )
    octopus_service = OctopusEnergySummary(application)
    original_ask: AskHandler = application.ask
    original_classifier = request_tracing.classify_query

    def classify_with_hybrid_reads(query: str) -> RouteDecision:
        if is_power_summary_query(query):
            return RouteDecision(
                "mcp-fast",
                "verified current-power summary; live Power Meter values are read and totalled deterministically",
            )
        if is_octopus_energy_query(query):
            return RouteDecision(
                "mcp-fast",
                "verified Octopus whole-house display summary; period and live display values are read deterministically",
            )
        return original_classifier(query)

    request_tracing.classify_query = classify_with_hybrid_reads

    async def ask_with_hybrid_reads(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        if is_power_summary_query(query):
            answer = dict(await power_service.power_summary(query))
            answer.setdefault("version", application.VERSION)
            return answer
        if is_octopus_energy_query(query):
            answer = dict(await octopus_service.answer(query))
            answer.setdefault("version", application.VERSION)
            return answer
        return await original_ask(request)

    application.ask = ask_with_hybrid_reads
    application.hybrid_power_summary = power_service
    application.octopus_energy_summary = octopus_service
    return {"power": power_service, "octopus": octopus_service}


__all__ = [
    "OctopusEnergySummary",
    "install_hybrid_assistant_query_policy",
    "install_hybrid_verified_read_routes",
    "is_direct_control_query",
    "is_hybrid_ai_query",
    "is_octopus_energy_query",
]
