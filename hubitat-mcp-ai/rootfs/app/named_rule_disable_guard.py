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
                return self._error(
                    "The connected MCP server does not advertise rule enable/disable control. "
                    "No command was sent. Use pause or resume only when you want paused-state control.",
                    listed,
                    started,
                    rule=rule,
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
                current = next(
                    (
                        item
                        for item in self._rule_rows(refreshed.data)
                        if str(item["id"]) == str(rule["id"])
                    ),
                    None,
                )
                if current is not None:
                    # _rule_rows may not preserve disabled yet, so inspect the raw inventory.
                    for raw in getattr(refreshed, "data", {}).get("rules", []) if isinstance(getattr(refreshed, "data", None), dict) else []:
                        if str(raw.get("id")) == str(rule["id"]):
                            readback_state = _bool_value(raw.get("disabled"))
                            readback_verified = readback_state is desired_disabled
                            break
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


__all__ = ["install_named_rule_disable_guard"]
