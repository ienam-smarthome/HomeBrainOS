"""Generic scope notes for native MCP event-history responses.

Notes describe only RETURNED rows and the request parameters. They never infer
the cause of missing records, a historic device state, or completeness of a
native store. Original MCP results remain intact in the client-side envelope.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _payload(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    content = value.get("content")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict) or not isinstance(part.get("text"), str):
                continue
            try:
                inner = json.loads(part["text"])
            except ValueError:
                continue
            if isinstance(inner, dict) and isinstance(inner.get("events"), list):
                return inner
    return value if isinstance(value.get("events"), list) else None


def _normalized_date(value: str):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def scope_of(result: dict, arguments: dict | None = None) -> dict | None:
    """Derive only observational metadata, never conclusions about cause."""
    if not isinstance(result, dict) or result.get("isError"):
        return None
    source = _payload(result)
    if source is None:
        return None
    rows = source["events"]
    times = [
        (dt, row["date"])
        for row in rows if isinstance(row, dict) and isinstance(row.get("date"), str)
        if (dt := _normalized_date(row["date"])) is not None
    ]
    # Sort actual UTC instants rather than source display strings. The gaps
    # measure spacing BETWEEN RETURNED ROWS, not a sensor's reporting cadence
    # or continuous historical coverage. Mixed-attribute results may contain
    # additional rows that say nothing about a particular attribute.
    ordered_instants = sorted(dt for dt, _ in times)
    observed_gaps = [
        (later - earlier).total_seconds()
        for earlier, later in zip(ordered_instants, ordered_instants[1:])
    ]
    args = arguments if isinstance(arguments, dict) else {}
    leaf = args.get("args") if isinstance(args.get("args"), dict) else args
    limit = leaf.get("limit") if type(leaf.get("limit")) is int else None
    result_scope = {
        "source_scope": "returned event rows only",
        "events_returned": len(rows),
        "oldest_returned_event": min(times)[1] if times else None,
        "newest_returned_event": max(times)[1] if times else None,
        "adjacent_returned_timestamp_pairs": len(observed_gaps),
        "largest_gap_between_returned_events_seconds": (
            round(max(observed_gaps), 3) if observed_gaps else None
        ),
        "can_infer_uninterrupted_state_between_events": False,
        "date_rows_without_parseable_offset": sum(
            1 for row in rows if isinstance(row, dict) and isinstance(row.get("date"), str)
            and _normalized_date(row["date"]) is None
        ),
        "requested_lookback_hours": leaf.get("hoursBack") if type(leaf.get("hoursBack")) is int else None,
        "requested_limit": limit,
        "limit_reached": len(rows) >= limit if limit is not None else None,
        "native_store_checked_independently": False,
        "can_infer_older_events_absent": False,
        "can_infer_requested_window_fully_covered": False,
        "can_infer_cause_of_missing_records": False,
        "note": (
            "The query window, first returned timestamp, count, and limit describe "
            "only the rows that the source returned. They do not establish the "
            "oldest event in the native store, absence of earlier events, or a "
            "retention/truncation/transport cause. Rows are discrete reports, "
            "not continuous measurements: their timestamps and even an "
            "isStateChange flag do not establish uninterrupted intermediate "
            "states or exact unobserved threshold crossings. The largest "
            "reported timestamp gap is not proof of a reporting outage. "
            "Where the distinction matters, seek a discriminating source "
            "or explicitly qualify the unobserved interval."
        ),
    }
    # An upstream-provided truncation flag has distinct meaning from an inferred
    # cap; preserve the source claim without deriving a causal explanation.
    for key in ("truncated", "hasMore", "matchedCount", "timeFilterUnparseable"):
        if key in source and isinstance(source[key], (bool, int)):
            result_scope["upstream_" + key] = source[key]
    return result_scope



def command_issuer_scope(result: dict) -> dict | None:
    """Index only command actors from returned event rows, not their causes.

    Command rows can establish a recorded issuer and chronological sequence.
    They do not, by themselves, identify which internal callback or configured
    condition led that issuer to act. This is source metadata, not a rule about
    what the model must read next.
    """
    if not isinstance(result, dict) or result.get("isError"):
        return None
    source = _payload(result)
    if source is None:
        return None
    returned_commands = 0
    samples = []
    for row in source["events"]:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if row.get("type") != "command" and not (
                isinstance(name, str) and name.startswith("command-")):
            continue
        returned_commands += 1
        if len(samples) >= 12:
            continue
        issuer = row.get("producedBy")
        actor = {}
        if isinstance(issuer, dict):
            for key in ("name", "appId", "deviceId"):
                value = issuer.get(key)
                if isinstance(value, (str, int)) and not isinstance(value, bool):
                    if len(str(value)) <= 120:
                        actor[key] = value
        sample = {"event_name": name[:100] if isinstance(name, str) else None}
        stamp = row.get("date")
        if isinstance(stamp, str) and len(stamp) <= 80:
            sample["timestamp"] = stamp
        if actor:
            sample["reported_command_issuer"] = actor
        samples.append(sample)
    if not returned_commands:
        return None
    return {
        "source_scope": "command rows in this returned event response only",
        "command_rows_returned": returned_commands,
        "command_examples": samples,
        "command_examples_omitted": max(0, returned_commands - len(samples)),
        "issuer_field_alone_proves_internal_trigger": False,
        "note": (
            "The command row's producedBy identifies its recorded issuer, not "
            "the internal decision that caused the issuer to act. A device's "
            "subsequent state report or an event's triggered[] subscribers do "
            "not establish that decision either. If the question asks why "
            "a controller issued a command, consider proportionate available "
            "read-only sources for its configuration, participating inputs "
            "and event-specific execution or callback evidence. Clock-time "
            "coincidence and an app's name cannot uniquely establish a "
            "scheduled cause. This index does not prove missing history, "
            "historical configuration or a global absence of cause evidence; "
            "the model owns source selection and may report unresolved cause."
        ),
    }


def model_result_with_scope(result: dict, arguments: dict | None = None) -> dict:
    """Retain exact original payload under its original keys plus a separate note."""
    info = scope_of(result, arguments)
    commands = command_issuer_scope(result)
    if info is None and commands is None:
        return result
    return {
        **result,
        **({"client_event_source_scope": info} if info is not None else {}),
        **({"client_command_issuer_scope": commands} if commands is not None else {}),
    }
