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
        if not _PERFORMANCE_SCOPE.search(question) or _EXACT_TARGET.search(question):
            return "model_led"
    return route if route in _ROUTES else "model_led"


def _parse_route(reply: Any) -> str | None:
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
    return route if isinstance(route, str) and route in _ROUTES else None


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
        'Output exactly one JSON object such as {"route":"model_led"} '
        "with no other text."
    )
    try:
        result = await asyncio.wait_for(
            chat([
                {"role": "system", "content": instructions},
                {"role": "user", "content": str(question or "")[:12000]},
            ], []),
            timeout=max(1.0, min(float(timeout_seconds), 15.0)),
        )
        proposal = _parse_route(result)
        if proposal is None:
            return ReadRouteDecision("model_led", "invalid_model_reply")
        route = _safe_route(proposal, question)
        return ReadRouteDecision(
            route, "model_choice" if route == proposal else "host_scope_override",
        )
    except Exception:
        return ReadRouteDecision("model_led", "model_route_unavailable")


__all__ = [
    "ReadRouteDecision", "decide_read_route", "active_read_route",
    "set_read_route", "reset_read_route", "explicit_system_check_command",
]
