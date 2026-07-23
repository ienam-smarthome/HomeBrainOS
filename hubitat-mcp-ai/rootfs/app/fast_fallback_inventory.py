from __future__ import annotations

from typing import Any

from fallback_router import _normalise
from fast_fallback_speech import FastFallbackRouter as SpeechFastFallbackRouter
from mcp_client import MCPError
from presenter import bool_label, display_payload, first_value, safe_debug, walk


_ACTIVE_RULE_STATES = {"active", "enabled", "running"}
_INACTIVE_RULE_STATES = {"paused", "disabled", "inactive", "stopped"}


class FastFallbackRouter(SpeechFastFallbackRouter):
    """Speech-aware fallback with accurate room/rule inventory responses."""

    async def answer(self, query: str) -> dict[str, Any]:
        q = _normalise(query)
        if "rule" in q and any(
            term in q for term in ("list", "show", "active", "automation")
        ):
            return await self._rules_inventory(active_only="active" in q)
        return await super().answer(query)

    async def _rules_inventory(self, *, active_only: bool) -> dict[str, Any]:
        result = await self._execute_catalog_tool(
            "hub_list_rules",
            "hub_read_rules",
            {},
        )
        if result.is_error:
            raise MCPError(result.text or "Rule lookup failed")

        rules = self._rule_rows(result.data)
        active = [rule for rule in rules if rule["state"] == "active"]
        inactive = [rule for rule in rules if rule["state"] == "inactive"]
        unknown = [rule for rule in rules if rule["state"] == "unknown"]

        if active_only:
            if active:
                shown = active
                message = f"{len(active)} active automation rule{'' if len(active) == 1 else 's'}:\n" + "\n".join(
                    f"- {rule['name']}" for rule in active
                )
                subtitle = f"{len(active)} active"
            elif unknown:
                shown = unknown[:30]
                message = (
                    f"The MCP server returned {len(rules)} automation rules, but it does not "
                    "expose an active, enabled, disabled, or paused state for them. I cannot "
                    "accurately claim that zero rules are active."
                )
                subtitle = "Active status not exposed"
            else:
                shown = []
                message = "No active automation rules were returned."
                subtitle = "No active rules"
        else:
            shown = rules[:30]
            status_bits = []
            if active:
                status_bits.append(f"{len(active)} active")
            if inactive:
                status_bits.append(f"{len(inactive)} inactive")
            if unknown:
                status_bits.append(f"{len(unknown)} status unknown")
            subtitle = f"{len(rules)} rules"
            if status_bits:
                subtitle += " · " + " · ".join(status_bits)
            message = f"{len(rules)} automation rules were returned:"
            if shown:
                message += "\n" + "\n".join(
                    f"- {rule['name']}: {rule['status']}" for rule in shown
                )

        items = [
            {
                "icon": "⚙️",
                "title": rule["name"],
                "value": rule["status"],
                "subtitle": f"Rule ID {rule['id']}",
                "tone": (
                    "success"
                    if rule["state"] == "active"
                    else "warning"
                    if rule["state"] == "inactive"
                    else None
                ),
            }
            for rule in shown
        ]
        note_bits = []
        if len(shown) < len(active if active_only and active else rules):
            note_bits.append("Showing the first 30 rules.")
        if unknown:
            note_bits.append(
                f"{len(unknown)} rule{'' if len(unknown) == 1 else 's'} did not include an activity state."
            )

        display = display_payload(
            "rules",
            "Active automation rules" if active_only else "Automation rules",
            subtitle=subtitle,
            metrics=[
                {"label": "Total", "value": str(len(rules)), "icon": "⚙️"},
                {
                    "label": "Active",
                    "value": str(len(active)) if not unknown or active else "Unknown",
                    "icon": "▶️",
                },
                {"label": "Inactive", "value": str(len(inactive)), "icon": "⏸️"},
                {"label": "Status unknown", "value": str(len(unknown)), "icon": "❔"},
            ],
            items=items,
            note=" ".join(note_bits) if note_bits else None,
        )
        response = self._response(
            message,
            "fallback-active-rules" if active_only else "fallback-rules",
            True,
            result,
        )
        response["display"] = display
        response["technical"] = safe_debug(result.data)
        return response

    @staticmethod
    def _rule_rows(value: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in walk(value):
            if not isinstance(item, dict):
                continue
            name = first_value(item, "name", "label", "appName", "ruleName")
            rule_id = first_value(item, "id", "ruleId", "appId")
            if not name or rule_id in (None, ""):
                continue

            state = "unknown"
            status = first_value(item, "status", "state")
            normalised_status = _normalise(status)
            disabled = first_value(item, "disabled", "isDisabled")
            paused = first_value(item, "paused", "isPaused")
            enabled = first_value(item, "enabled", "active")

            # Negative state flags must win. Hubitat includes paused=false on every
            # rule, so treating that alone as Active masks disabled=true.
            if disabled not in (None, "") and bool_label(disabled) == "Yes":
                state = "inactive"
                status = "Disabled"
            elif paused not in (None, "") and bool_label(paused) == "Yes":
                state = "inactive"
                status = "Paused"
            elif normalised_status in _ACTIVE_RULE_STATES:
                state = "active"
                status = normalised_status.title()
            elif normalised_status in _INACTIVE_RULE_STATES:
                state = "inactive"
                status = normalised_status.title()
            elif enabled not in (None, ""):
                is_enabled = bool_label(enabled) == "Yes"
                state = "active" if is_enabled else "inactive"
                status = "Active" if is_enabled else "Disabled"
            elif disabled not in (None, "") and bool_label(disabled) == "No":
                state = "active"
                status = "Active"
            else:
                status = "Status not exposed"

            rows.append(
                {
                    "name": str(name),
                    "id": rule_id,
                    "status": str(status),
                    "state": state,
                }
            )

        deduped: dict[str, dict[str, Any]] = {}
        for row in rows:
            deduped[str(row["id"])] = row
        return sorted(deduped.values(), key=lambda row: row["name"].lower())


__all__ = ["FastFallbackRouter"]
