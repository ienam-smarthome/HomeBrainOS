"""Stage 8.5: bounded, read-only Hubitat command-vs-state incident comparison.

No historical absence, causal conclusion, device-origin timestamp, delivery or
physical actuator claim may follow from these target-scoped event pages.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any

from device_history_service import DeviceHistoryService
from mcp_client import tool_succeeded

_OPS = ("command-off", "command-on", "switch")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def read_plan(target_id: str, incident_utc_date: str, now: datetime) -> dict[str, Any]:
    if (type(target_id) is not str or not target_id.isascii()
            or not target_id.isdecimal() or not 1 <= len(target_id) <= 12):
        raise ValueError("invalid numeric target")
    if type(incident_utc_date) is not str or not _DATE.fullmatch(incident_utc_date):
        raise ValueError("invalid UTC date")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("UTC aware clock required")
    try:
        start = datetime.fromisoformat(incident_utc_date).replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("invalid UTC date") from None
    end = start + timedelta(days=1)
    if start > now.astimezone(timezone.utc) or start < now.astimezone(timezone.utc) - timedelta(days=30):
        raise ValueError("historical date outside 30-day allowed lookback")
    return {
        "device_id": target_id,
        "utc_date": incident_utc_date,
        "window_start_utc": start.isoformat(),
        "window_end_utc_exclusive": end.isoformat(),
        "hours_back": min(744, math.ceil((now.astimezone(timezone.utc) - start).total_seconds() / 3600) + 1),
        "operations": _OPS,
        "limit_per_operation": 50,
    }


def _iso(value: Any) -> datetime | None:
    if type(value) is not str or len(value) > 64:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def project_command_shadow(plan: dict[str, Any], responses: Any,
                           *, read_at_utc: str) -> dict[str, Any]:
    """Normalise only explicit command and reported switch records.

    Every response is expected to be a (operation, MCPToolResult) pair; the
    original target/operation must have been fixed by the host, not the model.
    """
    base = {
        "schema": "homebrain-stage85-command-shadow.v1",
        "device_id": plan["device_id"],
        "requested_utc_date": plan["utc_date"],
        "window_start_utc": plan["window_start_utc"],
        "window_end_utc_exclusive": plan["window_end_utc_exclusive"],
        "read_at_utc": read_at_utc,
        "source": "hubitat_target_scoped_read_only_device_event_history",
        "cloud_requests": 0,
        "device_commands": 0,
        "publisher_approval": False,
        "complete_history_proven": False,
        "source_clock_authenticated": False,
        "delivery_verified": False,
        "physical_execution_verified": False,
        "causal_attribution_verified": False,
        "events": [],
        "read_status": {},
        "limitations": [
            "Hubitat event page filters and retention can omit relevant older records.",
            "An empty or partial command page does not prove no command was issued.",
            "Hubitat reported event timestamps are not independently authenticated device clocks.",
            "A recorded command and an OFF state report do not prove delivery, physical switching or unique causation.",
            "This test never reads app-log history and does not establish an app's upstream trigger.",
        ],
    }
    if type(responses) is not list or len(responses) != len(_OPS):
        return {**base, "status": "blocked_incomplete_source_reads"}
    start = _iso(plan["window_start_utc"])
    end = _iso(plan["window_end_utc_exclusive"])
    output = []
    for expected, pair in zip(_OPS, responses):
        if type(pair) not in (list, tuple) or len(pair) != 2 or pair[0] != expected:
            return {**base, "status": "blocked_unexpected_read_operation"}
        source = pair[1]
        if not tool_succeeded(source):
            base["read_status"][expected] = "upstream_read_failed"
            continue
        base["read_status"][expected] = "successful_bounded_page"
        events = DeviceHistoryService._events(source.data, limit=50)
        # Target/operation in the upstream response is not absolute trust.
        for event in events:
            name = str(event.get("name") or "").casefold()
            if name != expected:
                continue
            row_device = event.get("deviceId")
            if row_device not in (None, "") and str(row_device) != plan["device_id"]:
                continue
            observed = _iso(event.get("date"))
            if observed is None or not (start <= observed < end):
                continue
            if name == "switch":
                value = str(event.get("value") or "").casefold()
                if value not in ("on", "off"):
                    continue
                item = {"kind": "reported_switch_state", "value": value}
            else:
                item = {"kind": "recorded_command", "command": name.removeprefix("command-")}
                producer = event.get("producedBy")
                if type(producer) is dict and producer.get("type") == "app":
                    app_id = str(producer.get("id") or "")
                    if app_id.isascii() and app_id.isdecimal() and len(app_id) <= 12:
                        item["recorded_issuer_app_id"] = app_id
            item["source_reported_time_utc"] = observed.isoformat()
            item["source_clock_authenticated"] = False
            item["physical_execution_verified"] = False
            output.append(item)
    base["events"] = sorted(output, key=lambda x: (x["source_reported_time_utc"], x["kind"]))
    base["returned_event_count"] = len(output)
    base["status"] = ("bounded_source_evidence" if all(
        v == "successful_bounded_page" for v in base["read_status"].values()
    ) and len(base["read_status"]) == len(_OPS) else "partial_or_failed_read")
    return base


__all__ = ["read_plan", "project_command_shadow"]
