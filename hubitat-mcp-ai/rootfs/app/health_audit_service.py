from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from frozen_core import health_audit_service_core as _core


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
            health_keys = (
                _core._HEALTH_STATE_KEYS if explicitly_offline
                else _core._BOOL_ONLINE_KEYS
            )
            source_attribute = next(
                (
                    key for key in health_keys
                    if _core._first(values, (key,)) not in (None, "")
                ),
                None,
            )
            has_activity, raw_activity, activity_at = _core._activity_value(device)
            offline.append({
                "id": identifier,
                "label": label,
                "state": reason,
                "source_attribute": source_attribute,
                "battery": round(battery, 1) if battery is not None else None,
                "last_activity": (
                    activity_at.isoformat() if activity_at
                    else str(raw_activity) if has_activity and raw_activity not in (None, "")
                    else None
                ),
                "reachability_independently_verified": False,
            })
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

def is_comprehensive_system_audit_request(prompt: str) -> bool:
    """Narrow read-only chat shortcut for whole-hub diagnostic requests.

    This selects a report workflow, not a tool's read/write effect. Every
    underlying MCP action is a fixed read. Specific repair commands continue
    through the normal agent and its tool-based confirmation checks.
    """
    words = " ".join(str(prompt or "").casefold().split())
    if any(phrase in words for phrase in (
        "comprehensive system audit", "full system audit",
        "comprehensive hub audit", "full hub audit",
        "run system check", "full system check",
    )):
        return True
    is_investigation = any(
        phrase in words for phrase in (
            "check", "audit", "inspect", "investigate", "diagnose", "review",
        )
    )
    has_logs = "logs" in words or "log entries" in words
    broad_scope = sum(
        token in words for token in ("device", "app", "hub event", "statistics", "stats")
    ) >= 2
    return is_investigation and has_logs and broad_scope


def _name_only_broken_marker(item: dict[str, Any]) -> bool:
    """A *BROKEN* name marker is a reported label, not a verified runtime fault."""
    detail = str(item.get("detail") or "").casefold()
    return (
        "marked the automation name *broken*" in detail
        and "reports broken=true" not in detail
    )


def _audit_issue_lines(snapshot: dict[str, Any], *, limit: int = 12) -> list[str]:
    issues = [
        row for row in snapshot.get("issues", [])
        if isinstance(row, dict) and row.get("severity") in ("critical", "warning")
    ]
    confirmed_signals = [item for item in issues if not _name_only_broken_marker(item)]
    name_markers = [item for item in issues if _name_only_broken_marker(item)]
    lines = []
    for row in confirmed_signals[:limit]:
        severity = str(row.get("severity") or "warning").upper()
        title = str(row.get("title") or "Unknown issue").strip()
        detail = str(row.get("detail") or "").strip()
        count = int(row.get("count") or 1)
        suffix = f" ({count} observations in checked sample)" if count > 1 else ""
        lines.append(f"- **{severity}: {title}**{suffix} — {detail}")
    if len(confirmed_signals) > limit:
        lines.append(
            f"- … and {len(confirmed_signals) - limit} additional alerts in System Check."
        )
    if not lines:
        lines.append("- No independent fault signal was returned from the checked sources.")
    if name_markers:
        lines.extend((
            "",
            f"### Automations flagged by name only — {len(name_markers)}, unverified",
            "These automations carry *BROKEN* in their names, but the supplied "
            "status data does not independently demonstrate a current execution "
            "failure. Do not treat these markers as confirmed broken rules.",
        ))
        for item in name_markers[:15]:
            lines.append(
                f"- {str(item.get('title') or 'Unnamed automation').removeprefix('Automation broken: ')}"
            )
        if len(name_markers) > 15:
            lines.append(f"- … and {len(name_markers) - 15} more name-marked automations.")
    return lines


def _performance_population_total(
    performance: dict[str, Any], kind: str
) -> int | None:
    """Only read explicitly labelled source totals; never infer from top-N rows."""
    summary = performance.get(f"{kind}Summary")
    if not isinstance(summary, dict):
        return None
    names = ("totalDevices", "totalApps", "totalCount", "count", "total")
    for key in names:
        value = summary.get(key)
        if isinstance(value, bool):
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number >= 0:
            return number
    return None


def _concise_log_message(message: Any) -> str:
    """Read MCP structured log entry.message instead of displaying raw JSON blobs."""
    text = " ".join(str(message or "").split())
    start = text.find("{")
    if start >= 0:
        try:
            payload = json.loads(text[start:])
            entry = payload.get("entry") if isinstance(payload, dict) else None
            if isinstance(entry, dict):
                detail = entry.get("details")
                message = entry.get("message") or (
                    detail.get("error") if isinstance(detail, dict) else None
                )
                if message:
                    text = " ".join(str(message).split())
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    # The upstream group may truncate the JSON after the nested message,
    # making json.loads impossible. A bounded quoted-field fallback still
    # extracts the actual log text rather than a raw transport envelope.
    if '"entry"' in text and '"message"' in text and '"appId"' in text:
        nested = re.search(r'"message"\s*:\s*("(?:\\.|[^"\\])*")', text)
        if nested:
            try:
                parsed = json.loads(nested.group(1))
                text = " ".join(str(parsed).split())
            except (TypeError, ValueError):
                pass
    return re.sub(r"[\r\n\t]+", " ", text)[:280]


