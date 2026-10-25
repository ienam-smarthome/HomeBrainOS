"""Bounded AI route arbitration for competing read-only host fast paths.

The language model chooses a workflow based on the original objective, not
on words such as comprehensive, audit, apps and scheduled jobs. This function
does not select permissions, perform writes, or verify MCP evidence.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from contextlib import contextmanager
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
    answer_goal: str | None = None

_VALID_OBJECTIVES = frozenset((
    "device_connectivity", "source_code", "existing_rule_verification",
    "rule_design_review", "historical_command", "general_investigation",
    "system_audit", "performance_report",
))
_ANSWER_GOALS = frozenset((
    "diagnose_cause", "verify_configuration", "trace_event",
    "inspect_implementation", "describe_status", "inventory_or_report",
    "design_change",
))
_REQUEST_OBJECTIVE = ContextVar("homebrain_interpreted_objective", default=None)


def set_request_interpretation(request: str, decision: ReadRouteDecision) -> Token:
    return _REQUEST_OBJECTIVE.set((str(request), decision))


def reset_request_interpretation(token: Token) -> None:
    _REQUEST_OBJECTIVE.reset(token)


@contextmanager
def without_request_interpretation():
    """Host safety parsers MUST not trust model intent labels."""
    token = _REQUEST_OBJECTIVE.set(None)
    try:
        yield
    finally:
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
    # Do not treat a *negative example* of a whole-system audit as an
    # instruction to run one. Leave ambiguous/negative cases to the model.
    # This check does not determine a diagnostic domain or grant permissions.
    if re.search(
        r"(?i)\b(?:not|no|without|instead\s+of|rather\s+than|"
        r"do\s+not|don['’]t)\s+(?:a|an|the)?\s*"
        r"(?:comprehensive|full|whole|entire|system[- ]wide)\b",
        text,
    ):
        return False
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
    if obj.get("answer_goal") in _ANSWER_GOALS:
        parsed["answer_goal"] = obj["answer_goal"]
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
        "Choose a specialist fast report ONLY if the objective matches that "
        "specialist route; do not omit the objective field. "
        "Include a single objective from: device_connectivity, source_code, "
        "existing_rule_verification, rule_design_review, historical_command, "
        "general_investigation, system_audit, performance_report. "
        "Classify the ANSWER the user wants independently from the type of "
        "entity being inspected. A question explaining why an existing "
        "automation behaved unexpectedly is a diagnosis, even if verifying "
        "its settings is part of the investigation. Formal existing-rule "
        "verification is only the primary objective when the user wants "
        "to certify its configuration or exact action logic. "
        "Offline-device causes are not historical ON/OFF command attribution. "
        "Set answer_goal to one of: diagnose_cause, verify_configuration, "
        "trace_event, inspect_implementation, describe_status, "
        "inventory_or_report, design_change. This field describes the "
        "requested deliverable, not a guessed finding or permission. "
        "Add target (the subject as "
        "written by user) and purpose (short statement of the actual goal). "
        'Return only JSON like {"route":"model_led",'
        '"objective":"device_connectivity",'
        '"answer_goal":"diagnose_cause",'
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
            return ReadRouteDecision(
                "model_led", "invalid_model_reply",
                objective="general_investigation",
            )
        proposal = parsed["route"]
        objective = parsed.get("objective")
        answer_goal = parsed.get("answer_goal")
        # A semantic deliverable is orthogonal to entity type: inspecting
        # a rule as evidence for WHY must not convert the user\'s requested
        # explanation into a strict configuration-certification report.
        # This arbitration is advisory and cannot expand read permissions.
        if proposal == "model_led":
            if answer_goal == "diagnose_cause" and objective == "existing_rule_verification":
                objective = "general_investigation"
            elif answer_goal == "verify_configuration" and objective == "general_investigation":
                objective = "existing_rule_verification"
        # Never enter a specialist fast report from a route label alone.
        # The model must consistently identify both the task objective and
        # the matching workflow; otherwise preserve the interactive MCP path.
        fast_objective = {
            "system_audit": "system_audit",
            "performance_report": "performance_report",
        }
        if (proposal in fast_objective
                and objective != fast_objective[proposal]):
            route = "model_led"
        else:
            route = _safe_route(proposal, question)
        # A missing/invalid model objective must not re-enable downstream
        # keyword classifiers (notably rule authoring and ON/OFF causality).
        # Generic investigation is safe: it never grants write permissions.
        if route == "model_led" and objective in (
            "system_audit", "performance_report",
        ):
            objective = None
        if objective is None:
            objective = "general_investigation"
        return ReadRouteDecision(
            route, "model_choice" if route == proposal else "host_scope_override",
            objective=objective, target=parsed.get("target"),
            purpose=parsed.get("purpose"), answer_goal=answer_goal,
        )
    except Exception:
        return ReadRouteDecision(
            "model_led", "model_route_unavailable",
            objective="general_investigation",
        )


__all__ = [
    "ReadRouteDecision", "decide_read_route", "active_read_route",
    "set_read_route", "reset_read_route", "explicit_system_check_command",
    "explicit_whole_hub_report_request", "explicit_aggregate_performance_request",
    "active_request_interpretation", "set_request_interpretation",
    "reset_request_interpretation",
    "without_request_interpretation",
]
