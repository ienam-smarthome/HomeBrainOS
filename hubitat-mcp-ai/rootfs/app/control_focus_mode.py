from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

import request_tracing
from control_agent_intent import is_control_candidate
from presenter import display_payload, safe_debug
from routing_policy import RouteDecision, classify_query, normalise
from semantic_metric_comparison import _SPECS, format_measurement
from semantic_read_intent import SemanticReadIntent


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_POWER_SUMMARY_TERMS = (
    "power consumption",
    "power usage",
    "current power",
    "current consumption",
    "power draw",
    "electricity draw",
    "wattage",
    "watt readings",
    "power readings",
    "device power",
)
_COMPARISON_TERMS = (
    " most ",
    " highest ",
    " lowest ",
    " least ",
    " top ",
    " rank",
    " compare",
    " versus ",
    " vs ",
)
_CONTROL_REPLY = re.compile(
    r"^(?:yes|y|no|n|cancel|stop|confirm|apply|do it|go ahead|[1-9]|10)$",
    re.IGNORECASE,
)
_SHORT_DEVICE_REPLY = re.compile(
    r"^(?=.{1,100}$)(?:[a-z0-9 &'_.\-]+\s+)?(?:light|lamp|fan|switch|socket|plug|tv|"
    r"thermostat|trv|dehumidifier|purifier|computer|fridge|freezer)(?:\s+[a-z0-9 &'_.\-]+)?$",
    re.IGNORECASE,
)
_VERIFIED_STATE_WORDS = (
    " state",
    " status",
    " on",
    " off",
    " level",
    " battery",
    " power",
    " temperature",
    " temp",
    " humidity",
    " open",
    " closed",
    " active",
    " inactive",
    " online",
    " offline",
    " stale",
)


def _query(value: str) -> str:
    return normalise(value).strip(" .!?")


def is_power_summary_query(query: str) -> bool:
    q = _query(query)
    if not q:
        return False
    padded = f" {q} "
    if any(term in padded for term in _COMPARISON_TERMS):
        return False
    if q in _POWER_SUMMARY_TERMS:
        return True
    if not q.startswith(("show ", "list ", "display ", "get ", "check ", "give me ", "tell me ")):
        return False
    return any(term in q for term in _POWER_SUMMARY_TERMS)


def is_control_followup(query: str) -> bool:
    q = _query(query)
    if not q:
        return False
    if _CONTROL_REPLY.fullmatch(q):
        return True
    if q.startswith(("remember ", "forget alias ")):
        return True
    return len(q.split()) <= 7 and bool(_SHORT_DEVICE_REPLY.fullmatch(q))


def is_verified_read_query(query: str) -> bool:
    q = _query(query)
    if not q:
        return False
    if is_power_summary_query(q):
        return True
    decision = classify_query(q)
    if decision.route in {"mcp-fast", "semantic-read"}:
        return True
    if q.startswith(("what is ", "what's ", "is ", "are ", "show ", "check ", "tell me ")):
        padded = f" {q} "
        return any(term in padded for term in _VERIFIED_STATE_WORDS)
    return False


