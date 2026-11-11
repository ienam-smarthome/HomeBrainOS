"""Optional, read-only bridge to the installed Hub & Device Monitor REST API.

The monitor already writes its own locally archived five-minute bins. This
bridge never subscribes, schedules, polls devices, modifies Hubitat or
claims that empty native event history means zero load. All fetched values
come from authenticated GETs to a pinned RFC1918 Hubitat installed-app URL.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import ipaddress
import math
import re
from typing import Any
from urllib.parse import urlsplit

import httpx

TOOL_NAME = "homebrain_read_device_monitor"
MAX_BODY_BYTES = 1_500_000
MAX_SAMPLES = 750
_TOKEN = re.compile(r"[A-Za-z0-9_-]{16,150}\Z")
_APP_PATH = re.compile(r"/apps/api/([0-9]{1,9})/?\Z")
_METRIC_FIELDS = {
    "power": ("series", "w", "W"),
    "temperature": ("sensors", "tempC", "°C"),
    "humidity": ("sensors", "humidityPct", "%RH"),
    "heating_setpoint": ("sensors", "setpointC", "°C"),
    "level": ("levels", "levelPct", "%"),
}
_ALLOWED_RANGES = frozenset({"1h", "6h", "24h", "3d", "7d", "custom"})

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "READ-ONLY history from the separately installed Hub & Device Monitor "
            "dashboard's saved five-minute wattage bins and sensor snapshots. "
            "This is a separate source from native Hubitat device-event history. "
            "Choose it when historical measurements may be absent from native "
            "event history, or to compare sources. No polling or writes. "
            "Use mode=status first to discover which devices are selected for "
            "monitoring and their IDs. mode=history requires a monitored device_id. "
            "For exact periods, set range=custom with start/end offset-aware ISO "
            "times (e.g. 2026-11-10T20:00:00Z). Other ranges are relative to "
            "the monitor's current time. Each wattage value is a SAVED BIN "
            "value, not a continuous peak or a direct report at the bin start. "
            "powerReports>0 identifies a bin containing a report; other "
            "values may be held/cached. Unknown bins are NOT zero. "
            "No history predating the monitor's installation can be recovered."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["status", "history"]},
                "device_id": {
                    "type": "string",
                    "description": "Exact selected device ID from the monitor's status response.",
                },
                "metric": {"type": "string", "enum": list(_METRIC_FIELDS)},
                "range": {
                    "type": "string", "enum": sorted(_ALLOWED_RANGES),
                    "description": "Relative monitor window or custom ISO timestamp interval.",
                },
                "start": {
                    "type": "string",
                    "description": "Start of custom interval; ISO 8601 with UTC Z or explicit offset.",
                },
                "end": {
                    "type": "string",
                    "description": "End of custom interval; ISO 8601 with UTC Z or explicit offset.",
                },
            },
            "required": ["mode"],
            "additionalProperties": False,
        },
    },
}


def validate_api_base(raw: str) -> str:
    """Pin requests to one local Hubitat installed-app namespace, no DNS/redirects."""
    parts = urlsplit(str(raw).strip())
    if (parts.scheme != "http" or parts.username or parts.password
            or parts.query or parts.fragment or not _APP_PATH.fullmatch(parts.path)):
        raise ValueError("Set an HTTP local Hubitat API base URL of the form http://192.168.x.x/apps/api/1234")
    try:
        address = ipaddress.IPv4Address(parts.hostname or "")
        port = parts.port
    except (ValueError, TypeError):
        raise ValueError("Monitor API must use a private IPv4 Hubitat address") from None
    allowed = (
        ipaddress.IPv4Network("10.0.0.0/8"),
        ipaddress.IPv4Network("172.16.0.0/12"),
        ipaddress.IPv4Network("192.168.0.0/16"),
    )
    if not any(address in subnet for subnet in allowed) or port not in (None, 80, 8080):
        raise ValueError("Monitor API must use a private LAN Hubitat IPv4 and port 80/8080")
    host = str(address) + (f":{port}" if port else "")
    app_id = _APP_PATH.fullmatch(parts.path).group(1)
    return f"http://{host}/apps/api/{app_id}"


def _timestamp(raw: Any) -> datetime:
    if not isinstance(raw, str) or len(raw) > 45:
        raise ValueError("Use an offset-aware ISO 8601 timestamp")
    try:
        value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Use an offset-aware ISO 8601 timestamp") from None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Specify an explicit timezone offset in the requested interval")
    return value.astimezone(timezone.utc)


def _iso_ms(raw: Any) -> str | None:
    if type(raw) is not int or raw <= 0:
        return None
    try:
        return datetime.fromtimestamp(raw / 1000, timezone.utc).isoformat(timespec="milliseconds")
    except (ValueError, OverflowError, OSError):
        return None


def _num(value: Any, *, min_value: float, max_value: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        n = float(value)
    except ValueError:
        return None
    return round(n, 4) if math.isfinite(n) and min_value <= n <= max_value else None


def _count(value: Any, maximum: int = 100000) -> int:
    return value if type(value) is int and 0 <= value <= maximum else 0


def _event_samples(raw: dict, metric: str, device_id: str,
                   start_ms: int | None, end_ms: int | None) -> tuple[list[dict], dict]:
    source, key, unit = _METRIC_FIELDS[metric]
    if source == "series":
        candidates = raw.get("series")
    else:
        lines = raw.get(source)
        if not isinstance(lines, list):
            candidates = []
        else:
            selected = next(
                (item for item in lines if isinstance(item, dict)
                 and str(item.get("id")) == device_id), None
            )
            candidates = selected.get("series") if isinstance(selected, dict) else []
    if not isinstance(candidates, list):
        raise ValueError("Monitor returned invalid historical series")
    if len(candidates) > 8000:
        raise ValueError("Monitor returned an unexpectedly large historical series")

    samples = []
    missing = 0
    classes = {"reported_bin": 0, "held_from_report": 0,
               "unclassified_bin": 0, "derived_or_held_sensor_bin": 0}
    observed_reported = []
    for row in candidates:
        if not isinstance(row, dict):
            continue
        at = row.get("t")
        if type(at) is not int or not _iso_ms(at):
            continue
        if start_ms is not None and at < start_ms:
            continue
        if end_ms is not None and at >= end_ms:
            continue
        reading = _num(row.get(key), min_value=-80 if metric == "temperature" else 0,
                       max_value=1000000 if metric == "power" else 200)
        if reading is None:
            missing += 1
            continue
        record = {"bin_start_utc": _iso_ms(at), "bin_start_epoch_ms": at,
                  "saved_value": reading, "unit": unit}
        if metric == "power":
            count = _count(row.get("powerReports"))
            source_at = row.get("powerSourceAt")
            source_iso = _iso_ms(source_at)
            if count:
                provenance = "reported_bin"
                observed_reported.append((reading, at))
            elif source_iso:
                provenance = "held_from_report"
            else:
                provenance = "unclassified_bin"
            classes[provenance] += 1
            record.update({
                "sample_class": provenance,
                "reports_in_bin": count,
                "last_source_report_utc": source_iso,
                "last_report_in_bin_utc": _iso_ms(row.get("powerReportAt")),
            })
        else:
            record["sample_class"] = "derived_or_held_sensor_bin"
            classes["derived_or_held_sensor_bin"] += 1
        samples.append(record)

    if len(samples) > MAX_SAMPLES:
        # Reject, rather than present silently incomplete extrema/samples.
        raise ValueError("Monitor query exceeds safe sample bound; request a shorter interval")
    extrema = {}
    if observed_reported:
        low = min(observed_reported, key=lambda item: item[0])
        high = max(observed_reported, key=lambda item: item[0])
        extrema = {
            "lowest_report_containing_saved_bin": {"value": low[0], "bin_start_utc": _iso_ms(low[1]), "unit": unit},
            "highest_report_containing_saved_bin": {"value": high[0], "bin_start_utc": _iso_ms(high[1]), "unit": unit},
        }
    return samples, {
        "returned_non_null_bins": len(samples),
        "returned_null_or_unclassified_missing_bins": missing,
        **classes,
        **extrema,
        "coverage_complete": False,
        "continuous_physical_peak_verified": False,
        "zero_for_unobserved_bins": False,
    }


class HubDeviceMonitor:
    """Read an existing installed Hubitat app; no subscription or mutation."""
    def __init__(self, api_base: str, access_token: str):
        self.base = validate_api_base(api_base)
        token = str(access_token).strip()
        if not _TOKEN.fullmatch(token):
            raise ValueError("Set a valid Hubitat installed-app OAuth access token")
        self._token = token
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(8.0), follow_redirects=False, trust_env=False,
        )

    async def close(self):
        await self._client.aclose()

    async def _get(self, endpoint: str, query: dict) -> dict:
        # The token stays inside this private network request; never echo URL,
        # request parameters or downstream errors into model/user receipts.
        try:
            reply = await self._client.get(
                self.base + endpoint,
                params={**query, "access_token": self._token},
            )
            if reply.status_code in (401, 403):
                raise ValueError("Monitor access denied; verify app OAuth token")
            if reply.status_code != 200:
                raise ValueError("Monitor endpoint unavailable or returned an HTTP error")
            if len(reply.content) > MAX_BODY_BYTES:
                raise ValueError("Monitor API response exceeds safe size limit")
            data = reply.json()
        except (httpx.TimeoutException, httpx.RequestError):
            raise ValueError("Monitor endpoint unreachable from HomeBrainOS") from None
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("Monitor"):
                raise
            raise ValueError("Monitor API did not return valid data") from None
        if not isinstance(data, dict):
            raise ValueError("Monitor API returned invalid response")
        if data.get("success") is not True:
            raise ValueError("Monitor did not return history for this selected device/range")
        return data

    async def query(self, arguments: dict) -> dict:
        if not isinstance(arguments, dict):
            raise ValueError("Monitor tool arguments must be an object")
        mode = arguments.get("mode")
        if mode == "status":
            if set(arguments) != {"mode"}:
                raise ValueError("Monitor status accepts only mode=status")
            data = await self._get("/api/status", {})
            devices = data.get("devices")
            if not isinstance(devices, list) or len(devices) > 150:
                raise ValueError("Monitor returned invalid device inventory")
            return {
                "source": "Hub & Device Monitor installed app (separate from native Hubitat history)",
                "read_only": True,
                "monitor_version": str(data.get("version") or "")[:32],
                "instance": str(data.get("instanceName") or "")[:100],
                "monitor_mode": str(data.get("monitorMode") or "")[:18],
                "hub_time_zone": str(data.get("timeZone") or "")[:60],
                "monitor_observed_at_utc": _iso_ms(data.get("now")),
                "monitor_sampling": {
                    "status": ((data.get("sampling") or {}).get("status")
                               if isinstance(data.get("sampling"), dict) else None),
                    "last_device_success_utc": _iso_ms(
                        (data.get("sampling") or {}).get("lastDeviceSuccess")
                        if isinstance(data.get("sampling"), dict) else None
                    ),
                },
                "selected_devices": [
                    {
                        "id": str(row.get("id") or "")[:24],
                        "name": str(row.get("name") or "")[:120],
                        "has_power": row.get("hasPower") is True,
                        "has_temperature": row.get("hasTemperature") is True,
                        "has_humidity": row.get("hasHumidity") is True,
                        "power_w": _num(row.get("powerW"), min_value=0, max_value=1000000),
                        "power_fresh": row.get("powerFresh") is True,
                        "last_power_report_utc": _iso_ms(row.get("lastPowerEventAt")),
                    }
                    for row in devices if isinstance(row, dict)
                ],
                "historical_source_note": (
                    "Current power values are snapshots, not historical samples. "
                    "History includes archived bins plus pending current bins. "
                    "Only explicitly selected monitored devices are available."
                ),
            }
        if mode != "history":
            raise ValueError("Monitor mode must be status or history")
        if set(arguments) - {"mode", "device_id", "metric", "range", "start", "end"}:
            raise ValueError("Unsupported monitor history arguments")
        device_id = arguments.get("device_id")
        if not isinstance(device_id, str) or not re.fullmatch(r"[0-9]{1,12}", device_id):
            raise ValueError("Monitor history requires the exact numeric selected device_id")
        metric = arguments.get("metric", "power")
        if metric not in _METRIC_FIELDS:
            raise ValueError("Monitor history metric is unsupported")
        window = arguments.get("range", "24h")
        if window not in _ALLOWED_RANGES:
            raise ValueError("Monitor history range is unsupported")
        params = {"device": device_id, "range": window}
        start_ms = end_ms = None
        if window == "custom":
            start = _timestamp(arguments.get("start"))
            finish = _timestamp(arguments.get("end"))
            now = datetime.now(timezone.utc)
            if finish <= start or finish - start < timedelta(minutes=10):
                raise ValueError("Monitor history window must be at least ten minutes")
            if finish > now + timedelta(minutes=1) or start < now - timedelta(days=30, minutes=1):
                raise ValueError("Monitor history must be within the last 30 days and not future")
            if finish - start > timedelta(days=30, minutes=1):
                raise ValueError("Monitor history interval cannot exceed 30 days")
            start_ms = int(start.timestamp() * 1000)
            end_ms = int(finish.timestamp() * 1000)
            params.update({"from": str(start_ms), "to": str(end_ms)})
        elif "start" in arguments or "end" in arguments:
            raise ValueError("Start/end require range=custom")
        data = await self._get("/api/history", params)
        if str(data.get("device")) != device_id:
            raise ValueError("Monitor returned a different device's history")
        if data.get("resolution") not in {"5m", "hourly", "daily"}:
            raise ValueError("Monitor returned unsupported history resolution")
        # For windows >14d the monitor's daily field named 'w' is actually
        # estimated Wh per day, not watts. Never expose it as a power reading.
        if metric == "power" and data.get("resolution") == "daily":
            raise ValueError("Monitor only provides daily estimated energy for this range, not wattage; request <=14 days")
        interval_start = data.get("start")
        interval_end = data.get("end")
        if type(interval_start) is not int or type(interval_end) is not int:
            raise ValueError("Monitor omitted historical interval boundaries")
        samples, summary = _event_samples(data, metric, device_id, start_ms, end_ms)
        return {
            "source": "Hub & Device Monitor installed-app saved history",
            "read_only": True,
            "device_id": device_id,
            "metric": metric,
            "unit": _METRIC_FIELDS[metric][2],
            "range": window,
            "returned_resolution": data["resolution"],
            "historical_start_utc": _iso_ms(interval_start),
            "historical_end_utc": _iso_ms(interval_end),
            "summary": summary,
            "samples": samples,
            "source_note": (
                "Power chart bins are archived wattage snapshots/aggregation, "
                "not raw, continuously sampled device-event history. A bin "
                "with reports_in_bin>0 contains at least one received power "
                "report. Other values may be carried forward from earlier "
                "reports, while legacy bins may have unknown provenance. "
                "For temperature/humidity/setpoint, the monitor holds cached "
                "or previously reported values; a plotted bin does NOT prove "
                "a fresh physical measurement at that time. The source may "
                "have collection/archive gaps, and absent rows do not equal "
                "zero. Report only the sampled-bin extrema supported by the "
                "returned source; do not claim unobserved physical peaks."
            ),
            "monitor_note": str(data.get("note") or "")[:450],
        }
