"""Bounded source-only projections for memory statistics and event chronology.

No new reads, model calls, writes, or inference of continuous physical state.
Only original successful read-only receipts are eligible. Original receipts are
never changed. Every output is explicitly scoped to returned source rows.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import math
import re

from investigation_source_ledger import _response
from memory_window_provenance import (
    memory_history_window_index, public_memory_window_scope,
)
from native_device_event_receipt import original_device_event_history

_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _().+&'/-]{0,79}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_SAFE_STATE = {
    "switch": frozenset({"on", "off"}),
    "contact": frozenset({"open", "closed"}),
    "motion": frozenset({"active", "inactive"}),
    "thermostatOperatingState": frozenset({
        "idle", "heating", "cooling", "pending heat", "pending cool",
        "fan only", "vent economizer", "unknown",
    }),
    "lock": frozenset({"locked", "unlocked", "unknown"}),
    "presence": frozenset({"present", "not present"}),
}
_ATTR_ALIASES = {
    "thermostatoperatingstate": "thermostatOperatingState",
    "thermostat operating state": "thermostatOperatingState",
    "operating-state": "thermostatOperatingState",
    "switch": "switch",
    "contact": "contact",
    "motion": "motion",
}
_HOURS_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12,
}


def _utc(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 48:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _number(value: float, places: int = 1) -> str:
    rendered = f"{value:,.{places}f}"
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _duration(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    sign = "-" if millis < 0 else ""
    millis = abs(millis)
    whole_seconds, remainder = divmod(millis, 1000)
    hours, rem = divmod(whole_seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{sign}{hours}h {minutes}m {secs}.{remainder:03d}s"
    if minutes:
        return f"{sign}{minutes}m {secs}.{remainder:03d}s"
    return f"{sign}{secs}.{remainder:03d}s"


def memory_window_statistics_answer(
    question: str, receipts: list[dict], timezone_name: str | None,
) -> dict | None:
    """Return exact sample arithmetic for explicit free-memory comparisons.

    'Latest returned sample' is deliberately not renamed to a live/current
    reading: the memory-history source has no instantaneous read in this path.
    The mean is an arithmetic mean of returned samples, not time-weighted.
    """
    if (not isinstance(question, str)
            or not re.search(r"\bfree\s+memory\b", question, re.I)
            or not re.search(r"\b(?:compare|average|mean|minimum|maximum|range)\b", question, re.I)):
        return None
    history_receipts = [
        row for row in receipts[:24] if isinstance(row, dict)
        and row.get("name") == "hub_get_memory_history"
        and row.get("success") is True
        and row.get("operation_executed") is not False
    ]
    clock_receipts = [
        row for row in receipts[:24] if isinstance(row, dict)
        and row.get("name") == "homebrain_read_clock"
        and row.get("success") is True
    ]
    if len(history_receipts) != 1 or len(clock_receipts) != 1:
        return None
    for row in history_receipts:
        outer, native = _response(row)
        if (not isinstance(outer, dict) or not isinstance(native, dict)
                or outer.get("truncated") is True or native.get("truncated") is True
                or outer.get("response_too_large") is True
                or native.get("response_too_large") is True
                or not isinstance(native.get("entries"), list)):
            return None
    index = memory_history_window_index(question, receipts, timezone_name)
    if not isinstance(index, dict):
        return None
    inside = index.get("_in_window")
    outside = index.get("_out_of_window")
    if not isinstance(inside, list) or not inside:
        return None
    samples = []
    for item in inside:
        if not isinstance(item, dict):
            return None
        stamp, raw = item.get("timestamp"), item.get("freeMemoryKB")
        if not isinstance(stamp, datetime) or type(raw) not in (int, float):
            return None
        if not (0 <= raw < 10**11):
            return None
        samples.append((stamp, float(raw)))
    samples.sort(key=lambda item: item[0])
    values = [value for _, value in samples]
    count = len(values)
    mean = sum(values) / count
    minimum = min(samples, key=lambda item: item[1])
    maximum = max(samples, key=lambda item: item[1])
    latest = samples[-1]
    delta = latest[1] - mean
    start = _utc(index.get("window_start_utc"))
    now = _utc(index.get("client_now_utc"))
    if start is None or now is None:
        return None
    internal_gaps = [
        (later[0] - earlier[0]).total_seconds()
        for earlier, later in zip(samples, samples[1:])
    ]
    first_gap = (samples[0][0] - start).total_seconds()
    last_gap = (now - latest[0]).total_seconds()
    if first_gap < 0 or last_gap < 0:
        return None
    outside_samples = []
    for item in outside if isinstance(outside, list) else []:
        if (isinstance(item, dict) and isinstance(item.get("timestamp"), datetime)
                and type(item.get("freeMemoryKB")) in (int, float)):
            outside_samples.append((item["timestamp"], float(item["freeMemoryKB"])))
    preceding = [item for item in outside_samples if item[0] < start]
    nearest_before = max(preceding, key=lambda item: item[0]) if preceding else None
    future = [item for item in outside_samples if item[0] > now]
    nearest_after = min(future, key=lambda item: item[0]) if future else None

    requested_minutes = index.get("requested_minutes")
    if type(requested_minutes) is not int or requested_minutes < 1:
        return None
    if requested_minutes >= 60 and requested_minutes % 60 == 0:
        window_label = f"{requested_minutes // 60} hour(s)"
    elif requested_minutes >= 60:
        window_label = f"{requested_minutes // 60} hour(s) {requested_minutes % 60} minutes"
    else:
        window_label = f"{requested_minutes} minutes"
    outside_count = index.get("out_of_window_sample_count", 0)
    outside_word = "sample" if outside_count == 1 else "samples"
    lines = [
        "**Source-derived free-memory comparison — returned history samples**",
        f"Client UTC time: `{index['client_now_utc']}`.",
        f"Inclusive {window_label} window: `{index['window_start_utc']}` to "
        f"`{index['client_now_utc']}`.",
        f"The source returned **{count} samples inside** this window and "
        f"**{outside_count} parsed {outside_word} outside** it "
        f"({index.get('total_parsed_original_samples', count)} parsed in total).",
        "| Returned sample (UTC) | Free memory (KB) |",
        "|---|---:|",
    ]
    for stamp, value in samples:
        lines.append(f"| {_stamp(stamp)} | {_number(value, 1)} |")
    if nearest_before:
        lines.append(
            f"Nearest sample before the window: `{_stamp(nearest_before[0])}` — "
            f"{_number(nearest_before[1], 1)} KB (outside the inclusive lower bound)."
        )
        earliest_before = min(preceding, key=lambda item: item[0])
        if earliest_before[0] < nearest_before[0]:
            lines.append(
                f"Earlier outside-window samples span from `{_stamp(earliest_before[0])}` "
                f"through `{_stamp(nearest_before[0])}`."
            )
    if nearest_after:
        lines.append(
            f"Nearest sample after the client time: `{_stamp(nearest_after[0])}` — "
            "outside the requested interval."
        )
    lines.extend([
        "**Statistics for the in-window samples**",
        f"- Arithmetic mean (not time-weighted): **{_number(mean, 1)} KB**.",
        f"- Minimum: **{_number(minimum[1], 1)} KB** at `{_stamp(minimum[0])}`.",
        f"- Maximum: **{_number(maximum[1], 1)} KB** at `{_stamp(maximum[0])}`.",
        f"- Range (maximum − minimum): **{_number(maximum[1] - minimum[1], 1)} KB**.",
        f"- Latest returned sample: **{_number(latest[1], 1)} KB** at "
        f"`{_stamp(latest[0])}` — **{_number(abs(delta), 1)} KB "
        f"{'below' if delta < 0 else 'above' if delta > 0 else 'equal to'} the mean**.",
        "**Unobserved intervals**",
        f"- Lower bound to first in-window sample: {_duration(first_gap)}.",
        f"- Latest in-window sample to client clock: {_duration(last_gap)}.",
        f"- Largest interval between consecutive in-window samples: "
        f"{_duration(max(internal_gaps, default=0))}.",
    ])
    large_gaps = [gap for gap in internal_gaps if gap > 360]
    if large_gaps:
        lines.append(f"- Consecutive-sample intervals longer than six minutes: {len(large_gaps)}.")
    else:
        lines.append("- No interval between consecutive returned in-window samples exceeded six minutes.")
    lines.append(
        "The native history timestamps omit year and timezone; their UTC "
        "interpretation uses the configured hub timezone and client clock. "
        "These are discrete returned samples, not continuous telemetry. The "
        "latest sample is not a live memory read at the client-clock time."
    )
    return {
        "status": "source_derived_statistics",
        "answer": "\n".join(lines),
        "scope": public_memory_window_scope(index),
    }


def _normal(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value).casefold()


def _safe_event_value(attribute: str, value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _SAFE_STATE.get(attribute, frozenset()):
            return text
        if re.fullmatch(r"-?\d{1,8}(?:\.\d{1,4})?", text):
            return text
    elif type(value) in (int, float) and math.isfinite(float(value)) and abs(value) < 10**8:
        return str(value)
    return None


def _event_receipt_candidates(
    question: str, receipts: list[dict], *, attribute: str,
) -> list[tuple[dict, dict, str, str, list[dict]]]:
    found = []
    for receipt in receipts[:40]:
        if (not isinstance(receipt, dict) or receipt.get("success") is not True
                or receipt.get("operation_executed") is False
                or receipt.get("name") != "hub_list_device_events"):
            continue
        args = receipt.get("arguments")
        if not isinstance(args, dict) or args.get("attribute") != attribute:
            continue
        validated = original_device_event_history(receipt)
        if validated is None:
            continue
        device_id, label, events = validated
        if not _SAFE_ID.fullmatch(device_id) or not _SAFE_LABEL.fullmatch(label):
            continue
        if _normal(label) not in _normal(question):
            continue
        outer, native = _response(receipt)
        if (not isinstance(outer, dict) or not isinstance(native, dict)
                or outer.get("truncated") is True or native.get("truncated") is True
                or outer.get("response_too_large") is True
                or native.get("response_too_large") is True):
            continue
        if native.get("count") != len(events) or not events:
            continue
        parsed = []
        valid = True
        for event in events:
            if not isinstance(event, dict) or event.get("name") != attribute:
                valid = False
                break
            stamp = _utc(event.get("date"))
            value = _safe_event_value(attribute, event.get("value"))
            if stamp is None or value is None:
                valid = False
                break
            parsed.append({"time": stamp, "value": value,
                           "is_state_change": event.get("isStateChange")})
        if not valid:
            continue
        parsed.sort(key=lambda row: row["time"])
        found.append((receipt, native, device_id, label, parsed))
    return found


def bounded_newest_two_event_answer(question: str, receipts: list[dict]) -> dict | None:
    """Publish exactly two source-returned samples without inventing trajectory."""
    if (not isinstance(question, str)
            or not re.search(r"\b(?:(?:newest|latest|most recent)\s+two|two\s+(?:newest|latest))\b", question, re.I)
            or not re.search(r"\b(?:samples?|events?)\b", question, re.I)
            or not re.search(r"\belapsed\b", question, re.I)):
        return None
    attribute = None
    lowered = question.lower()
    for alias, native_name in _ATTR_ALIASES.items():
        if alias in lowered:
            attribute = native_name
            break
    if attribute is None:
        return None
    candidates = _event_receipt_candidates(question, receipts, attribute=attribute)
    candidates = [item for item in candidates
                  if item[0].get("arguments", {}).get("limit") == 2
                  and len(item[4]) == 2]
    if len(candidates) != 1:
        return None
    receipt, native, device_id, label, events = candidates[0]
    delta = (events[1]["time"] - events[0]["time"]).total_seconds()
    if delta < 0:
        return None
    outer, _ = _response(receipt)
    headline = outer.get("client_claim_evidence_headline")
    if (not isinstance(headline, dict)
            or headline.get("returned_row_count") != 2
            or headline.get("requested_row_limit") != 2
            or type(headline.get("row_limit_reached")) is not bool):
        return None
    row_limit = headline["row_limit_reached"]
    lines = [
        f"**Two newest returned `{attribute}` samples — {label} (device {device_id})**",
        "| Order | Timestamp (UTC) | Recorded value |",
        "|---|---|---|",
        f"| Older | {_stamp(events[0]['time'])} | {events[0]['value']} |",
        f"| Newer | {_stamp(events[1]['time'])} | {events[1]['value']} |",
        f"**Elapsed time:** {_number(delta, 3)} seconds ({_duration(delta)}).",
        "**What remains unobserved:** The receipt contains only these two "
        "discrete rows; the native request limit was 2. It does not establish "
        "the attribute's trajectory between the timestamps, any unreturned "
        "intermediate event, other attributes, a command issuer, or a cause.",
    ]
    if row_limit is True:
        lines.append("The source metadata also reports that the two-row limit was reached.")
    elif row_limit is False:
        lines.append("The source metadata does not report that its row limit was reached.")
    if all(row["is_state_change"] is True for row in events):
        lines.append("Both rows carry `isStateChange=true`; that flag does not identify the preceding value.")
    return {
        "status": "bounded_newest_two_event_rows",
        "answer": "\n".join(lines),
        "device_id": device_id,
        "attribute": attribute,
        "returned_rows": len(events),
        "row_limit_reached": row_limit if type(row_limit) is bool else None,
        "trajectory_verified": False,
    }


def _requested_hours(question: str) -> int | None:
    match = re.search(
        r"\b(?:last|past|preceding|previous)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+hours?\b",
        question, re.I,
    )
    if not match:
        return None
    raw = match.group(1).lower()
    value = int(raw) if raw.isdigit() else _HOURS_WORDS.get(raw)
    return value if type(value) is int and 1 <= value <= 168 else None


def bounded_contact_event_sequence_answer(question: str, receipts: list[dict]) -> dict | None:
    """Sort returned contact rows chronologically and bound gaps to that list."""
    if (not isinstance(question, str)
            or not re.search(r"\b(?:open|closed)\b", question, re.I)
            or not re.search(r"\b(?:earliest|latest)\b", question, re.I)
            or not re.search(r"\b(?:gaps?|unobserved intervals?)\b", question, re.I)):
        return None
    hours = _requested_hours(question)
    if hours is None:
        return None
    candidates = _event_receipt_candidates(question, receipts, attribute="contact")
    candidates = [item for item in candidates
                  if item[0].get("arguments", {}).get("hoursBack") == hours
                  and item[1].get("hoursBack") == hours]
    if len(candidates) != 1:
        return None
    receipt, native, device_id, label, events = candidates[0]
    outer, _ = _response(receipt)
    headline = outer.get("client_claim_evidence_headline")
    if not isinstance(headline, dict):
        return None
    if (headline.get("returned_row_count") != len(events)
            or headline.get("requested_row_limit") != receipt.get("arguments", {}).get("limit")
            or type(headline.get("row_limit_reached")) is not bool):
        return None
    if not all(row["value"] in ("open", "closed") for row in events):
        return None
    opens = [row for row in events if row["value"] == "open"]
    closes = [row for row in events if row["value"] == "closed"]
    if not opens or not closes:
        return None
    gaps = []
    for earlier, later in zip(events, events[1:]):
        seconds = (later["time"] - earlier["time"]).total_seconds()
        if seconds < 0:
            return None
        if seconds >= 300:
            gaps.append((seconds, earlier, later))
    gaps.sort(key=lambda item: item[0], reverse=True)
    since = _utc(native.get("sinceTimestamp"))
    if since is None or any(row["time"] < since for row in events):
        return None
    limit_reached = headline["row_limit_reached"]
    lines = [
        f"**Contact history — returned rows only: {label} (device {device_id})**",
        f"Requested lookback: {hours} hours; {len(events)} rows returned; "
        + ("source reports the row limit was reached." if limit_reached
           else "source does not report the row limit was reached."),
    ]
    if since is not None:
        lines.append(f"Source-reported query lower bound: `{_stamp(since)}`.")
    lines.extend([
        f"- Latest OPEN report among returned rows: **{_stamp(opens[-1]['time'])}**.",
        f"- Latest CLOSED report among returned rows: **{_stamp(closes[-1]['time'])}**.",
        f"- Earliest returned event: `{_stamp(events[0]['time'])}`.",
        f"- Latest returned event: `{_stamp(events[-1]['time'])}`.",
        "**Largest gaps between adjacent returned rows (threshold: 5 minutes)**",
    ])
    if gaps:
        for seconds, earlier, later in gaps[:5]:
            lines.append(
                f"- {earlier['value'].upper()} report `{_stamp(earlier['time'])}` "
                f"to {later['value'].upper()} report `{_stamp(later['time'])}`: "
                f"{_duration(seconds)}."
            )
    else:
        lines.append("No adjacent returned-row interval was at least five minutes.")
    lines.append(
        "These durations are gaps between returned event rows, not proof that "
        "the contact stayed in either state, that no event/command occurred, "
        "or that the source provides complete historical coverage."
    )
    if headline.get("unseen_rows_or_commands_proven_absent") is False:
        lines.append("The native receipt explicitly does not prove unseen rows or commands absent.")
    return {
        "status": "bounded_contact_event_sequence",
        "answer": "\n".join(lines),
        "device_id": device_id,
        "attribute": "contact",
        "returned_rows": len(events),
        "row_limit_reached": limit_reached,
        "largest_gap_seconds": gaps[0][0] if gaps else None,
        "continuous_state_verified": False,
    }
