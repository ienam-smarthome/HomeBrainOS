"""Bounded AI route arbitration for competing read-only host fast paths.

The language model chooses a workflow based on the original objective, not
on words such as comprehensive, audit, apps and scheduled jobs. This function
does not select permissions, perform writes, or verify MCP evidence.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from dataclasses import dataclass
import json
import re
from typing import Any, Awaitable, Callable, Literal

ReadRoute = Literal["model_led", "system_audit", "performance_report"]
_ROUTES = frozenset(("model_led", "system_audit", "performance_report"))
_WHOLE_SCOPE = re.compile(
    r"(?i)\b(?:whole|entire)\s+(?:(?:my|the|our)\s+)?"
    r"(?:hubitat\s+)?(?:system|hub|smart\s*home)\b"
    r"|\b(?:all|every)\s+(?:my\s+|the\s+)?"
    r"(?:devices|apps|rules|automations)\b"
    r"|\bsystem[- ]wide\b"
    r"|\b(?:full|comprehensive)\s+(?:system|hub|hubitat)\s+audit\b"
    r"|\brun\s+(?:the\s+)?system\s+check\b"
)
_PERFORMANCE_SCOPE = re.compile(
    r"(?i)\b(?:performance|cpu|hub\s+load|resource\s+usage|"
    r"pctBusy|busy\s+time|scheduled[- ]job\s+statistics)\b"
)
_SPECIFIC_INCIDENT = re.compile(
    r"(?i)\b(?:why|root[- ]cause|fault|offline|unreachable|"
    r"diagnos\w*|troubleshoot|investigat\w*|"
    r"what\s+caused|not\s+working|failed|exception)\b"
)
_EXACT_TARGET = re.compile(
    r"(?i)\b(?:device|app|rule)\s*(?:id\s*)?[:#]?\s*[1-9]\d{2,8}\b"
)
_DIRECT_CHECK = re.compile(
    r"(?i)^\s*(?:please\s+)?(?:run|show|display|generate)\s+"
    r"(?:(?:the|my)\s+)?(?:system\s+check|system\s+check\s+report)"
    r"\s*[.!?]?\s*$"
)
_ACTIVE_ROUTE: ContextVar[str | None] = ContextVar(
    "homebrain_model_directed_read_route", default=None,
)


@dataclass(frozen=True)
class ReadRouteDecision:
    route: ReadRoute
    provenance: str
    objective: str | None = None
    target: str | None = None
    purpose: str | None = None

_VALID_OBJECTIVES = frozenset((
    "device_connectivity", "source_code", "existing_rule_verification",
    "rule_design_review", "historical_command", "general_investigation",
    "system_audit", "performance_report",
))
_REQUEST_OBJECTIVE = ContextVar("homebrain_interpreted_objective", default=None)


def set_request_interpretation(request: str, decision: ReadRouteDecision) -> Token:
    return _REQUEST_OBJECTIVE.set((str(request), decision))


def reset_request_interpretation(token: Token) -> None:
    _REQUEST_OBJECTIVE.reset(token)


def active_request_interpretation(request: str) -> ReadRouteDecision | None:
    stored = _REQUEST_OBJECTIVE.get()
    return stored[1] if stored is not None and stored[0] == str(request) else None



_CLEAR_WHOLE_HUB = re.compile(
    r"(?i)\b(?:comprehensive|full)\s+(?:read[- ]only\s+)?"
    r"(?:hubitat\s+)?(?:system|hub)\s+audit\b"
    r"|\b(?:comprehensive|full)\s+(?:read[- ]only\s+)?"
    r"(?:audit|investigation|review)\s+of\s+"
    r"(?:(?:my|the|our)\s+)?(?:entire\s+|whole\s+)?"
    r"(?:hubitat\s+)?(?:hub|system)\b"
    r"|\b(?:audit|review|inspect|analyse|analyze|investigate)\s+"
    r"(?:(?:my|the|our)\s+)?(?:entire|whole)\s+(?:hubitat\s+)?(?:hub|system)\b"
    r"|\b(?:all|every)\s+(?:my\s+|the\s+)?(?:devices|apps|automations)\b"
)
_AGGREGATE_SCHEDULER = re.compile(
    r"(?i)\b(?:all|every)\s+scheduled\s+jobs?\b"
    r".{0,160}\b(?:by\s+handler|efficien\w*|performance\s+stats?|"
    r"overall\s+load|statistic\w*|optimis\w*|optimiz\w*)\b"
)


def explicit_whole_hub_report_request(question: str) -> bool:
    text = str(question or "")
    if _EXACT_TARGET.search(text) and not re.search(
        r"(?i)\b(?:all|every|entire|whole|system[- ]wide)\b", text,
    ):
        return False
    return bool(_CLEAR_WHOLE_HUB.search(text))


def explicit_aggregate_performance_request(question: str) -> bool:
    text = str(question or "")
    return bool(
        _AGGREGATE_SCHEDULER.search(text)
        and not _EXACT_TARGET.search(text)
        and not _SPECIFIC_INCIDENT.search(text)
    )


def explicit_system_check_command(question: str) -> bool:
    return bool(_DIRECT_CHECK.fullmatch(str(question or "")))


def active_read_route() -> str | None:
    return _ACTIVE_ROUTE.get()


def set_read_route(route: str) -> Token:
    return _ACTIVE_ROUTE.set(route)


def reset_read_route(token: Token) -> None:
    _ACTIVE_ROUTE.reset(token)


def _safe_route(route: str, question: str) -> ReadRoute:
    """A model may select a fast path only when the user supplied its scope."""
    question = str(question or "")
    if route == "system_audit":
        if not _WHOLE_SCOPE.search(question):
            return "model_led"
        if (_EXACT_TARGET.search(question)
                and not re.search(
                    r"(?i)\b(?:whole|entire|all|every|system[- ]wide)\b",
                    question,
                )):
            return "model_led"
    if route == "performance_report":
        if (not _PERFORMANCE_SCOPE.search(question)
                or _EXACT_TARGET.search(question)
                or _SPECIFIC_INCIDENT.search(question)):

            return "model_led"
    return route if route in _ROUTES else "model_led"


def _parse_interpretation(reply: Any) -> dict[str, str] | None:
    if not isinstance(reply, dict) or reply.get("tool_calls"):
        return None
    content = str(reply.get("content") or "").strip()
    fence = chr(96) * 3
    if content.startswith(fence):
        content = re.sub(r"^" + re.escape(fence) + r"(?:json)?\s*", "", content, flags=re.I)
        content = re.sub(r"\s*" + re.escape(fence) + r"\s*$", "", content)
    try:
        obj = json.loads(content)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    route = obj.get("route")
    if not isinstance(route, str) or route not in _ROUTES:
        return None
    parsed = {"route": route}
    objective = obj.get("objective")
    if isinstance(objective, str) and objective in _VALID_OBJECTIVES:
        parsed["objective"] = objective
    for field, maximum in (("target", 120), ("purpose", 240)):
        value = obj.get(field)
        if isinstance(value, str) and 0 < len(value.strip()) <= maximum:
            parsed[field] = value.strip()
    return parsed


def _parse_route(reply: Any) -> str | None:
    parsed = _parse_interpretation(reply)
    return parsed["route"] if parsed else None


async def decide_read_route(
    chat: Callable[[list[dict[str, str]], list[Any]], Awaitable[Any]],
    question: str, *, timeout_seconds: float = 9.0,
) -> ReadRouteDecision:
    """One no-tools model decision; bad/unavailable decisions -> MCP agent."""
    if explicit_system_check_command(question):
        return ReadRouteDecision("system_audit", "explicit_command")
    instructions = (
        "Select a READ-ONLY workflow. Do not answer the question or call tools. "
        "Determine what the USER wants examined, NOT whether their wording "
        "mentions comprehensive, audit, apps, logs or jobs. "
        "Routes: model_led = investigate a device, app, rule, specific cause, "
        "or complex uncertain question through interactive MCP tool calls; "
        "system_audit = whole-hub inventory/report, not a focused cause; "
        "performance_report = aggregate hub performance statistics only, "
        "not a specific incident. Choose model_led when uncertain. "
        "A thorough investigation of one device is NOT a whole-hub audit. "
        "Include a single objective from: device_connectivity, source_code, "
        "existing_rule_verification, rule_design_review, historical_command, "
        "general_investigation, system_audit, performance_report. "
        "A diagnostic question about an existing automation is not a "
        "request to design a future rule. Offline-device causes are not "
        "historical ON/OFF command attribution. Add target (the subject as "
        "written by user) and purpose (short statement of the actual goal). "
        'Return only JSON like {"route":"model_led",'
        '"objective":"device_connectivity",'
        '"target":"Bedroom 3 Mesh",'
        '"purpose":"explain offline versus MQTT connected"}.'
        " Never call tools."
    )
    try:
        result = await asyncio.wait_for(
            chat([
                {"role": "system", "content": instructions},
                {"role": "user", "content": str(question or "")[:12000]},
            ], []),
            timeout=max(1.0, min(float(timeout_seconds), 15.0)),
        )
        parsed = _parse_interpretation(result)
        if parsed is None:
            return ReadRouteDecision("model_led", "invalid_model_reply")
        proposal = parsed["route"]
        route = _safe_route(proposal, question)
        objective = parsed.get("objective")
        if route == "model_led" and objective in ("system_audit", "performance_report"):
            objective = None
        return ReadRouteDecision(
            route, "model_choice" if route == proposal else "host_scope_override",
            objective=objective, target=parsed.get("target"),
            purpose=parsed.get("purpose"),
        )
    except Exception:
        return ReadRouteDecision("model_led", "model_route_unavailable")


__all__ = [
    "ReadRouteDecision", "decide_read_route", "active_read_route",
    "set_read_route", "reset_read_route", "explicit_system_check_command",
    "explicit_whole_hub_report_request", "explicit_aggregate_performance_request",
    "active_request_interpretation", "set_request_interpretation",
    "reset_request_interpretation",
]
