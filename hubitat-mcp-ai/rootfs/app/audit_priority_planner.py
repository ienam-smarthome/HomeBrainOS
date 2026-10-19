"""Evidence-led priorities for an existing read-only comprehensive Hubitat audit.

This is a report planner, not a repair engine. It only ranks observed typed
status, log and scheduled-job receipts, never infers root cause, job ownership
or physical actuation from an unrelated status/activity timestamp.
"""
from __future__ import annotations

import re
from typing import Any


def _safe_name(value: Any) -> str:
    # Treat labels as data, not rich Markdown or a link.
    s = re.sub(r"[\r\n|<>{}\[\]\x60*]", " ", str(value or ""))
    return re.sub(r"\s+", " ", s).strip()[:85]


def _positive_int(value: Any) -> int | None:
    try:
        candidate = int(value)
        return candidate if candidate >= 0 else None
    except (ValueError, TypeError):
        return None


def _matching_patterns(row: dict[str, Any]) -> tuple[bool, bool]:
    groups = row.get("groups") or []
    if not isinstance(groups, list):
        return False, False
    watched = False
    error = False
    for group in groups[:8]:
        if not isinstance(group, dict):
            continue
        level = str(group.get("level") or "").lower()
        text = " ".join(str(group.get(k) or "") for k in ("summary", "message", "detail"))
        if "watchdog" in text.casefold() and level in {"warning", "warn", "error"}:
            watched = True
        if level == "error":
            error = True
    return watched, error


def _priority_entries(
    snapshot: dict[str, Any],
    targeted_logs: list[dict[str, Any]] | None,
    *,
    sensecap_known_unpowered: bool,
) -> list[tuple[str, str, str]]:
    devices = (snapshot.get("sections") or {}).get("devices") or {}
    offline = [
        item for item in (devices.get("offline") or [])
        if isinstance(item, dict) and str(item.get("id") or "").isdigit()
    ]
    scoped = [
        row for row in (targeted_logs or [])
        if isinstance(row, dict) and str(row.get("id") or "").isdigit()
        and _positive_int(row.get("matching_rows")) is not None
        and not row.get("error")
    ]
    by_id = {
        (str(item.get("kind") or ""), str(item["id"])): item
        for item in scoped
    }
    entries: list[tuple[str, str, str]] = []
    flagged_offline: set[str] = set()
    for row in offline:
        device_id = str(row["id"])
        source = by_id.get(("device", device_id))
        if source is None:
            continue
        watchdog, _ = _matching_patterns(source)
        if not watchdog:
            continue
        flagged_offline.add(device_id)
        name = _safe_name(row.get("label") or device_id)
        entries.append((
            "Investigate",
            f"**{name} (device {device_id})** reports offline; its "
            f"scoped log sample has {_positive_int(source.get('matching_rows'))} matched "
            "rows including a watchdog warning.",
            "Check actual power and upstream telemetry. Hubitat activity may be a "
            "watchdog event, not physical device recovery; do not reset or re-pair yet.",
        ))
    remaining = [row for row in offline if str(row["id"]) not in flagged_offline]
    if remaining:
        names = ", ".join(
            f"{_safe_name(row.get('label') or row['id'])} ({row['id']})"
            for row in remaining[:5]
        )
        suffix = f"; {len(remaining)-5} more" if len(remaining) > 5 else ""
        entries.append((
            "Verify",
            f"**{len(remaining)} other explicitly offline device(s):** {names}{suffix}.",
            "Check power, signal and last physical report individually. An offline "
            "status alone does not establish the cause.",
        ))

    for source in scoped:
        if len(entries) >= 5:
            break
        _, has_error = _matching_patterns(source)
        if not has_error:
            continue
        name = _safe_name(source.get("name") or source["id"])
        if sensecap_known_unpowered and "sensecap d1" in name.lower():
            continue
        # Avoid duplicating an offline device already prioritised.
        if source.get("kind") == "device" and str(source["id"]) in flagged_offline:
            continue
        entries.append((
            "Investigate",
            f"**{name} ({source.get('kind') or 'source'} {source['id']})** "
            f"has {_positive_int(source.get('matching_rows'))} matched sampled log "
            "rows, including an ERROR.",
            "Inspect error details, endpoint/reachability and configured retry "
            "policy. Do not infer timeouts caused hub-wide instability.",
        ))

    quiet = [
        row for row in devices.get("no_recent_activity") or []
        if isinstance(row, dict) and
        re.search(r"\bheartbeat\b", str(row.get("label") or ""), re.I)
    ]
    if quiet and len(entries) < 5:
        top = quiet[0]
        entries.append((
            "Confirm",
            f"**{_safe_name(top.get('label'))}** is recorded as quiet since "
            f"{_safe_name(top.get('last_activity') or 'an unknown date')}.",
            "Check the intended heartbeat schedule and sender/receiver roles. "
            "An old last-activity timestamp alone cannot prove failover is broken.",
        ))
    return entries[:5]


