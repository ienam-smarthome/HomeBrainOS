"""Evidence-specific Hub Events interpretation for HomeBrain's AI incident review.

The verified **trigger** of a restart and its **underlying memory consumer**
are different questions. An authenticated Hubitat event with a reboot message
may establish the former, not the latter. The assessment deliberately reads
existing receipts; it never makes an MCP call or trusts generated prose.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        pass
    return None


def _display(value: datetime) -> str:
    return value.strftime("%d %b %Y, %H:%M:%S UTC")


def _local_startups(snapshot: dict[str, Any], first: datetime, last: datetime) -> list[datetime]:
    recorder = snapshot.get("recorder") or {}
    if not isinstance(recorder, dict):
        return []
    return sorted({
        when for entry in (recorder.get("startups") or [])
        if isinstance(entry, dict)
        for when in [_parse_time(entry.get("occurred_at"))]
        if when is not None and first <= when <= last
    })


def assess_hub_event_trigger(snapshot: dict[str, Any],
                             receipts: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Classify an exact Hubitat event only when typed, successful and time bounded."""
    empty = {
        "restart_trigger": "unverified",
        "restart_trigger_source": "not_verified",
        "underlying_memory_cause": "unverified",
        "firmware_memory_causality": "unverified",
        "typed_hub_events_checked": False,
        "observed_system_events": [],
        "app_specific_logs": "not_verified",
        "app_specific_log_attempts": 0,
        "coverage_note": (
            "Unobserved source records and retained-history gaps cannot "
            "establish that an event never occurred."
        ),
    }
    first = _parse_time(snapshot.get("window_start"))
    last = _parse_time(snapshot.get("window_end"))
    if first is None or last is None or first >= last:
        return empty
    events: dict[tuple[str, datetime, str], dict[str, Any]] = {}
    attempts = 0
    failures = 0
    successes = 0
    checked = False
    for receipt in (receipts or []):
        if not isinstance(receipt, dict) or receipt.get("mutates"):
            continue
        sub_tool = receipt.get("sub_tool")
        args = receipt.get("arguments") or {}
        if not isinstance(args, dict):
            args = {}
        params = args.get("args") if isinstance(args.get("args"), dict) else {}
        if sub_tool == "hub_get_logs" and params.get("mode") == "apps":
            attempts += 1
            if receipt.get("success") is True:
                successes += 1
            else:
                failures += 1
        # A successful generic log query or local archive counter does NOT
        # establish that Hubitat's relevant typed Hub Events were returned.
        if (sub_tool != "hub_list_device_events"
                or receipt.get("success") is not True
                or receipt.get("supports_live_claim") is not True):
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict) or not isinstance(details.get("observedEvents"), list):
            continue
        checked = True
        for event in details["observedEvents"]:
            if not isinstance(event, dict):
                continue
            name = event.get("name")
            if name not in ("systemStart", "lowMemory", "update"):
                continue
            when = _parse_time(event.get("date"))
            if when is None or not first <= when <= last:
                continue
            value = str(event.get("value") or "")[:40]
            description = str(event.get("description") or "")[:160]
            explicitly_rebooting = (name == "lowMemory"
                and "memory is critically low" in description.casefold()
                and "rebooting now" in description.casefold())
            key = (name, when, value)
            events[key] = {
                "name": name, "occurred_at": when.isoformat(timespec="milliseconds"),
                "firmware": value if name in ("update", "systemStart") else "",
                "explicit_reboot_message": explicitly_rebooting,
                "source": "verified_hubitat_device_events",
            }
    selected = sorted(events.values(), key=lambda row: row["occurred_at"])
    starts = _local_startups(snapshot, first, last)
    starts.extend(
        when for row in selected if row["name"] == "systemStart"
        for when in [_parse_time(row["occurred_at"])] if when is not None
    )
    starts = sorted(set(starts))

    def followed_by_startup(when: datetime, minutes: int = 30) -> bool:
        return any(0 <= (start - when).total_seconds() <= minutes * 60
                   for start in starts)

    reported_low_memory = any(
        row["name"] == "lowMemory" and row["explicit_reboot_message"]
        and (when := _parse_time(row["occurred_at"])) is not None
        and followed_by_startup(when)
        for row in selected
    )
    update_with_startup = any(
        row["name"] == "update"
        and (when := _parse_time(row["occurred_at"])) is not None
        and followed_by_startup(when)
        for row in selected
    )
    if reported_low_memory and update_with_startup:
        trigger = "multiple_hub_reboot_signals"
    elif reported_low_memory:
        trigger = "hub_explicit_critical_low_memory_reboot"
    elif update_with_startup:
        trigger = "firmware_update_recorded_before_startup"
    elif starts:
        trigger = "startup_observed_trigger_unverified"
    else:
        trigger = "unverified"
    return {
        **empty,
        "restart_trigger": trigger,
        "restart_trigger_source": (
            "verified_hubitat_device_events" if checked else "not_verified"
        ),
        "typed_hub_events_checked": checked,
        "observed_system_events": selected[:20],
        "app_specific_logs": (
            "read_failed" if failures and not successes
            else "read_succeeded_coverage_unverified" if successes
            else "not_verified"
        ),
        "app_specific_log_attempts": attempts,
    }


