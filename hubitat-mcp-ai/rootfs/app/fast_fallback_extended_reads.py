from __future__ import annotations

import json
import re
from statistics import mean
from typing import Any, Iterable

from fallback_router import _device_id, _label, _normalise
from fast_fallback_device_health import SpeechFastFallbackRouter
from fast_fallback_live import _looks_like_light, live_attributes
from hub_cpu_probe import probe_hub_cpu
from hub_metric_formatting import format_database_size
from mcp_client import MCPError, MCPToolResult
from presenter import (
    bool_label,
    compact_number,
    display_payload,
    first_mapping,
    first_value,
    format_memory_kb,
    normalise_text,
    present_hub_info,
    safe_debug,
    walk,
)

_ACTIVE_RULE_STATES = {"active", "enabled", "running"}
_INACTIVE_RULE_STATES = {"paused", "disabled", "inactive", "stopped"}

_HUB_LOG_QUERY = re.compile(
    r"^(?:please\s+)?(?:(?:check|show|review|inspect|scan|list|get)\s+|look\s+at\s+)"
    r"(?:the\s+)?(?:(?:hub|hubitat)\s+)?(?:logs?|errors?|warnings?)"
    r"(?:\s+and\s+(?:errors?|warnings?))?"
    r"(?:\s+(?:"
    r"(?:for|and\s+(?:show|list))\s+(?:any\s+)?"
    r"(?:issues?|errors?|warnings?)"
    r"|(?:to|and)\s+(?:see|check|find)\s+"
    r"(?:(?:if|whether)\s+)?(?:there\s+(?:are|is)\s+)?(?:any\s+)?"
    r"(?:issues?|errors?|warnings?)"
    r"))?[?.!]*$",
    re.IGNORECASE,
)

_COMPARE_RE = re.compile(
    r"^compare\s+(humidity|temperature)\s+(?:in|between)\s+(?:the\s+)?(.+?)\s+and\s+(?:the\s+)?(.+?)[?.!]*$",
    re.IGNORECASE,
)

_MOTION_QUERY = re.compile(
    r"^(?:(?:which|what|list|show)\s+)?(?:motion\s+)?sensors?\s+(?:are\s+)?active\??$|^(?:where\s+is\s+)?motion\s+active\??$",
    re.IGNORECASE,
)

_ROOM_DEVICE_PATTERNS = (
    re.compile(
        r"^(?:list|show|display|find)\s+(?:all\s+)?devices\s+"
        r"(?:listed\s+)?(?:in|under|inside|from|assigned\s+to)\s+(?:the\s+)?(.+?)[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:what|which)\s+devices\s+(?:are\s+)?(?:listed\s+)?"
        r"(?:in|under|inside|from|assigned\s+to)\s+(?:the\s+)?(.+?)[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:list|show|display)\s+(?:the\s+)?(.+?)\s+room[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:list|show|display|find)\s+(?:all\s+)?(?:the\s+)?"
        r"(.+?)\s+devices[?.!]*$",
        re.IGNORECASE,
    ),
    # Mobile/voice shorthand: "List Apps" where Apps is an exact Hubitat room.
    re.compile(
        r"^(?:list|show|display)\s+(?:the\s+)?([a-z0-9][a-z0-9 &'_\-]{0,50})[?.!]*$",
        re.IGNORECASE,
    ),
)

_MAX_EMPTY_SENSOR_DETAIL_PROBES = 4


def is_hub_logs_query(query: str) -> bool:
    """Match live Hubitat logs without claiming HomeBrain self-diagnostics."""

    q = _normalise(query)
    if re.search(
        r"\b(?:homebrain|assistant|request)\s+"
        r"(?:logs?|errors?|warnings?|diagnostics?)\b",
        q,
    ):
        return False
    return bool(
        _HUB_LOG_QUERY.match(str(query or "").strip())
        or q
        in {
            "logs",
            "errors",
            "warnings",
            "logs and errors",
            "hub logs",
            "hub errors",
            "hub warnings",
        }
    )


def _log_identity(row: dict[str, Any]) -> tuple[str, str, str, str]:
    """Return stable timestamp, level, source and detail fields for a Hubitat log row."""

    level = (_text(row, "level", "severity", "type") or "info").strip().lower()
    timestamp = _text(row, "date", "timestamp", "time", "name") or ""
    message = _text(row, "message", "msg", "description") or ""
    parts = message.split("|", 3)
    if len(parts) == 4 and parts[0] in {"app", "dev"}:
        source = parts[2].strip() or f"{parts[0]} {parts[1]}"
        detail = parts[3].strip() or message
    else:
        source = _text(row, "source", "appName", "deviceName") or "Hubitat"
        detail = message
    return timestamp, level, source, detail


def _dedupe_log_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        timestamp, level, _source, detail = _log_identity(row)
        unique.setdefault((timestamp, level, detail), dict(row))
    return sorted(
        unique.values(),
        key=lambda row: _log_identity(row)[0],
        reverse=True,
    )


def _needs_empty_device_detail(
    item: dict[str, Any],
    attrs: dict[str, Any],
) -> bool:
    """Identify useful devices whose compact inventory omitted live states."""

    if attrs:
        return False

    text = _normalise(
        " ".join(
            str(item.get(key) or "")
            for key in (
                "label",
                "name",
                "displayName",
                "deviceType",
                "type",
                "category",
                "capabilities",
            )
        )
    )

    return any(
        condition
        for condition in (
            " lux" in f" {text}",
            "illuminance" in text,
            " fan" in f" {text}",
            "fancontrol" in text,
            "fan control" in text,
            "power meter" in text,
            "powermeter" in text,
            "energy meter" in text,
            "energymeter" in text,
            "thermostat" in text,
            "temperaturemeasurement" in text,
            "lock" in text,
            "valve" in text,
            "water sensor" in text,
            "watersensor" in text,
            "leak" in text,
            "smoke" in text,
        )
    )


