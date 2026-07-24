from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


def _mcp_payload(answer: dict[str, Any]) -> dict[str, Any]:
    technical = str(answer.get("technical") or "")
    if "\n\nMCP response\n" in technical:
        technical = technical.split("\n\nMCP response\n", 1)[1]
    try:
        parsed = json.loads(technical)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _hub_info(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("hub_info", "hubInfo", "hub", "data", "result"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def _database_value(display: dict[str, Any], hub_info: dict[str, Any]) -> str | None:
    note = str(display.get("note") or "")
    match = re.search(r"\bDatabase:\s*([^\n]+)", note, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()

    raw = hub_info.get("databaseSizeMB")
    if raw not in (None, ""):
        return f"{raw} MB"
    raw = hub_info.get("databaseSizeKB")
    if raw not in (None, ""):
        # Current MCP versions expose this value in MB despite the legacy key name.
        return f"{raw} MB"
    return None


def enhance_hub_health_answer(answer: dict[str, Any]) -> dict[str, Any]:
    display = answer.get("display")
    if not isinstance(display, dict) or display.get("kind") != "hub-health":
        return answer

    payload = _mcp_payload(answer)
    hub_info = _hub_info(payload)
    platform = hub_info.get("platformUpdate")
    platform = platform if isinstance(platform, dict) else {}

    metrics = [dict(item) for item in (display.get("metrics") or []) if isinstance(item, dict)]
    firmware = hub_info.get("firmwareVersion") or platform.get("currentVersion")

    for metric in metrics:
        if str(metric.get("label") or "").strip().lower() == "firmware":
            metric["label"] = "Installed firmware"
            if firmware not in (None, ""):
                metric["value"] = str(firmware)

    labels = {str(item.get("label") or "").strip().lower() for item in metrics}
    if firmware not in (None, "") and "installed firmware" not in labels:
        metrics.append({"label": "Installed firmware", "value": str(firmware), "icon": "🧩"})
        labels.add("installed firmware")

    available = platform.get("available")
    available_version = platform.get("availableVersion") or platform.get("latestVersion")
    if available is True:
        update_value = f"Available {available_version}" if available_version else "Available"
        update_icon = "⬆️"
    elif available is False:
        update_value = "Up to date"
        update_icon = "✅"
    else:
        update_value = "Unknown"
        update_icon = "❔"

    replaced_update = False
    for metric in metrics:
        if str(metric.get("label") or "").strip().lower() in {"hub update", "software update"}:
            metric.update({"label": "Software update", "value": update_value, "icon": update_icon})
            replaced_update = True
            break
    if not replaced_update:
        metrics.append({"label": "Software update", "value": update_value, "icon": update_icon})

    database = _database_value(display, hub_info)
    if database:
        replaced_database = False
        for metric in metrics:
            if str(metric.get("label") or "").strip().lower() == "database size":
                metric.update({"value": database, "icon": "🗄️"})
                replaced_database = True
                break
        if not replaced_database:
            metrics.append({"label": "Database size", "value": database, "icon": "🗄️"})

        note = str(display.get("note") or "")
        note = re.sub(r"(?:^|\n)Database:\s*[^\n]+", "", note, flags=re.IGNORECASE).strip()
        display["note"] = note or None

    display["metrics"] = metrics
    answer["display"] = display
    return answer


def install_hub_health_display_bridge(application: Any) -> AskHandler:
    original_ask: AskHandler = application.ask

    async def hub_health_display_ask(request: Any) -> dict[str, Any]:
        answer = await original_ask(request)
        return enhance_hub_health_answer(answer)

    application.ask = hub_health_display_ask
    return original_ask


__all__ = ["enhance_hub_health_answer", "install_hub_health_display_bridge"]
