"""Observed runtime/source evidence for existing-rule verification reports.

An incomplete Rule Machine action-tree projection cannot erase confirmed app
commands, sensor timing, native performance WARNs, or full source retrieval.
Each observation is scoped to requested/typed target app IDs and is carefully
separated from proof of a compiled rule or real-world occupancy.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from occupancy_timing_correlation import correlate_occupancy_off_timing
from observed_long_method_guard import observed_long_method_warnings


def _clock(value: Any) -> datetime | None:
    try:
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return date if date.tzinfo else None
    except (ValueError, TypeError):
        return None


def _gateway_args(row: dict[str, Any]) -> dict[str, Any]:
    args = row.get("arguments") or {}
    for _ in range(3):
        if not isinstance(args, dict):
            return {}
        if not isinstance(args.get("args"), dict):
            break
        args = args["args"]
    return args if isinstance(args, dict) else {}


def observed_rule_runtime(
    evidence: list[dict[str, Any]],
    scoped_app_ids: set[str],
) -> tuple[list[str], bool]:
    """Report real commands before denying their existence.

    A device bridge event may be attributed to an app only when a preceding
    device command has a typed app producer. A switch event's triggered
    listeners are *not* command producers.
    """
    if not scoped_app_ids:
        return [], False
    lines: list[str] = []
    pair_records: dict[tuple[str, str, str], tuple[datetime, float, str]] = {}
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("tool") != "homebrain_device_history":
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict) or details.get("attribute") != "switch":
            continue
        label = str(details.get("label") or "Device")[:100]
        events = details.get("boundaryEvents") or []
        if not isinstance(events, list):
            continue
        off_states = [
            _clock(event.get("date")) for event in events
            if isinstance(event, dict)
            and event.get("name") == "switch"
            and event.get("value") == "off"
            and _clock(event.get("date"))
        ]
        for event in events:
            if not isinstance(event, dict) or event.get("name") != "command-off":
                continue
            when = _clock(event.get("date"))
            producer = event.get("producedBy") or {}
            if (not when or not isinstance(producer, dict)
                    or producer.get("type") != "app"):
                continue
            app = str(producer.get("id") or "")
            if app not in scoped_app_ids:
                continue
            matched = [
                (date - when).total_seconds() for date in off_states
                if 0 <= (date - when).total_seconds() <= 3
            ]
            if not matched:
                continue
            pair_records[(app, label, when.isoformat())] = (
                when, min(matched), label
            )
    for (app, _, _), (issued, delay, device) in sorted(
        pair_records.items(), key=lambda x: x[1][0]
    )[-4:]:
        lines.append(
            f"- App {app} issued OFF for {device} at "
            f"{issued:%H:%M:%S.%f}"[:-3]
            + f" (timestamp timezone from source); device reported OFF "
            f"{delay:.3f}s later (typed command/state event pair)."
        )
    timing = [
        item for item in correlate_occupancy_off_timing(evidence)
        if item["appId"] in scoped_app_ids
    ]
    for row in timing[-4:]:
        when = _clock(row["inactiveAt"])
        lines.append(
            f"- {row['lastObservedInactiveSensor']} reported inactive at "
            f"{when:%H:%M:%S.%f}"[:-3]
            + f"; App {row['appId']} issued OFF "
            f"{row['inactiveToCommandSeconds']:.3f}s later. "
            "The sensor event lists that app as a listener; this is "
            "bounded temporal evidence, not proof that the physical room "
            "was empty or that the entire timer implementation is verified."
        )
    return lines, bool(pair_records)


def observed_rule_warnings(
    evidence: list[dict[str, Any]],
    scoped_app_ids: set[str],
) -> list[str]:
    observations = observed_long_method_warnings(evidence)
    lines: list[str] = []
    for app in sorted(scoped_app_ids):
        value = observations.get(app)
        if value is None:
            continue
        durations = [x for x in value.get("durations_ms", []) if type(x) is int]
        if not durations:
            continue
        methods = ", ".join(value.get("methods") or ()) or "unknown method"
        timestamps = value.get("timestamps") or []
        stamp = f" at {max(timestamps)} (log timezone unverified)" if timestamps else ""
        lines.append(
            f"- App {app} native WARN/ERROR: {methods} ran for "
            f"{max(durations):,}ms ({max(durations)/1000:.3f}s)"
            f"{stamp}. This is a recorded long-running handler, "
            "not independent proof of which lighting timer or occupancy "
            "event it affected."
        )
    return lines


def observed_complete_source(
    evidence: list[dict[str, Any]],
    scoped_app_ids: set[str],
) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for row in evidence:
        if (not isinstance(row, dict) or row.get("success") is not True
                or row.get("tool") != "homebrain_read_groovy_source"):
            continue
        app = str(_gateway_args(row).get("appId") or "")
        if app not in scoped_app_ids or app in seen:
            continue
        details = row.get("details") or {}
        if not isinstance(details, dict):
            continue
        if not (details.get("sourceRetrieved") is True
                and details.get("fullImplementationVerified") is True):
            continue
        length = details.get("verifiedCharacters")
        declared = details.get("declaredTotalCharacters")
        source_id = str(details.get("sourceCodeId") or "")
        if (type(length) is not int or type(declared) is not int
                or length <= 0 or length != declared
                or not source_id.isdigit()):
            continue
        seen.add(app)
        lines.append(
            f"- App {app} installed Groovy code {source_id}: all "
            f"{length:,} characters were retrieved in this investigation. "
            "Complete source retrieval does not independently validate "
            "which configured branches executed at runtime."
        )
    return lines


__all__ = [
    "observed_rule_runtime", "observed_rule_warnings",
    "observed_complete_source",
]
