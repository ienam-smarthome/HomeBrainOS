from __future__ import annotations

import re
import time
from typing import Any, Awaitable, Callable

from named_rule_control import NamedRuleIntent, _target_variants
from named_rule_disable_guard import _raw_rule_state
from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_STATUS_PATTERNS = (
    re.compile(r"^\s*(?:what(?:'s| is)\s+)?(?:the\s+)?status\s+(?:of\s+)?(?P<target>.+?)\s*[.!?]*$", re.IGNORECASE),
    re.compile(r"^\s*is\s+(?P<target>.+?)\s+(?:active|enabled|disabled|paused|running)\s*[.!?]*$", re.IGNORECASE),
    re.compile(r"^\s*(?:check|show|tell me)\s+(?:the\s+)?(?P<target>.+?)\s+(?:rule\s+)?status\s*[.!?]*$", re.IGNORECASE),
)


def parse_rule_status_target(query: str) -> str | None:
    text = str(query or "").strip()
    for pattern in _STATUS_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        target = match.group("target").strip(" .!?")
        if re.search(r"(?:^|\s)(?:rule|automation)(?:\s|$)", target, re.IGNORECASE):
            return target
    return None


def _state_message(name: str, state: dict[str, Any]) -> str:
    disabled = state.get("disabled")
    paused = state.get("paused")
    status = str(state.get("status") or "unknown").lower()
    if disabled is True:
        return f"**{name}** is disabled. It is not available to run until enabled."
    if paused is True:
        return f"**{name}** is paused but not disabled. Future triggers will not run until it is resumed."
    if disabled is False and paused is False:
        return f"**{name}** is active. It is enabled and not paused."
    return f"**{name}** reports status **{status}**. Disabled or paused state is incomplete."


def build_named_rule_status_terminal_route(controller: Any):
    """Build a registry terminal route for exact named Rule Machine status reads."""

    async def terminal_route(request: Any) -> dict[str, Any] | None:
        target = parse_rule_status_target(str(getattr(request, "query", "") or ""))
        if target is None:
            return None

        started = time.perf_counter()
        listed = await controller.mcp.call_tool("hub_list_rules", {})
        if listed.is_error:
            return {
                "success": False,
                "route": "mcp-rule-status-error",
                "intent": "automation-rule-status-error",
                "message": "I could not read the Rule Machine inventory.",
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            }

        intent = NamedRuleIntent(
            action="status",
            requested_name=target,
            variants=_target_variants(target),
            explicit_rule=True,
        )
        rules = controller._rule_rows(listed.data)
        matches = controller._exact_matches(rules, intent)
        if len(matches) != 1:
            candidates = matches or controller._possible_matches(rules, intent)
            if candidates:
                display = display_payload(
                    "rules",
                    "Select rule",
                    subtitle="No command has been sent",
                    items=[
                        {
                            "icon": "⚙️",
                            "title": rule["name"],
                            "value": str(rule["id"]),
                            "subtitle": "Select to read status",
                        }
                        for rule in candidates
                    ],
                )
                display["actions"] = [
                    {
                        "label": f"Status of {rule['name']}",
                        "query": f"status of rule id {rule['id']}",
                        "tone": "primary",
                    }
                    for rule in candidates
                ] + [{"label": "Cancel", "cancel": True, "tone": "secondary"}]
                message = "I did not find one exact rule match. Select a rule to read its status."
            else:
                display = display_payload("rules", "Rule not found", subtitle="No command has been sent")
                message = f"I could not find a Rule Machine rule named **{target}**."
            return {
                "success": False,
                "route": "mcp-rule-status-clarification",
                "intent": "automation-rule-status-clarification",
                "message": message,
                "display": display,
                "technical": safe_debug({"requested": target, "candidates": candidates}),
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            }

        rule = matches[0]
        state = _raw_rule_state(listed.data, rule["id"])
        message = _state_message(rule["name"], state)
        display = display_payload(
            "rule-status",
            "Rule status",
            subtitle="Read directly from Hubitat Rule Machine",
            metrics=[
                {"label": "Rule ID", "value": str(rule["id"]), "icon": "⚙️"},
                {"label": "Disabled", "value": str(state["disabled"]).title(), "icon": "⛔"},
                {"label": "Paused", "value": str(state["paused"]).title(), "icon": "⏸️"},
                {"label": "Status", "value": str(state["status"]).title(), "icon": "📋"},
            ],
            items=[
                {
                    "icon": "⚙️",
                    "title": rule["name"],
                    "value": str(state["status"]).title(),
                    "subtitle": "Authoritative Hubitat inventory state",
                }
            ],
        )
        if state["paused"] is True:
            display["actions"] = [
                {"label": "Resume", "query": f"resume rule id {rule['id']}", "tone": "primary"}
            ]
        elif state["disabled"] is not True:
            display["actions"] = [
                {"label": "Pause", "query": f"pause rule id {rule['id']}", "tone": "secondary"}
            ]

        return {
            "success": True,
            "route": "mcp-rule-status",
            "intent": "automation-rule-status",
            "message": message,
            "answered_by": "Hubitat MCP deterministic rule status reader",
            "display": display,
            "rule": {
                "id": rule["id"],
                "name": rule["name"],
                **state,
            },
            "technical": safe_debug({"resolved_rule": rule, "state": state, "mcp": listed.data}),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }

    return terminal_route


def install_named_rule_status_route(application: Any, controller: Any) -> AskHandler:
    original_ask: AskHandler = application.ask
    terminal_route = build_named_rule_status_terminal_route(controller)

    async def ask(request: Any) -> dict[str, Any]:
        answer = await terminal_route(request)
        if answer is not None:
            return answer
        return await original_ask(request)

    application.ask = ask
    application.named_rule_status_route = ask
    return ask


__all__ = [
    "build_named_rule_status_terminal_route",
    "install_named_rule_status_route",
    "parse_rule_status_target",
]