def _audit_followups(
    snapshot: dict[str, Any], performance: dict[str, Any] | None,
    *, sensecap_known_unpowered: bool = False,
) -> list[str]:
    issues = snapshot.get("issues") or []
    text = " ".join(
        f"{row.get('title', '')} {row.get('detail', '')}"
        for row in issues if isinstance(row, dict)
    ).casefold()
    quiet = (snapshot.get("sections") or {}).get("devices", {}).get(
        "no_recent_activity", []
    ) or []
    quiet_labels = {
        str(row.get("label") or "").casefold()
        for row in quiet if isinstance(row, dict)
    }
    rows: list[str] = []
    if sensecap_known_unpowered:
        rows.append(
            "- **SenseCap D1 power:** The user has marked this device intentionally "
            "unpowered in the add-on configuration. Transport failures are expected "
            "until power is restored. Re-enable power and clear that temporary option "
            "before testing connectivity or changing network settings."
        )
    if not sensecap_known_unpowered and "sensecap d1" in text and (
        "http 408" in text or "live push failed" in text
        or "live updates are suspended" in text
    ):
        rows.append(
            "- **SenseCap D1 live push:** The reported HTTP timeout suspended "
            "live updates pending automatic backoff/retry. Check current reachability "
            "and a later successful push before calling this recovered; do not "
            "assume the retry has succeeded."
        )
    if not sensecap_known_unpowered and "sensecap d1" in text and ("unreachable" in text or "no route to host" in text):
        rows.append(
            "- **SenseCap D1:** Verify its current IP/reachability and configuration "
            "push endpoint. A failed config push does not prove live updates stopped."
        )
    if "mcp rule server" in text:
        rows.append(
            "- **MCP Rule Server:** Inspect logged server errors and request latency. "
            "Correct unsupported device-list projection arguments at their caller "
            "before retrying; do not restart the hub for one slow log request."
        )
    if "lg webos tv" in quiet_labels and isinstance(performance, dict):
        performance_names = {
            str(row.get("name") or "").casefold()
            for row in performance.get("deviceStats", []) if isinstance(row, dict)
        }
        if "lg webos tv" in performance_names:
            rows.append(
                "- **LG webOS TV:** High historical performance share and old "
                "activity coexist; verify TV reachability, driver connectivity "
                "and older events. This does not establish the cause of load."
            )
    if any(
        isinstance(row, dict) and row.get("category") == "device-offline"
        for row in issues
    ):
        rows.append(
            "- **Unavailable devices:** Confirm power, battery and radio/network "
            "reachability individually before attempting re-pairing or resets."
        )
    if any(isinstance(row, dict) and _name_only_broken_marker(row) for row in issues):
        rows.append(
            "- **Name-marked automations:** Inspect each rule's actual enabled "
            "state, device references and execution errors before editing it."
        )
    return rows[:6]


_AUDIT_SOURCE_PREFIX = re.compile(r"\b(?P<kind>app|dev)\|(?P<id>\d+)\|(?P<name>[^|]{2,100})\|")