def _detail_device_record(value: Any, device_id: str) -> dict[str, Any] | None:
    """Find the requested device record inside a detailed MCP response."""

    fallback: dict[str, Any] | None = None

    for candidate in walk(value):
        if not isinstance(candidate, dict):
            continue

        candidate_id = str(
            candidate.get("id")
            or candidate.get("deviceId")
            or candidate.get("device_id")
            or ""
        )

        if candidate_id and candidate_id == device_id:
            return candidate

        if fallback is None and any(
            key in candidate
            for key in (
                "currentStates",
                "current_states",
                "attributes",
                "states",
                "illuminance",
                "speed",
                "switch",
                "power",
                "energy",
                "thermostatMode",
                "thermostatOperatingState",
                "thermostatSetpoint",
                "heatingSetpoint",
                "coolingSetpoint",
                "lock",
                "valve",
                "water",
                "smoke",
            )
        ):
            fallback = candidate

    return fallback


def _format_number(value: Any) -> str:
    try:
        number = float(str(value).replace("%", "").strip())
    except Exception:
        return str(value).strip()
    return f"{number:g}"


def _room_display_title(room_name: str) -> str:
    """Avoid titles such as 'Living Room room'."""

    name = str(room_name or "").strip()
    if _normalise(name).endswith(" room"):
        return name
    return f"{name} room"


def _room_device_icon(
    item: dict[str, Any],
    attrs: dict[str, Any],
    device_type: str,
) -> str:
    """Choose a meaningful room-card icon from label, type and live attributes."""

    text = _normalise(
        " ".join(
            (
                str(item.get("label") or ""),
                str(item.get("name") or ""),
                str(item.get("displayName") or ""),
                str(device_type or ""),
                " ".join(str(key) for key in attrs),
            )
        )
    )

    if _looks_like_light(item):
        return "💡"
    if "fan" in text or "speed" in attrs:
        return "🌀"
    if "illuminance" in attrs or " lux" in f" {text}":
        return "🔆"
    if any(
        key in attrs
        for key in (
            "thermostatMode",
            "thermostatOperatingState",
            "thermostatSetpoint",
            "heatingSetpoint",
            "coolingSetpoint",
        )
    ):
        return "♨️"
    if "power" in attrs or "energy" in attrs:
        return "⚡"
    if "lock" in attrs:
        return "🔒"
    if "valve" in attrs:
        return "🚰"
    if "water" in attrs:
        return "💧"
    if "smoke" in attrs:
        return "🚨"
    if "temperature" in attrs:
        return "🌡️"
    if "humidity" in attrs:
        return "💧"
    if "motion" in attrs:
        return "🏃"
    if "presence" in attrs:
        return "📍"
    if "contact" in attrs:
        return "🚪"
    if "battery" in attrs:
        return "🔋"
    if "switch" in attrs:
        return "🔌"
    return "📱"


def _room_device_states(attrs: dict[str, Any], primary_state: str) -> list[str]:
    """Return useful compact live states without discarding secondary metrics."""

    states: list[str] = []

    speed = attrs.get("speed")
    illuminance = attrs.get("illuminance")
    temperature = attrs.get("temperature")
    humidity = attrs.get("humidity")
    power = attrs.get("power")
    energy = attrs.get("energy")
    thermostat_mode = attrs.get("thermostatMode")
    operating_state = attrs.get("thermostatOperatingState")
    thermostat_setpoint = attrs.get("thermostatSetpoint")
    heating_setpoint = attrs.get("heatingSetpoint")
    cooling_setpoint = attrs.get("coolingSetpoint")

    if thermostat_mode not in (None, ""):
        states.append(
            str(thermostat_mode).strip().replace("_", " ").title()
        )

    if operating_state not in (None, ""):
        formatted_operating = (
            str(operating_state).strip().replace("_", " ").title()
        )
        if _normalise(formatted_operating) not in {
            _normalise(item) for item in states
        }:
            states.append(formatted_operating)

    setpoint = next(
        (
            value
            for value in (
                thermostat_setpoint,
                heating_setpoint,
                cooling_setpoint,
            )
            if value not in (None, "")
        ),
        None,
    )
    if setpoint is not None:
        states.append(f"{_format_number(setpoint)}°C setpoint")

    if speed not in (None, ""):
        states.append(str(speed).strip().replace("_", " ").title())

    if illuminance not in (None, ""):
        states.append(f"{_format_number(illuminance)} lx")

    if temperature not in (None, ""):
        states.append(f"{_format_number(temperature)}°C")

    if humidity not in (None, ""):
        states.append(f"{_format_number(humidity)}% humidity")

    if power not in (None, ""):
        states.append(f"{_format_number(power)} W")

    if energy not in (None, ""):
        states.append(f"{_format_number(energy)} kWh")

    for attribute, labels in (
        ("switch", {"on": "On", "off": "Off"}),
        ("motion", {"active": "Active", "inactive": "Inactive"}),
        ("contact", {"open": "Open", "closed": "Closed"}),
        ("presence", {"present": "Present", "not present": "Not present"}),
        ("lock", {"locked": "Locked", "unlocked": "Unlocked"}),
        ("valve", {"open": "Open", "closed": "Closed"}),
        ("water", {"wet": "Wet", "dry": "Dry"}),
        ("smoke", {"detected": "Smoke detected", "clear": "Clear"}),
    ):
        value = _normalise(attrs.get(attribute))
        formatted = labels.get(value)
        if formatted and _normalise(formatted) not in {
            _normalise(item) for item in states
        }:
            states.append(formatted)
            break

    battery = attrs.get("battery")
    if battery not in (None, "") and not states:
        states.append(f"{_format_number(battery)}% battery")

    if not states and primary_state:
        states.append(str(primary_state))

    return states


_RESERVED_SHORTHAND = {
    "all devices",
    "devices",
    "all lights",
    "lights",
    "switches",
    "rooms",
    "my rooms",
    "hubitat rooms",
    "my hubitat rooms",
    "rules",
    "active rules",
    "automation rules",
    "active automation rules",
    "low batteries",
    "batteries",
    "weather",
    "forecast",
    "motion sensors",
    "active motion sensors",
    "hub health",
    "hub status",
    "hub resources",
}