def render_hub_event_findings(assessment: dict[str, Any]) -> str:
    """A small deterministic, evidence-first interpretation without model prose."""
    rows = ["**Hubitat system-event verification**"]
    events = assessment.get("observed_system_events") or []
    if events:
        for event in events:
            when = _parse_time(event.get("occurred_at"))
            if when is None:
                continue
            time = _display(when)
            name = event["name"]
            if name == "lowMemory":
                qualifier = ("explicitly says critical memory and rebooting now"
                             if event.get("explicit_reboot_message")
                             else "lowMemory event recorded; reboot message not confirmed")
            elif name == "update":
                qualifier = "updated with build " + str(event.get("firmware") or "unavailable")
            else:
                qualifier = "systemStart on build " + str(event.get("firmware") or "unavailable")
            rows.append(f"- {time} — Hubitat {name}: {qualifier}.")
    else:
        rows.append(
            "- No typed Hubitat system-event rows were verified for this "
            "window. This is **not** evidence that no events occurred."
        )
    trigger = assessment.get("restart_trigger")
    if trigger == "hub_explicit_critical_low_memory_reboot":
        rows.append(
            "**Restart trigger: Hubitat explicitly reported critically low "
            "memory and an impending reboot, followed by a recorded startup.** "
            "This supports the reboot trigger, not which process consumed memory."
        )
    elif trigger == "firmware_update_recorded_before_startup":
        rows.append(
            "**Restart context: Hubitat recorded a firmware update followed "
            "by a startup.** The update-associated sequence is verified, "
            "but the exact reboot initiator and cause of any preceding "
            "memory reduction are not established by timestamps."
        )
    elif trigger == "multiple_hub_reboot_signals":
        rows.append(
            "**Restart context: Hubitat reported both critical memory "
            "and firmware-update signals before a startup.** The "
            "relationship between those signals is not established."
        )
    else:
        rows.append("**Restart trigger: unverified from available typed Hub Events.**")
    rows.append(
        "**Underlying memory-pressure cause: UNVERIFIED.** No individual "
        "application, driver, scheduled job or hardware event is proven responsible."
    )
    if assessment.get("app_specific_logs") == "read_failed":
        rows.append(
            "**Evidence gap:** A targeted app-log read failed; "
            "the retained Journal counts are not equivalent to actual "
            "app-log message review."
        )
    rows.append(
        "The time between a reboot message and systemStart does not, "
        "by itself, prove an uninterrupted connectivity outage."
    )
    return "\n".join(rows)
