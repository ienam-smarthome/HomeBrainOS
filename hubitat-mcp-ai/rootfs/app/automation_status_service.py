from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mcp_client import HubitatMCPClient, MCPToolResult

_STATUSES = ("active", "disabled", "paused", "broken", "unknown")


@dataclass(slots=True)
class AutomationStatusOutcome:
    message: str
    request_class: str = "live-read"
    evidence: list[dict[str, Any]] = field(default_factory=list)
    choices: list[str] = field(default_factory=list)
    automation_items: list[dict[str, Any]] = field(default_factory=list)
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

    @classmethod
    def normalise_status(cls, item: dict[str, Any]) -> str:
        status_text = " ".join(
            str(item.get(key) or "").casefold()
            for key in ("status", "state", "healthStatus")
        ).strip()
        broken = cls._bool(item.get("broken"))
        disabled = cls._bool(item.get("disabled"))
        enabled = cls._bool(item.get("enabled"))
        paused = cls._bool(item.get("paused"))
        active = cls._bool(item.get("active"))

        if broken is True or any(word in status_text for word in ("broken", "error", "failed")):
            return "broken"
        if disabled is True or enabled is False or "disabled" in status_text:
            return "disabled"
        if paused is True or "paused" in status_text:
            return "paused"
        if active is True or enabled is True or any(
            word in status_text for word in ("active", "enabled", "running")
        ):
            return "active"

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

    _SCHEMA_ONLY_KEYS = (
        "input_schema", "inputSchema", "output_schema", "outputSchema",
        "parameters",
    )

    @classmethod
    def _looks_like_automation_item(cls, row: dict[str, Any]) -> bool:
        name = row.get("label") or row.get("name") or row.get("displayName") or row.get("title")
        if not name or any(key in row for key in cls._SCHEMA_ONLY_KEYS):
            return False
        return any(key in row for key in ("id", "appId", "ruleId", *cls._STATE_FIELDS))

    @classmethod
    def _items_from_result(cls, result: MCPToolResult, *, item_type: str, source: str) -> list[dict[str, Any]]:
        candidates = cls._candidate_lists(result.data)
        scored = [[row for row in rows if cls._looks_like_automation_item(row)] for rows in candidates]
        rows = max(scored, key=len, default=[])
        return [
            {
                "id": str(row.get("id") or row.get("appId") or row.get("ruleId")) if (row.get("id") or row.get("appId") or row.get("ruleId")) is not None else None,
                "name": str(row.get("label") or row.get("name") or row.get("displayName") or row.get("title")),
                "type": item_type,
                "status": cls.normalise_status(row),
                "source": source,
            }
            for row in rows
            if row.get("label") or row.get("name") or row.get("displayName") or row.get("title")
        ]

    @staticmethod
    def _evidence(tool: str, arguments: dict[str, Any], result: MCPToolResult, elapsed_ms: int) -> dict[str, Any]:
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
    def _message(items: list[dict[str, Any]]) -> str:
        if not items:
            return "No automation apps or Rule Machine rules were returned by Hubitat."
        counts = {status: 0 for status in _STATUSES}
        for item in items:
            counts[item["status"]] += 1
        lines = [f"Hubitat returned {len(items)} automation items."]
        for status in _STATUSES:
            matching = [item for item in items if item["status"] == status]
            if matching:
                lines.append(f"\n### {status.title()}")
                lines.extend(f"- [{status.upper()}] {item['name']} ({item['type']})" for item in matching)
        return "\n".join(lines)

    async def snapshot(self) -> AutomationStatusOutcome:
        calls = (("hub_read_apps_code", {"tool": "hub_list_apps", "args": {"scope": "instances"}}, "app"), ("hub_read_rules", {}, "rule"))
        items: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        for tool, arguments, item_type in calls:
            started = time.monotonic()
            result = await self.mcp.call_tool(tool, arguments)
            evidence.append(self._evidence(tool, arguments, result, round((time.monotonic() - started) * 1000)))
            if not getattr(result, "is_error", False):
                items.extend(self._items_from_result(result, item_type=item_type, source=tool))
        unique = {(i["type"], i.get("id") or "", i["name"].casefold()): i for i in items}
        ordered = sorted(unique.values(), key=lambda i: (_STATUSES.index(i["status"]), i["name"].casefold()))
        return AutomationStatusOutcome(message=self._message(ordered), evidence=evidence, automation_items=ordered)


__all__ = ["AutomationStatusOutcome", "AutomationStatusService"]
