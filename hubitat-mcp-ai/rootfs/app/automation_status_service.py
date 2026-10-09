from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mcp_client import HubitatMCPClient, MCPToolResult

_STATUSES = ("active", "disabled", "paused", "broken", "unknown")
_ATTENTION_STATUSES = ("broken", "paused", "unknown")
_STATUS_PRECEDENCE = ("broken", "paused", "disabled", "active")
_ADVISORY_WORDS = (
    "recommend", "recommendation", "recommendations",
    "suggest", "suggestion", "suggestions",
    "advice", "improve", "review", "clean up", "cleanup", "audit",
)
# Distinguishes genuinely creative new-automation requests from status reads.
# Broad advisory wording such as "improve my automations" is intentionally NOT
# enough to select the deterministic status shortcut: those requests need the
# reasoning agent, which can inspect the user's actual objective and supporting
# diagnostics instead of returning a broken/disabled inventory dump.
_NEW_IDEA_SIGNAL = (
    "for my home", "for my house", "should i", "could i",
    "new automation", "new automations", "automation ideas",
    "set up", "set it up", "what automations", "which automations",
)
_EXISTING_AUTOMATION_WORDS = (
    "broken", "existing", "current", "my automations", "my rules",
    "review", "clean up", "cleanup", "audit", "fix",
)
_SAFETY_CAPABILITIES = ("WaterSensor", "SmokeDetector", "CarbonMonoxideDetector")

_COMMON_AUTOMATION_SUGGESTIONS: dict[str, str] = {
    "WaterSensor": "a water leak alert",
    "SmokeDetector": "a smoke alert",
    "CarbonMonoxideDetector": "a carbon monoxide alert",
    "MotionSensor": "a motion-activated light",
    "ContactSensor": "a door/window-left-open alert",
    "Lock": "an auto-lock after being left unlocked",
    "PresenceSensor": "an arrival/departure automation",
}


@dataclass(slots=True)
class AutomationStatusOutcome:
    message: str
    request_class: str = "live-read"
    evidence: list[dict[str, Any]] = field(default_factory=list)
    choices: list[str] = field(default_factory=list)
    automation_items: list[dict[str, Any]] = field(default_factory=list)
    automation_counts: dict[str, int] = field(default_factory=dict)
    attention_count: int = 0
    conflict_count: int = 0
    route: str = "automation-status"
    devices: list[dict[str, Any]] = field(default_factory=list)


