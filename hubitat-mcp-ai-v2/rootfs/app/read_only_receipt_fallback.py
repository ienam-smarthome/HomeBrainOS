"""Bounded source-only partial answer for failed/empty read-only model completion.

This is NOT an investigation planner, source selector, causal inference engine or
a replacement for a successful model response. It ONLY preserves already
received original native read-only device event observations when the connected
model did not return usable prose. No writes, tool calls or additional AI rounds.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from investigation_source_ledger import _SAFE_FIELD, _SAFE_ID, _response
from native_device_event_receipt import original_device_event_history
from native_command_provenance import original_command_rows
from receipt_grounding_anchors import receipt_grounding_anchors

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
_SAFE_APP_ID = re.compile(r"[0-9]{1,9}\Z")
_LOG_SECRET = re.compile(
    r"(?i)(?:https?://|www\.|@|\b(?:token|password|secret|bearer|"
    r"credential|api[_-]?key|private[_-]?key)\b)"
)
_LOG_INSTRUCTION = re.compile(
    r"(?i)\b(?:ignore\s+(?:all\s+)?previous|system\s+prompt|"
    r"developer\s+message|assistant\s+instructions|"
    r"do\s+not\s+follow\s+instructions)\b"
)
_MAX_LOG_SCANNED_RECEIPTS = 40
_MAX_LOG_ROWS_PER_RECEIPT = 150
_MAX_LOG_PER_EVENT = 4
_MAX_LOG_EXCERPTS = 8
_MAX_LOG_MESSAGE_CHARACTERS = 500

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
    "healthStatus": frozenset({"online", "offline", "unknown", "unavailable"}),
    "water": frozenset({"wet", "dry"}),
    "valve": frozenset({"open", "closed", "opening", "closing", "on", "off"}),
    "fanSpeed": frozenset({"off", "low", "medium", "high", "on", "auto"}),
    "speed": frozenset({"off", "low", "medium", "high", "on", "auto"}),
}
# Generic output/observation fields: NONE is evidence of native physical action.
_STATE_FIELDS = frozenset({
    "thermostatOperatingState", "switch", "motion", "contact", "lock",
    "presence", "water", "valve", "fanSpeed", "speed", "power",
    "temperature", "level", "heatingSetpoint", "thermostatMode", "healthStatus",
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



def _safe_execution_log_message(raw: object, app_id: str) -> str | None:
    """Source-bound short excerpt from an app-scoped native past-log entry.

    A prefix of app|id|label|body must match the original requested app ID.
    The text remains untrusted; neither code nor credential-like content is
    eligible for the fallback. No log's claim is treated as executed action.
    """
    if not isinstance(raw, str) or len(raw) > 2000 or "\n" in raw or "\r" in raw:
        return None
    fields = raw.split("|", 3)
    if len(fields) != 4 or fields[0] != "app" or fields[1] != app_id:
        return None
    body = fields[3].strip()
    if (not body or _LOG_SECRET.search(body) or _LOG_INSTRUCTION.search(body)
            or any(char in body for char in ("<", chr(96), "{", "}", "\\"))):
        return None
    if ">" in body.replace("=>", ""):
        return None
    body = body.replace("=>", "→")
    # Disallow markdown/html metacharacters and multiline log injections.
    body = re.sub(r"[^\w \t.,:;()/=+\-°%\[\]!?&→]", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    if not body:
        return None
    if len(body) > _MAX_LOG_MESSAGE_CHARACTERS:
        body = body[:_MAX_LOG_MESSAGE_CHARACTERS].rstrip() + "…"
    return body.replace("[", r"\[").replace("]", r"\]")


def _original_nearby_past_app_logs(
    receipts: list[dict], anchors: list[datetime], zone: ZoneInfo,
) -> list[str]:
    """Display only bounded, identity-scoped source log observations.

    Proximity to a device-reported state never proves command issuance,
    internal controller decision, or independent physical operation.
    """
    if not anchors:
        return []
    rows: list[tuple[datetime, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for receipt in receipts[:_MAX_LOG_SCANNED_RECEIPTS]:
        if (not isinstance(receipt, dict) or receipt.get("success") is not True
                or receipt.get("name") != "hub_get_logs"):
            continue
        args = receipt.get("arguments")
        if not isinstance(args, dict) or args.get("mode") != "past":
            continue
        ident = args.get("appId")
        if type(ident) is int:
            ident = str(ident)
        if not isinstance(ident, str) or not _SAFE_APP_ID.fullmatch(ident):
            continue
        since = _timestamp(args.get("since"))
        until = _timestamp(args.get("until"))
        if (since is None or until is None or since > until
                or until - since > timedelta(days=2)):
            continue
        _, native = _response(receipt)
        if (not isinstance(native, dict) or native.get("mode") != "past"
                or not isinstance(native.get("entries"), list)):
            continue
        for entry in native["entries"][:_MAX_LOG_ROWS_PER_RECEIPT]:
            if not isinstance(entry, dict) or entry.get("type") != "app":
                continue
            message = _safe_execution_log_message(entry.get("message"), ident)
            if message is None:
                continue
            clock = entry.get("time")
            if not isinstance(clock, str) or len(clock) > 48:
                continue
            try:
                instant = datetime.fromisoformat(clock.replace("Z", "+00:00"))
            except ValueError:
                continue
            # Native log clock lacks an explicit offset in common envelopes.
            # Use configured hub timezone as an interpretation, not as
            # independent proof of wall-clock synchronization.
            if instant.tzinfo is None:
                instant = instant.replace(tzinfo=zone)
            if not since <= instant <= until:
                continue
            key = (ident, instant.isoformat(), message)
            if key not in seen:
                seen.add(key)
                rows.append((instant, ident, message))
    chosen: dict[tuple[str, str, str], tuple[datetime, str, str]] = {}
    for anchor in anchors[:2]:
        nearby = sorted(
            (item for item in rows
             if abs((item[0] - anchor).total_seconds()) <= 180),
            key=lambda item: (abs((item[0] - anchor).total_seconds()), item[0]),
        )
        for instant, ident, message in nearby[:_MAX_LOG_PER_EVENT]:
            chosen[(ident, instant.isoformat(), message)] = (
                instant, ident, message
            )
    ordered = sorted(chosen.values(), key=lambda item: item[0])
    return [
        f"- App {ident} past-log entry at "
        f"{instant.astimezone(zone):%Y-%m-%d %H:%M:%S} (configured hub time): "
        f"“{message}”"
        for instant, ident, message in ordered[:_MAX_LOG_EXCERPTS]
    ]


def _inventory_activity(receipts: list[dict], device_ids: set[str]) -> dict[str, datetime]:
    """Return retrieval-time inventory fields for the same native device IDs."""
    reported = {}
    if not device_ids:
        return reported
    for receipt in receipts[:_MAX_RECEIPTS]:
        if (not isinstance(receipt, dict) or receipt.get("success") is not True
                or receipt.get("operation_executed") is False
                or receipt.get("name") != "hub_list_devices"):
            continue
        envelope, data = _response(receipt)
        if (not isinstance(envelope, dict) or not isinstance(data, dict)
                or envelope.get("isError") is True or data.get("isError") is True
                or envelope.get("truncated") is True or data.get("truncated") is True
                or data.get("response_too_large") is True):
            continue
        devices = data.get("devices")
        if not isinstance(devices, list):
            continue
        for device in devices[:700]:
            if not isinstance(device, dict):
                continue
            value = device.get("id")
            device_id = str(value) if type(value) in (str, int) else ""
            if device_id not in device_ids or not _SAFE_ID.fullmatch(device_id):
                continue
            stamp = _timestamp(device.get("lastActivity"))
            if stamp is not None:
                reported[device_id] = stamp
    return reported


def source_only_partial_answer(
    question: str, receipts: list[dict], *, timezone_name: str | None = None,
    lead_with_latest_heating: bool = False,
) -> str | None:
    """Use only parsed, source-bound original device states and command rows.

    Returns None when no validated event facts exist. This does NOT infer a
    focal output, controller decision, initiating trigger or physical cause.
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
            producer = event.get("producedBy")
            if isinstance(producer, dict):
                source_id = producer.get("deviceId")
                reporter_name = producer.get("name")
                # Only a device producer can be a state reporter here.
                # A source app ID or notified triggered[] listener is not
                # a bridge/physical reporter and cannot be promoted to one.
                if (type(source_id) in (str, int) and isinstance(reporter_name, str)
                        and reporter_name.strip() and producer.get("appId") is None):
                    bucket.setdefault("reporters", {})[(stamp.isoformat(), value)] = (
                        _safe_name(reporter_name, "Unlabelled device")
                    )

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
    if lead_with_latest_heating:
        latest_heating = []
        for _, _, bucket, ordered in candidates:
            if bucket["field"] != "thermostatOperatingState":
                continue
            latest = next(
                (entry for entry in reversed(ordered)
                 if entry[0][1].lower() == "heating"),
                None,
            )
            if latest is not None:
                latest_heating.append((latest, bucket))
        if latest_heating:
            latest_heating.sort(key=lambda item: item[0][1], reverse=True)
            lines.append("**Latest heating reports in the returned history, by device**")
            for (key, stamp), bucket in latest_heating[:_MAX_DEVICES]:
                reporter = bucket.get("reporters", {}).get(key)
                attribution = f" (reported by {reporter})" if reporter else ""
                lines.append(
                    f"- **{bucket['name']}** (ID {bucket['device_id']}) "
                    f"reported state `heating` at {_friendly_time(stamp, zone)}"
                    f"{attribution}."
                )
            lines.append(
                "These are individual device state reports. The room that "
                "requested heat and physical boiler operation remain unverified."
            )
    health = [candidate for candidate in candidates if candidate[2]["field"] == "healthStatus"]
    activity = _inventory_activity(receipts, {
        candidate[2]["device_id"] for candidate in health[:_MAX_DEVICES]
    })
    if health:
        lines.append("**Reported activity and health timestamps**")
        for _, _, bucket, ordered in health[:_MAX_DEVICES]:
            (_, status), stamp = ordered[-1]
            device_id = bucket["device_id"]
            observed = activity.get(device_id)
            snapshot = (
                f"; inventory `lastActivity` {_friendly_time(observed, zone)}"
                if observed is not None else ""
            )
            lines.append(
                f"- **{bucket['name']}** (ID {device_id}): latest returned "
                f"`healthStatus` {status} at {_friendly_time(stamp, zone)}{snapshot}."
            )
        lines.append(
            "The inventory timestamp and the health report describe different "
            "source fields. Neither identifies the operation that updated the "
            "activity timestamp or independently verifies device reachability."
        )
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
    if any(bucket["field"] != "healthStatus" for bucket in records.values()):
        lines.append("**Returned device state reports:**")
    chosen_devices = set()
    chosen_fields = 0
    state_time_anchors: list[datetime] = []
    for varied, _, bucket, ordered in candidates:
        if bucket["field"] == "healthStatus":
            continue
        if len(chosen_devices) >= _MAX_DEVICES and bucket["device_id"] not in chosen_devices:
            continue
        if chosen_fields >= _MAX_EVENT_FIELDS:
            break
        chosen_devices.add(bucket["device_id"])
        chosen_fields += 1
        if not state_time_anchors and len({key[1] for key in bucket["rows"]}) > 1:
            most_recent = ordered[-1]
            preceding = next(
                (item for item in reversed(ordered[:-1])
                 if item[0][1] != most_recent[0][1]),
                None,
            )
            if preceding is not None:
                state_time_anchors = [most_recent[1], preceding[1]]
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
            + (f" (reported by {bucket['reporters'][entry[0]]})"
               if entry[0] in bucket.get("reporters", {}) else "")
            for entry in selected
        )
        lines.append(
            f"- **{bucket['name']}** (ID {bucket['device_id']}), "
            f"`{bucket['field']}`: {states}."
        )
    # Tie notified apps to the specific returned report. A command elsewhere
    # in the same history does not give these listeners an initiating role.
    listener_lines = []
    seen_listener_events = set()
    for receipt in receipt_grounding_anchors(receipts, zone.key):
        for event in receipt.get("events", []):
            key = (event["device_id"], event["field"], event["utc_timestamp"])
            notified = event.get("notified_app_ids")
            if (not notified or key in seen_listener_events
                    or event["device_id"] not in chosen_devices):
                continue
            seen_listener_events.add(key)
            listener_lines.append(
                f"- Device {event['device_id']}, `{event['field']}` at "
                f"{event['hub_display_time']} — notified app IDs {', '.join(notified)}."
            )
    if listener_lines:
        lines.append("**Notified apps on selected state reports**")
        lines.extend(listener_lines[:_MAX_DEVICES])
    log_excerpts = _original_nearby_past_app_logs(
        receipts, state_time_anchors, zone
    )
    if log_excerpts:
        lines.append(
            "**Original event-time application-log excerpts:** The following "
            "were returned by bounded app-scoped past-log queries near the "
            "reported device state times. The native log clock is interpreted "
            "using the configured hub timezone. They record what the "
            "application logged, **not independent verification of the "
            "initiating command, execution effect, exclusive cause or physical "
            "outcome**. Source scope may be incomplete."
        )
        lines.extend(log_excerpts)
    if command_rows:
        lines.append(
            "These are bounded returned rows, not exhaustive or continuous history. "
            "**A recorded command issuer is not proof of the "
            "initiating command, upstream trigger, internal controller decision or physical "
            "outcome. A later state report shows only what the device reported; "
            "chronological proximity does not prove exclusive causation.** "
            "Relevant app execution logs and input histories may still be "
            "unread. The original tool receipts and any source errors remain "
            "in Technical JSON."
        )
    else:
        lines.append(
            "These are bounded returned rows, not exhaustive or continuous history. "
            "**This partial state-event summary does not independently establish the "
            "initiating command, controller decision or physical outcome; these remain "
            "unverified within this partial state-only summary.** Separate original command "
            "and application-log receipts, if any, remain available for review. "
            "The original tool receipts and any source errors remain in Technical JSON."
        )
    if any_page_at_limit:
        lines.append(
            "At least one native event-history page reached its requested "
            "row limit. Earlier unreturned events and overall retention "
            "coverage remain unknown."
        )
    return "\n\n".join([lines[0], "\n".join(lines[1:])])
