from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import health_audit_service_core as _core


# Freshness contracts must be explicit data supplied by a device/integration.
# Capabilities such as TemperatureMeasurement or PowerMeter are deliberately
# not treated as proof that a device must report on any particular cadence.
_FRESHNESS_SECONDS_KEYS = (
    "expectedUpdateSeconds",
    "freshnessSeconds",
    "maxAgeSeconds",
    "reportingIntervalSeconds",
    "pollIntervalSeconds",
    "refreshIntervalSeconds",
    "heartbeatIntervalSeconds",
)
_FRESHNESS_MINUTES_KEYS = (
    "expectedUpdateMinutes",
    "freshnessMinutes",
    "maxAgeMinutes",
    "reportingIntervalMinutes",
    "pollIntervalMinutes",
    "refreshIntervalMinutes",
    "heartbeatIntervalMinutes",
)
_FRESHNESS_HOURS_KEYS = (
    "expectedUpdateHours",
    "freshnessHours",
    "maxAgeHours",
    "reportingIntervalHours",
    "pollIntervalHours",
    "refreshIntervalHours",
    "heartbeatIntervalHours",
)


def _freshness_seconds(device: dict[str, Any]) -> float | None:
    """Return an explicit freshness contract, never an inferred cadence."""
    values = _core._canonical_attributes(device)
    for keys, multiplier in (
        (_FRESHNESS_SECONDS_KEYS, 1.0),
        (_FRESHNESS_MINUTES_KEYS, 60.0),
        (_FRESHNESS_HOURS_KEYS, 3600.0),
    ):
        raw = _core._first(values, keys)
        value = _core._safe_float(raw)
        if value is not None and value > 0:
            return value * multiplier
    return None


