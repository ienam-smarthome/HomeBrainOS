from __future__ import annotations

import json
from typing import Any

from presenter import (
    display_payload,
    first_mapping,
    first_value,
    format_memory_kb,
    present_hub_info,
)


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "available"}:
        return True
    if text in {"0", "false", "no", "off", "none", "up to date", "unavailable"}:
        return False
    return None


def _walk_text(value: Any) -> list[str]:
    rows: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            rows.append(str(key))
            rows.extend(_walk_text(item))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_walk_text(item))
    elif value not in (None, ""):
        rows.append(str(value))
    return rows


def _platform_status(data: dict[str, Any]) -> dict[str, Any]:
    platform = data.get("platformUpdate")
    platform = platform if isinstance(platform, dict) else {}

    current = first_value(platform, "currentVersion", "installedVersion")
    available_version = first_value(
        platform,
        "availableVersion",
        "latestVersion",
        "newVersion",
    )
    available = _bool_or_none(platform.get("available"))
    note = first_value(platform, "note", "message", "error")

    # A version advertised as available is stronger evidence than a stale false flag.
    if available_version and str(available_version) != str(current):
        available = True

    alert_text = " ".join(_walk_text(data.get("healthAlerts"))).lower()
    if "platformupdateavailable" in alert_text:
        available = True
    elif "platform update" in alert_text and "available" in alert_text:
        available = True

    if note and "unreadable" in str(note).lower():
        available = None

    if available is True:
        label = f"Available {available_version}" if available_version else "Available"
        message = (
            f"Hub platform update available: {available_version}."
            if available_version
            else "A Hubitat platform update is available."
        )
        tone = "warning"
    elif available is False:
        label = "Up to date"
        message = "Hub platform software is up to date."
        tone = "success"
    else:
        label = "Unknown"
        message = "Hub platform update status could not be read reliably."
        tone = "warning"

    return {
        "available": available,
        "label": label,
        "message": message,
        "current": current,
        "available_version": available_version,
        "note": note,
        "tone": tone,
    }


def _app_status(data: dict[str, Any]) -> dict[str, Any]:
    app_update = data.get("appUpdate")
    app_update = app_update if isinstance(app_update, dict) else {}
    installed = first_value(app_update, "installedVersion", "currentVersion")
    latest = first_value(app_update, "latestVersion", "availableVersion")
    available = _bool_or_none(
        first_value(app_update, "updateAvailable", "available")
    )
    error = first_value(app_update, "error", "message")

    if latest and "unknown" not in str(latest).lower() and str(latest) != str(installed):
        available = True

    if error:
        label = "Check failed"
        message = f"MCP server software update check failed: {error}."
        tone = "warning"
    elif latest and "check in progress" in str(latest).lower():
        label = "Checking"
        message = "MCP server software update check is still in progress."
        tone = "warning"
    elif available is True:
        label = f"Available {latest}" if latest else "Available"
        message = (
            f"MCP Rule Server update available: {latest}."
            if latest
            else "An MCP Rule Server software update is available."
        )
        tone = "warning"
    elif available is False and (installed or latest):
        label = "Up to date"
        message = "MCP Rule Server software is up to date."
        tone = "success"
    else:
        label = "Unknown"
        message = "MCP Rule Server update status is not available yet."
        tone = "warning"

    return {
        "available": available,
        "label": label,
        "message": message,
        "installed": installed,
        "latest": latest,
        "error": error,
        "tone": tone,
    }


def present_hub_info_v2(value: Any) -> tuple[str, dict[str, Any]]:
    base_message, base_display = present_hub_info(value)
    # The older presenter collapses platformUpdate into a single line. Remove it
    # so the tri-state platform result below is the only update statement shown.
    base_message = "\n".join(
        line
        for line in base_message.splitlines()
        if not line.strip().lower().startswith("platform update:")
    )

    data = first_mapping(value)
    platform = _platform_status(data)
    app_update = _app_status(data)
    database_size = format_memory_kb(
        first_value(data, "databaseSizeKB", "databaseSizeKb")
    )

    metrics = []
    for metric in list(base_display.get("metrics") or []):
        copied = dict(metric)
        if copied.get("label") == "Firmware":
            copied["label"] = "Installed firmware"
        metrics.append(copied)

    metrics.extend(
        [
            {
                "label": "Software update",
                "value": platform["label"],
                "icon": (
                    "⬆️"
                    if platform["available"] is True
                    else "✅"
                    if platform["available"] is False
                    else "❔"
                ),
            },
            {
                "label": "MCP app update",
                "value": app_update["label"],
                "icon": "📦",
            },
        ]
    )
    if database_size:
        metrics.append(
            {
                "label": "Database size",
                "value": database_size,
                "icon": "🗄️",
            }
        )

    items: list[dict[str, Any]] = []
    if platform["available"] is True or platform["available"] is None:
        items.append(
            {
                "icon": "⬆️" if platform["available"] else "❔",
                "title": "Hub platform update",
                "subtitle": platform["message"],
                "value": platform["available_version"] or platform["label"],
                "tone": platform["tone"],
            }
        )
    if app_update["available"] is True or app_update["label"] in {
        "Checking",
        "Check failed",
        "Unknown",
    }:
        items.append(
            {
                "icon": "📦",
                "title": "MCP Rule Server update",
                "subtitle": app_update["message"],
                "value": app_update["latest"] or app_update["label"],
                "tone": app_update["tone"],
            }
        )

    messages = [base_message, platform["message"], app_update["message"]]
    display = display_payload(
        "hub-health",
        str(base_display.get("title") or "Hubitat hub"),
        subtitle=base_display.get("subtitle"),
        metrics=metrics,
        items=items,
        note=None,
    )
    display["platform_update"] = platform
    display["app_update"] = app_update
    display["database_size"] = database_size
    return "\n".join(message for message in messages if message), display


def safe_update_debug(value: Any) -> str:
    data = first_mapping(value)
    return json.dumps(
        {
            "platformUpdate": data.get("platformUpdate"),
            "appUpdate": data.get("appUpdate"),
            "healthAlerts": data.get("healthAlerts"),
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