class ControlFocusMode:
    """Keep HomeBrain focused on controls and authoritative device reads.

    This wrapper deliberately sits outside the broader AI answer routes. It lets
    proven controls and verified read paths continue unchanged, provides a direct
    current-power summary, and gives a truthful scope response for broad assistant
    questions instead of allowing overlapping routers to guess.
    """

    def __init__(
        self,
        application: Any,
        metric_executor: Any,
        *,
        enabled: bool = True,
        allow_verified_reads: bool = True,
    ) -> None:
        self.application = application
        self.metric_executor = metric_executor
        self.enabled = bool(enabled)
        self.allow_verified_reads = bool(allow_verified_reads)

    def allows(self, query: str) -> bool:
        if not self.enabled:
            return True
        if is_control_candidate(query) or is_control_followup(query):
            return True
        return self.allow_verified_reads and is_verified_read_query(query)

    async def power_summary(self, query: str) -> dict[str, Any]:
        intent = SemanticReadIntent(
            intent="metric_comparison",
            metric="power",
            operation="rank",
            group_by="device",
            scope_kind="all",
            scope_name="",
            entity_names=(),
            top_n=10,
            confidence=1.0,
        )
        answer = dict(await self.metric_executor.execute(intent, query=query))
        raw_readings = [
            item
            for item in list(answer.get("measurement_readings") or [])
            if isinstance(item, dict) and not bool(item.get("aggregate"))
        ]

        # A merged live read should already be unique, but custom drivers can expose
        # the same source through aliases. Keep one current value per device/label.
        unique: dict[str, dict[str, Any]] = {}
        for item in raw_readings:
            key = str(item.get("id") or "").strip() or normalise(str(item.get("label") or ""))
            if not key:
                continue
            unique[key] = item
        readings = sorted(
            unique.values(),
            key=lambda item: (-float(item.get("value") or 0.0), str(item.get("label") or "").lower()),
        )
        active = [item for item in readings if float(item.get("value") or 0.0) > 0.05]
        idle = [item for item in readings if float(item.get("value") or 0.0) <= 0.05]
        total = sum(float(item.get("value") or 0.0) for item in active)
        spec = _SPECS["power"]

        if active:
            lines = [
                f"{index}. {item.get('label')}: {format_measurement(spec, float(item.get('value') or 0.0))}"
                for index, item in enumerate(active[:20], start=1)
            ]
            message = "Current measured power consumption:\n" + "\n".join(lines)
            message += (
                f"\n\nTotal across {len(active)} active individual reading"
                f"{'s' if len(active) != 1 else ''}: {format_measurement(spec, total)}."
            )
            if idle:
                idle_names = ", ".join(str(item.get("label") or "Unknown") for item in idle[:20])
                message += f"\n0 W / idle readings: {idle_names}."
        elif readings:
            message = (
                f"{len(readings)} selected devices returned power readings, but all are currently "
                "0 W or effectively idle."
            )
        else:
            message = "No selected device returned a current numeric power reading."

        aggregate = [
            item
            for item in list((answer.get("technical") or {}).get("aggregate_readings") or [])
            if isinstance(item, dict)
        ]
        if aggregate:
            meter = max(aggregate, key=lambda item: float(item.get("value") or 0.0))
            message += (
                f" Whole-home meter: {format_measurement(spec, float(meter.get('value') or 0.0))} "
                "(shown separately, not added to the individual-device total)."
            )

        items = [
            {
                "icon": "⚡",
                "title": str(item.get("label") or "Unknown device"),
                "value": format_measurement(spec, float(item.get("value") or 0.0)),
                "subtitle": str(item.get("room") or "No room assigned"),
                "tone": "warning" if index == 0 and active else None,
            }
            for index, item in enumerate(readings[:20])
        ]
        display = display_payload(
            "verified-power-summary",
            "Current power consumption",
            subtitle=f"{len(readings)} live numeric readings",
            metrics=[
                {"label": "Active draw", "value": format_measurement(spec, total), "icon": "⚡"},
                {"label": "Active readings", "value": str(len(active)), "icon": "📡"},
                {"label": "0 W / idle", "value": str(len(idle)), "icon": "💤"},
            ],
            items=items,
            note=(
                "Fresh Hubitat Power Meter values were read and totalled deterministically. "
                "No AI model selected devices or calculated the total."
            ),
        )
        display["summary"] = message
        answer.update(
            {
                "success": bool(readings),
                "route": "mcp-power-summary",
                "intent": "verified-power-summary",
                "message": message,
                "display": display,
                "active_power_readings": active,
                "idle_power_readings": idle,
                "active_power_total_w": total,
                "answered_by": "Deterministic live Hubitat power summary",
                "model": None,
                "technical": safe_debug(
                    {
                        "query": query,
                        "normalised_readings": readings,
                        "active_readings": active,
                        "idle_readings": idle,
                        "active_total_w": total,
                        "aggregate_readings": aggregate,
                    }
                ),
            }
        )
        answer.pop("ai_provider", None)
        return answer

    def scope_response(self, query: str) -> dict[str, Any]:
        message = (
            "HomeBrain is in Control Focus mode. It can control selected devices and answer verified "
            "device-state questions such as lights on, power readings, batteries, temperatures, device "
            "health and room inventories. Broader AI analysis is disabled in this mode."
        )
        display = display_payload(
            "control-focus-scope",
            "Control Focus mode",
            subtitle="Device control and verified live reads only",
            metrics=[
                {"label": "Device controls", "value": "Enabled", "icon": "🎛️"},
                {"label": "Verified reads", "value": "Enabled" if self.allow_verified_reads else "Disabled", "icon": "📡"},
                {"label": "Broad AI analysis", "value": "Disabled", "icon": "🛡️"},
            ],
            note="Disable Control Focus in add-on Configuration to restore the broader AI Evidence Planner.",
        )
        display["summary"] = message
        return {
            "success": True,
            "route": "control-focus",
            "intent": "control-focus-scope",
            "message": message,
            "display": display,
            "answered_by": "HomeBrain Control Focus scope policy",
            "technical": safe_debug(
                {
                    "query": query,
                    "control_focus_enabled": self.enabled,
                    "verified_reads_enabled": self.allow_verified_reads,
                    "broad_ai_analysis_enabled": False,
                }
            ),
        }


def install_control_focus_mode(
    application: Any,
    metric_executor: Any,
    *,
    enabled: bool = True,
    allow_verified_reads: bool = True,
) -> ControlFocusMode:
    original_ask: AskHandler = application.ask
    original_classifier = request_tracing.classify_query
    service = ControlFocusMode(
        application,
        metric_executor,
        enabled=enabled,
        allow_verified_reads=allow_verified_reads,
    )

    def classify_with_control_focus(query: str) -> RouteDecision:
        if service.enabled and is_power_summary_query(query):
            return RouteDecision(
                "mcp-fast",
                "Control Focus verified current-power summary; read and total live Power Meter values deterministically",
            )
        if service.enabled and not service.allows(query):
            return RouteDecision(
                "control-focus",
                "Control Focus permits device controls and verified read-only device evidence; broad AI analysis is disabled",
            )
        return original_classifier(query)

    request_tracing.classify_query = classify_with_control_focus

    async def ask_with_control_focus(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        if not service.enabled:
            return await original_ask(request)
        if is_power_summary_query(query):
            answer = dict(await service.power_summary(query))
            answer.setdefault("version", application.VERSION)
            return answer
        if service.allows(query):
            return await original_ask(request)
        answer = service.scope_response(query)
        answer.setdefault("version", application.VERSION)
        return answer

    application.ask = ask_with_control_focus
    application.control_focus_mode = service
    return service


__all__ = [
    "ControlFocusMode",
    "install_control_focus_mode",
    "is_control_followup",
    "is_power_summary_query",
    "is_verified_read_query",
]
