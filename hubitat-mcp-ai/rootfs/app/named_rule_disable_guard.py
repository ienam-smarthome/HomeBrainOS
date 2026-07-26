from __future__ import annotations

import time
from types import MethodType
from typing import Any, Awaitable, Callable

from presenter import display_payload, safe_debug


Handle = Callable[[Any], Awaitable[dict[str, Any] | None]]


def _bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "disabled"}:
        return True
    if text in {"false", "0", "no", "enabled"}:
        return False
    return None


def _raw_rule_state(value: Any, rule_id: Any) -> dict[str, Any]:
    rows = value.get("rules", []) if isinstance(value, dict) else []
    for raw in rows:
        if isinstance(raw, dict) and str(raw.get("id")) == str(rule_id):
            disabled = _bool_value(raw.get("disabled"))
            paused = _bool_value(raw.get("paused"))
            status = str(raw.get("status") or "").strip().lower()
            if not status:
                status = "disabled" if disabled is True else "paused" if paused is True else "active"
            return {
                "disabled": disabled,
                "paused": paused,
                "status": status,
            }
    return {"disabled": None, "paused": None, "status": "unknown"}


def _unsupported_response(
    controller: Any,
    *,
    intent: Any,
    rule: dict[str, Any],
    listed: Any,
    available: set[str],
    started: float,
) -> dict[str, Any]:
    state = _raw_rule_state(getattr(listed, "data", None), rule["id"])
    display = display_payload(
        "rule-control",
        "Rule enable/disable unavailable",
        subtitle="The MCP server can read disabled state but cannot change it",
        metrics=[
            {"label": "Requested", "value": intent.action.title(), "icon": "🎯"},
            {"label": "Rule ID", "value": str(rule["id"]), "icon": "⚙️"},
            {"label": "Disabled", "value": str(state["disabled"]).title(), "icon": "⛔"},
            {"label": "Paused", "value": str(state["paused"]).title(), "icon": "⏸️"},
        ],
        items=[
            {
                "icon": "⚙️",
                "title": rule["name"],
                "value": state["status"].title(),
                "subtitle": "No command was sent",
            }
        ],
    )
    replacement_action = "resume" if state["paused"] is True else "pause"
    display["actions"] = [
        {
            "label": f"{replacement_action.title()} instead",
            "query": f"{replacement_action} rule id {rule['id']}",
            "tone": "primary",
        },
        {"label": "Cancel", "cancel": True, "tone": "secondary"},
    ]
    return {
        "success": False,
        "route": "mcp-rule-control-unsupported",
        "intent": "automation-rule-disabled-write-unsupported",
        "message": (
            "The connected MCP server can report whether this rule is disabled, but it does not "
            "advertise a rule enable/disable write operation. No command was sent. Pause and disable "
            "remain separate states."
        ),
        "answered_by": "Hubitat MCP deterministic rule controller",
        "display": display,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "technical": safe_debug(
            {
                "requested_action": intent.action,
                "resolved_rule": rule,
                "current_state": state,
                "advertised_tools": sorted(available),
                "required_mcp_capability": {
                    "preferred_tool": "hub_set_rule_disabled",
                    "arguments": {"ruleId": rule["id"], "disabled": intent.action == "disable"},
                    "required_response_fields": ["success", "ruleId", "disabled"],
                    "verification": "Read hub_list_rules and confirm disabled state by Rule ID",
                },
                "command_sent": False,
            }
        ),
    }


def install_named_rule_disable_guard(controller: Any) -> Any:
    """Keep pause/resume and disable/enable as distinct Rule Machine actions."""

    original_handle: Handle = controller.handle

    async def guarded_handle(self: Any, intent: Any) -> dict[str, Any] | None:
        if intent.action not in {"disable", "enable"}:
            return await original_handle(intent)

        started = time.perf_counter()
        listed = await self.mcp.call_tool("hub_list_rules", {})
        if listed.is_error:
            return self._error(
                "I could not read the Rule Machine inventory, so no rule command was sent.",
                listed,
                started,
            )

        rules = self._rule_rows(listed.data)
        matches = self._exact_matches(rules, intent)
        if len(matches) != 1:
            candidates = matches or self._possible_matches(rules, intent)
            return self._clarification(intent, candidates, listed, started)

        rule = matches[0]
        available = await self._available_tool_names()
        desired_disabled = intent.action == "disable"

        if "hub_set_rule_disabled" in available:
            tool_name = "hub_set_rule_disabled"
            arguments = {"ruleId": rule["id"], "disabled": desired_disabled}
        else:
            legacy = "hub_disable_rule" if desired_disabled else "hub_enable_rule"
            if legacy not in available:
                return _unsupported_response(
                    self,
                    intent=intent,
                    rule=rule,
                    listed=listed,
                    available=available,
                    started=started,
                )
            tool_name = legacy
            arguments = {"ruleId": rule["id"]}

        result = await self.mcp.call_tool(tool_name, arguments)
        if result.is_error:
            return self._error(
                f"No verified rule change can be reported for **{rule['name']}**: {result.text}",
                result,
                started,
                rule=rule,
            )

        reported_disabled = _bool_value(getattr(result, "data", {}).get("disabled") if isinstance(getattr(result, "data", None), dict) else None)
        command_verified = reported_disabled is desired_disabled
        readback_verified = False
        readback_state: bool | None = None
        try:
            refreshed = await self.mcp.call_tool("hub_list_rules", {})
            if not refreshed.is_error:
                state = _raw_rule_state(getattr(refreshed, "data", None), rule["id"])
                readback_state = state["disabled"]
                readback_verified = readback_state is desired_disabled
        except Exception:
            pass

        verified = command_verified or readback_verified
        verb = "disabled" if desired_disabled else "enabled"
        message = (
            f"Rule {verb} for **{rule['name']}**. Hubitat confirmed `disabled: {str(desired_disabled).lower()}`."
            if verified
            else f"The {intent.action} command was accepted for **{rule['name']}**, but the disabled state was not verified."
        )

        return {
            "success": True,
            "route": "mcp-rule-control",
            "intent": f"automation-rule-{intent.action}-{'verified' if verified else 'accepted'}",
            "message": message,
            "answered_by": "Hubitat MCP deterministic rule controller",
            "display": display_payload(
                "rule-control",
                f"Rule {verb}",
                subtitle=("Confirmed by Hubitat." if verified else "Command accepted without state confirmation."),
                metrics=[
                    {"label": "Action", "value": intent.action.title(), "icon": "🎯"},
                    {"label": "Rule ID", "value": str(rule["id"]), "icon": "⚙️"},
                ],
                items=[
                    {
                        "icon": "⚙️",
                        "title": rule["name"],
                        "value": verb.title(),
                        "subtitle": "Disabled state" if desired_disabled else "Enabled state",
                    }
                ],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "requested_action": intent.action,
                    "resolved_rule": rule,
                    "tool": tool_name,
                    "arguments": arguments,
                    "mcp": getattr(result, "data", None),
                    "command_verified": command_verified,
                    "inventory_readback_verified": readback_verified,
                    "inventory_reported_disabled": readback_state,
                    "post_state_verified": verified,
                }
            ),
        }

    controller.handle = MethodType(guarded_handle, controller)
    return controller


__all__ = [
    "_raw_rule_state",
    "install_named_rule_disable_guard",
]