def _fault_first_log_targets(
    snapshot: dict[str, Any],
    performance: dict[str, Any] | None,
    *,
    previous_snapshot: dict[str, Any] | None = None,
    sensecap_known_unpowered: bool = False,
) -> list[dict[str, str]]:
    """Select at most four identity-grounded investigation targets, faults first.

    Prefer explicit offline IDs and current error-source IDs. A recently reported
    SenseCap live-push failure remains worth investigating after it drops from
    the capped latest error sample. Do not infer an ID from a label alone.
    """
    from performance_host_plan import select_adaptive_log_targets

    targets: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, identifier: Any, name: Any, selection: str) -> None:
        identifier = str(identifier or "").strip()
        if kind not in {"device", "app"} or not identifier.isdecimal():
            return
        key = (kind, identifier)
        if (
            sensecap_known_unpowered and kind == "app"
            and "sensecap d1" in str(name or "").casefold()
        ):
            return
        if key in seen or len(targets) >= 4:
            return
        seen.add(key)
        targets.append({
            "kind": kind, "id": identifier,
            "name": str(name or identifier).strip()[:100],
            "selection": selection,
        })

    devices = (snapshot.get("sections") or {}).get("devices") or {}
    older_devices = ((previous_snapshot or {}).get("sections") or {}).get("devices") or {}
    previous_offline = {
        str(row.get("id")): str(row.get("state") or "")
        for row in older_devices.get("offline") or []
        if isinstance(row, dict) and row.get("id") not in (None, "")
    }
    still_offline: list[dict[str, Any]] = []
    for row in devices.get("offline") or []:
        if not isinstance(row, dict):
            continue
        identifier = str(row.get("id") or "")
        if identifier in previous_offline and (
            previous_offline[identifier] == str(row.get("state") or "")
        ):
            still_offline.append(row)
        else:
            add(
                "device", identifier, row.get("label"),
                "new/changed offline state" if previous_snapshot is not None
                else "explicit offline state",
            )

    identity_by_name: dict[str, set[str]] = {}
    for row in devices.get("inventory_labels") or []:
        if isinstance(row, dict) and row.get("id") not in (None, "") and row.get("label"):
            identity_by_name.setdefault(
                str(row["label"]).strip().casefold(), set()
            ).add(str(row["id"]))

    def add_issue_targets(issues: Any, *, selection: str) -> None:
        for issue in issues if isinstance(issues, list) else []:
            if not isinstance(issue, dict) or issue.get("severity") not in ("critical", "warning"):
                continue
            if _name_only_broken_marker(issue):
                continue
            content = " ".join(str(issue.get(k) or "") for k in ("title", "detail"))
            if selection == "previously observed fault" and not (
                "sensecap d1" in content.casefold()
                and ("live push failed" in content.casefold()
                     or "live updates are suspended" in content.casefold())
            ):
                continue
            for match in _AUDIT_SOURCE_PREFIX.finditer(content):
                add(
                    "app" if match.group("kind") == "app" else "device",
                    match.group("id"), match.group("name"), selection,
                )
            # A log alert may identify a device only by label (e.g. ADB).
            # Use ONLY a unique exact ID/name pair from the same live snapshot.
            title = str(issue.get("title") or "").strip()
            matching_ids = identity_by_name.get(title.casefold()) or set()
            if len(matching_ids) == 1:
                add("device", next(iter(matching_ids)), title, selection)

    add_issue_targets(snapshot.get("issues"), selection="observed fault")
    add_issue_targets(
        (previous_snapshot or {}).get("issues"),
        selection="previously observed fault",
    )
    # Do not repeatedly spend the full diagnostic budget on unchanged offline
    # flags. Sample at most one; the other offline verdicts remain reported.
    if still_offline and len(targets) < 4:
        index = 0
        checked_at = _core._parse_datetime(snapshot.get("checked_at"))
        if checked_at is not None:
            index = (int(checked_at.timestamp()) // 60) % len(still_offline)
        row = still_offline[index]
        add("device", row.get("id"), row.get("label"), "unchanged offline sample")


    # A transient SenseCap error can disappear from the capped main log
    # sample. When identifiable in performance data, check for recovery.
    for row in (performance or {}).get("appStats", []):
        if isinstance(row, dict) and "sensecap d1" in str(row.get("name") or "").casefold():
            add("app", row.get("id"), row.get("name"), "live-push recovery check")

    performance_targets = select_adaptive_log_targets(performance or {})
    if len(targets) >= 2:
        # When faults have occupied most of the budget, favour the app source
        # so a recurring MCP Rule Server failure still gets attention.
        performance_targets.sort(key=lambda item: item.get("kind") != "app")
    for target in performance_targets:
        add(target["kind"], target["id"], target["name"], "performance outlier")
    return targets


def _live_push_log_evidence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Report only observed SenseCap log messages; never infer resumed service."""
    errors: list[datetime] = []
    successes: list[datetime] = []
    failed = 0
    config_failed = 0
    succeeded = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        message = _core._log_message(row).casefold()
        if "sensecap" not in message and "live push" not in message:
            continue
        timestamp = _core._log_timestamp(row)
        if ("live push failed" in message or "live updates are suspended" in message):
            failed += 1
            if timestamp is not None:
                errors.append(timestamp)
        if "config push failed" in message:
            config_failed += 1
        if any(phrase in message for phrase in (
            "live push succeeded", "live push successful",
            "live updates resumed", "live push resumed",
        )):
            succeeded += 1
            if timestamp is not None:
                successes.append(timestamp)
    newer_success = bool(successes and errors) and (
        max(successes) > max(errors)
    )
    return {
        "failure_rows": failed,
        "config_failure_rows": config_failed,
        "success_rows": succeeded,
        "latest_failure": max(errors).isoformat() if errors else None,
        "latest_success": max(successes).isoformat() if successes else None,
        # Even a positive log does not establish current continuous service.
        "later_success_observed": newer_success,
    }


def _bounded_log_window_evidence(
    rows: list[dict[str, Any]], *, start: datetime, end: datetime
) -> dict[str, Any]:
    """Verify returned timestamps, never confuse a successful call with coverage."""
    parsed = [
        _core._log_timestamp(row)
        for row in rows
        if isinstance(row, dict)
    ]
    dated = [ts for ts in parsed if ts is not None]
    within = [
        ts for ts in dated if start <= ts <= end
    ]
    complete_timestamps = bool(rows) and len(dated) == len(rows)
    window_supported_by_rows = complete_timestamps and len(within) == len(rows)
    result: dict[str, Any] = {
        "entries_checked": len(rows),
        "rows_with_timestamps": len(dated),
        "rows_in_requested_window": len(within),
        "window_supported_by_rows": window_supported_by_rows,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
    }
    if dated:
        result["observed_earliest"] = min(dated).isoformat()
        result["observed_latest"] = max(dated).isoformat()
    return result


_EXPLICIT_OFFSET = re.compile(r"(?:Z|[+-]\d{2}:?\d{2})$", re.I)


def _audit_log_time_quality(
    rows: list[dict[str, Any]], *, checked_at: str | datetime | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Withhold unverified log chronology; never guess Hubitat's timezone.

    The generic date parser assumes UTC for naive strings. Hubitat log sources
    can use local wall-clock time, so treating such strings as UTC is unsafe.
    Explicit offsets and epoch timestamps are eligible, but a timestamp more
    than 60 seconds beyond the snapshot check is also untrustworthy.
    The underlying message and severity are never removed.
    """
    reference = _core._parse_datetime(checked_at)
    sanitized: list[dict[str, Any]] = []
    ambiguous = future = undated = 0
    examples: list[str] = []
    for row in rows:
        copy = dict(row)
        values = {_core._normalized_key(key): key for key in row}
        key = next(
            (values[_core._normalized_key(candidate)]
             for candidate in _core._TIMESTAMP_KEYS
             if _core._normalized_key(candidate) in values
             and row[values[_core._normalized_key(candidate)]] not in (None, "")),
            None,
        )
        if key is None:
            undated += 1
        else:
            raw = row[key]
            verified_zone = (
                isinstance(raw, (int, float))
                or isinstance(raw, datetime) and raw.tzinfo is not None
                or isinstance(raw, str) and bool(_EXPLICIT_OFFSET.search(raw.strip()))
            )
            parsed = _core._parse_datetime(raw) if verified_zone else None
            if not verified_zone or parsed is None:
                ambiguous += 1
                if len(examples) < 2:
                    examples.append(str(raw)[:60])
            elif reference is not None and parsed > reference + timedelta(seconds=60):
                future += 1
                if len(examples) < 2:
                    examples.append(str(raw)[:60])
            else:
                sanitized.append(copy)
                continue
        # Keep the row for severity analysis, but block all its time fields so
        # _log_findings / _live_push_log_evidence cannot infer event ordering.
        for candidate in list(copy):
            if _core._normalized_key(candidate) in {
                _core._normalized_key(field) for field in _core._TIMESTAMP_KEYS
            }:
                copy[candidate] = None
        sanitized.append(copy)
    return sanitized, {
        "rows": len(rows),
        "undated_rows": undated,
        "ambiguous_timezone_rows": ambiguous,
        "future_timestamp_rows": future,
        "chronology_withheld_rows": undated + ambiguous + future,
        "raw_examples": examples,
    }


def _scoped_log_pattern_summary(targeted_logs: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Summarise observed warning/error patterns, not inferred outages.

    Targets are identity-deduplicated by the planner. Individual log rows are
    occurrences, not separate incidents; matching patterns from scoped reads
    may also overlap the initial System Check snapshot.
    """
    patterns: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for target in targeted_logs or []:
        if not isinstance(target, dict) or target.get("error"):
            continue
        kind = str(target.get("kind") or "")
        identifier = str(target.get("id") or "")
        for group in target.get("groups") or []:
            if not isinstance(group, dict):
                continue
            key = (
                kind, identifier,
                str(group.get("level") or ""),
                str(group.get("fingerprint") or group.get("summary") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            patterns.append({
                "name": str(target.get("name") or identifier),
                "id": identifier,
                "level": str(group.get("level") or "unknown"),
                "detail": _concise_log_message(
                    group.get("summary") or group.get("message")
                ),
                "rows": max(0, int(group.get("count") or 0)),
                "first_seen": group.get("first_seen"),
                "last_seen": group.get("last_seen"),
            })
    return {
        "patterns": patterns,
        "pattern_count": len(patterns),
        "rows": sum(item["rows"] for item in patterns),
    }


def render_comprehensive_system_audit(
    snapshot: dict[str, Any],
    performance: dict[str, Any] | None,
    *,
    performance_error: str | None = None,
    targeted_logs: list[dict[str, Any]] | None = None,
    historical_logs: dict[str, Any] | None = None,
    context_reconciliation: dict[str, Any] | None = None,
    sensecap_known_unpowered: bool = False,
    ai_advisory: str | None = None,
) -> str:
    """Render checked data, neutral quiet-device observations and repair status."""
    sections = snapshot.get("sections") or {}
    devices = sections.get("devices") or {}
    automations = sections.get("automations") or {}
    logs = sections.get("logs") or {}
    alert_issues = [
        item for item in snapshot.get("issues", [])
        if isinstance(item, dict)
        and item.get("severity") in ("critical", "warning")
    ]
    marker_count = sum(_name_only_broken_marker(item) for item in alert_issues)
    other_count = len(alert_issues) - marker_count
    status = "ATTENTION" if other_count else (
        "REVIEW NAME MARKERS" if marker_count else "NO ALERTS OBSERVED"
    )
    scoped_summary = _scoped_log_pattern_summary(targeted_logs)
    lines = [
        f"## Comprehensive Hubitat audit — {status}",
        f"Alert signals: {other_count} from current health/log/automation data; "
        f"{marker_count} name-only *BROKEN* markers (not verified failures).",
        f"Scoped diagnostics: {scoped_summary['pattern_count']} warning/error "
        f"patterns across {scoped_summary['rows']} matched log rows. "
        "These may overlap the main alerts; log rows are not separate outages.",
        f"Checked: {snapshot.get('checked_at') or 'time not available'} (hub report).",
        "**Read-only:** no devices, rules, apps or settings have been changed.",
        "",
        "### Coverage",
        f"- Devices: {devices.get('total', 'unavailable')} in the MCP-visible "
        "detailed device inventory; "
        f"{devices.get('offline_count', 'unknown')} explicitly reported unavailable; "
        f"{devices.get('low_battery_count', 'unknown')} low-battery reports.",
        f"- Automations: {automations.get('total', 'unavailable')} distinct "
        "apps/rules normalised from the automation sources; "
        f"{marker_count} name-only markers and "
        f"{sum(item.get('domain') == 'automations' and not _name_only_broken_marker(item) for item in alert_issues)} "
        "other automation alerts. The underlying System Check retains its "
        "original flagged-item total.",
        f"- Logs: {logs.get('entries_checked', 'unavailable')} returned rows "
        f"(requested lookback: {logs.get('checked_hours', 'unknown')} hours, "
        "at most 200 rows). This is not proof that older or omitted events are absent.",
    ]
    unavailable = [
        label for label, section in (
            ("device inventory", devices), ("automations", automations), ("logs", logs)
        )
        if section.get("available") is False
    ]
    if unavailable:
        lines.append("- Incomplete sources: " + ", ".join(unavailable) + ".")
    if logs.get("entries_checked") == 200:
        lines.append(
            "- **Log window saturated:** all 200 requested rows were returned. "
            "Older errors in the 24-hour period may have been displaced by newer events; "
            "this does not verify complete 24-hour log coverage."
        )
    if sensecap_known_unpowered:
        lines.extend((
            "",
            "### Temporary user-reported device condition",
            "- **SenseCap D1: intentionally switched off (no power)** — supplied "
            "by the user through the add-on option, not independently verified "
            "by MCP. Its live/config push failures are expected while unpowered; "
            "they are not evidence of an unexplained network fault. Once powered "
            "back on, clear the option and verify communications resume.",
        ))
    lines.extend(("", "### Observed alerts (not necessarily proven causes)"))
    lines.extend(_audit_issue_lines(snapshot))
    offline_rows = [r for r in devices.get("offline", []) if isinstance(r, dict)]
    if offline_rows:
        lines.extend((
            "",
            "### Offline-device evidence (identity-grounded)",
            "The status originates from the MCP detailed device attributes. "
            "It does not alone establish whether the cause is radio reachability, "
            "device power, driver configuration or a stale status attribute.",
        ))
        for row in offline_rows[:8]:
            level = (
                f"{row['battery']}%" if row.get("battery") is not None
                else "not supplied"
            )
            lines.append(
                f"- {row.get('label') or 'Unnamed'} (ID {row.get('id') or '?'}): "
                f"state={row.get('state') or 'unknown'}, "
                f"source={row.get('source_attribute') or 'unspecified'}, "
                f"battery={level}, last recorded activity="
                f"{row.get('last_activity') or 'not supplied'}."
            )

    quiet = devices.get("no_recent_activity") or []
    if isinstance(quiet, list) and quiet:
        ranked = sorted(
            (item for item in quiet if isinstance(item, dict)),
            key=lambda item: float(item.get("age_hours") or 0),
            reverse=True,
        )
        lines.extend((
            "",
            f"### Quiet devices — {len(ranked)} observations, **not offline verdicts**",
            "These devices have old recorded activity. Event-driven sensors may "
            "normally remain quiet; reachability must be independently checked.",
        ))
        for item in ranked[:8]:
            lines.append(
                f"- {item.get('label') or item.get('id') or 'Unknown'}: "
                f"last activity {item.get('last_activity') or 'unknown'} "
                f"({item.get('age_hours', '?')} hours ago)."
            )
        if len(ranked) > 8:
            lines.append(f"- … and {len(ranked) - 8} more quiet devices in System Check.")

    overdue = devices.get("expected_update_overdue") or []
    if overdue:
        lines.append(
            f"\nExplicit reporting expectations missed: {len(overdue)}. "
            "A missed update does not by itself identify the cause."
        )

    lines.extend(("", "### Source scope and ID reconciliation"))
    if isinstance(performance, dict):
        for kind, label, source_key in (
            ("device", "Device", "deviceStats"),
            ("app", "App", "appStats"),
        ):
            total = _performance_population_total(performance, kind)
            listed = performance.get(source_key)
            sample_size = len(listed) if isinstance(listed, list) else 0
            source_total = str(total) if total is not None else "not supplied"
            lines.append(
                f"- {label} performance source: {source_total} reported total; "
                f"{sample_size} top-ranked rows returned. The top-ranked sample "
                "must not be treated as a full inventory."
            )
        inventory_ids = devices.get("inventory_ids")
        if isinstance(inventory_ids, list):
            ids = set(map(str, inventory_ids))
            performance_rows = performance.get("deviceStats") or []
            selected = [
                row for row in performance_rows
                if isinstance(row, dict) and row.get("id") not in (None, "")
            ]
            matched = [row for row in selected if str(row.get("id")) in ids]
            unlisted = [row for row in selected if str(row.get("id")) not in ids]
            lines.append(
                f"- Exact ID overlap: {len(matched)} of {len(selected)} sampled "
                "performance-device IDs appear in the MCP detailed inventory."
            )
            if unlisted:
                example = ", ".join(
                    f"{row.get('name') or 'Unknown'} (ID {row['id']})"
                    for row in unlisted[:4]
                )
                lines.append(
                    f"- Performance IDs outside this MCP inventory sample: {example}. "
                    "Different visibility/scope or paging could explain this; "
                    "it does NOT prove these devices are missing from Hubitat."
                )
                if context_reconciliation is not None:
                    if context_reconciliation.get("complete") is True:
                        found = context_reconciliation.get("found") or []
                        absent = context_reconciliation.get("absent") or []
                        lines.append(
                            f"- Independent live-context cross-check: {len(found)} of "
                            f"{len(unlisted)} unmatched performance IDs appear in a "
                            "complete live-context identity response."
                        )
                        if found:
                            lines.append("- IDs found in live context: " + ", ".join(found) + ".")
                        if absent:
                            lines.append(
                                "- IDs still unexplained after live-context cross-check: "
                                + ", ".join(absent) + ". Historical performance "
                                "entries or different visibility remain hypotheses."
                            )
                    else:
                        lines.append(
                            "- Independent live-context cross-check unavailable or "
                            "incomplete; unmatched IDs remain unresolved."
                        )
        else:
            lines.append(
                "- Full inventory IDs were not provided; exact device population "
                "reconciliation is unverified."
            )
        lines.append(
            "- App performance statistics and normalised automation app/rule items "
            "are not equivalent populations; a count difference alone is not a fault."
        )
    else:
        lines.append("- Performance scope is unknown because that source was unavailable.")

    lines.extend(("", "### Performance leaders (not automatic faults)"))
    if isinstance(performance, dict):
        for kind, key in (("Device", "deviceStats"), ("App", "appStats")):
            ranked = [
                row for row in performance.get(key, [])
                if isinstance(row, dict) and row.get("name")
            ]
            ranked.sort(
                key=lambda row: _core._safe_float(
                    str(row.get("pctBusy") or "0").replace("%", "")
                ) or 0.0,
                reverse=True,
            )
            for row in ranked[:3]:
                lines.append(
                    f"- {kind} {row['name']} (ID {row.get('id', '?')}): "
                    f"pctBusy={row.get('pctBusy', 'unknown')}%, "
                    f"pctTotal={row.get('pctTotal', 'unknown')}%, "
                    f"averageMs={row.get('averageMs', 'unknown')}."
                )
        lines.append(
            "Performance data is a top-ranked sample, not an audit of every device "
            "or app. Busy percentages do not establish errors or their causes."
        )
    else:
        lines.append(
            f"- Performance statistics unavailable: {performance_error or 'source did not return usable data'}."
        )

    if scoped_summary["patterns"]:
        lines.extend((
            "",
            "### Additional scoped diagnostic findings",
            "Counts represent repeated log rows grouped by source and message, "
            "not distinct outages. This sampled evidence is not a full event history.",
        ))
        for pattern in scoped_summary["patterns"][:8]:
            window = (
                f"; observed {pattern['first_seen']} to {pattern['last_seen']}"
                if pattern.get("first_seen") and pattern.get("last_seen")
                else "; event timestamps unavailable"
            )
            lines.append(
                f"- [{pattern['level']}] {pattern['name']} (ID {pattern['id']}): "
                f"{pattern['rows']} matching log rows — {pattern['detail']}{window}."
            )

    if historical_logs is not None:
        lines.extend(("", "### Older-log follow-up (24h to 6h before audit)"))
        if historical_logs.get("skipped_reason"):
            lines.append(
                "- Historical read skipped: "
                + str(historical_logs["skipped_reason"])
                + " Earlier errors remain unverified."
            )
        elif historical_logs.get("error"):
            lines.append(
                "- Historical bounded log read failed: "
                + str(historical_logs["error"]) + ". No historical claims made."
            )
        else:
            count = int(historical_logs.get("entries_checked") or 0)
            lines.append(
                f"- {count} returned rows in a separate older-log window "
                "(maximum 200). This does not certify complete historical coverage."
            )
            if not historical_logs.get("window_supported_by_rows"):
                lines.append(
                    "- **Historical window unverified:** the response contained "
                    "no rows, missing row timestamps or timestamps outside the "
                    "requested boundaries. A successful request does not confirm "
                    "server retention or support for the requested time filters."
                )
            else:
                lines.append(
                    "- Returned timestamps fall within the requested historical "
                    "window, but this does not establish that every event was returned."
                )
            if historical_logs.get("observed_earliest"):
                lines.append(
                    "- Observed timestamps: "
                    f"{historical_logs['observed_earliest']} to "
                    f"{historical_logs['observed_latest']} "
                    f"({historical_logs.get('rows_with_timestamps', 0)} dated rows)."
                )
            if count >= 200:
                lines.append(
                    "- Older-window sample also saturated: some historical "
                    "errors may remain hidden."
                )
            for group in (historical_logs.get("groups") or [])[:5]:
                lines.append(
                    f"- [{group.get('level')}] "
                    f"{_concise_log_message(group.get('summary'))} "
                    f"({group.get('count')} rows)."
                )

    for item in targeted_logs or []:
        kind = item.get("kind") or "target"
        name = item.get("name") or item.get("id") or "unknown"
        elapsed = (
            f", read {item['elapsed_ms']}ms"
            if item.get("elapsed_ms") is not None else ""
        )
        lines.append(
            f"- Scoped investigation target: {kind} {name} (ID {item.get('id') or '?'})"
            f" — {item.get('selection') or 'performance outlier'}{elapsed}."
        )
        quality = item.get("time_quality") or {}
        if quality.get("chronology_withheld_rows"):
            lines.append(
                f"  - Timestamp integrity: {quality.get('ambiguous_timezone_rows', 0)} "
                "timezone-ambiguous, "
                f"{quality.get('future_timestamp_rows', 0)} apparently future, "
                f"{quality.get('undated_rows', 0)} undated rows. Chronology withheld "
                "for those rows; do not infer BST/UTC offsets without source metadata."
            )
            if quality.get("raw_examples"):
                lines.append(
                    "  - Example unverified source time(s): "
                    + ", ".join(str(v) for v in quality["raw_examples"]) + "."
                )
        if item.get("error"):
            lines.append(f"- Follow-up log read for {kind} {name} failed: {item['error']}.")
        elif item.get("groups"):
            lines.append(
                f"- Follow-up for {kind} {name}: {item.get('matching_rows', 0)} "
                "matching log rows within 6h; observed messages:"
            )
            for group in item["groups"][:3]:
                lines.append(
                    f"  - [{group.get('level')}] "
                    f"{_concise_log_message(group.get('message') or group.get('summary'))} "
                    f"({group.get('count')} rows)"
                )
        else:
            lines.append(
                f"- Follow-up for {kind} {name}: no matching warnings/errors "
                "in the returned 6h sample (not proof of no earlier issues)."
            )
        if "sensecap" in str(name).casefold() and "live_push_evidence" in item:
            observed = item["live_push_evidence"]
            lines.append(
                "- SenseCap correlation: "
                f"{observed.get('failure_rows', 0)} live-push failure rows, "
                f"{observed.get('config_failure_rows', 0)} configuration-push "
                "failure rows; these may share a network cause, but the logs "
                "do not establish causality or distinct outage counts."
            )
            if observed.get("latest_failure"):
                lines.append(
                    "- Latest timestamped live-push failure: "
                    + str(observed["latest_failure"]) + "."
                )
            if observed.get("latest_success"):
                lines.append(
                    "- Latest timestamped explicit live-push success: "
                    + str(observed["latest_success"]) + "."
                )
            if observed.get("later_success_observed"):
                lines.append(
                    "- SenseCap live-push follow-up: an explicit successful push/resume "
                    "log is newer than the sampled failed push. This supports an "
                    "observed recovery event, not guaranteed ongoing operation."
                )
            else:
                lines.append(
                    "- SenseCap live-push follow-up: no timestamp-supported later "
                    "successful push was established in the returned log sample; "
                    "recovery remains unverified."
                )
        for group in item.get("groups") or []:
            detail = " ".join(str(group.get(field) or "") for field in ("message", "summary"))
            lower_detail = detail.casefold()
            if "metering_cluster" in lower_detail and "0x84" in lower_detail:
                lines.append(
                    "  - **Zigbee metering:** The device returned code 0x84 for a "
                    "METERING_CLUSTER command. Its meaning and effect on current "
                    "meter readings are not established by these logs. Inspect "
                    "the driver command and independently check recent metering "
                    "updates before changing the driver or reporting interval."
                )
            if "adb shell connection timed out" in lower_detail:
                lines.append(
                    "  - **ADB connection:** The retained shell timed out. Verify "
                    "the streamer's IP reachability and supported ADB reconnect "
                    "state using read-only information before changing settings."
                )
            if "attributeNames" in detail and (
                "format='summary'" in detail or "format 'summary'" in detail
            ):
                lines.append(
                    "  - **MCP device-list validation:** The observed request combines "
                    "attributeNames with format='summary', which the MCP gateway rejects. "
                    "The log identifies hub_list_devices but does not identify the "
                    "original requesting caller. Inspect server request tracing and "
                    "correct the caller's projection; no Hubitat change was made."
                )
                break

    lines.extend(("", "### Evidence-based next checks"))
    lines.extend(_audit_followups(
        snapshot, performance, sensecap_known_unpowered=sensecap_known_unpowered,
    ) or [
        "- No specific fix is justified from the currently returned fault evidence."
    ])
    if ai_advisory:
        lines.extend((
            "",
            "### Optional AI diagnostic hypotheses — unverified",
            "Model-generated investigation suggestions only. These do not "
            "replace MCP evidence or authorize device changes.",
            ai_advisory[:1800],
        ))
    lines.extend((
        "",
        "### Repair status",
        "- No repairs performed; current and historical co-observations do not prove causality.",
        "- Any Hubitat mutation requires a separate explicitly targeted request, "
        "verified capability and the existing confirmation safeguards.",
        (
            "- Deterministic evidence was host-assembled; an optional bounded AI "
            "advisory was requested but cannot establish additional facts."
            if ai_advisory else
            "- This report is host-assembled from MCP reads; no Gemma reasoning round "
            "was used to infer missing evidence."
        ),
    ))
    return "\n".join(lines)


async def run_comprehensive_chat_audit(
    audit: Any,
    mcp: Any,
    *, analysis_chat: Any = None,
) -> Any:
    """Reuse the full System Check, then inspect performance outliers safely."""
    from automation_status_service import AutomationStatusOutcome
    from mcp_client import tool_succeeded
    snapshot = await audit.run(reason="chat")
    sensecap_known_unpowered = bool(
        getattr(audit, "sensecap_d1_intentionally_powered_off", False)
    )
    previous_method = getattr(audit, "previous", None)
    previous_snapshot: dict[str, Any] | None = None
    if callable(previous_method):
        try:
            previous_value = previous_method()
            if isinstance(previous_value, dict):
                previous_snapshot = previous_value
        except Exception:
            pass
    evidence: list[dict[str, Any]] = []
    checked_at = snapshot.get("checked_at")
    evidence.append({
        "tool": "health_audit.run",
        "success": True,
        "timestamp": checked_at,
        "supports_live_claim": True,
        "evidence_kind": "read_only_system_audit_snapshot",
        "mutates": False,
        "effect": "read",
        "summary": (
            f"System Check {snapshot.get('status', 'unknown')}; "
            f"{snapshot.get('attention_count', '?')} flagged findings"
        ),
    })
    for label, key in (("devices", "devices"), ("automations", "automations"), ("logs", "logs")):
        section = (snapshot.get("sections") or {}).get(key) or {}
        complete = section.get("available") is not False and (
            ("total" in section) if key != "logs" else section.get("available") is True
        )
        evidence.append({
            "tool": "health_audit.run",
            "sub_tool": key,
            "timestamp": checked_at,
            "success": bool(complete),
            "supports_live_claim": bool(complete),
            "evidence_kind": "audit_source_section",
            "mutates": False,
            "effect": "read",
            "summary": (
                f"{label} section {'available' if complete else 'unavailable'}; "
                f"{section.get('total', section.get('entries_checked', '?'))} "
                "records/items in the returned source"
            ),
        })

    stats: dict[str, Any] | None = None
    performance_error: str | None = None
    targeted_logs: list[dict[str, Any]] = []
    historical_logs: dict[str, Any] | None = None
    context_reconciliation: dict[str, Any] | None = None
    try:
        tools = {tool.name: tool for tool in await mcp.list_tools()}
        gateway = tools.get("hub_manage_logs") or tools.get("hub_read_diagnostics")
        if gateway is None:
            performance_error = "no supported log/performance gateway"
        else:
            arguments = _gateway_arguments(
                gateway,
                "hub_get_performance_stats",
                {"limit": 20, "sortBy": "pct", "type": "both"},
            )
            response = await mcp.call_tool(gateway.name, arguments)
            valid_performance = (
                tool_succeeded(response) and isinstance(response.data, dict)
                and isinstance(response.data.get("deviceStats"), list)
                and isinstance(response.data.get("appStats"), list)
            )
            if valid_performance:
                stats = response.data
            else:
                performance_error = "performance tool returned no usable device/app data"
            evidence.append({
                "tool": gateway.name,
                "sub_tool": "hub_get_performance_stats",
                "arguments": arguments,
                "timestamp": checked_at,
                "success": bool(valid_performance),
                "supports_live_claim": bool(valid_performance),
                "evidence_kind": "chat_audit_performance_stats",
                "mutates": False,
                "effect": "read",
                "summary": (
                    "top-ranked device/app rows"
                    if valid_performance else "performance read unavailable or incomplete"
                ),
            })

            for target in _fault_first_log_targets(
                snapshot, stats, previous_snapshot=previous_snapshot,
                sensecap_known_unpowered=sensecap_known_unpowered,
            ):
                kind = target["kind"]
                identifier = target["id"]
                name = target["name"]
                scope = "deviceId" if kind == "device" else "appId"
                args = _gateway_arguments(
                    gateway,
                    "hub_get_logs",
                    {scope: identifier, "since": "6h", "limit": 120},
                )
                read_started = time.monotonic()
                try:
                    response = await mcp.call_tool(gateway.name, args)
                    elapsed_ms = round((time.monotonic() - read_started) * 1000)
                    if not tool_succeeded(response):
                        raise ValueError("filtered log read failed")
                    prefix = ("dev|" if kind == "device" else "app|") + identifier + "|"
                    rows = [
                        row for row in _log_rows(response)
                        if prefix in str(row.get("message") or "")
                        or name.casefold() in str(row.get("message") or "").casefold()
                    ]
                    safe_rows, time_quality = _audit_log_time_quality(
                        rows, checked_at=checked_at,
                    )
                    findings, _ = _log_findings(safe_rows)
                    evidence.append({
                        "tool": gateway.name,
                        "sub_tool": "hub_get_logs",
                        "arguments": args,
                        "timestamp": checked_at,
                        "success": True,
                        "supports_live_claim": True,
                        "evidence_kind": "chat_audit_scoped_logs",
                        "elapsed_ms": elapsed_ms,
                        "mutates": False,
                        "effect": "read",
                        "summary": (
                            f"{kind} {name} (ID {identifier}): "
                            f"{len(rows)} matched rows in a bounded 6h log request"
                        ),
                    })
                    targeted_logs.append({
                        **target,
                        "matching_rows": len(rows),
                        "elapsed_ms": elapsed_ms,
                        "returned_rows": len(_log_rows(response)),
                        "time_quality": time_quality,
                        **({
                            "live_push_evidence": _live_push_log_evidence(safe_rows),
                        } if "sensecap d1" in name.casefold() else {}),
                        "groups": (
                            findings["error_groups"] + findings["warning_groups"]
                        )[:3],
                    })
                except Exception as exc:
                    elapsed_ms = round((time.monotonic() - read_started) * 1000)
                    error = f"{type(exc).__name__}: {str(exc)[:120]}"
                    evidence.append({
                        "tool": gateway.name,
                        "sub_tool": "hub_get_logs",
                        "arguments": args,
                        "timestamp": checked_at,
                        "success": False,
                        "supports_live_claim": False,
                        "evidence_kind": "chat_audit_scoped_logs",
                        "elapsed_ms": elapsed_ms,
                        "mutates": False,
                        "effect": "read",
                        "summary": f"{kind} {name} scoped logs failed: {error}",
                    })
                    targeted_logs.append({**target, "error": error, "elapsed_ms": elapsed_ms})
            # A saturated 24h sample can be all recent INFO rows. Fetch one
            # explicitly older, bounded, disjoint segment using the existing
            # supported since/until window contract (not a guessed severity
            # filter). Never label this a complete historical audit.
            audit_logs = (snapshot.get("sections") or {}).get("logs") or {}
            if (
                audit_logs.get("entries_checked") == 200 and checked_at
                and len(targeted_logs) >= 3
            ):
                historical_logs = {
                    "skipped_reason": (
                        "three or more fault/performance log scopes already checked; "
                        "avoid another potentially slow /logs/json request on this run."
                    )
                }
            elif audit_logs.get("entries_checked") == 200 and checked_at:
                started_at = datetime.fromisoformat(str(checked_at).replace("Z", "+00:00"))
                older_args = _gateway_arguments(
                    gateway,
                    "hub_get_logs",
                    {
                        "since": (started_at - timedelta(hours=24)).isoformat(),
                        "until": (started_at - timedelta(hours=6)).isoformat(),
                        "limit": 200,
                    },
                )
                try:
                    older_result = await mcp.call_tool(gateway.name, older_args)
                    if not tool_succeeded(older_result):
                        raise ValueError("historical bounded log request failed")
                    older_rows = _log_rows(older_result)
                    safe_older, history_time_quality = _audit_log_time_quality(
                        older_rows, checked_at=checked_at,
                    )
                    older_findings, _ = _log_findings(safe_older)
                    historical_logs = {
                        "time_quality": history_time_quality,
                        **_bounded_log_window_evidence(
                            older_rows,
                            start=started_at - timedelta(hours=24),
                            end=started_at - timedelta(hours=6),
                        ),
                        "groups": (
                            older_findings["error_groups"] +
                            older_findings["warning_groups"]
                        )[:5],
                    }
                    evidence.append({
                        "tool": gateway.name, "sub_tool": "hub_get_logs",
                        "arguments": older_args, "timestamp": checked_at,
                        "success": True,
                        "supports_live_claim": bool(
                            historical_logs.get("window_supported_by_rows")
                        ),
                        "evidence_kind": "chat_audit_historical_logs",
                        "mutates": False, "effect": "read",
                        "summary": (
                            f"historical 24h-to-6h bounded window: {len(older_rows)} "
                            "returned rows (max 200); timestamp membership "
                            + (
                                "verified for returned records, not exhaustive"
                                if historical_logs.get("window_supported_by_rows")
                                else "unverified (empty/undated/out-of-window)"
                            )
                        ),
                    })
                except Exception as exc:
                    error = f"{type(exc).__name__}: {str(exc)[:120]}"
                    historical_logs = {"error": error}
                    evidence.append({
                        "tool": gateway.name, "sub_tool": "hub_get_logs",
                        "arguments": older_args, "timestamp": checked_at,
                        "success": False, "supports_live_claim": False,
                        "evidence_kind": "chat_audit_historical_logs",
                        "mutates": False, "effect": "read",
                        "summary": error,
                    })
    except Exception as exc:
        performance_error = f"{type(exc).__name__}: {str(exc)[:160]}"

    # Check unmatched performance identities against a separate live-context
    # source only when available and demonstrably complete. This check does
    # not change or repair the detailed inventory.
    if isinstance(stats, dict):
        inventory_ids = {
            str(value) for value in (
                (snapshot.get("sections") or {}).get("devices") or {}
            ).get("inventory_ids", [])
        }
        unmatched = [
            row for row in (stats.get("deviceStats") or [])
            if isinstance(row, dict) and row.get("id") not in (None, "")
            and str(row["id"]) not in inventory_ids
        ] if inventory_ids else []
        read_context = getattr(mcp, "get_live_context", None)
        if unmatched and callable(read_context):
            from device_read_contract import live_context_is_complete
            try:
                context = await read_context(refresh=False)
                complete = live_context_is_complete(context)
                context_ids = {
                    str(row.get("id") or row.get("deviceId"))
                    for row in (context.get("devices") or [])
                    if isinstance(row, dict)
                } if complete else set()
                context_reconciliation = {
                    "complete": complete,
                    "found": [
                        str(row.get("name") or row["id"])
                        for row in unmatched if str(row["id"]) in context_ids
                    ],
                    "absent": [
                        str(row.get("name") or row["id"])
                        for row in unmatched if str(row["id"]) not in context_ids
                    ] if complete else [],
                }
                evidence.append({
                    "tool": "hubitat://context",
                    "timestamp": checked_at, "success": complete,
                    "supports_live_claim": complete,
                    "evidence_kind": "chat_audit_inventory_crosscheck",
                    "mutates": False, "effect": "read",
                    "summary": (
                        f"live context {'complete' if complete else 'incomplete'}; "
                        f"{len(context_reconciliation['found'])}/{len(unmatched)} "
                        "unmatched performance IDs found" if complete
                        else "live-context identity cross-check incomplete"
                    ),
                })
            except Exception as exc:
                context_reconciliation = {"complete": False}
                evidence.append({
                    "tool": "hubitat://context", "timestamp": checked_at,
                    "success": False, "supports_live_claim": False,
                    "evidence_kind": "chat_audit_inventory_crosscheck",
                    "mutates": False, "effect": "read",
                    "summary": f"live-context cross-check failed: {type(exc).__name__}",
                })

    message = render_comprehensive_system_audit(
        snapshot, stats, performance_error=performance_error,
        targeted_logs=targeted_logs, historical_logs=historical_logs,
        context_reconciliation=context_reconciliation,
        sensecap_known_unpowered=sensecap_known_unpowered,
    )
    if callable(analysis_chat):
        # Explicit opt-in: one short, tool-free model pass, never executing
        # suggestions. The deterministic report remains authoritative.
        system_prompt = (
            "You are analysing a read-only Hubitat diagnostic report. "
            "Return at most three brief, evidence-linked investigative hypotheses. "
            "Use only the supplied report. Separate known user configuration from "
            "verified device evidence. Do not invent IP addresses, missing tools, "
            "diagnoses or repairs. Never request or execute a state change. "
            "If the SenseCap device is intentionally unpowered, say that is "
            "the user-reported explanation for its transport failures."
        )
        try:
            response = await asyncio.wait_for(
                analysis_chat([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message[:7000]},
                ], []),
                timeout=12.0,
            )
            advisory = str(
                response.get("content") or "" if isinstance(response, dict) else ""
            ).strip()[:1800]
            if advisory:
                message = render_comprehensive_system_audit(
                    snapshot, stats, performance_error=performance_error,
                    targeted_logs=targeted_logs, historical_logs=historical_logs,
                    context_reconciliation=context_reconciliation,
                    sensecap_known_unpowered=sensecap_known_unpowered,
                    ai_advisory=advisory,
                )
                evidence.append({
                    "tool": "optional_ai_advisory", "timestamp": checked_at,
                    "success": True, "supports_live_claim": False,
                    "evidence_kind": "non_authoritative_model_hypotheses",
                    "mutates": False, "effect": "read",
                    "summary": "Tool-free optional AI analysis; no additional facts or actions",
                })
        except Exception as exc:
            evidence.append({
                "tool": "optional_ai_advisory", "timestamp": checked_at,
                "success": False, "supports_live_claim": False,
                "evidence_kind": "non_authoritative_model_hypotheses",
                "mutates": False, "effect": "read",
                "summary": f"Optional AI analysis unavailable: {type(exc).__name__}",
            })
    return AutomationStatusOutcome(
        message=message,
        route="comprehensive-system-audit",
        evidence=evidence,
    )



__all__ = [
    "HealthAuditService",
    "is_comprehensive_system_audit_request",
    "render_comprehensive_system_audit",
    "run_comprehensive_chat_audit",
    "_device_findings",
    "_freshness_seconds",
    "_gateway_arguments",
    "_log_findings",
    "_log_rows",
]
