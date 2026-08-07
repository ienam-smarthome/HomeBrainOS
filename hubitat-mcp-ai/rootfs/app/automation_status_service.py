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
# Capabilities where an unmonitored device is a meaningful safety gap --
# deliberately narrow and high-signal, not every capability a device has.
_SAFETY_CAPABILITIES = ("WaterSensor", "SmokeDetector", "CarbonMonoxideDetector")

# A broader, still-bounded set of capabilities where an automation is
# commonly worth having -- not just safety-critical. Live test: "recommend
# useful automations for my home" only ever found something to say when a
# safety-capability device happened to be uncovered; when it wasn't (as on
# this hub), the response fell back to a plain broken/disabled status dump
# with an honest "I can't invent new ideas" caveat -- which is truthful but
# not actually useful in response to "recommend automations". This mapping
# extends the same grounded, name-match gap analysis (never invents a
# device or automation, only cross-references real retrieved data) to a
# few more device kinds where a specific, well-understood automation is
# genuinely common, so a real, concrete suggestion is possible far more
# often -- while still declining to invent creative ideas that aren't
# reducible to "this device has capability X and nothing named for it
# uses it".
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


class AutomationStatusService:
    """Read and normalise app/rule state without relying on LLM formatting."""

    def __init__(self, mcp: HubitatMCPClient) -> None:
        self.mcp = mcp

    @staticmethod
    def matches_request(prompt: str) -> bool:
        value = " ".join(str(prompt).casefold().split())
        if any(word in value for word in ("enable ", "disable ", "pause ", "resume ")):
            return False
        subject = any(word in value for word in ("automation", "automations", "rule", "rules", "apps"))
        read = any(word in value for word in ("list", "show", "which", "status", "active", "disabled", "paused", "broken"))
        advisory = any(word in value for word in _ADVISORY_WORDS)
        return subject and (read or advisory)

    @staticmethod
    def is_advisory_request(prompt: str) -> bool:
        """True when the request wants feedback on existing automations
        ("recommend", "review", "clean up", ...) rather than a literal
        status listing. Only meaningful when matches_request() is already
        True; a request can match on `read` words alone with no advisory
        words present, in which case this is False and the literal listing
        applies as before.
        """

        value = " ".join(str(prompt).casefold().split())
        return any(word in value for word in _ADVISORY_WORDS)

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
        # Broken+paused is meaningful precedence, but it is still conflicting source
        # evidence and should be visible to diagnostics/API consumers.
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
        """Devices with one of `capabilities` but no automation whose name
        references the device's label.

        This is a name-match heuristic against the same automation names
        already retrieved for the status listing -- not a certainty (an
        automation could reference a device without naming it, or name-match
        something unrelated), but a genuinely useful, fully grounded
        starting point: every device and every automation name involved is
        real, retrieved data, nothing is invented. Shared by both the
        narrow safety-only view and the broader common-automation view
        below -- only the capability set differs.
        """

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
        # Genuine new-automation suggestions lead the response -- this is
        # the direct answer to "recommend automations", so it must not be
        # buried after a diagnostic dump of existing app/rule health that
        # wasn't actually what was asked for.
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
        summary = f"Hubitat returned {len(items)} automation items."
        if attention_count:
            summary += f" {attention_count} need attention."
        if conflict_count:
            summary += f" {conflict_count} have conflicting source-state signals."
        lines = [summary]
        for status in ("broken", "paused", "unknown", "disabled", "active"):
            matching = [item for item in items if item["status"] == status]
            if matching:
                lines.append(f"\n### {status.title()} ({len(matching)})")
                lines.extend(
                    f"- [{status.upper()}] {item.get('display_name') or item['name']} ({item['type']})"
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
        )


__all__ = ["AutomationStatusOutcome", "AutomationStatusService"]
