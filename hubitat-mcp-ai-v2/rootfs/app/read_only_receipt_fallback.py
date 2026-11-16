"""Bounded source-only partial answer for failed/empty read-only model completion.

This is NOT an investigation planner, source selector, causal inference engine or
a replacement for a successful model response. It ONLY preserves already
received original native read-only device event observations when the connected
model did not return usable prose. No writes, tool calls or additional AI rounds.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from investigation_source_ledger import _SAFE_FIELD
from native_device_event_receipt import original_device_event_history
from native_command_provenance import original_command_rows

_MAX_RECEIPTS = 40
_MAX_EVENTS_PER_RECEIPT = 300
_MAX_DEVICES = 3
_MAX_EVENT_FIELDS = 3
_MAX_SAMPLES = 4
_MAX_NAME = 60
_MAX_VALUE = 28
_SAFE_LABEL = re.compile(r"[^\w\s().,\-\u00b0%/]+", re.UNICODE)
_SAFE_VALUE = re.compile(r"^[\w .,%+\-\u00b0/%]+$", re.UNICODE)
_SAFE_NUMERIC = re.compile(r"^-?(?:\d{1,9})(?:\.\d{1,6})?$")
_NUMERIC_FIELDS = frozenset({"temperature", "level", "heatingSetpoint", "power"})
_STATE_VALUES = {
    "switch": frozenset({"on", "off"}),
    "thermostatOperatingState": frozenset({
        "idle", "heating", "cooling", "pending heat", "pending cool",
        "fan only", "vent economizer", "unknown",
    }),
    "thermostatMode": frozenset({
        "off", "heat", "cool", "auto", "emergency heat", "eco", "dry", "fan only",
    }),
    "motion": frozenset({"active", "inactive"}),
    "contact": frozenset({"open", "closed"}),
    "lock": frozenset({"locked", "unlocked", "unknown"}),
    "presence": frozenset({"present", "not present"}),
    "water": frozenset({"wet", "dry"}),
    "valve": frozenset({"open", "closed", "opening", "closing", "on", "off"}),
    "fanSpeed": frozenset({"off", "low", "medium", "high", "on", "auto"}),
    "speed": frozenset({"off", "low", "medium", "high", "on", "auto"}),
}
# Generic output/observation fields: NONE is evidence of native physical action.
_STATE_FIELDS = frozenset({
    "thermostatOperatingState", "switch", "motion", "contact", "lock",
    "presence", "water", "valve", "fanSpeed", "speed", "power",
    "temperature", "level", "heatingSetpoint", "thermostatMode",
})


def _safe_name(value: object, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    name = _SAFE_LABEL.sub("", value.strip().replace("\n", " "))
    return name[:_MAX_NAME] or fallback


def _safe_value(value: object) -> str | None:
    if type(value) not in (str, int, float):
        return None
    rendered = str(value).strip()
    return rendered if (0 < len(rendered) <= _MAX_VALUE
                        and _SAFE_VALUE.fullmatch(rendered)) else None


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 48:
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return instant if instant.tzinfo is not None and instant.utcoffset() is not None else None


def _friendly_time(instant: datetime, tz: ZoneInfo) -> str:
    local = instant.astimezone(tz)
    hr = str(local.hour % 12 or 12)
    return (f"{local.strftime('%A')} {local.day} {local.strftime('%B %Y')}"
            f" at {hr}:{local:%M:%S} {'am' if local.hour < 12 else 'pm'} "
            f"{local.tzname() or 'UTC'}")


def source_only_partial_answer(
    question: str, receipts: list[dict], *, timezone_name: str | None = None
) -> str | None:
    """Use only parseable successful original device-state history receipts.

    Returns None if no such evidence exists. Cannot infer what the user's
    'actual' focal actuator is, classify a cause, or deny unseen events.
    """
    if not isinstance(question, str) or not question.strip():
        return None
    try:
        zone = ZoneInfo(timezone_name or "Europe/London")
    except (ZoneInfoNotFoundError, KeyError, ValueError):
        zone = ZoneInfo("UTC")
    command_rows, any_page_at_limit = original_command_rows(receipts)
    records: dict[tuple[str, str], dict] = {}
    for receipt in receipts[:_MAX_RECEIPTS]:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("name") != "hub_list_device_events":
            continue
        args = receipt.get("arguments")
        if not isinstance(args, dict):
            continue
        validated = original_device_event_history(receipt)
        if validated is None:
            continue
        device_id, native_label, events = validated
        label = _safe_name(native_label, f"Device {device_id}")
        attribute = args.get("attribute")
        for event in events[:_MAX_EVENTS_PER_RECEIPT]:
            if not isinstance(event, dict) or event.get("type") == "command":
                continue
            field = event.get("name")
            if (not isinstance(field, str) or not _SAFE_FIELD.fullmatch(field)
                    or field not in _STATE_FIELDS or field.startswith("command-")):
                continue
            if isinstance(attribute, str) and attribute and field != attribute:
                continue
            value = _safe_value(event.get("value"))
            stamp = _timestamp(event.get("date"))
            if value is None or stamp is None:
                continue
            # Even a successful native response is untrusted data. Natural
            # language in a state value is not a valid reported device state.
            if field in _NUMERIC_FIELDS:
                if not _SAFE_NUMERIC.fullmatch(value):
                    continue
            elif value.lower() not in _STATE_VALUES.get(field, frozenset()):
                continue
            key = (device_id, field)
            bucket = records.setdefault(key, {
                "name": label, "device_id": device_id, "field": field,
                "rows": {}, "request_filters": set(),
            })
            bucket["request_filters"].add(
                str(args.get("hoursBack") or "unspecified")[:20]
            )
            # Do not count duplicates from overlapping broad/focused reads.
            bucket["rows"][(stamp.isoformat(), value)] = stamp

    if not records and not command_rows:
        return None

    # Prioritise sources showing DIFFERENT reported values, but do not assume
    # any device is the focal output or any event is the physical transition.
    candidates = []
    for bucket in records.values():
        values = {key[1] for key in bucket["rows"]}
        ordered = sorted(bucket["rows"].items(), key=lambda kv: kv[1])
        if not ordered:
            continue
        candidates.append((len(values) > 1, ordered[-1][1], bucket, ordered))
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)

    lines = [
        "**Investigation incomplete — source-only partial result.** "
        "A reliable complete causal explanation could not be published. The following "
        "are original recorded command rows and reported states from this "
        "request's successful read-only MCP histories. They do not establish "
        "a controller's internal trigger or an independent physical effect.",
    ]
    if command_rows:
        lines.append(
            "**Recorded command issuers from the returned native device histories:** "
            "These app issuers are native command-row producers, not proof of "
            "the initiating sensor/button condition, internal app decision, "
            "command delivery or physical effect."
        )
        for row in command_rows:
            app_id = row["issuer_app_id"]
            issuer = (
                f"recorded issuer **{row['issuer_label']}** (app ID {app_id})"
                if app_id is not None else
                "issuer not established from this command row"
            )
            lines.append(
                f"- **{row['device_label']}** (ID {row['device_id']}), "
                f"`{row['command_name']}` at "
                f"{_friendly_time(row['timestamp'], zone)}; {issuer}."
            )
    if records:
        lines.append("**Returned device state reports:**")
    chosen_devices = set()
    chosen_fields = 0
    for varied, _, bucket, ordered in candidates:
        if len(chosen_devices) >= _MAX_DEVICES and bucket["device_id"] not in chosen_devices:
            continue
        if chosen_fields >= _MAX_EVENT_FIELDS:
            break
        chosen_devices.add(bucket["device_id"])
        chosen_fields += 1
        # Preserve a bounded transition-like context from original rows:
        # include latest two different values (if present), then latest rows.
        selected = []
        for pair, dt in reversed(ordered):
            if not selected or pair[1] != selected[-1][0][1]:
                selected.append((pair, dt))
            if len(selected) >= _MAX_SAMPLES:
                break
        selected.reverse()
        if len(selected) < 2 and len(ordered) > 1:
            selected = ordered[-2:]
        states = "; ".join(
            f"{entry[0][1]} at {_friendly_time(entry[1], zone)}"
            for entry in selected
        )
        lines.append(
            f"- **{bucket['name']}** (ID {bucket['device_id']}), "
            f"`{bucket['field']}`: {states}."
        )
    lines.append(
        "These are bounded returned rows, not exhaustive or continuous history. "
        "**This partial state-event summary does not independently establish the "
        "initiating command, controller decision or physical outcome; these remain "
        "unverified within this partial state-only summary.** Separate original command "
        "and application-log receipts, if any, remain available for review. "
        "The original tool receipts and any source errors remain in Technical JSON."
    )
    return "\n\n".join([lines[0], "\n".join(lines[1:])])