def render_audit_priorities(
    snapshot: dict[str, Any],
    targeted_logs: list[dict[str, Any]] | None,
    *,
    sensecap_known_unpowered: bool = False,
) -> str:
    entries = _priority_entries(
        snapshot, targeted_logs,
        sensecap_known_unpowered=sensecap_known_unpowered,
    )
    if not entries:
        return (
            "### Prioritised evidence checks\n"
            "No additional fault priority was established from the available "
            "status and scoped log samples. This is not proof of system-wide health."
        )
    lines = [
        "### Prioritised evidence-backed checks",
        "Ranked for investigation, not as proven root causes or permission to change settings.",
    ]
    for index, (kind, finding, next_step) in enumerate(entries, 1):
        lines.append(f"{index}. **{kind}:** {finding}")
        lines.append(f"   - **Next read-only check:** {next_step}")
    if sensecap_known_unpowered:
        lines.append(
            "- **Known condition, not an unexplained fault:** SenseCap D1 is "
            "user-marked intentionally unpowered. Recheck it only after restoring power."
        )
    return "\n".join(lines)


def render_audit_scheduled_jobs(
    summary: dict[str, Any] | None,
    *,
    unavailable: str | None = None,
) -> str:
    lines = ["### Scheduled jobs — queue evidence"]
    if not isinstance(summary, dict) or summary.get("status") != "parsed":
        return "\n".join(lines + [
            f"- Not independently examined: {_safe_name(unavailable or 'source unavailable')}. "
            "No scheduler-level absence or duplication verdict can be made."
        ])
    total = _positive_int(summary.get("reportedJobs"))
    checked = _positive_int(summary.get("rowsExamined"))
    if total is None or checked is None:
        return "\n".join(lines + ["- Scheduler source returned no usable totals."])
    lines.append(
        f"- **{total} scheduled entries reported**, {checked} rows examined"
        + (" (all reported rows represented)." if summary.get("completeRows") is True
           else " (incomplete/paged collection; missing rows remain unchecked).")
    )
    owners = _positive_int(summary.get("ownerIdentifiedRows"))
    if owners is not None:
        lines.append(
            f"- {owners} rows have explicit, source-recognised owner fields; "
            "inferred scheduler-key owner IDs are candidates only."
        )
    methods = [row for row in summary.get("topMethods") or [] if isinstance(row, dict)]
    if methods:
        portions = [
            f"{_safe_name(row.get('method'))} ({_positive_int(row.get('jobs'))} entries)"
            for row in methods[:4] if _safe_name(row.get("method"))
            and _positive_int(row.get("jobs")) is not None
        ]
        if portions:
            lines.append("- Most frequent scheduled handlers: " + "; ".join(portions) + ".")
    clusters = [row for row in summary.get("sameNextRunGroups") or [] if isinstance(row, dict)]
    if clusters:
        cluster = clusters[0]
        n = _positive_int(cluster.get("jobs"))
        when = _safe_name(cluster.get("nextRun"))
        if n is not None and when:
            lines.append(
                f"- Largest returned shared next-run timestamp: {n} entries at "
                f"{when}. Shared timing does **not** prove CPU contention."
            )
    lines.extend([
        "- **Dependency and disabled-app scheduling not yet verified.** "
        "An app-labelled scheduler key alone does not prove which installed "
        "app owns or executed a job.",
        "- **Next read-only check:** reconcile explicit scheduler owner IDs with "
        "installed app states; then inspect the actual callback and disable "
        "behaviour before suggesting stagger, cancellation or deletion.",
    ])
    return "\n".join(lines)


__all__ = ["render_audit_priorities", "render_audit_scheduled_jobs"]