class AutomationStatusService:
    """Read and normalise app/rule state without relying on LLM formatting."""

    def __init__(self, mcp: HubitatMCPClient) -> None:
        self.mcp = mcp

    @staticmethod
    def matches_request(prompt: str) -> bool:
        """Route only explicit status/listing or explicit new-idea requests here.

        The previous matcher treated any automation request containing broad
        advisory words such as "improve", "recommend", or "review" as a status
        request. That caused follow-up optimisation questions to bypass the
        reasoning agent and return a deterministic broken/disabled inventory.
        Keep the shortcut narrow: literal status/list queries stay deterministic;
        explicit new-idea requests can use the creative advisory path; everything
        else is left to the unified agent.
        """

        value = " ".join(str(prompt).casefold().split())
        if any(word in value for word in ("enable ", "disable ", "pause ", "resume ")):
            return False
        subject = any(word in value for word in ("automation", "automations", "rule", "rules", "apps"))
        if not subject:
            return False
        explicit_status = any(
            word in value
            for word in ("list", "show", "which", "status", "active", "disabled", "paused", "broken")
        )
        explicit_new_ideas = (
            any(word in value for word in _ADVISORY_WORDS)
            and any(signal in value for signal in _NEW_IDEA_SIGNAL)
        )
        return explicit_status or explicit_new_ideas

    @staticmethod
    def is_advisory_request(prompt: str) -> bool:
        value = " ".join(str(prompt).casefold().split())
        return any(word in value for word in _ADVISORY_WORDS)

    @staticmethod
    def wants_new_automation_ideas(prompt: str) -> bool:
        value = " ".join(str(prompt).casefold().split())
        wants_new = any(signal in value for signal in _NEW_IDEA_SIGNAL)
        mentions_existing = any(
            word in value for word in _EXISTING_AUTOMATION_WORDS
        )
        return wants_new and not mentions_existing

    @staticmethod
    def _bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().casefold()
        if normalized in {"true", "yes", "1", "on"}:
            return True
        if normalized in {"false", "no", "0", "off"}:
            return False
        return None

    _STATE_FIELDS = (
        "broken", "disabled", "enabled", "paused", "active",
        "status", "state", "healthStatus",
    )
    _SCHEMA_ONLY_KEYS = (
        "input_schema", "inputSchema", "output_schema", "outputSchema", "parameters",
    )

    @staticmethod
    def _name(item: dict[str, Any]) -> str:
        return str(
            item.get("label")
            or item.get("name")
            or item.get("displayName")
            or item.get("title")
            or ""
        )

    @staticmethod
    def display_name(name: str) -> str:
        value = re.sub(r"\s*\(Paused\)\s*", " ", str(name), flags=re.IGNORECASE)
        value = re.sub(r"\s*\*BROKEN\*\s*", " ", value, flags=re.IGNORECASE)
        return " ".join(value.split()).strip()

    @classmethod
    def _status_signals(cls, item: dict[str, Any]) -> dict[str, bool]:
        status_text = " ".join(
            str(item.get(key) or "").casefold()
            for key in ("status", "state", "healthStatus")
        ).strip()
        name_text = cls._name(item).casefold()
        return {
            "broken": (
                cls._bool(item.get("broken")) is True
                or any(word in status_text for word in ("broken", "error", "failed"))
                or "*broken*" in name_text
            ),
            "paused": (
                cls._bool(item.get("paused")) is True
                or "paused" in status_text
                or "(paused)" in name_text
            ),
            "disabled": (
                cls._bool(item.get("disabled")) is True
                or cls._bool(item.get("enabled")) is False
                or "disabled" in status_text
            ),
            "active": (
                cls._bool(item.get("active")) is True
                or cls._bool(item.get("enabled")) is True
                or any(word in status_text for word in ("active", "enabled", "running"))
            ),
        }

    @staticmethod
    def conflicting_statuses(signals: dict[str, bool]) -> list[str]:
        asserted = [status for status in _STATUS_PRECEDENCE if signals.get(status)]
        if len(asserted) < 2:
            return []
        return asserted

    @classmethod
    def normalise_status(cls, item: dict[str, Any]) -> str:
        signals = cls._status_signals(item)
        for status in _STATUS_PRECEDENCE:
            if signals[status]:
                return status
        status_text = " ".join(
            str(item.get(key) or "").casefold()
            for key in ("status", "state", "healthStatus")
        ).strip()
        has_state_signal = status_text or any(
            item.get(key) is not None
            for key in (*cls._STATE_FIELDS, "id", "appId", "ruleId")
        )
        return "active" if has_state_signal else "unknown"

    @classmethod
    def _status_evidence(
        cls,
        item: dict[str, Any],
        signals: dict[str, bool],
    ) -> tuple[dict[str, Any], str | None]:
        evidence: dict[str, Any] = {}
        for key in (
            "broken",
            "paused",
            "disabled",
            "enabled",
            "active",
            "status",
            "state",
            "healthStatus",
            "reason",
            "statusReason",
            "statusMessage",
            "message",
            "error",
        ):
            value = item.get(key)
            if value in (None, ""):
                continue
            if isinstance(value, (str, int, float, bool)):
                evidence[key] = " ".join(str(value).split())[:240]

        for key in ("reason", "statusReason", "statusMessage", "message", "error"):
            value = evidence.get(key)
            if value:
                return evidence, str(value)

        for key in ("healthStatus", "status", "state"):
            value = evidence.get(key)
            if value and str(value).casefold() not in {
                "active",
                "enabled",
                "running",
                "disabled",
                "paused",
                "broken",
                "error",
                "failed",
            }:
                return evidence, str(value)

        name_text = cls._name(item).casefold()
        if signals.get("broken"):
            if cls._bool(item.get("broken")) is True:
                return evidence, "Hubitat reports broken=true."
            if "*broken*" in name_text:
                return evidence, "Hubitat marked the automation name *BROKEN*."
            return evidence, "Hubitat status reports an error, failure, or broken state."
        if signals.get("paused"):
            if cls._bool(item.get("paused")) is True:
                return evidence, "Hubitat reports paused=true."
            return evidence, "Hubitat reports the automation as paused."
        return evidence, None

    @staticmethod
    def _candidate_lists(value: Any) -> list[list[dict[str, Any]]]:
        found: list[list[dict[str, Any]]] = []
        if isinstance(value, list):
            rows = [item for item in value if isinstance(item, dict)]
            if rows:
                found.append(rows)
            for item in value:
                found.extend(AutomationStatusService._candidate_lists(item))
        elif isinstance(value, dict):
            for child in value.values():
                found.extend(AutomationStatusService._candidate_lists(child))
        return found

    @classmethod
    def _looks_like_automation_item(cls, row: dict[str, Any]) -> bool:
        if not cls._name(row) or any(key in row for key in cls._SCHEMA_ONLY_KEYS):
            return False
        return any(key in row for key in ("id", "appId", "ruleId", *cls._STATE_FIELDS))

    @classmethod
    def _items_from_result(
        cls,
        result: MCPToolResult,
        *,
        item_type: str,
        source: str,
    ) -> list[dict[str, Any]]:
        candidates = cls._candidate_lists(result.data)
        scored = [[row for row in rows if cls._looks_like_automation_item(row)] for rows in candidates]
        rows = max(scored, key=len, default=[])
        items: list[dict[str, Any]] = []
        for row in rows:
            name = cls._name(row)
            if not name:
                continue
            signals = cls._status_signals(row)
            conflicts = cls.conflicting_statuses(signals)
            status_evidence, status_reason = cls._status_evidence(row, signals)
            identifier = row.get("id") or row.get("appId") or row.get("ruleId")
            items.append(
                {
                    "id": str(identifier) if identifier is not None else None,
                    "name": name,
                    "display_name": cls.display_name(name),
                    "type": item_type,
                    "status": cls.normalise_status(row),
                    "broken": signals["broken"],
                    "paused": signals["paused"],
                    "disabled": signals["disabled"],
                    "active": signals["active"],
                    "status_conflict": bool(conflicts),
                    "conflicting_statuses": conflicts,
                    "status_reason": status_reason,
                    "status_evidence": status_evidence,
                    "source": source,
                }
            )
        return items

    @staticmethod
    def status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
        counts = {status: 0 for status in _STATUSES}
        for item in items:
            status = str(item.get("status") or "unknown")
            counts[status if status in counts else "unknown"] += 1
        return counts

    @staticmethod
    def _evidence(
        tool: str,
        arguments: dict[str, Any],
        result: MCPToolResult,
        elapsed_ms: int,
    ) -> dict[str, Any]:
        return {
            "tool": tool,
            "sub_tool": arguments.get("tool"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": elapsed_ms,
            "success": not bool(getattr(result, "is_error", False)),
            "supports_live_claim": True,
            "evidence_kind": "authoritative_automation_status",
            "arguments": arguments,
            "summary": f"normalised live automation status from {tool}",
        }

    @staticmethod
    def _capability_names(device: dict[str, Any]) -> set[str]:
        values = device.get("capabilities") or []
        if isinstance(values, dict):
            values = list(values)
        names = set()
        for item in values if isinstance(values, (list, tuple, set)) else []:
            if isinstance(item, dict):
                item = item.get("name") or item.get("capability")
            if item:
                names.add(str(item))
        return names

    @classmethod
    def _uncovered_capability_devices(
        cls,
        devices: list[dict[str, Any]],
        automation_items: list[dict[str, Any]],
        capabilities: "Iterable[str]",
    ) -> list[tuple[str, list[str]]]:
        automation_text = " | ".join(
            str(item.get("display_name") or item.get("name") or "").casefold()
            for item in automation_items
        )
        capability_set = set(capabilities)
        uncovered: list[tuple[str, list[str]]] = []
        seen_labels: set[str] = set()
        for device in devices:
            matched = cls._capability_names(device) & capability_set
            if not matched:
                continue
            label = str(device.get("label") or device.get("name") or "").strip()
            if not label or label.casefold() in seen_labels:
                continue
            if label.casefold() in automation_text:
                continue
            seen_labels.add(label.casefold())
            uncovered.append((label, sorted(matched)))
        return sorted(uncovered, key=lambda item: item[0].casefold())

    @classmethod
    def _uncovered_safety_devices(
        cls,
        devices: list[dict[str, Any]],
        automation_items: list[dict[str, Any]],
    ) -> list[tuple[str, list[str]]]:
        return cls._uncovered_capability_devices(
            devices, automation_items, _SAFETY_CAPABILITIES
        )

    @classmethod
    def _uncovered_common_automation_devices(
        cls,
        devices: list[dict[str, Any]],
        automation_items: list[dict[str, Any]],
    ) -> list[tuple[str, list[str]]]:
        return cls._uncovered_capability_devices(
            devices, automation_items, _COMMON_AUTOMATION_SUGGESTIONS.keys()
        )

    @classmethod
    def _advisory_message(
        cls,
        items: list[dict[str, Any]],
        devices: list[dict[str, Any]] | None = None,
    ) -> str:
        if not items:
            return (
                "No automation apps or Rule Machine rules were returned by "
                "Hubitat, so there's nothing to review yet."
            )
        counts = cls.status_counts(items)
        broken = [item for item in items if item["status"] == "broken"]
        disabled = [item for item in items if item["status"] == "disabled"]
        lines = [
            f"You have {len(items)} automation apps and Rule Machine rules: "
            f"{counts['active']} active, {len(disabled)} disabled, "
            f"{len(broken)} broken."
        ]
        found_suggestions = False
        if devices:
            uncovered = cls._uncovered_common_automation_devices(devices, items)
            if uncovered:
                found_suggestions = True
                suggestion_lines = []
                for label, caps in uncovered:
                    suggestion = " / ".join(
                        _COMMON_AUTOMATION_SUGGESTIONS[cap]
                        for cap in caps
                        if cap in _COMMON_AUTOMATION_SUGGESTIONS
                    )
                    suggestion_lines.append(
                        f"- **{label}** ({', '.join(caps)}): consider "
                        f"{suggestion}"
                    )
                lines.append(
                    "\nReal gap: these devices report a capability that "
                    "commonly gets its own automation, but no automation "
                    "name references them, so they don't appear to be "
                    "covered by anything yet:\n"
                    + "\n".join(suggestion_lines)
                )
        if broken:
            lines.append(
                "\nWorth fixing first (broken):\n"
                + "\n".join(
                    f"- {item.get('display_name') or item['name']}"
                    for item in broken
                )
            )
        if disabled:
            shown = disabled[:10]
            remainder = len(disabled) - len(shown)
            lines.append(
                "\nCurrently disabled -- worth a look if any are still "
                "relevant:\n"
                + "\n".join(
                    f"- {item.get('display_name') or item['name']}"
                    for item in shown
                )
                + (f"\n...and {remainder} more disabled." if remainder else "")
            )
        if not broken and not disabled:
            lines.append(
                "\nEverything currently configured is active -- nothing "
                "obviously broken or disabled to fix."
            )
        if found_suggestions:
            lines.append(
                "\nThese suggestions are grounded in matching your real "
                "device capabilities against your real automation names -- "
                "not certainty an existing automation doesn't already cover "
                "a device without naming it. Beyond capability gaps like "
                "these, I can't invent creative new automation ideas from "
                "scratch."
            )
        else:
            lines.append(
                "\nThis is a name-match against your existing automations, "
                "not certainty -- an automation could cover a device "
                "without naming it. And beyond capability coverage gaps, I "
                "don't yet have a way to suggest brand-new automation ideas "
                "from general device inventory."
            )
        return "\n".join(lines)

    @classmethod
    def _message(cls, items: list[dict[str, Any]]) -> str:
        if not items:
            return "No automation apps or Rule Machine rules were returned by Hubitat."
        counts = cls.status_counts(items)
        attention_count = sum(counts[status] for status in _ATTENTION_STATUSES)
        conflict_count = sum(bool(item.get("status_conflict")) for item in items)
        app_count = sum(item.get("type") == "app" for item in items)
        rule_count = sum(item.get("type") == "rule" for item in items)
        summary = (
            f"Hubitat returned {len(items)} automation items "
            f"({app_count} app instances, {rule_count} Rule Machine entries)."
        )
        if attention_count:
            summary += f" {attention_count} have configuration status flags requiring review."
        if conflict_count:
            summary += f" {conflict_count} have conflicting source-state signals."
        lines = [
            summary,
            "",
            "Configuration inventory only: enabled/not-disabled does not prove an "
            "automation ran successfully. Runtime errors, device availability, "
            "invalid actions and missing dependencies were not verified by this check. "
            "A *BROKEN* name marker alone does not identify a failing action. "
            "For execution failures, run the comprehensive read-only System Check.",
        ]
        for status in ("broken", "paused", "unknown", "disabled", "active"):
            matching = [item for item in items if item["status"] == status]
            if matching:
                lines.append(f"\n### {status.title()} ({len(matching)})")
                lines.extend(
                    f"- [{status.upper()}] {item.get('display_name') or item['name']} "
                    f"({item['type']}, ID {item.get('id') or 'unknown'})"
                    + (" [Hubitat name marker; cause unverified]"
                       if status == "broken" and "marked the automation name" in
                       str(item.get("status_reason") or "") else "")
                    + (" [conflicting source state]" if item.get("status_conflict") else "")
                    for item in matching
                )
        return "\n".join(lines)

    async def snapshot(self, *, advisory: bool = False) -> AutomationStatusOutcome:
        calls = (
            ("hub_read_apps_code", {"tool": "hub_list_apps", "args": {"scope": "instances"}}, "app"),
            ("hub_read_rules", {}, "rule"),
        )
        items: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        for tool, arguments, item_type in calls:
            started = time.monotonic()
            result = await self.mcp.call_tool(tool, arguments)
            evidence.append(
                self._evidence(
                    tool,
                    arguments,
                    result,
                    round((time.monotonic() - started) * 1000),
                )
            )
            if not getattr(result, "is_error", False):
                items.extend(self._items_from_result(result, item_type=item_type, source=tool))
        unique = {(i["type"], i.get("id") or "", i["name"].casefold()): i for i in items}
        ordered = sorted(
            unique.values(),
            key=lambda item: (_STATUSES.index(item["status"]), item["name"].casefold()),
        )
        counts = self.status_counts(ordered)
        devices: list[dict[str, Any]] = []
        if advisory:
            device_arguments = {"tool": "hub_list_devices", "args": {}}
            started = time.monotonic()
            device_result = await self.mcp.call_tool("hub_read_devices", device_arguments)
            evidence.append(
                self._evidence(
                    "hub_read_devices",
                    device_arguments,
                    device_result,
                    round((time.monotonic() - started) * 1000),
                )
            )
            if not getattr(device_result, "is_error", False):
                devices = [
                    item
                    for item in (HubitatMCPClient._find_device_list(device_result.data) or [])
                    if isinstance(item, dict)
                ]
        message = (
            self._advisory_message(ordered, devices) if advisory else self._message(ordered)
        )
        return AutomationStatusOutcome(
            message=message,
            evidence=evidence,
            automation_items=ordered,
            automation_counts=counts,
            attention_count=sum(counts[status] for status in _ATTENTION_STATUSES),
            conflict_count=sum(bool(item.get("status_conflict")) for item in ordered),
            devices=devices,
        )


__all__ = ["AutomationStatusOutcome", "AutomationStatusService"]