def _device_findings(
    devices: list[dict[str, Any]],
    *,
    low_battery_threshold: int,
    stale_hours: int = 24,
    long_stale_hours: int = 24 * 7,
    cluster_minutes: int = 15,
    motion_active_hours: int = 2,
    previously_stale_ids: set[str] | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Classify health without promoting quiet timestamps into failures.

    Direct health/unreachable signals can create an offline issue. An old
    last-activity timestamp alone is neutral. Only an explicit freshness or
    reporting contract can create an expected-update-overdue issue.

    ``long_stale_hours``, ``motion_active_hours`` and ``previously_stale_ids``
    remain in the signature for compatibility with the existing service, but
    age-only state is no longer promoted into a warning by those heuristics.
    """
    del long_stale_hours, motion_active_hours, previously_stale_ids

    checked_at = (now or _core._utc_now()).astimezone(timezone.utc)
    low_batteries: list[dict[str, Any]] = []
    offline: list[dict[str, Any]] = []
    no_recent_activity: list[dict[str, Any]] = []
    expected_update_overdue: list[dict[str, Any]] = []
    never_reported: list[dict[str, Any]] = []
    unconfirmed_cached_state: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    active_state_rules = {
        "switch": {"on"},
        "motion": {"active"},
        "presence": {"present", "home"},
        "occupancy": {"occupied", "active", "present"},
        "contact": {"open"},
        "lock": {"unlocked"},
        "water": {"wet"},
    }

    for device in devices:
        label = _core._label(device)
        identifier = _core._device_id(device)
        values = _core._canonical_attributes(device)

        battery = _core._safe_float(_core._first(values, ("battery",)))
        if battery is not None and battery <= low_battery_threshold:
            low_batteries.append(
                {"id": identifier, "label": label, "battery": round(battery, 1)}
            )
            issues.append(
                _core._issue(
                    "device-battery",
                    "warning",
                    f"Low battery: {label}",
                    f"{battery:g}% (threshold {low_battery_threshold}%).",
                    key=identifier,
                )
            )

        state = _core._first(values, _core._HEALTH_STATE_KEYS)
        online_flag = _core._first(values, _core._BOOL_ONLINE_KEYS)
        state_text = str(state or "").strip().casefold()
        explicitly_offline = state_text in _core._OFFLINE_VALUES
        explicitly_unreachable = (
            online_flag is not None and _core._false_like(online_flag)
        )
        if explicitly_offline or explicitly_unreachable:
            reason = str(state or "not reachable").strip()
            offline.append({"id": identifier, "label": label, "state": reason})
            issues.append(
                _core._issue(
                    "device-offline",
                    "warning",
                    f"Device unavailable: {label}",
                    reason or "Device reports unavailable/offline.",
                    key=identifier,
                )
            )
            continue

        has_activity_field, raw_activity, activity_at = _core._activity_value(device)
        profile = _core._device_profile(device)
        subsystem = _core._device_subsystem(device)
        freshness_seconds = _freshness_seconds(device)

        if has_activity_field and activity_at is None:
            never_reported.append(
                {
                    "id": identifier,
                    "label": label,
                    "profile": profile,
                    "last_activity": raw_activity,
                }
            )
            continue
        if activity_at is None:
            continue

        age = _core._age_hours(activity_at, checked_at)
        activity_row: dict[str, Any] = {
            "id": identifier,
            "label": label,
            "profile": profile,
            "subsystem": subsystem,
            "last_activity": activity_at.isoformat(),
            "last_activity_at": activity_at,
            "age_hours": round(age, 2),
        }

        if freshness_seconds is not None:
            activity_row["freshness_contract_seconds"] = round(
                freshness_seconds, 3
            )
            if age * 3600 > freshness_seconds:
                overdue = dict(activity_row)
                overdue["overdue_by_seconds"] = round(
                    age * 3600 - freshness_seconds, 3
                )
                expected_update_overdue.append(overdue)
                issues.append(
                    _core._issue(
                        "device-update-overdue",
                        "warning",
                        f"Expected update overdue: {label}",
                        "Explicit freshness contract is "
                        f"{_core._format_age(freshness_seconds / 3600)}; "
                        f"last activity was {_core._format_age(age)} ago. "
                        "The missed expectation does not establish the cause.",
                        key=identifier,
                    )
                )

        if age < stale_hours:
            continue

        no_recent_activity.append(dict(activity_row))
        cached: dict[str, str] = {}
        for key, active_values in active_state_rules.items():
            value = _core._first(values, (key,))
            rendered = str(value or "").strip().casefold()
            if rendered in active_values:
                cached[key] = str(value)
        if cached:
            unconfirmed_cached_state.append(
                {
                    **dict(activity_row),
                    "cached_state": cached,
                    "live_status_confirmed": False,
                }
            )

    # Timestamp clustering is retained only as neutral evidence. It must never
    # create a shared-failure/interruption issue without separate mechanism
    # evidence tying the devices together.
    raw_clusters = _core._stale_clusters(
        no_recent_activity,
        cluster_minutes=cluster_minutes,
    )
    activity_clusters: list[dict[str, Any]] = []
    for cluster in raw_clusters:
        members = list(cluster["members"])
        identifiers = sorted(str(item["id"]) for item in members)
        labels = sorted(str(item["label"]) for item in members)
        first = min(item["last_activity_at"] for item in members)
        last = max(item["last_activity_at"] for item in members)
        activity_clusters.append(
            {
                "subsystem": str(cluster["subsystem"]),
                "count": len(members),
                "device_ids": identifiers,
                "devices": labels,
                "first_activity_timestamp": first.isoformat(),
                "last_activity_timestamp": last.isoformat(),
                "interpretation": "timestamp_cluster_only",
                "common_failure_proven": False,
            }
        )

    low_batteries.sort(
        key=lambda row: (row["battery"], str(row["label"]).casefold())
    )
    offline.sort(key=lambda row: str(row["label"]).casefold())
    for rows in (
        no_recent_activity,
        expected_update_overdue,
        never_reported,
        unconfirmed_cached_state,
    ):
        rows.sort(key=lambda row: str(row["label"]).casefold())
        for row in rows:
            row.pop("last_activity_at", None)
    activity_clusters.sort(
        key=lambda row: (row["subsystem"], row["first_activity_timestamp"])
    )

    # Legacy keys remain present and neutral during migration so existing UI
    # consumers do not break. New code should use the explicit v3 fields.
    return {
        "total": len(devices),
        "low_battery_count": len(low_batteries),
        "offline_count": len(offline),
        "no_recent_activity_count": len(no_recent_activity),
        "expected_update_overdue_count": len(expected_update_overdue),
        "activity_cluster_count": len(activity_clusters),
        "unconfirmed_cached_state_count": len(unconfirmed_cached_state),
        "never_reported_count": len(never_reported),
        "low_batteries": low_batteries,
        "offline": offline,
        "no_recent_activity": no_recent_activity,
        "expected_update_overdue": expected_update_overdue,
        "activity_clusters": activity_clusters,
        "unconfirmed_cached_state": unconfirmed_cached_state,
        "never_reported": never_reported,
        "suspicious_stale_count": 0,
        "stale_candidate_count": 0,
        "long_term_stale_count": 0,
        "passive_quiet_count": len(no_recent_activity),
        "motion_active_too_long_count": 0,
        "occupied_long_count": 0,
        "stale_cluster_count": 0,
        "suspicious_stale": [],
        "stale_candidates": [],
        "long_term_stale": [],
        "passive_quiet": no_recent_activity,
        "motion_active_too_long": [],
        "occupied_long": [],
        "stale_clusters": [],
    }, issues


# The existing service remains responsible for MCP reads, log grouping,
# persistence and UI shape. Patch only the semantic producer it resolves from
# its module globals, and bump the snapshot schema so old stale warnings are
# not reported as newly resolved against the new semantics.
_core._device_findings = _device_findings
_core._SNAPSHOT_SCHEMA_VERSION = 3

HealthAuditService = _core.HealthAuditService
_gateway_arguments = _core._gateway_arguments
_log_findings = _core._log_findings
_log_rows = _core._log_rows
_previous_stale_ids = _core._previous_stale_ids

__all__ = [
    "HealthAuditService",
    "_device_findings",
    "_freshness_seconds",
    "_gateway_arguments",
    "_log_findings",
    "_log_rows",
]
