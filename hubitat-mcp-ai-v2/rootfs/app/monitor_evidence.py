"""Compact, source-derived evidence boundaries for the optional saved-history reader.

A presentation aid, not a validator or tool planner. The original monitor
response stays unchanged. This module never guesses missing samples, selects
a source, authenticates a sensor clock, or rewrites the model's conclusion.
"""
from __future__ import annotations

from typing import Any


def _count(summary: dict, key: str) -> int | None:
    value = summary.get(key)
    return value if type(value) is int and value >= 0 else None


def _history_scope(payload: dict) -> dict | None:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return None
    metric = payload.get("metric")
    is_power = metric == "power"
    sensor_freshness = summary.get("sensor_freshness_known_from_source")
    return {
        "device_id": str(payload.get("device_id") or "")[:32],
        "metric": metric,
        "unit": payload.get("unit"),
        "observational_unit": "saved time bin, not an instantaneous physical event",
        "resolution": payload.get("returned_resolution") or payload.get("resolution"),
        "requested_window_start_utc": (
            payload.get("historical_start_utc")
            or payload.get("requested_interval_start_utc")
        ),
        "requested_window_end_exclusive_utc": (
            payload.get("historical_end_utc")
            or payload.get("requested_interval_end_exclusive_utc")
        ),
        "returned_window_start_utc": payload.get("upstream_returned_window_start_utc"),
        "returned_window_end_utc": payload.get("upstream_returned_window_end_utc"),
        "expected_bin_positions": _count(summary, "expected_bin_positions"),
        "bins_with_saved_values": _count(summary, "populated_bin_positions"),
        "bins_containing_monitor_received_power_reports": (
            _count(summary, "reported_bin") if is_power else None
        ),
        "bins_held_from_previous_power_report": (
            _count(summary, "held_from_report") if is_power else None
        ),
        "bins_with_sensor_freshness_unverified": (
            _count(summary, "sensor_freshness_unverified") if not is_power else None
        ),
        "explicit_null_bin_positions": _count(summary, "null_bin_positions_within_expected"),
        "absent_bin_positions": _count(summary, "absent_bin_positions"),
        "all_saved_bin_values_present": (
            summary.get("all_expected_bin_positions_populated") is True
        ),
        "fresh_sensor_reports_independently_verified": (
            False if sensor_freshness is False else
            summary.get("fresh_sensor_reports_verified") is True
        ),
        "source_verified_continuous_physical_observation": False,
        "source_verified_exact_physical_threshold_crossing_time": False,
        "source_verified_device_connection_or_offline_cause": False,
        "source_verified_instantaneous_physical_peak": False,
        "reported_power_bin_extrema": (
            summary.get("report_containing_saved_bin_extrema") if is_power else None
        ),
        "saved_bin_extrema": summary.get("saved_bin_extrema"),
        "source_completeness_verified": summary.get("coverage_complete") is True,
        "meaning": (
            "The source distinguishes a saved value, a power report-containing "
            "bin, a held power bin, an explicit null, and a missing position. "
            "Do not convert null to zero or infer a reporting outage. "
            "Monitor-received power reports do not authenticate the physical "
            "sensor clock. For non-power sensors, saved values may be fresh "
            "or cached when freshness is unknown; a filled grid cannot prove "
            "a physical threshold-crossing instant. A latest-value status "
            "snapshot is not a historical reading."
        ),
    }


def monitor_evidence_scope(result: Any) -> dict | None:
    """Return a bounded semantic map only for actual read-only monitor data."""
    if not isinstance(result, dict):
        return None
    payload = result.get("local_device_monitor")
    if not isinstance(payload, dict) or payload.get("read_only") is not True:
        return None
    mode = payload.get("mode")
    if mode == "compare":
        rows = payload.get("devices")
        if not isinstance(rows, list):
            return None
        devices = [_history_scope(row) for row in rows[:5] if isinstance(row, dict)]
        return {
            "source_kind": "separate saved-device-history archive",
            "mode": "compare",
            "same_requested_window_verified": payload.get("shared_window_verified") is True,
            "shared_window_start_utc": payload.get("shared_window_start_utc"),
            "shared_window_end_exclusive_utc": payload.get("shared_window_end_exclusive_utc"),
            "device_summaries": [row for row in devices if row is not None],
            "device_summaries_omitted": max(0, len(rows) - 5),
            "causal_inference_supported": False,
        }
    if mode == "history" or (
        isinstance(payload.get("summary"), dict)
        and isinstance(payload.get("samples"), list)
    ):
        scoped = _history_scope(payload)
        return ({
            "source_kind": "separate saved-device-history archive",
            "mode": "history",
            "history": scoped,
        } if scoped is not None else None)
    if isinstance(payload.get("selected_devices"), list):
        return {
            "source_kind": "separate monitor latest-value status",
            "mode": "status",
            "observed_at_utc": payload.get("monitor_observed_at_utc"),
            "selected_device_count": len(payload["selected_devices"]),
            "proves_historical_readings": False,
            "proves_historical_connectivity": False,
            "meaning": "Latest or cached device values, not past interval measurements.",
        }
    return None
