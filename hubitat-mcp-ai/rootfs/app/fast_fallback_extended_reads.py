from __future__ import annotations

import re
from typing import Any, Iterable

from fallback_router import _device_id, _label, _normalise
from fast_fallback_device_status import FastFallbackRouter as DeviceStatusRouter
from mcp_client import MCPError, MCPToolResult
from presenter import display_payload, first_value, normalise_text, safe_debug


_EVENT_PATTERNS = (
    re.compile(
        r"^(?:show|list|get|find)\s+(?:the\s+)?(?:recent\s+)?events\s+(?:for|from|of)\s+(.+?)[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(r"^(?:show|list|get)\s+(.+?)\s+events[?.!]*$", re.IGNORECASE),
)


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _rows(value: Any, preferred: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        lowered = {str(key).lower(): item for key, item in value.items()}
        for key in preferred:
            candidate = lowered.get(key.lower())
            if isinstance(candidate, list):
                found = [item for item in candidate if isinstance(item, dict)]
                if found:
                    return found
    best: list[dict[str, Any]] = []
    for item in _walk(value):
        if not isinstance(item, list):
            continue
        found = [entry for entry in item if isinstance(entry, dict)]
        if len(found) > len(best):
            best = found
    return best


def _text(row: dict[str, Any], *names: str) -> str | None:
    value = first_value(row, *names)
    if value in (None, ""):
        return None
    cleaned = normalise_text(value)
    return cleaned or None


class FastFallbackRouter(DeviceStatusRouter):
    """Direct read-only routes for high-value tools behind MCP gateways."""

    async def answer(self, query: str) -> dict[str, Any]:
        q = _normalise(query)

        if self._is_logs_query(q):
            return await self._logs(q)
        if any(term in q for term in ("slow apps", "slow devices", "performance stats", "hub performance", "busy apps", "busy devices")):
            return await self._performance()
        if any(term in q for term in ("scheduled jobs", "running jobs", "hub jobs", "scheduled tasks")):
            return await self._jobs()
        if self._is_installed_apps_query(q):
            return await self._installed_apps()
        if any(term in q for term in ("hpm packages", "installed packages", "package manager packages")):
            return await self._hpm_packages()
        if any(term in q for term in ("hub variables", "global variables", "list variables", "show variables")):
            return await self._variables()
        if any(term in q for term in ("easy dashboards", "hub dashboards", "list dashboards", "show dashboards")):
            return await self._dashboards()
        if any(term in q for term in ("memory history", "cpu history", "memory trend", "cpu trend")):
            return await self._memory_history()
        if any(term in q for term in ("z-wave details", "zwave details", "zigbee details", "radio details", "matter details")):
            return await self._radio_details(q)

        event_device = self._event_device_candidate(query)
        if event_device:
            return await self._device_events(event_device)

        return await super().answer(query)

    @staticmethod
    def _is_logs_query(q: str) -> bool:
        return bool(
            re.search(r"\bhub\s+(?:logs?|errors?|warnings?)\b", q)
            or q in {"logs", "errors", "logs and errors", "show logs", "show errors"}
        )

    @staticmethod
    def _is_installed_apps_query(q: str) -> bool:
        return bool(
            re.match(r"^(?:list|show|find|get)\s+(?:all\s+)?(?:installed\s+)?(?:hubitat\s+)?apps?\??$", q)
            or q in {"installed apps", "hub apps", "app instances"}
        )

    @staticmethod
    def _event_device_candidate(query: str) -> str | None:
        text = str(query or "").strip()
        for pattern in _EVENT_PATTERNS:
            match = pattern.match(text)
            if match:
                candidate = re.sub(r"\s+", " ", match.group(1).strip(" .!?"))
                if _normalise(candidate) not in {"hub", "location", "mode", "hsm"}:
                    return candidate
        return None

    async def _read_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        result = await self.client.call_tool(name, arguments or {})
        if result.is_error:
            raise MCPError(result.text or f"{name} failed")
        return result

    def _response_with_rows(
        self,
        *,
        result: MCPToolResult,
        intent: str,
        title: str,
        subtitle: str,
        rows: list[dict[str, Any]],
        title_fields: tuple[str, ...],
        value_fields: tuple[str, ...],
        subtitle_fields: tuple[str, ...],
        icon: str,
        note: str,
        empty_message: str,
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        lines: list[str] = []
        for row in rows[:20]:
            item_title = _text(row, *title_fields) or "Item"
            item_value = _text(row, *value_fields) or "Available"
            item_subtitle = _text(row, *subtitle_fields)
            items.append(
                {
                    "icon": icon,
                    "title": item_title,
                    "value": item_value,
                    "subtitle": item_subtitle,
                }
            )
            line = f"- {item_title}: {item_value}"
            if item_subtitle:
                line += f" ({item_subtitle})"
            lines.append(line)

        message = empty_message if not rows else f"{title}:\n" + "\n".join(lines)
        display = display_payload(
            intent,
            title,
            subtitle=subtitle,
            metrics=[{"label": "Found", "value": str(len(rows)), "icon": icon}],
            items=items,
            note=note,
        )
        response = self._response(message, intent, True, result)
        response["display"] = display
        response["technical"] = safe_debug(result.data)
        return response

    async def _logs(self, q: str) -> dict[str, Any]:
        result = await self._read_tool("hub_get_logs")
        rows = _rows(result.data, ("logs", "entries", "items"))
        error_only = any(term in q for term in ("error", "warning", "warn"))
        if error_only:
            important = [
                row
                for row in rows
                if (_text(row, "level", "severity", "type") or "").lower()
                in {"error", "warn", "warning", "fatal"}
            ]
            if important:
                rows = important
        return self._response_with_rows(
            result=result,
            intent="fallback-hub-logs",
            title="Hub logs and errors",
            subtitle=f"{len(rows)} recent entr{'y' if len(rows) == 1 else 'ies'}",
            rows=rows,
            title_fields=("message", "msg", "description"),
            value_fields=("level", "severity", "type"),
            subtitle_fields=("date", "timestamp", "time", "source", "appName", "deviceName"),
            icon="📜",
            note="Read from the MCP hub_get_logs diagnostic tool.",
            empty_message="No matching recent hub log entries were returned.",
        )

    async def _performance(self) -> dict[str, Any]:
        result = await self._read_tool("hub_get_performance_stats")
        rows = _rows(result.data, ("stats", "apps", "devices", "items"))
        rows.sort(
            key=lambda row: float(first_value(row, "percentBusy", "busyPercent", "totalMs") or 0),
            reverse=True,
        )
        return self._response_with_rows(
            result=result,
            intent="fallback-performance-stats",
            title="Hub performance",
            subtitle="Apps and devices with the highest recorded activity",
            rows=rows,
            title_fields=("name", "label", "appName", "deviceName"),
            value_fields=("percentBusy", "busyPercent", "totalMs", "count"),
            subtitle_fields=("type", "stateSize", "events", "id"),
            icon="📊",
            note="Read from hub_get_performance_stats.",
            empty_message="No performance statistics were returned by the MCP server.",
        )

    async def _jobs(self) -> dict[str, Any]:
        result = await self._read_tool("hub_get_jobs")
        rows = _rows(result.data, ("jobs", "scheduledJobs", "runningJobs", "actions"))
        return self._response_with_rows(
            result=result,
            intent="fallback-hub-jobs",
            title="Hub jobs",
            subtitle=f"{len(rows)} scheduled or running job{'s' if len(rows) != 1 else ''}",
            rows=rows,
            title_fields=("name", "method", "handler", "description"),
            value_fields=("status", "state", "nextRun", "date"),
            subtitle_fields=("appName", "deviceName", "id", "schedule"),
            icon="⏲️",
            note="Read from hub_get_jobs.",
            empty_message="No scheduled or running hub jobs were returned.",
        )

    async def _installed_apps(self) -> dict[str, Any]:
        result = await self._read_tool("hub_list_apps", {"scope": "instances"})
        rows = _rows(result.data, ("apps", "instances", "items"))
        return self._response_with_rows(
            result=result,
            intent="fallback-installed-apps",
            title="Installed apps",
            subtitle=f"{len(rows)} app instance{'s' if len(rows) != 1 else ''}",
            rows=rows,
            title_fields=("label", "name", "appName"),
            value_fields=("status", "enabled", "type", "id"),
            subtitle_fields=("parentName", "namespace", "builtIn", "disabled"),
            icon="🧩",
            note="Read from hub_list_apps through the apps/code gateway.",
            empty_message="No installed app instances were returned.",
        )

    async def _hpm_packages(self) -> dict[str, Any]:
        result = await self._read_tool("hub_list_hpm_packages")
        rows = _rows(result.data, ("packages", "items"))
        return self._response_with_rows(
            result=result,
            intent="fallback-hpm-packages",
            title="HPM packages",
            subtitle=f"{len(rows)} package{'s' if len(rows) != 1 else ''} tracked",
            rows=rows,
            title_fields=("name", "packageName"),
            value_fields=("version", "installedVersion", "status"),
            subtitle_fields=("author", "beta", "updateAvailable"),
            icon="📦",
            note="Read from hub_list_hpm_packages. HPM must be installed.",
            empty_message="No HPM-tracked packages were returned.",
        )

    async def _variables(self) -> dict[str, Any]:
        result = await self._read_tool("hub_list_variables")
        rows = _rows(result.data, ("variables", "items"))
        return self._response_with_rows(
            result=result,
            intent="fallback-hub-variables",
            title="Hub variables",
            subtitle=f"{len(rows)} variable{'s' if len(rows) != 1 else ''}",
            rows=rows,
            title_fields=("name", "variableName"),
            value_fields=("value", "currentValue"),
            subtitle_fields=("type", "connector", "id"),
            icon="🔣",
            note="Read from hub_list_variables.",
            empty_message="No hub variables were returned.",
        )

    async def _dashboards(self) -> dict[str, Any]:
        result = await self._read_tool("hub_list_dashboards")
        rows = _rows(result.data, ("dashboards", "items"))
        return self._response_with_rows(
            result=result,
            intent="fallback-hub-dashboards",
            title="Easy Dashboards",
            subtitle=f"{len(rows)} dashboard{'s' if len(rows) != 1 else ''}",
            rows=rows,
            title_fields=("name", "label", "title"),
            value_fields=("id", "tiles", "tileCount"),
            subtitle_fields=("theme", "layout", "pinProtected"),
            icon="🖥️",
            note="Read from hub_list_dashboards.",
            empty_message="No Easy Dashboards were returned.",
        )

    async def _memory_history(self) -> dict[str, Any]:
        result = await self._read_tool("hub_get_memory_history")
        rows = _rows(result.data, ("history", "samples", "entries", "items"))
        return self._response_with_rows(
            result=result,
            intent="fallback-memory-history",
            title="Memory and CPU history",
            subtitle=f"{len(rows)} sample{'s' if len(rows) != 1 else ''}",
            rows=rows,
            title_fields=("date", "timestamp", "time"),
            value_fields=("freeMemoryMB", "freeMemory", "memory"),
            subtitle_fields=("cpuPercent", "cpuLoad", "load", "temperature"),
            icon="📈",
            note="Read from hub_get_memory_history.",
            empty_message="No memory or CPU history samples were returned.",
        )

    async def _radio_details(self, q: str) -> dict[str, Any]:
        arguments: dict[str, Any] = {}
        if "zigbee" in q:
            arguments["radio"] = "zigbee"
        elif "z-wave" in q or "zwave" in q:
            arguments["radio"] = "zwave"
        result = await self._read_tool("hub_get_radio_details", arguments)
        rows = _rows(result.data, ("devices", "radios", "details", "items"))
        title = "Zigbee details" if arguments.get("radio") == "zigbee" else "Z-Wave details" if arguments.get("radio") == "zwave" else "Radio details"
        return self._response_with_rows(
            result=result,
            intent="fallback-radio-details",
            title=title,
            subtitle=f"{len(rows)} radio entr{'y' if len(rows) == 1 else 'ies'}",
            rows=rows,
            title_fields=("name", "label", "radio", "protocol"),
            value_fields=("status", "state", "firmware", "channel"),
            subtitle_fields=("id", "nodeId", "networkId", "route"),
            icon="📡",
            note="Read from hub_get_radio_details.",
            empty_message="No radio details were returned.",
        )

    async def _device_events(self, requested_name: str) -> dict[str, Any]:
        live = await self._live_devices()
        candidates = self._device_rows(live.data)
        match, alternatives = self._match_device(requested_name, candidates)
        if not match and hasattr(self, "_humidity_speech_alias_match"):
            match = self._humidity_speech_alias_match(requested_name, candidates)
        if not match:
            message = f'I could not find one exact selected MCP device named "{requested_name}".'
            if alternatives:
                message += " Closest matches: " + ", ".join(alternatives[:5]) + "."
            response = self._response(message, "fallback-device-events-not-found", False, live)
            response["alternatives"] = alternatives[:5]
            return response

        device_id = _device_id(match)
        result = await self._read_tool(
            "hub_list_device_events",
            {"deviceId": device_id, "hoursBack": 24},
        )
        rows = _rows(result.data, ("events", "items"))
        label = _label(match) or f"Device {device_id}"
        return self._response_with_rows(
            result=result,
            intent="fallback-device-events",
            title=f"{label} events",
            subtitle="Most recent events from the last 24 hours",
            rows=rows,
            title_fields=("name", "attribute", "descriptionText"),
            value_fields=("value", "currentValue", "descriptionText"),
            subtitle_fields=("date", "timestamp", "unit", "source"),
            icon="🕘",
            note="Read from hub_list_device_events using the resolved device ID.",
            empty_message=f"No events were returned for {label} in the last 24 hours.",
        )


__all__ = ["FastFallbackRouter"]
