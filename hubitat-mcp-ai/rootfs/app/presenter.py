from __future__ import annotations

import html
import json
import re
from typing import Any, Iterable


def normalise_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(?:div|p|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def first_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        for key in ("result", "data", "hub", "hubInfo", "hub_info", "value"):
            nested = value.get(key)
            if isinstance(nested, dict):
                return nested
        return value
    return {}


def first_value(data: dict[str, Any], *names: str) -> Any:
    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def compact_number(value: Any, suffix: str = "") -> str | None:
    parsed = number(value)
    if parsed is None:
        return None
    return f"{parsed:g}{suffix}"


def format_memory_kb(value: Any) -> str | None:
    parsed = number(value)
    if parsed is None:
        return None
    return f"{parsed / 1024:.1f} MB"


def bool_label(value: Any, true_text: str = "Yes", false_text: str = "No") -> str:
    if isinstance(value, bool):
        return true_text if value else false_text
    text = str(value or "").strip().lower()
    return true_text if text in {"1", "true", "yes", "on", "active"} else false_text


def display_payload(
    kind: str,
    title: str,
    *,
    subtitle: str | None = None,
    metrics: list[dict[str, Any]] | None = None,
    items: list[dict[str, Any]] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "title": title,
        "subtitle": subtitle,
        "metrics": metrics or [],
        "items": items or [],
        "note": note,
    }


def present_hub_info(value: Any) -> tuple[str, dict[str, Any]]:
    data = first_mapping(value)
    nested = data.get("hubData") if isinstance(data.get("hubData"), dict) else {}

    model = first_value(data, "hubName", "name")
    if not model:
        model = first_value(nested, "modelName", "hubName")
    if not model:
        raw_model = first_value(data, "model")
        model = f"Hubitat model {raw_model}" if raw_model else "Hubitat hub"

    firmware = first_value(data, "firmwareVersion", "currentVersion")
    platform_update = data.get("platformUpdate")
    if isinstance(platform_update, dict):
        firmware = firmware or first_value(platform_update, "currentVersion", "version")
        update_available = bool_label(platform_update.get("available"), "Available", "Up to date")
    else:
        update_available = None

    local_ip = first_value(data, "localIP", "ipAddress")
    uptime = first_value(data, "uptime", "formattedUptime")
    free_memory = format_memory_kb(first_value(data, "freeMemoryKB", "freeMemoryKb"))
    temperature = compact_number(first_value(data, "internalTempCelsius", "temperature"), "°C")
    database_size = format_memory_kb(first_value(data, "databaseSizeKB", "databaseSizeKb"))
    mcp_version = first_value(data, "mcpServerVersion")
    device_count = compact_number(first_value(data, "mcpDeviceCount"))
    rule_count = compact_number(first_value(data, "mcpRuleCount"))
    safe_mode = bool_label(first_value(data, "safeMode"), "On", "Off")
    timezone = first_value(data, "timeZone", "timezone")

    metrics: list[dict[str, Any]] = []
    for label, metric_value, icon in (
        ("Model", model, "🧠"),
        ("Firmware", firmware, "🧩"),
        ("Free memory", free_memory, "💾"),
        ("Temperature", temperature, "🌡️"),
        ("Uptime", uptime, "⏱️"),
        ("Safe mode", safe_mode, "🛡️"),
        ("MCP devices", device_count, "📟"),
        ("MCP rules", rule_count, "⚙️"),
    ):
        if metric_value not in (None, ""):
            metrics.append({"label": label, "value": str(metric_value), "icon": icon})

    lines = [f"Hub status: {model}."]
    details = []
    if firmware:
        details.append(f"firmware {firmware}")
    if free_memory:
        details.append(f"free memory {free_memory}")
    if temperature:
        details.append(f"internal temperature {temperature}")
    if uptime:
        details.append(f"uptime {uptime}")
    if details:
        lines.append(", ".join(details).capitalize() + ".")
    if mcp_version:
        mcp_bits = [f"MCP server v{mcp_version}"]
        if device_count:
            mcp_bits.append(f"{device_count} devices")
        if rule_count:
            mcp_bits.append(f"{rule_count} rules")
        lines.append(" · ".join(mcp_bits) + ".")
    if update_available:
        lines.append(f"Platform update: {update_available}.")
    if local_ip:
        lines.append(f"Local IP: {local_ip}.")

    subtitle_bits = [
        bit
        for bit in (
            f"IP {local_ip}" if local_ip else None,
            timezone,
            f"MCP v{mcp_version}" if mcp_version else None,
        )
        if bit
    ]
    display = display_payload(
        "hub-health",
        str(model),
        subtitle=" · ".join(subtitle_bits) if subtitle_bits else "Hub health",
        metrics=metrics,
        note=f"Database: {database_size}" if database_size else None,
    )
    return "\n".join(lines), display


def _room_candidates(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in walk(value):
        if not isinstance(item, dict):
            continue
        name = first_value(item, "name", "roomName", "label")
        room_id = first_value(item, "id", "roomId")
        count = first_value(item, "deviceCount", "devicesCount", "count")
        devices = item.get("devices")
        if count in (None, "") and isinstance(devices, list):
            count = len(devices)
        if name and (
            room_id not in (None, "")
            or count not in (None, "")
            or isinstance(devices, list)
        ):
            rows.append(
                {
                    "name": str(name),
                    "id": room_id,
                    "device_count": int(number(count) or 0),
                }
            )
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("id") or row["name"]).lower()
        deduped[key] = row
    return sorted(deduped.values(), key=lambda row: row["name"].lower())


def present_rooms(value: Any) -> tuple[str, dict[str, Any]]:
    rooms = _room_candidates(value)
    if not rooms:
        return (
            "No Hubitat rooms were returned.",
            display_payload("rooms", "Hubitat rooms", subtitle="No rooms returned"),
        )
    total_devices = sum(room["device_count"] for room in rooms)
    lines = [f"Hubitat has {len(rooms)} rooms:"]
    items = []
    for room in rooms:
        count = room["device_count"]
        lines.append(f"- {room['name']}: {count} device{'' if count == 1 else 's'}")
        items.append(
            {
                "icon": "🚪",
                "title": room["name"],
                "value": str(count),
                "subtitle": f"{count} device{'' if count == 1 else 's'}",
            }
        )
    return (
        "\n".join(lines),
        display_payload(
            "rooms",
            "Hubitat rooms",
            subtitle=f"{len(rooms)} rooms · {total_devices} assigned devices",
            items=items,
        ),
    )


def _rule_candidates(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in walk(value):
        if not isinstance(item, dict):
            continue
        name = first_value(item, "name", "label", "appName", "ruleName")
        rule_id = first_value(item, "id", "ruleId", "appId")
        if not name or rule_id in (None, ""):
            continue
        status = first_value(item, "status", "state")
        normalised_status = normalise_text(status).lower()
        disabled = first_value(item, "disabled", "isDisabled")
        paused = first_value(item, "paused", "isPaused")
        enabled = first_value(item, "enabled", "active")
        if disabled not in (None, "") and bool_label(disabled) == "Yes":
            status = "Disabled"
        elif paused not in (None, "") and bool_label(paused) == "Yes":
            status = "Paused"
        elif normalised_status in {"active", "enabled", "running"}:
            status = normalised_status.title()
        elif normalised_status in {"paused", "disabled", "inactive", "stopped"}:
            status = normalised_status.title()
        elif enabled not in (None, ""):
            status = "Active" if bool_label(enabled) == "Yes" else "Disabled"
        elif disabled not in (None, "") and bool_label(disabled) == "No":
            status = "Active"
        else:
            status = "Status not exposed"
        rows.append({"name": str(name), "id": rule_id, "status": str(status)})
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        deduped[str(row["id"])] = row
    return sorted(deduped.values(), key=lambda row: row["name"].lower())


def present_rules(value: Any) -> tuple[str, dict[str, Any]]:
    rules = _rule_candidates(value)
    if not rules:
        return (
            "No automation rules were returned.",
            display_payload("rules", "Automation rules", subtitle="No rules returned"),
        )
    active = sum(
        1
        for rule in rules
        if rule["status"].lower() in {"active", "enabled", "running"}
    )
    lines = [f"{len(rules)} automation rules were returned:"]
    items = []
    for rule in rules[:30]:
        lines.append(f"- {rule['name']}: {rule['status']}")
        items.append(
            {
                "icon": "⚙️",
                "title": rule["name"],
                "value": rule["status"],
                "subtitle": f"Rule ID {rule['id']}",
            }
        )
    return (
        "\n".join(lines),
        display_payload(
            "rules",
            "Automation rules",
            subtitle=f"{len(rules)} rules · {active} active",
            items=items,
            note="Showing the first 30 rules." if len(rules) > 30 else None,
        ),
    )


def present_weather(value: Any) -> tuple[str, dict[str, Any]]:
    candidates = [item for item in walk(value) if isinstance(item, dict)]
    weather = next(
        (
            item
            for item in candidates
            if any(
                key in item
                for key in (
                    "weatherSummary",
                    "weatherSummaryLine",
                    "condition",
                    "temperature",
                )
            )
        ),
        first_mapping(value),
    )
    attrs = weather.get("attributes") if isinstance(weather.get("attributes"), dict) else {}
    combined = {**attrs, **weather}
    summary = first_value(combined, "weatherSummary", "weatherSummaryLine", "summary")
    condition = first_value(combined, "condition", "weather")
    temperature = compact_number(first_value(combined, "temperature"), "°C")
    humidity = compact_number(first_value(combined, "humidity"), "%")
    precipitation = first_value(combined, "precipitation", "precipitationNow", "rain")

    clean_summary = normalise_text(summary) if summary else ""
    parts = [
        part
        for part in (condition, temperature, humidity, precipitation)
        if part not in (None, "")
    ]
    message = clean_summary or (
        "Weather: " + ", ".join(map(str, parts)) + "."
        if parts
        else "Weather data was returned, but no summary was available."
    )
    metrics = []
    for label, metric_value, icon in (
        ("Condition", condition, "🌦️"),
        ("Temperature", temperature, "🌡️"),
        ("Humidity", humidity, "💧"),
        ("Precipitation", precipitation, "🌧️"),
    ):
        if metric_value not in (None, ""):
            metrics.append(
                {
                    "label": label,
                    "value": normalise_text(metric_value),
                    "icon": icon,
                }
            )
    return (
        message,
        display_payload(
            "weather",
            "Weather",
            subtitle=clean_summary or None,
            metrics=metrics,
        ),
    )


def safe_debug(value: Any, max_chars: int = 6000) -> str | None:
    if value in (None, "", {}, []):
        return None
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception:
        text = str(value)
    return text[:max_chars]
