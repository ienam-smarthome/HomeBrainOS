"""Ground sensor-blocker diagnoses in actual sensor-state and decision receipts.

This checks proposed causal claims, not user wording or routes. Source-code
retrieval, a broad room inventory and a mode-change log cannot independently
establish a specific sensor's current state or its suppression of an OFF timer.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any


_SENSOR_ID = re.compile(
    r"\b(?P<label>(?:[A-Z][\w-]*\s+){1,6}Sensor)\s*"
    r"\(ID:\s*(?P<id>\d+)\)"
)
_STRONG_CAUSE = re.compile(
    r"\b(?:most likely cause|root cause|primary cause|definitive cause)\b",
    re.I,
)
_OFF_BLOCK = re.compile(
    r"\b(?:blocks?|prevents?|stops?|suppresses?|holds?)\b"
    r"[^.\n]{0,120}\b(?:off|timer|switching off)\b",
    re.I,
)


def _leaf(receipt: dict[str, Any]) -> str:
    args = receipt.get("arguments")
    return str(
        receipt.get("sub_tool")
        or (args.get("tool") if isinstance(args, dict) else "")
        or receipt.get("tool") or ""
    )


def _params(receipt: dict[str, Any]) -> dict[str, Any]:
    args = receipt.get("arguments")
    if not isinstance(args, dict):
        return {}
    child = args.get("args")
    return child if isinstance(child, dict) else args


def _direct_active_sensor(receipts: list[dict[str, Any]], sensor_id: str) -> bool:
    """An unexpanded list or bulk context is not a sensor-specific live state."""
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if _leaf(row) not in ("hub_get_device", "hub_list_devices"):
            continue
        details = row.get("details")
        if not isinstance(details, dict):
            continue
        snapshot = details.get("reportedDeviceState")
        if not isinstance(snapshot, dict):
            continue
        if str(snapshot.get("deviceId")) != sensor_id:
            continue
        attrs = snapshot.get("reportedAttributes")
        if isinstance(attrs, dict) and any(
            str(attrs.get(key) or "").casefold() == "active"
            for key in ("motion", "presence", "occupancy")
        ):
            return True
    return False


def _verified_block_decision(
    receipts: list[dict[str, Any]], sensor_id: str, label: str
) -> bool:
    """Demand a sensor-named timer decision, not just a generic mode log."""
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if _leaf(row) != "hub_get_logs":
            continue
        details = row.get("details")
        if not isinstance(details, dict):
            continue
        for event in details.get("logs") or []:
            if not isinstance(event, dict):
                continue
            msg = str(event.get("message") or "").casefold()
            if (sensor_id not in msg and label.casefold() not in msg):
                continue
            if _OFF_BLOCK.search(msg):
                return True
    return False


def _longest_on_interval(receipts: list[dict[str, Any]]) -> str:
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("tool") != "homebrain_device_history":
            continue
        details = row.get("details")
        if not isinstance(details, dict):
            continue
        temporal = details.get("temporalAnalysis")
        if not isinstance(temporal, dict):
            continue
        intervals = temporal.get("observedIntervals")
        if not isinstance(intervals, list):
            continue
        valid = [
            item for item in intervals
            if isinstance(item, dict)
            and isinstance(item.get("durationSeconds"), (int, float))
            and item.get("start") and item.get("end")
        ]
        if not valid:
            continue
        longest = max(valid, key=lambda item: item["durationSeconds"])
        try:
            start = datetime.fromisoformat(str(longest["start"]))
            end = datetime.fromisoformat(str(longest["end"]))
        except ValueError:
            return ""
        seconds = max(0, round(float(longest["durationSeconds"])))
        h, m = divmod(seconds // 60, 60)
        ss = seconds % 60
        duration = (f"{h}h {m}m {ss}s" if h else
                    f"{m}m {ss}s" if m else f"{ss}s")
        return (
            f"The longest recorded ON interval ran from "
            f"{start.strftime('%d %b %H:%M')} to "
            f"{end.strftime('%d %b %H:%M')} ({duration})."
        )
    return ""


def guard_unverified_sensor_blocker(
    message: str, receipts: list[dict[str, Any]]
) -> tuple[str, bool]:
    """Safely summarize an overconfident named-sensor causal claim.

    Do not discard supported observations just because an investigation is
    incomplete. Only replace a confidently identified sensor blocker when the
    answer lacks both sensor-specific live state and a matching timer decision.
    """
    source = str(message or "")
    clean = source.replace("**", "").replace("`", "")
    named = _SENSOR_ID.search(clean)
    if not named or not _STRONG_CAUSE.search(clean[:700]):
        return source, False
    if not _OFF_BLOCK.search(clean) or "off" not in clean.casefold():
        return source, False

    sensor_id = named.group("id")
    sensor_name = named.group("label").strip()
    if (_direct_active_sensor(receipts, sensor_id)
            and _verified_block_decision(receipts, sensor_id, sensor_name)):
        return source, False

    config_ids: set[str] = set()
    source_ids: set[str] = set()
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if _leaf(row) == "hub_get_app_config":
            app_id = str(_params(row).get("appId") or "")
            if app_id.isdigit():
                config_ids.add(app_id)
        if row.get("tool") == "homebrain_read_groovy_source":
            details = row.get("details") or {}
            if details.get("fullImplementationVerified") is True:
                app_id = str((row.get("arguments") or {}).get("appId") or "")
                if app_id.isdigit():
                    source_ids.add(app_id)

    app_id = sorted(config_ids & source_ids)
    setup = (
        f"App {app_id[0]}'s configuration and full Groovy source were read."
        if app_id else "The relevant automation was investigated."
    )
    interval = _longest_on_interval(receipts)
    paragraphs = [
        "**Possible cause, not verified:** An occupancy input staying active "
        "could postpone the light's OFF timer. The investigation did not "
        f"independently establish that {sensor_name} (ID {sensor_id}) was "
        "actively preventing the OFF command.",
        setup + " Complete source retrieval is not proof that a specific "
        "runtime timer branch was executed.",
    ]
    if interval:
        paragraphs.append(interval)
    paragraphs.append(
        "The initiating cause remains unverified; a sensor-specific live "
        "state, configured keep-on membership and a matching OFF-timer "
        "decision would be needed to confirm it."
    )
    return "\n\n".join(paragraphs), True


__all__ = ["guard_unverified_sensor_blocker"]
