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
        return subject and read

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

    async def snapshot(self) -> AutomationStatusOutcome:
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
        return AutomationStatusOutcome(
            message=self._message(ordered),
            evidence=evidence,
            automation_items=ordered,
            automation_counts=counts,
            attention_count=sum(counts[status] for status in _ATTENTION_STATUSES),
            conflict_count=sum(bool(item.get("status_conflict")) for item in ordered),
        )


__all__ = ["AutomationStatusOutcome", "AutomationStatusService"]