_DEVICE_STATUS_PATTERNS = (
    re.compile(
        r"^(?:show|display|get)\s+(?:the\s+)?(?:status\s+(?:of|for)\s+)?(.+?)[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:what(?:'s| is)\s+)?(?:the\s+)?status\s+(?:of|for)\s+(.+?)[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(r"^(.+?)\s+status[?.!]*$", re.IGNORECASE),
)

_RESERVED_STATUS_TARGETS = {
    "hub cpu",
    "hub memory",
    "hub free memory",
    "hub resources",
    "hub temperature",
    "hub uptime",
    "hub health",
    "hub health status",
    "hub status",
    "hub logs",
    "hub logs and errors",
    "logs",
    "logs and errors",
    "weather",
    "forecast",
    "rooms",
    "rules",
    "devices",
    "all devices",
    "lights",
    "all lights",
    "switches",
    "low batteries",
}

_ATTRIBUTE_ORDER = (
    "switch",
    "power",
    "energy",
    "level",
    "temperature",
    "humidity",
    "battery",
    "motion",
    "contact",
    "presence",
    "thermostatOperatingState",
    "thermostatMode",
    "heatingSetpoint",
    "coolingSetpoint",
    "healthStatus",
    "status",
    "voltage",
    "current",
    "illuminance",
)

_ATTRIBUTE_LABELS = {
    "switch": "Switch",
    "power": "Power",
    "energy": "Energy",
    "level": "Level",
    "temperature": "Temperature",
    "humidity": "Humidity",
    "battery": "Battery",
    "motion": "Motion",
    "contact": "Contact",
    "presence": "Presence",
    "thermostatOperatingState": "Operating state",
    "thermostatMode": "Thermostat mode",
    "heatingSetpoint": "Heating setpoint",
    "coolingSetpoint": "Cooling setpoint",
    "healthStatus": "Health",
    "status": "Status",
    "voltage": "Voltage",
    "current": "Current",
    "illuminance": "Illuminance",
}

_ATTRIBUTE_ICONS = {
    "switch": "⚡",
    "power": "🔌",
    "energy": "📈",
    "level": "🔆",
    "temperature": "🌡️",
    "humidity": "💧",
    "battery": "🔋",
    "motion": "🏃",
    "contact": "🚪",
    "presence": "📍",
    "thermostatOperatingState": "♨️",
    "thermostatMode": "🌡️",
    "heatingSetpoint": "🔥",
    "coolingSetpoint": "❄️",
    "healthStatus": "📡",
    "status": "ℹ️",
    "voltage": "🔋",
    "current": "⚡",
    "illuminance": "☀️",
}

_ATTRIBUTE_UNITS = {
    "power": "W",
    "energy": "kWh",
    "level": "%",
    "temperature": "°C",
    "humidity": "%",
    "battery": "%",
    "heatingSetpoint": "°C",
    "coolingSetpoint": "°C",
    "voltage": "V",
    "current": "A",
    "illuminance": "lx",
}

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

class InventoryFastFallbackRouter(SpeechFastFallbackRouter):
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

class DashboardFastFallbackRouter(InventoryFastFallbackRouter):
    """Fast structured inventories, room comparisons and live hub resources."""

    def __init__(
        self,
        client: Any,
        attention_stale_hours: float = 48,
        *,
        cpu_probe_enabled: bool = True,
        cpu_probe_timeout_seconds: float = 2.5,
    ) -> None:
        super().__init__(client, attention_stale_hours=attention_stale_hours)
        self.cpu_probe_enabled = bool(cpu_probe_enabled)
        self.cpu_probe_timeout_seconds = max(0.5, float(cpu_probe_timeout_seconds))

    async def answer(self, query: str) -> dict[str, Any]:
        q = _normalise(query)
        if re.match(r"^(?:list|show)\s+(?:all\s+)?devices\??$", q):
            return await self._device_inventory("device")
        if re.match(r"^(?:list|show)\s+(?:all\s+)?lights\??$", q):
            return await self._device_inventory("light")
        comparison = _COMPARE_RE.match(q)
        if comparison:
            return await self._compare_rooms(
                attribute=comparison.group(1).lower(),
                first_room=comparison.group(2),
                second_room=comparison.group(3),
            )
        return await super().answer(query)

    async def _hub_resources(self) -> dict[str, Any]:
        result = await self.client.call_tool("hub_get_info", {})
        if result.is_error:
            raise MCPError(result.text or "hub_get_info failed")

        data = first_mapping(result.data)
        model = first_value(data, "name", "hubName", "model") or "Hubitat hub"
        firmware = first_value(data, "firmwareVersion", "currentVersion")
        local_ip = first_value(data, "localIP", "ip", "ipAddress")
        free_memory = format_memory_kb(
            first_value(data, "freeMemoryKB", "freeMemoryKb")
        )
        temperature = compact_number(
            first_value(data, "internalTempCelsius", "temperature"),
            "°C",
        )
        database_size = format_memory_kb(
            first_value(data, "databaseSizeKB", "databaseSizeKb")
        )
        uptime = first_value(
            data,
            "uptimeFormatted",
            "formattedUptime",
            "uptime",
        )

        cpu = (
            await probe_hub_cpu(
                local_ip,
                timeout_seconds=self.cpu_probe_timeout_seconds,
            )
            if self.cpu_probe_enabled
            else {
                "available": False,
                "mode": "disabled",
                "error": "Direct local CPU probing is disabled in add-on options.",
            }
        )

        metrics: list[dict[str, Any]] = []
        if cpu.get("available"):
            metrics.append(
                {
                    "label": str(cpu.get("label") or "CPU load"),
                    "value": str(cpu.get("value") or "—"),
                    "icon": "🧠",
                }
            )
        else:
            metrics.append(
                {
                    "label": "CPU load",
                    "value": "Unavailable",
                    "icon": "🧠",
                }
            )

        for label, value, icon in (
            ("Free memory", free_memory, "💾"),
            ("Temperature", temperature, "🌡️"),
            ("Database", database_size, "🗄️"),
            ("Uptime", uptime, "⏱️"),
        ):
            if value not in (None, ""):
                metrics.append({"label": label, "value": str(value), "icon": icon})

        lines: list[str] = []
        if cpu.get("mode") == "percent":
            lines.append(f"Hub CPU load is {cpu['value']}.")
        elif cpu.get("mode") == "load-average":
            core_text = (
                f" across {cpu['processors']} processors"
                if cpu.get("processors")
                else ""
            )
            lines.append(
                f"Hub CPU one-minute load average is {cpu['value']}{core_text}."
            )
        else:
            lines.append(
                "Hub CPU load could not be read from the local /hub/cpuInfo endpoint."
            )
        if free_memory:
            lines.append(f"Free memory is {free_memory}.")
        if temperature:
            lines.append(f"Hub internal temperature is {temperature}.")
        if database_size:
            lines.append(f"Database size is {database_size}.")
        if uptime:
            lines.append(f"Uptime is {uptime}.")

        note = (
            "CPU is read directly from Hubitat's local /hub/cpuInfo endpoint; memory, "
            "temperature, database and uptime come from Kingpanther MCP."
            if cpu.get("available")
            else (
                "Kingpanther MCP does not expose CPU load. The add-on also tried Hubitat's "
                "local /hub/cpuInfo endpoint, but it was unavailable. "
                + str(cpu.get("error") or "")
            ).strip()
        )
        display = display_payload(
            "hub-resources",
            "Hub resources",
            subtitle=" · ".join(
                value
                for value in (
                    str(model),
                    f"Firmware {firmware}" if firmware else None,
                )
                if value
            ),
            metrics=metrics,
            note=note,
        )
        response = self._response(
            "\n".join(lines),
            "fallback-hub-resources",
            True,
            result,
        )
        response["display"] = display
        response["technical"] = json.dumps(
            {"hub_info": data, "cpu_probe": cpu},
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        return response

    async def _device_inventory(self, kind: str) -> dict[str, Any]:
        result = await self._live_devices("Switch" if kind == "light" else None)
        rows = self._device_rows(result.data)
        if kind == "light":
            rows = [item for item in rows if _looks_like_light(item)]

        inventory: list[dict[str, Any]] = []
        rooms: set[str] = set()
        on_count = 0
        for item in rows:
            label = _label(item) or f"Device {_device_id(item)}"
            room = self._room_name(item)
            if room:
                rooms.add(room)
            attrs = live_attributes(item)
            state = self._primary_state(attrs)
            if _normalise(attrs.get("switch")) == "on":
                on_count += 1
            inventory.append(
                {
                    "icon": "💡" if kind == "light" else "🔌",
                    "title": label,
                    "value": state,
                    "subtitle": room or "No room assigned",
                    "tone": "success" if state.lower() in {"on", "active", "open"} else None,
                }
            )

        inventory.sort(key=lambda item: (item["subtitle"].lower(), item["title"].lower()))
        noun = "light" if kind == "light" else "device"
        message = f"{len(inventory)} {noun}{'' if len(inventory) == 1 else 's'} returned."
        if inventory:
            message += "\n" + "\n".join(
                f"- {item['title']}: {item['value']} ({item['subtitle']})"
                for item in inventory
            )

        display = display_payload(
            f"{kind}-inventory",
            "All lights" if kind == "light" else "All devices",
            subtitle=f"{len(inventory)} {noun}{'' if len(inventory) == 1 else 's'}",
            metrics=[
                {"label": "Total", "value": str(len(inventory)), "icon": "💡" if kind == "light" else "📱"},
                {"label": "On", "value": str(on_count), "icon": "⚡"},
                {"label": "Rooms", "value": str(len(rooms)), "icon": "🚪"},
            ],
            items=inventory,
            note="Live device states were read directly from Hubitat MCP currentStates.",
        )
        response = self._response(
            message,
            f"fallback-{kind}-inventory",
            True,
            result,
        )
        response["display"] = display
        response["technical"] = safe_debug(result.data)
        return response

    async def _compare_rooms(
        self,
        *,
        attribute: str,
        first_room: str,
        second_room: str,
    ) -> dict[str, Any]:
        result = await self._live_devices()
        rows = self._device_rows(result.data)
        targets = [self._clean_room(first_room), self._clean_room(second_room)]
        unit = "%" if attribute == "humidity" else "°C"
        readings: dict[str, list[tuple[str, float]]] = {room: [] for room in targets}

        for item in rows:
            item_room = self._room_name(item)
            label = _label(item) or f"Device {_device_id(item)}"
            attrs = live_attributes(item)
            raw = attrs.get(attribute)
            try:
                value = float(str(raw).replace("%", "").replace("°C", "").strip())
            except Exception:
                continue
            for target in targets:
                if self._room_matches(target, item_room, label):
                    readings[target].append((label, value))

        metrics: list[dict[str, Any]] = []
        items: list[dict[str, Any]] = []
        averages: dict[str, float] = {}
        for room in targets:
            values = readings[room]
            if values:
                average = mean(value for _name, value in values)
                averages[room] = average
                metrics.append(
                    {
                        "label": room,
                        "value": f"{average:.1f}{unit}",
                        "icon": "💧" if attribute == "humidity" else "🌡️",
                    }
                )
                for name, value in sorted(values, key=lambda row: row[0].lower()):
                    items.append(
                        {
                            "icon": "💧" if attribute == "humidity" else "🌡️",
                            "title": name,
                            "value": f"{value:g}{unit}",
                            "subtitle": room,
                        }
                    )
            else:
                metrics.append(
                    {
                        "label": room,
                        "value": "No reading",
                        "icon": "❔",
                    }
                )

        if len(averages) == 2:
            first_value_avg = averages[targets[0]]
            second_value_avg = averages[targets[1]]
            difference = abs(first_value_avg - second_value_avg)
            warmer = targets[0] if first_value_avg > second_value_avg else targets[1]
            if attribute == "humidity":
                relation = "more humid"
            else:
                relation = "warmer"
            message = (
                f"{targets[0]} averages {first_value_avg:.1f}{unit}; "
                f"{targets[1]} averages {second_value_avg:.1f}{unit}. "
                f"{warmer} is {difference:.1f}{unit} {relation}."
            )
        else:
            missing = [room for room in targets if room not in averages]
            message = (
                f"I could not compare {attribute} accurately because no live reading was found "
                f"for {', '.join(missing)}."
            )

        display = display_payload(
            "room-environment-comparison",
            f"{attribute.title()} comparison",
            subtitle=f"{targets[0]} and {targets[1]}",
            metrics=metrics,
            items=items,
            note="Averages use every live matching sensor in each room.",
        )
        response = self._response(
            message,
            f"fallback-compare-{attribute}",
            len(averages) == 2,
            result,
        )
        response["display"] = display
        response["technical"] = safe_debug(
            {
                "attribute": attribute,
                "rooms": targets,
                "readings": readings,
            }
        )
        return response

    @staticmethod
    def _clean_room(value: str) -> str:
        text = re.sub(r"[?.!]+$", "", str(value or "").strip())
        return re.sub(r"\s+", " ", text).title()

    @staticmethod
    def _room_name(item: dict[str, Any]) -> str:
        value = item.get("room") or item.get("roomName")
        if isinstance(value, dict):
            value = value.get("name") or value.get("label")
        return str(value or "").strip()

    @staticmethod
    def _room_matches(target: str, room: str, label: str) -> bool:
        wanted = _normalise(target)
        return wanted == _normalise(room) or (
            not room and wanted in _normalise(label)
        )

    @staticmethod
    def _primary_state(attrs: dict[str, Any]) -> str:
        for key, suffix in (
            ("switch", ""),
            ("motion", ""),
            ("contact", ""),
            ("presence", ""),
            ("temperature", "°C"),
            ("humidity", "%"),
            ("battery", "%"),
        ):
            value = attrs.get(key)
            if value not in (None, ""):
                text = str(value)
                return text.title() if not suffix else f"{text}{suffix}"
        return "Available"

class EssentialsFastFallbackRouter(DashboardFastFallbackRouter):
    """Essential exact-state routes that should never wait for a language model."""

    async def answer(self, query: str) -> dict[str, Any]:
        if _MOTION_QUERY.match(_normalise(query)):
            return await self._active_motion_sensors()
        return await super().answer(query)

    async def _active_motion_sensors(self) -> dict[str, Any]:
        result = await self._live_devices("Motion Sensor")
        rows = self._device_rows(result.data)
        motion_rows = [
            item
            for item in rows
            if _normalise(live_attributes(item).get("motion")) in {"active", "inactive"}
        ]

        # Some MCP/driver combinations do not advertise the standard capability
        # even though currentStates includes motion. Retry the full live summary
        # before claiming that no motion sensors exist.
        if not motion_rows:
            result = await self._live_devices()
            rows = self._device_rows(result.data)
            motion_rows = [
                item
                for item in rows
                if _normalise(live_attributes(item).get("motion"))
                in {"active", "inactive"}
            ]

        active = sorted(
            {
                _label(item) or f"Device {_device_id(item)}"
                for item in motion_rows
                if _normalise(live_attributes(item).get("motion")) == "active"
            },
            key=str.lower,
        )
        total = len(motion_rows)

        if active:
            message = (
                f"{len(active)} motion sensor{'' if len(active) == 1 else 's'} active: "
                + ", ".join(active)
                + "."
            )
        elif total:
            message = "No motion sensors are currently reporting active."
        else:
            message = (
                "The MCP device response did not include any live motion states. "
                "Check that motion devices are selected in MCP Rule Server."
            )

        display = display_payload(
            "motion-active",
            "Active motion sensors",
            subtitle=f"{len(active)} active · {total} states read",
            metrics=[
                {"label": "Active", "value": str(len(active)), "icon": "🏃"},
                {"label": "Motion states read", "value": str(total), "icon": "📡"},
            ],
            items=[
                {
                    "icon": "🏃",
                    "title": name,
                    "value": "Active",
                    "tone": "success",
                }
                for name in active
            ],
            note="Live values come from Hubitat MCP currentStates.",
        )
        response = self._response(
            message,
            "fallback-motion-active",
            total > 0,
            result,
        )
        response["display"] = display
        response["technical"] = safe_debug(result.data)
        return response

class RoomInventoryRouter(EssentialsFastFallbackRouter):
    """Essential routes plus exact Hubitat room-device inventory lookup."""

    async def answer(self, query: str) -> dict[str, Any]:
        candidate = self._room_candidate(query)
        if candidate:
            room_answer = await self._room_inventory_if_exact(candidate)
            if room_answer is not None:
                return room_answer
        return await super().answer(query)

    async def _room_inventory_if_exact(self, requested_room: str) -> dict[str, Any] | None:
        rooms_result = await self._execute_catalog_tool(
            "hub_list_rooms",
            "hub_read_rooms",
            {},
        )
        if rooms_result.is_error:
            raise MCPError(rooms_result.text or "Room lookup failed")

        rooms = self._room_rows(rooms_result.data)
        requested_key = self._room_key(requested_room)
        exact = next(
            (room for room in rooms if self._room_key(room["name"]) == requested_key),
            None,
        )
        # Prefer an exact room whose real name includes "room". Only treat a
        # trailing "room" as descriptive wording when the full name did not
        # match, e.g. "devices under Apps room" for the room named "Apps".
        if exact is None:
            without_suffix = re.sub(
                r"\s+room$",
                "",
                str(requested_room or "").strip(),
                flags=re.IGNORECASE,
            )
            if without_suffix != str(requested_room or "").strip():
                fallback_key = self._room_key(without_suffix)
                exact = next(
                    (
                        room
                        for room in rooms
                        if self._room_key(room["name"]) == fallback_key
                    ),
                    None,
                )
        if exact is None:
            return None

        devices_result = await self._live_devices()
        if devices_result.is_error:
            raise MCPError(devices_result.text or "Device lookup failed")

        room_name = exact["name"]
        room_key = self._room_key(room_name)
        all_device_rows = self._device_rows(devices_result.data)
        devices = [
            item
            for item in all_device_rows
            if self._room_key(self._room_name(item)) == room_key
        ]

        items: list[dict[str, Any]] = []
        detail_reads: list[dict[str, Any]] = []
        detail_probes = 0
        on_count = 0
        active_count = 0

        for item in devices:
            attrs = live_attributes(item)

            if (
                detail_probes < _MAX_EMPTY_SENSOR_DETAIL_PROBES
                and _needs_empty_device_detail(item, attrs)
            ):
                device_id = str(_device_id(item) or "")
                if device_id:
                    detail_probes += 1
                    try:
                        detail_result = await self._execute_catalog_tool(
                            "hub_get_device",
                            "hub_read_devices",
                            {"deviceId": device_id},
                        )
                    except MCPError as exc:
                        detail_reads.append(
                            {
                                "device_id": device_id,
                                "label": _label(item),
                                "success": False,
                                "error": str(exc),
                            }
                        )
                    else:
                        detail_success = not detail_result.is_error
                        detail_reads.append(
                            {
                                "device_id": device_id,
                                "label": _label(item),
                                "success": detail_success,
                            }
                        )
                        if detail_success:
                            detail_record = _detail_device_record(
                                detail_result.data,
                                device_id,
                            )
                            detail_attrs = live_attributes(detail_record or {})
                            if detail_attrs:
                                attrs.update(detail_attrs)

            state = self._primary_state(attrs)
            presented_states = _room_device_states(attrs, state)
            state = ", ".join(presented_states)
            normalised_state = _normalise(self._primary_state(attrs))
            if _normalise(attrs.get("switch")) == "on":
                on_count += 1
            if normalised_state in {"active", "open", "present", "unlocked"}:
                active_count += 1

            device_type = str(
                first_value(item, "deviceType", "type", "category", "driverName")
                or "Hubitat device"
            )
            icon = _room_device_icon(item, attrs, device_type)

            items.append(
                {
                    "icon": icon,
                    "title": _label(item) or f"Device {_device_id(item)}",
                    "value": state,
                    "subtitle": device_type,
                    "tone": (
                        "success"
                        if normalised_state in {"on", "active", "open", "present"}
                        else None
                    ),
                }
            )

        items.sort(key=lambda item: item["title"].lower())
        count = len(items)
        if items:
            room_title = _room_display_title(room_name)
            message = (
                f"{count} device{'' if count == 1 else 's'} are assigned to {room_title}:\n"
                + "\n".join(
                    f"- {item['title']}: {item['value']}" for item in items
                )
            )
        else:
            message = f'The Hubitat room "{room_name}" exists, but no selected MCP devices are assigned to it.'

        display = display_payload(
            "room-device-inventory",
            _room_display_title(room_name),
            subtitle=f"{count} device{'' if count == 1 else 's'} assigned",
            metrics=[
                {"label": "Devices", "value": str(count), "icon": "📱"},
                {"label": "Switches on", "value": str(on_count), "icon": "⚡"},
                {"label": "Active/open", "value": str(active_count), "icon": "📡"},
            ],
            items=items,
            note=(
                "Room membership and live states come from Hubitat MCP. Devices not selected "
                "in MCP Rule Server cannot appear here."
            ),
        )
        response = self._response(
            message,
            "fallback-room-devices",
            True,
            devices_result,
        )
        response["display"] = display
        response["room"] = room_name
        response["technical"] = safe_debug(
            {
                "matched_room": exact,
                "inventory_count": len(all_device_rows),
                "room_device_count": len(devices),
                "detail_probes": detail_probes,
                "detail_reads": detail_reads,
            }
        )
        return response

    @classmethod
    def _room_candidate(cls, query: str) -> str | None:
        text = str(query or "").strip()
        for index, pattern in enumerate(_ROOM_DEVICE_PATTERNS):
            match = pattern.match(text)
            if not match:
                continue
            candidate = re.sub(r"\s+", " ", match.group(1).strip(" .!?"))
            if not candidate:
                return None

            # The general "<room name> devices" form correctly preserves
            # multi-word room names such as "living room". Clean up only
            # duplicated descriptive forms such as "Livingroom room" or
            # "Bedroom room".
            duplicated_room = re.fullmatch(
                r"(.+?room)\s+room",
                candidate,
                flags=re.IGNORECASE,
            )
            if duplicated_room:
                candidate = duplicated_room.group(1)

            if index >= len(_ROOM_DEVICE_PATTERNS) - 2:
                normalised = _normalise(candidate)
                if normalised in _RESERVED_SHORTHAND:
                    return None
                if len(normalised.split()) > 4:
                    return None
            return candidate
        return None

    @staticmethod
    def _room_key(value: Any) -> str:
        """Canonical room key tolerant of spaces, punctuation and spoken numbering."""
        return re.sub(r"[^a-z0-9]+", "", _normalise(value))

    @staticmethod
    def _room_rows(value: Any) -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for item in walk(value):
            if not isinstance(item, dict):
                continue
            name = first_value(item, "name", "label", "roomName")
            room_id = first_value(item, "id", "roomId")
            if not name:
                continue
            key = FastFallbackRouter._room_key(name)
            if not key:
                continue
            rows[key] = {"name": str(name), "id": room_id}
        return sorted(rows.values(), key=lambda room: room["name"].lower())

class ReleaseFastFallbackRouter(RoomInventoryRouter):
    """Release-level corrections for Hubitat metrics and room inventory."""

    async def _hub_info(self) -> dict[str, Any]:
        result = await self.client.call_tool("hub_get_info", {})
        if result.is_error:
            raise MCPError(result.text or "hub_get_info failed")

        data = first_mapping(result.data)
        message, display = present_hub_info(result.data)
        local_ip = first_value(data, "localIP", "ip", "ipAddress")
        cpu = (
            await probe_hub_cpu(
                local_ip,
                timeout_seconds=self.cpu_probe_timeout_seconds,
            )
            if self.cpu_probe_enabled
            else {
                "available": False,
                "mode": "disabled",
                "error": "Direct local CPU probing is disabled in add-on options.",
            }
        )

        database_size = format_database_size(
            first_value(data, "databaseSizeMB", "databaseSizeKB", "databaseSizeKb")
        )
        metrics = list(display.get("metrics") or [])
        if cpu.get("available"):
            cpu_metric = {
                "label": "CPU load",
                "value": str(cpu.get("value") or "—"),
                "icon": "🧠",
            }
            insert_at = next(
                (
                    index + 1
                    for index, item in enumerate(metrics)
                    if str(item.get("label") or "").lower() == "firmware"
                ),
                1,
            )
            metrics.insert(insert_at, cpu_metric)
            message += f"\nHub CPU load is {cpu.get('value')}."
        else:
            metrics.append(
                {
                    "label": "CPU load",
                    "value": "Unavailable",
                    "icon": "🧠",
                }
            )

        display["metrics"] = metrics
        display["note"] = f"Database: {database_size}" if database_size else None
        if database_size:
            message += f"\nDatabase size is {database_size}."

        response = self._response(message, "fallback-hub-info", True, result)
        response["display"] = display
        response["technical"] = json.dumps(
            {"hub_info": data, "cpu_probe": cpu},
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        return response

    async def _hub_resources(self) -> dict[str, Any]:
        response = await super()._hub_resources()
        technical = response.get("technical")
        try:
            details = json.loads(technical) if isinstance(technical, str) else {}
        except Exception:
            details = {}
        hub_info = details.get("hub_info") if isinstance(details, dict) else {}
        if not isinstance(hub_info, dict):
            hub_info = {}

        database_size = format_database_size(
            first_value(hub_info, "databaseSizeMB", "databaseSizeKB", "databaseSizeKb")
        )
        if not database_size:
            return response

        display = response.get("display") if isinstance(response.get("display"), dict) else {}
        for metric in display.get("metrics") or []:
            if str(metric.get("label") or "").lower() == "database":
                metric["value"] = database_size

        lines = [
            line
            for line in str(response.get("message") or "").splitlines()
            if not line.lower().startswith("database size is ")
        ]
        lines.append(f"Database size is {database_size}.")
        response["message"] = "\n".join(lines)
        return response

class DeviceStatusRouter(ReleaseFastFallbackRouter):
    """Release router with exact device-status reads and honest fast-path errors."""

    async def answer(self, query: str) -> dict[str, Any]:
        answer = await super().answer(query)
        if answer.get("intent") != "fallback-unsupported":
            return answer

        requested_name = self._device_status_candidate(query)
        if requested_name:
            return await self._device_status(requested_name)

        answer = dict(answer)
        answer["message"] = (
            "The request was routed to the local MCP fast path, but no deterministic "
            "handler matched it. Ollama was not attempted for this fast-path request."
        )
        answer["fast_path_unhandled"] = True
        return answer

    @staticmethod
    def _device_status_candidate(query: str) -> str | None:
        text = str(query or "").strip()
        for pattern in _DEVICE_STATUS_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue
            candidate = re.sub(r"\s+", " ", match.group(1).strip(" .!?"))
            if not candidate or _normalise(candidate) in _RESERVED_STATUS_TARGETS:
                return None
            return candidate
        return None

    async def _device_status(self, requested_name: str) -> dict[str, Any]:
        result = await self._live_devices()
        candidates = self._device_rows(result.data)
        match, alternatives = self._match_device(requested_name, candidates)

        if not match and hasattr(self, "_humidity_speech_alias_match"):
            match = self._humidity_speech_alias_match(requested_name, candidates)

        if not match:
            if alternatives:
                message = (
                    f'I could not find one exact device named "{requested_name}". '
                    "Closest matches: " + ", ".join(alternatives[:5]) + "."
                )
                intent = "fallback-ambiguous-device-status"
            else:
                message = f'I could not find a selected MCP device named "{requested_name}".'
                intent = "fallback-device-status-not-found"
            response = self._response(message, intent, False, result)
            response["alternatives"] = alternatives[:5]
            response["technical"] = safe_debug(
                {
                    "requested_name": requested_name,
                    "candidate_count": len(candidates),
                }
            )
            return response

        label = _label(match) or f"Device {_device_id(match)}"
        attrs = live_attributes(match)
        metrics: list[dict[str, Any]] = []
        message_parts: list[str] = []

        for key in _ATTRIBUTE_ORDER:
            if key not in attrs:
                continue
            value = self._display_state_value(key, attrs.get(key))
            if value is None:
                continue
            metrics.append(
                {
                    "label": _ATTRIBUTE_LABELS.get(key, key),
                    "value": value,
                    "icon": _ATTRIBUTE_ICONS.get(key, "ℹ️"),
                }
            )
            message_parts.append(f"{_ATTRIBUTE_LABELS.get(key, key)}: {value}")
            if len(metrics) >= 10:
                break

        room = self._room_name(match)
        device_type = str(
            first_value(match, "deviceType", "type", "category", "driverName")
            or "Hubitat device"
        )
        primary = self._primary_state(attrs)
        message = f"{label}: {primary}."
        if message_parts:
            message += "\n" + "\n".join(message_parts)
        else:
            message += " No live currentStates were returned for this device."

        tone = "success" if _normalise(primary) in {
            "on",
            "active",
            "open",
            "present",
            "heating",
            "cooling",
        } else None
        display = display_payload(
            "device-status",
            label,
            subtitle=" · ".join(bit for bit in (room, device_type) if bit),
            metrics=metrics,
            items=[
                {
                    "icon": "📱",
                    "title": label,
                    "value": primary,
                    "subtitle": room or "No room assigned",
                    "tone": tone,
                }
            ],
            note="Live state was read from Hubitat MCP currentStates.",
        )
        response = self._response(
            message,
            "fallback-device-status",
            True,
            result,
        )
        response["display"] = display
        response["device_id"] = _device_id(match)
        response["device_label"] = label
        response["technical"] = safe_debug(
            {
                "requested_name": requested_name,
                "matched_device": match,
                "current_states": attrs,
            }
        )
        return response

    @staticmethod
    def _display_state_value(key: str, raw: Any) -> str | None:
        if isinstance(raw, dict):
            raw = (
                raw.get("value")
                or raw.get("currentValue")
                or raw.get("currentState")
            )
        if raw in (None, ""):
            return None
        text = str(raw).strip()
        if not text:
            return None
        unit = _ATTRIBUTE_UNITS.get(key, "")
        if unit and unit.lower() not in text.lower():
            text = f"{text}{unit}"
        if key in {
            "switch",
            "motion",
            "contact",
            "presence",
            "thermostatOperatingState",
            "thermostatMode",
            "healthStatus",
            "status",
        }:
            return text.replace("_", " ").title()
        return text

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
        return is_hub_logs_query(q)

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
        issue_only = any(
            term in q for term in ("error", "warning", "warn", "issue")
        )
        if not issue_only:
            result = await self._read_tool(
                "hub_get_logs",
                {"since": "24h", "limit": 500},
            )
            rows = _rows(result.data, ("logs", "entries", "items"))
            return self._response_with_rows(
                result=result,
                intent="fallback-hub-logs",
                title="Hub logs",
                subtitle=f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'} from the last 24 hours",
                rows=rows,
                title_fields=("message", "msg", "description"),
                value_fields=("level", "severity", "type"),
                subtitle_fields=(
                    "date",
                    "timestamp",
                    "time",
                    "name",
                    "source",
                    "appName",
                    "deviceName",
                ),
                icon="📜",
                note="Read from hub_get_logs with a 24-hour window.",
                empty_message="No hub log entries were returned for the last 24 hours.",
            )

        results: list[MCPToolResult] = []
        failures: list[str] = []
        issue_rows: list[dict[str, Any]] = []
        for level in ("error", "warn"):
            try:
                result = await self._read_tool(
                    "hub_get_logs",
                    {
                        "since": "24h",
                        "level": level,
                        "limit": 500,
                    },
                )
            except MCPError as exc:
                failures.append(f"{level}: {exc}")
                continue
            results.append(result)
            issue_rows.extend(_rows(result.data, ("logs", "entries", "items")))

        if not results:
            raise MCPError(
                "Could not read 24-hour warning or error logs"
                + (": " + "; ".join(failures) if failures else "")
            )

        rows = _dedupe_log_rows(issue_rows)
        errors = [
            row
            for row in rows
            if _log_identity(row)[1] in {"error", "fatal"}
        ]
        warnings = [
            row
            for row in rows
            if _log_identity(row)[1] in {"warn", "warning"}
        ]

        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            source = _log_identity(row)[2]
            grouped.setdefault(source, []).append(row)
        ordered_groups = sorted(
            grouped.items(),
            key=lambda item: (-len(item[1]), item[0].casefold()),
        )

        items: list[dict[str, Any]] = []
        lines: list[str] = []
        for source, source_rows in ordered_groups[:20]:
            latest, _level, _source, detail = _log_identity(source_rows[0])
            source_errors = sum(
                _log_identity(row)[1] in {"error", "fatal"}
                for row in source_rows
            )
            source_warnings = len(source_rows) - source_errors
            counts = []
            if source_errors:
                counts.append(
                    f"{source_errors} error{'s' if source_errors != 1 else ''}"
                )
            if source_warnings:
                counts.append(
                    f"{source_warnings} warning{'s' if source_warnings != 1 else ''}"
                )
            count_text = ", ".join(counts)
            items.append(
                {
                    "icon": "❌" if source_errors else "⚠️",
                    "title": source,
                    "value": count_text,
                    "subtitle": " · ".join(
                        value for value in (latest, detail) if value
                    ),
                    "tone": "danger" if source_errors else "warning",
                }
            )
            lines.append(
                f"- {source}: {count_text}"
                + (f". Latest: {detail}" if detail else "")
            )

        if rows:
            opening = (
                f"Found {len(errors)} error{'s' if len(errors) != 1 else ''} "
                f"and {len(warnings)} warning{'s' if len(warnings) != 1 else ''} "
                f"across {len(grouped)} source{'s' if len(grouped) != 1 else ''} "
                "in the last 24 hours."
            )
            message = opening + ("\n" + "\n".join(lines) if lines else "")
        else:
            message = "No errors or warnings were returned for the last 24 hours."

        display = display_payload(
            "fallback-hub-logs",
            "Hub log issues",
            subtitle="Server-filtered warning and error entries from the last 24 hours",
            metrics=[
                {"label": "Errors", "value": str(len(errors)), "icon": "❌"},
                {"label": "Warnings", "value": str(len(warnings)), "icon": "⚠️"},
                {"label": "Sources", "value": str(len(grouped)), "icon": "🧩"},
                {"label": "Window", "value": "24h", "icon": "🕘"},
            ],
            items=items,
            note=(
                "Read from hub_get_logs using separate server-side error and warning "
                "filters, then deduplicated and grouped by source."
            ),
        )
        combined = MCPToolResult(
            name="hub_get_logs",
            arguments={"since": "24h", "levels": ["error", "warn"], "limit": 500},
            raw={},
            text="",
            data={
                "window": "24h",
                "errors": len(errors),
                "warnings": len(warnings),
                "sources": len(grouped),
                "entries": rows,
                "partial_failures": failures,
            },
            is_error=False,
        )
        response = self._response(
            message,
            "fallback-hub-logs",
            not failures,
            combined,
        )
        response["display"] = display
        response["error_count"] = len(errors)
        response["warning_count"] = len(warnings)
        response["source_count"] = len(grouped)
        response["window"] = "24h"
        response["partial"] = bool(failures)
        response["technical"] = safe_debug(combined.data)
        return response

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

__all__ = [
    "DashboardFastFallbackRouter",
    "DeviceStatusRouter",
    "EssentialsFastFallbackRouter",
    "FastFallbackRouter",
    "InventoryFastFallbackRouter",
    "ReleaseFastFallbackRouter",
    "RoomInventoryRouter",
    "_needs_empty_device_detail",
    "_room_device_states",
    "_rows",
    "is_hub_logs_query",
]
