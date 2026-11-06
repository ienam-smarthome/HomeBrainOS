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
        "app_runtime_stats_attempts": 0,
        "app_runtime_stats_successes": 0,
        "bounded_generic_log_reads": 0,
        "bounded_generic_log_read_successes": 0,
        "hub_event_log_read_successes": 0,
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
    runtime_attempts = 0
    runtime_successes = 0
    failures = 0
    successes = 0
    checked = False
    generic_attempts = 0
    generic_successes = 0
    event_log_successes = 0
    for receipt in (receipts or []):
        if not isinstance(receipt, dict) or receipt.get("mutates"):
            continue
        sub_tool = receipt.get("sub_tool")
        args = receipt.get("arguments") or {}
        if not isinstance(args, dict):
            args = {}
        params = args.get("args") if isinstance(args.get("args"), dict) else {}
        if sub_tool == "hub_get_logs":
            mode = params.get("mode")
            if mode == "apps":
                # Upstream MCP 'apps' returns current App Stats, not log lines.
                runtime_attempts += 1
                if receipt.get("success") is True:
                    runtime_successes += 1
            elif (mode in (None, "", "past") and params.get("appId")
                  and params.get("since") and params.get("until")):
                # Scoped historical app-message query; a successful call
                # remains an unverified-content receipt until rows are read.
                attempts += 1
                if receipt.get("success") is True:
                    successes += 1
                else:
                    failures += 1
            elif mode == "hubEvents" and receipt.get("success") is True:
                event_log_successes += 1
            elif mode in (None, "") and params.get("since") and params.get("until"):
                generic_attempts += 1
                if receipt.get("success") is True:
                    generic_successes += 1
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
        "app_runtime_stats_attempts": runtime_attempts,
        "app_runtime_stats_successes": runtime_successes,
        "bounded_generic_log_reads": generic_attempts,
        "bounded_generic_log_read_successes": generic_successes,
        "hub_event_log_read_successes": event_log_successes,
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
    app_status = assessment.get("app_specific_logs")
    generic_success = int(assessment.get("bounded_generic_log_read_successes") or 0)
    if app_status == "read_failed":
        rows.append(
            "**App-log coverage:** A targeted past-log query scoped to one app failed."
            + (" A bounded generic log query also succeeded, but its"
               " receipt does not independently verify app-specific"
               " historical coverage." if generic_success else
               " No successful bounded generic fallback was recorded.")
            + " Historical Journal receipt counts are not proof of"
              " reviewed app-log messages."
        )
    elif app_status == "read_succeeded_coverage_unverified":
        rows.append(
            "**App-log coverage:** A targeted past-log query returned successfully,"
            " but its receipt alone does not verify complete historical"
            " app-message coverage."
        )
    elif generic_success:
        rows.append(
            "**App-log coverage:** Bounded generic log query succeeded;"
            " it has not independently established historical app-log"
            " message coverage."
        )
    else:
        rows.append(
            "**App-log coverage:** No successful app-specific historical"
            " message review is verified. Journal receipt counts cannot"
            " substitute for the message source."
        )
    runtime_attempts = int(assessment.get("app_runtime_stats_attempts") or 0)
    if runtime_attempts:
        rows.append(
            "**App runtime statistics:** "
            + str(assessment.get("app_runtime_stats_successes") or 0)
            + "/" + str(runtime_attempts)
            + " query attempts succeeded. The apps tab is runtime statistics,"
              " not historical application log messages; date filters are"
              " unsupported for that mode."
        )
    rows.append(
        "The time between a reboot message and systemStart does not, "
        "by itself, prove an uninterrupted connectivity outage."
    )
    return "\n".join(rows)
