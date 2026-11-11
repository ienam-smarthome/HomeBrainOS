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
_ALLOWED_RANGES = frozenset({"1h", "6h", "12h", "24h", "3d", "7d", "custom"})
_BIN_PERIOD_MS = {"5m": 300_000, "hourly": 3_600_000}
_COMPARE_RANGES = {"1h": timedelta(hours=1), "6h": timedelta(hours=6),
                   "12h": timedelta(hours=12), "24h": timedelta(hours=24)}
MAX_COMPARISON_DEVICES = 5

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "READ-ONLY history from the separately installed Hub & Device Monitor "
            "dashboard's saved five-minute wattage bins and sensor snapshots. "
            "This is a separate source from native Hubitat device-event history. "
            "For historical numeric measurements, trends, extrema or "
            "threshold questions, consider this available saved-history "
            "source even if the user did NOT name the monitor. Choose "
            "sources by returned coverage and provenance, not keywords. "
            "Native events may cover a shorter returned time span and "
            "cannot alone exclude older measurements. No polling or writes. "
            "Use mode=status to discover selected device IDs. mode=history "
            "reads one device; mode=compare reads 2–5 distinct selected "
            "device_ids with ONE shared interval, per-device source-derived "
            "extrema, counts and consecutive missing/held runs. The compare "
            "mode returns bounded summaries, not fabricated raw samples; "
            "use mode=history for a full per-device saved-bin list. "
            "For exact periods and device comparisons, use range=custom with BOTH "
            "start AND end offset-aware ISO times (e.g. 2026-11-10T20:00:00Z). "
            "For a relative last-12-hours request, range=12h is supported; "
            "other ranges are relative to the monitor clock. For comparisons "
            "prefer the same explicit custom window across devices. "
            "History includes conservative source-derived extrema, counts "
            "and missing positions scoped to the ACTUAL returned interval. "
            "A saved bin is not a continuous physical measurement or peak; "
            "powerReports>0 means at least one report in that bin. A sensor "
            "bin's freshness is UNKNOWN, not definitely held or reported. "
            "Do not mix held bins, absent bin positions and explicit nulls. "
            "Unknown bins are NOT zero. "
            "No history predating the monitor's installation can be recovered."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["status", "history", "compare"]},
                "device_ids": {
                    "type": "array", "minItems": 2, "maxItems": 5,
                    "items": {"type": "string", "pattern": "^[0-9]{1,12}$"},
                    "description": "2–5 unique monitored device IDs for a shared-window comparison.",
                },
                "device_id": {
                    "type": "string",
                    "description": "Exact selected device ID from the monitor's status response.",
                },
                "metric": {"type": "string", "enum": list(_METRIC_FIELDS)},
                "range": {
                    "type": "string", "enum": sorted(_ALLOWED_RANGES),
                    "description": "Relative duration (including 12h) or custom exact interval; when custom, BOTH start and end are REQUIRED.",
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
                   start_ms: int | None, end_ms: int | None,
                   *, resolution: str = "5m") -> tuple[list[dict], dict]:
    """Summarize ONLY saved-bin readings in a specified half-open source window.

    No synthetic observations, continuous-state interpolation or assumed sensor
    reports. Timestamps are bin STARTS. Null rows and absent bin positions are
    tracked separately from held values. Raw upstream data is left untouched.
    """
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
    explicit_nulls = 0
    ignored_invalid_time_rows = 0
    ignored_outside_window_rows = 0
    classes = {
        "reported_bin": 0, "held_from_report": 0,
        "unclassified_bin": 0, "sensor_freshness_unverified": 0,
        # Keep the legacy summary count as a compatibility alias. This does
        # NOT mean all sensor readings were definitely carried forward.
        "derived_or_held_sensor_bin": 0,
    }
    reported = []
    saved = []
    observed_time_bins = set()
    non_null_times = set()
    null_times = set()
    report_total = 0
    held_times = set()
    for row in candidates:
        if not isinstance(row, dict):
            ignored_invalid_time_rows += 1
            continue
        at = row.get("t")
        if type(at) is not int or not _iso_ms(at):
            ignored_invalid_time_rows += 1
            continue
        if (start_ms is not None and at < start_ms) or (
                end_ms is not None and at >= end_ms):
            ignored_outside_window_rows += 1
            continue
        # Archive and pending chunks may overlap. A repeated bin timestamp
        # is ambiguous; rejecting avoids inventing a trustworthy extremum.
        if at in observed_time_bins:
            raise ValueError("Monitor returned duplicate timestamp bins; history is ambiguous")
        observed_time_bins.add(at)
        reading = _num(
            row.get(key), min_value=-80 if metric == "temperature" else 0,
            max_value=1000000 if metric == "power" else 200)
        if reading is None:
            explicit_nulls += 1
            null_times.add(at)
            continue
        non_null_times.add(at)
        record = {
            "bin_start_utc": _iso_ms(at),
            "bin_start_epoch_ms": at,
            "saved_value": reading,
            "unit": unit,
        }
        saved.append((reading, at))
        if metric == "power":
            count = _count(row.get("powerReports"))
            source_iso = _iso_ms(row.get("powerSourceAt"))
            if count:
                provenance = "reported_bin"
                reported.append((reading, at))
                report_total += count
            elif source_iso:
                provenance = "held_from_report"
                held_times.add(at)
            else:
                provenance = "unclassified_bin"
            classes[provenance] += 1
            record.update({
                "sample_class": provenance,
                "reports_in_bin": count,
                "last_monitor_power_event_at_utc": source_iso,
                "last_monitor_report_in_bin_utc": _iso_ms(row.get("powerReportAt")),
            })
        else:
            # The current monitor export does not contain per-sensor report
            # counters: this value MAY be newly reported OR cached/held.
            record["sample_class"] = "sensor_freshness_unverified"
            record["fresh_sensor_report_verified"] = False
            classes["sensor_freshness_unverified"] += 1
            classes["derived_or_held_sensor_bin"] += 1
        samples.append(record)
    samples.sort(key=lambda item: item["bin_start_epoch_ms"])

    if len(samples) > MAX_SAMPLES:
        raise ValueError("Monitor query exceeds safe sample bound; request a shorter interval")

    def _extrema(values: list[tuple[float, int]]) -> dict | None:
        if not values:
            return None
        minimum = min(values, key=lambda item: (item[0], item[1]))
        maximum = max(values, key=lambda item: (item[0], -item[1]))
        return {
            "lowest": {"value": minimum[0], "bin_start_utc": _iso_ms(minimum[1]), "unit": unit},
            "highest": {"value": maximum[0], "bin_start_utc": _iso_ms(maximum[1]), "unit": unit},
        }

    summary = {
        "returned_non_null_bins": len(samples),
        "returned_null_or_unclassified_missing_bins": explicit_nulls,
        "explicit_null_bin_rows": explicit_nulls,
        "returned_bin_positions_with_rows": len(observed_time_bins),
        "ignored_outside_window_rows": ignored_outside_window_rows,
        "ignored_invalid_time_rows": ignored_invalid_time_rows,
        "statistics_scope": "returned bin starts within the displayed half-open interval",
        "window_start_utc": _iso_ms(start_ms),
        "window_end_exclusive_utc": _iso_ms(end_ms),
        "resolution": resolution,
        **classes,
        "saved_bin_extrema": _extrema(saved),
        "report_containing_saved_bin_extrema": _extrema(reported) if metric == "power" else None,
        "fresh_sensor_reports_verified": None if metric != "power" else False,
        "sensor_freshness_known_from_source": False if metric != "power" else None,
        "power_report_rows_in_bins": report_total if metric == "power" else None,
        "coverage_complete": False,
        "continuous_physical_peak_verified": False,
        "zero_for_unobserved_bins": False,
    }
    if reported:
        low = min(reported, key=lambda item: (item[0], item[1]))
        high = max(reported, key=lambda item: (item[0], -item[1]))
        summary.update({
            "lowest_report_containing_saved_bin": {
                "value": low[0], "bin_start_utc": _iso_ms(low[1]), "unit": unit,
            },
            "highest_report_containing_saved_bin": {
                "value": high[0], "bin_start_utc": _iso_ms(high[1]), "unit": unit,
            },
        })

    step = _BIN_PERIOD_MS.get(resolution)
    if (step is not None and start_ms is not None and end_ms is not None
            and end_ms > start_ms):
        first = ((start_ms + step - 1) // step) * step
        expected = max(0, (end_ms - 1 - first) // step + 1)
        if expected > 9000:
            raise ValueError("Monitor history window exceeds the supported summary interval")
        expected_times = range(first, end_ms, step)
        # Only fully in-window time positions are counted; samples outside
        # the requested interval never influence the statistics.
        empty_times = [stamp for stamp in expected_times if stamp not in non_null_times]
        absent_times = [stamp for stamp in expected_times if stamp not in observed_time_bins]
        def consecutive_runs(matched):
            # Runs describe saved-bin *positions* only. They do not prove
            # telemetry outage or a continuous physical reading between bins.
            runs = []
            first_missing = previous_missing = None
            for stamp in expected_times:
                if matched(stamp):
                    if first_missing is None:
                        first_missing = stamp
                    previous_missing = stamp
                elif first_missing is not None:
                    runs.append((first_missing, previous_missing + step))
                    first_missing = previous_missing = None
            if first_missing is not None:
                runs.append((first_missing, previous_missing + step))
            duration = lambda r: (r[1] - r[0]) // step
            longest = max(runs, key=duration) if runs else None
            return {
                "count": len(runs),
                "total_bin_positions": sum(duration(r) for r in runs),
                "longest": ({
                    "start_utc": _iso_ms(longest[0]),
                    "end_exclusive_utc": _iso_ms(longest[1]),
                    "bin_count": duration(longest),
                    "duration_minutes": (longest[1] - longest[0]) // 60000,
                } if longest else None),
                "runs_preview": [{
                    "start_utc": _iso_ms(a), "end_exclusive_utc": _iso_ms(b),
                    "bin_count": (b - a) // step,
                    "duration_minutes": (b - a) // 60000,
                } for a, b in runs[:16]],
                "preview_truncated": len(runs) > 16,
                "meaning": "bin-position coverage only, not a verified physical or reporting outage",
            }
        missing_runs = consecutive_runs(lambda stamp: stamp not in non_null_times)
        held_runs = consecutive_runs(lambda stamp: stamp in held_times) if metric == "power" else None
        summary.update({
            "expected_bin_positions": expected,
            "populated_bin_positions": sum(stamp in non_null_times for stamp in expected_times),
            "missing_bin_positions_total": len(empty_times),
            "absent_bin_positions": len(absent_times),
            "null_bin_positions_within_expected": sum(stamp in null_times for stamp in expected_times),
            "all_expected_bin_positions_populated": len(empty_times) == 0,
            "missing_bin_start_utc_preview": [_iso_ms(stamp) for stamp in empty_times[:20]],
            "missing_bin_preview_truncated": len(empty_times) > 20,
            "missing_runs": missing_runs,
            "held_value_runs": held_runs,
            "bin_grid_complete_does_not_prove_observation_continuity": True,
        })
    else:
        summary.update({
            "expected_bin_positions": None,
            "populated_bin_positions": None,
            "missing_bin_positions_total": None,
            "absent_bin_positions": None,
            "null_bin_positions_within_expected": None,
            "all_expected_bin_positions_populated": None,
            "missing_runs": None,
            "held_value_runs": None,
        })
    return samples, summary

class HubDeviceMonitor:
    """Read an existing installed Hubitat app; no subscription or mutation."""

    async def _compare(self, arguments: dict) -> dict:
        """Model-selected, read-only comparison pinned to one absolute UTC interval.

        Relative intervals end at the last complete five-minute boundary;
        this avoids treating an in-progress bin as a fully observed interval.
        The captured end is used unchanged for ALL selected devices.
        """
        if set(arguments) - {"mode", "device_ids", "metric", "range", "start", "end"}:
            raise ValueError("Unsupported monitor comparison arguments")
        ids = arguments.get("device_ids")
        if (not isinstance(ids, list) or not 2 <= len(ids) <= MAX_COMPARISON_DEVICES
                or not all(isinstance(x, str) and re.fullmatch(r"[0-9]{1,12}", x) for x in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError("Monitor comparison requires 2–5 distinct numeric device_ids")
        metric = arguments.get("metric", "power")
        if metric not in _METRIC_FIELDS:
            raise ValueError("Monitor comparison metric is unsupported")
        window = arguments.get("range", "12h")
        if window not in {*_COMPARE_RANGES, "custom"}:
            raise ValueError("Monitor comparison supports 1h, 6h, 12h, 24h or custom")
        captured_now = datetime.now(timezone.utc)
        if window == "custom":
            if not arguments.get("start") or not arguments.get("end"):
                raise ValueError("Custom monitor comparison requires BOTH start and end offset-aware ISO times")
            start = _timestamp(arguments["start"])
            end = _timestamp(arguments["end"])
            if end <= start:
                raise ValueError("Custom monitor comparison end must be later than start")
            aligned = False
        else:
            step = _BIN_PERIOD_MS["5m"] / 1000
            # Round END down only for default relative comparisons; a user
            # supplied custom interval remains exact.
            end = datetime.fromtimestamp(
                int(captured_now.timestamp() // step * step), timezone.utc
            )
            start = end - _COMPARE_RANGES[window]
            aligned = True

        start_text = start.isoformat()
        end_text = end.isoformat()
        histories = []
        for device_id in ids:
            # A regular history query validates the same contract and source
            # read independently; no retries or separate relative "now" calls.
            reading = await self.query({
                "mode": "history", "device_id": device_id,
                "metric": metric, "range": "custom",
                "start": start_text, "end": end_text,
            })
            histories.append({
                "device_id": device_id, "unit": reading["unit"],
                "requested_interval_start_utc": reading["historical_start_utc"],
                "requested_interval_end_exclusive_utc": reading["historical_end_utc"],
                "upstream_returned_window_start_utc": reading["upstream_returned_window_start_utc"],
                "upstream_returned_window_end_utc": reading["upstream_returned_window_end_utc"],
                "resolution": reading["returned_resolution"],
                "summary": reading["summary"],
                "saved_sample_count": len(reading["samples"]),
                "full_sample_list_included": False,
                "full_samples_available_via": "homebrain_read_device_monitor mode=history",
                "monitor_note": reading["monitor_note"],
            })
        return {
            "source": "Hub & Device Monitor installed-app saved history",
            "mode": "compare", "read_only": True, "metric": metric,
            "unit": _METRIC_FIELDS[metric][2],
            "requested_range": window,
            "shared_window_start_utc": start_text,
            "shared_window_end_exclusive_utc": end_text,
            "shared_window_verified": True,
            "relative_end_aligned_to_last_complete_5m_boundary": aligned,
            "time_of_comparison_request_utc": captured_now.isoformat(),
            "monitored_device_count": len(histories),
            "devices": histories,
            "source_note": (
                "All devices queried from the SAME saved-history source using "
                "identical explicit UTC boundaries. Bins can be recorded, "
                "held or unavailable; source-derived extrema refer to saved "
                "bins, not continuous physical peaks. A missing saved value "
                "does not prove a power reading of 0, a reporting outage or "
                "a device state. Source returned-window boundaries may differ "
                "slightly even when the requested windows match. For absolute "
                "custom times no rounding occurs. Missing_runs describe bin "
                "coverage, not a verified outage. Read per-device history "
                "separately if raw saved-bin points are needed."
            ),
        }

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
        if mode == "compare":
            return await self._compare(arguments)
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
                        "last_monitor_power_event_at_utc": _iso_ms(row.get("lastPowerEventAt")),
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
        if window == "12h":
            # The installed monitor supports 'custom' but not native 12h.
            # Do not expand a 12-hour comparison to 24 hours and let the
            # model mistakenly reuse 24-hour maxima or missing-bin totals.
            finish = datetime.now(timezone.utc)
            start = finish - timedelta(hours=12)
            start_ms = int(start.timestamp() * 1000)
            end_ms = int(finish.timestamp() * 1000)
            params = {"device": device_id, "range": "custom",
                      "from": str(start_ms), "to": str(end_ms)}
        elif window == "custom":
            if not arguments.get("start") or not arguments.get("end"):
                raise ValueError(
                    "Custom monitor history requires BOTH start and end "
                    "as offset-aware ISO 8601 timestamps; alternatively "
                    "use range=12h or range=24h")
            start = _timestamp(arguments["start"])
            finish = _timestamp(arguments["end"])
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
        # Relative ranges use the monitor's actual returned boundaries;
        # exact custom/12h ranges preserve the local requested bounds.
        effective_start = start_ms if start_ms is not None else interval_start
        effective_end = end_ms if end_ms is not None else interval_end
        if effective_end <= effective_start:
            raise ValueError("Monitor returned invalid history time boundaries")
        samples, summary = _event_samples(
            data, metric, device_id, effective_start, effective_end,
            resolution=data["resolution"])
        return {
            "source": "Hub & Device Monitor installed-app saved history",
            "read_only": True,
            "device_id": device_id,
            "metric": metric,
            "unit": _METRIC_FIELDS[metric][2],
            "range": window,
            "returned_resolution": data["resolution"],
            "historical_start_utc": _iso_ms(effective_start),
            "historical_end_utc": _iso_ms(effective_end),
            "upstream_returned_window_start_utc": _iso_ms(interval_start),
            "upstream_returned_window_end_utc": _iso_ms(interval_end),
            "summary": summary,
            "samples": samples,
            "source_note": (
                "Power chart bins are archived wattage snapshots/aggregation, "
                "not raw, continuously sampled device-event history. A bin "
                "with reports_in_bin>0 contains at least one received power "
                "report. Report times come from the monitor's Hubitat app handler, "
                "not an independently authenticated Tasmota device-source clock. "
                "Other values may be carried forward from earlier "
                "reports, while legacy bins may have unknown provenance. "
                "For sensor measurements the monitor does not supply per-bin "
                "fresh-report provenance. sensor_freshness_unverified means "
                "the bin MAY contain a fresh or a held value; it does NOT "
                "prove that all readings are stale. The summary's extrema, "
                "report/held counts and missing positions refer ONLY to "
                "the returned requested interval. Explicit null rows, "
                "missing bin positions and populated held bins are distinct. "
                "A fully populated bin grid does not prove uninterrupted "
                "physical measurement or any unobserved peak. "
                "Absent rows do not equal zero."
            ),
            "monitor_note": str(data.get("note") or "")[:450],
        }
