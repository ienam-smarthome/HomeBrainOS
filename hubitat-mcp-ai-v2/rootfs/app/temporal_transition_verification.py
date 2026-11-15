"""Bounded typed source verification of latest state-transition questions.

Output-only: no tool selection, new reads, writes or model round. A state
reported by ANOTHER device is never the requested device's transition.
Truncated original native MCP responses never prove missing events absent.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json
import re
from temporal_receipt_fidelity import _native_payload

_REQUEST = re.compile(
    r"\bwhen\s+(?:did|was)\s+(?:the\s+)?"
    r"(?P<target>[A-Za-z0-9][A-Za-z0-9 '_()./-]{1,90}?)\s+"
    r"(?:last|most\s+recently)\s+"
    r"(?:change|changed|transition|transitioned|go|move|switch|switched)\s+"
    r"from\s+(?P<before>heating|idle|cooling|on|off|active|inactive|open|closed)"
    r"\s+to\s+(?P<after>heating|idle|cooling|on|off|active|inactive|open|closed)\b",
    re.I,
)
_FIELDS = {
    frozenset(("heating", "idle")): "thermostatOperatingState",
    frozenset(("heating", "cooling")): "thermostatOperatingState",
    frozenset(("idle", "cooling")): "thermostatOperatingState",
    frozenset(("on", "off")): "switch",
    frozenset(("active", "inactive")): "motion",
    frozenset(("open", "closed")): "contact",
}
_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ()._'/&-]{0,90}$")
_PRIVATE = re.compile(r"passw|secret|token|auth|credential|api.key|pin.code", re.I)
# Only source-visible scalar telemetry relevant to a device's operation is
# eligible for supplementary context. Never replay arbitrary event values.
_CONTEXT_FIELDS = frozenset((
    "temperature", "heatingSetpoint", "coolingSetpoint", "thermostatMode",
    "valveLevel", "humidity", "power", "battery",
))
_NUMBER = re.compile(r"^-?\d{1,6}(?:\.\d{1,4})?$")
_MODE_VALUES = frozenset(("heat", "cool", "auto", "off", "emergency heat"))
_RELATIVE_HOURS = re.compile(
    r"\b(?:in\s+the\s+|for\s+the\s+)?(?:last|past|previous)\s+"
    r"(\d{1,3})\s*hours?\b", re.I,
)


def _normal(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value).casefold()


def _date(value):
    if not isinstance(value, str) or len(value) > 48:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else None


def _friendly_time(value, timezone_name=None):
    """Human-facing wall time, never a new source timestamp or clock read.

    The original ISO timestamp stays in the source index and Technical JSON.
    Only an explicit configured IANA zone is used for conversion; otherwise
    display UTC rather than silently assuming the reader's locality.
    """
    instant = _date(value)
    if instant is None:
        return None
    zone = timezone.utc
    if isinstance(timezone_name, str) and timezone_name.strip():
        try:
            zone = ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            pass
    local = instant.astimezone(zone)
    hour = local.hour % 12 or 12
    period = "am" if local.hour < 12 else "pm"
    label = local.tzname() or "UTC"
    return (f"{local:%A} {local.day} {local:%B} {local.year} "
            f"at {hour}:{local.minute:02d} {period} {label}")


def _safe(value, fallback=""):
    if isinstance(value, str) and _SAFE.fullmatch(value) and not _PRIVATE.search(value):
        return value
    return fallback


def _intent(question):
    if not isinstance(question, str):
        return None
    m = _REQUEST.search(question[:12000])
    if not m or m["before"].lower() == m["after"].lower():
        return None
    before, after = m["before"].lower(), m["after"].lower()
    field = _FIELDS.get(frozenset((before, after)))
    name = _safe(m["target"].strip())
    if not field or not name:
        return None
    return {"target": name, "field": field, "before": before, "after": after}


def _outer(receipt):
    try:
        obj = json.loads(receipt.get("response", ""))
    except (TypeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _target_ids(receipts, target):
    ids = set()
    for row in receipts[:24]:
        if not isinstance(row, dict) or row.get("success") is not True or row.get("name") not in ("hub_list_devices", "hub_get_device"):
            continue
        doc = _native_payload(row)
        if not isinstance(doc, dict):
            continue
        items = doc.get("devices") if row["name"] == "hub_list_devices" else [doc]
        if not isinstance(items, list):
            continue
        for d in items[:100]:
            if (isinstance(d, dict) and isinstance(d.get("label"), str)
                    and _normal(d["label"]) == _normal(target)
                    and type(d.get("id")) in (str, int)
                    and str(d["id"]).strip()
                    and d.get("disabled") is not True):
                ids.add(str(d["id"]).strip())
    return ids


def _observation(row, receipt_number):
    stamp = row.get("date")
    parsed = _date(stamp)
    name = row.get("name")
    if not parsed or not isinstance(name, str) or len(name) > 70 or _PRIVATE.search(name):
        return None
    value = row.get("value")
    allowed = {"heating", "idle", "cooling", "on", "off", "active",
               "inactive", "open", "closed", "pending heat", "pending cool"}
    normalized = value.strip().lower() if isinstance(value, str) and value.strip().lower() in allowed else None
    is_command = name.startswith("command-")
    # Preserve a few positive, timestamped operational observations without
    # treating them as a transition or letting arbitrary native text enter the
    # published answer. Scalar units remain as originally reported.
    if normalized is None and (name in _CONTEXT_FIELDS or is_command):
        if isinstance(value, str) and _NUMBER.fullmatch(value.strip()):
            normalized = value.strip()
        elif type(value) in (int, float) and str(value) != "nan" and _NUMBER.fullmatch(str(value)):
            normalized = str(value)
        elif name == "thermostatMode" and isinstance(value, str) and value.strip().lower() in _MODE_VALUES:
            normalized = value.strip().lower()
    if normalized is None and not is_command:
        return None
    producer = row.get("producedBy")
    reported_actor = _safe(producer.get("name")) if isinstance(producer, dict) else ""
    return {"time": parsed, "timestamp": stamp, "name": name,
            "value": normalized, "issuer": reported_actor if is_command else "",
            "reporter": reported_actor if not is_command else "",
            "receipt": receipt_number, "command": is_command}


def temporal_transition_evidence(question, receipts):
    """Evidence navigation: positive observed rows, not historical coverage."""
    req = _intent(question)
    if req is None:
        return {"status": "not_applicable"}
    result = {
        "status": "unverified_focal_transition", "requested": req,
        "target_id": None, "focal_report_count": 0,
        "focal_first": None, "focal_latest": None, "focal_pair": None,
        "focal_later_report": None, "focal_inventory_state": None,
        "focal_context": [], "focal_commands": [],
        "focal_truncated_reads": 0, "focal_limit_reached_reads": 0,
        "peer_reports": [],
        "requested_window_start": None,
        "requested_window_end": None,
        "requested_window_verified_from_source": False,
        "scope_note": "Only inspectable original returned event rows; not complete history, physical transitions or causal proof",
    }
    if not isinstance(receipts, list):
        return result
    matches = _target_ids(receipts, req["target"])
    if len(matches) != 1:
        result["status"] = "target_not_uniquely_verified"
        return result
    focal_id = next(iter(matches))
    result["target_id"] = focal_id
    # A source-scoped inventory snapshot is useful context, not an event at
    # the requested time or independent physical confirmation.
    for receipt in receipts[:24]:
        if (not isinstance(receipt, dict)
                or receipt.get("success") is not True
                or receipt.get("name") not in ("hub_list_devices", "hub_get_device")):
            continue
        doc = _native_payload(receipt)
        if not isinstance(doc, dict):
            continue
        items = doc.get("devices") if receipt["name"] == "hub_list_devices" else [doc]
        if not isinstance(items, list):
            continue
        for device in items[:100]:
            if (not isinstance(device, dict)
                    or str(device.get("id", "")).strip() != focal_id
                    or _normal(str(device.get("label", ""))) != _normal(req["target"])):
                continue
            current = device.get("currentStates")
            if not isinstance(current, dict):
                continue
            state = current.get(req["field"])
            if not isinstance(state, str) or state.strip().lower() not in (
                "on", "off", "heating", "idle", "cooling", "active",
                "inactive", "open", "closed"):
                continue
            snapshot = {"field": req["field"], "value": state.strip().lower()}
            level = current.get("level")
            if (type(level) in (str, int) and _NUMBER.fullmatch(str(level))
                    and 0 <= float(level) <= 100):
                snapshot["level_percent"] = str(level)
            result["focal_inventory_state"] = snapshot
    by_device = {}
    peer_labels = {}
    relative = _RELATIVE_HOURS.search(question)
    requested_hours = int(relative.group(1)) if relative else None
    matched_windows = []
    for n, receipt in enumerate(receipts[:24], 1):
        if not isinstance(receipt, dict) or receipt.get("success") is not True or receipt.get("name") != "hub_list_device_events":
            continue
        args = receipt.get("arguments")
        if not isinstance(args, dict) or type(args.get("deviceId")) not in (str, int):
            continue
        device_id = str(args["deviceId"]).strip()
        outer = _outer(receipt)
        if not isinstance(outer, dict) or outer.get("truncated") is True:
            if device_id == focal_id:
                result["focal_truncated_reads"] += 1
            continue
        original = _native_payload(receipt)
        if not isinstance(original, dict) or str(original.get("deviceId", "")).strip() != device_id:
            continue
        data = original.get("events")
        source_hours = args.get("hoursBack")
        source_since = _date(original.get("sinceTimestamp"))
        if (device_id == focal_id and requested_hours is not None
                and requested_hours == source_hours
                and source_since is not None):
            matched_windows.append((
                source_since, source_since + timedelta(hours=requested_hours)
            ))
        if not isinstance(data, list) or len(data) > 400:
            if device_id == focal_id:
                result["focal_truncated_reads"] += 1
            continue
        if type(original.get("count")) is int and original["count"] != len(data):
            continue
        limit = args.get("limit")
        head = outer.get("client_claim_evidence_headline")
        if device_id == focal_id and (
            (type(limit) is int and len(data) >= limit)
            or (isinstance(head, dict) and head.get("row_limit_reached") is True)
        ):
            result["focal_limit_reached_reads"] += 1
        peer_labels[device_id] = _safe(original.get("device"), peer_labels.get(device_id, ""))
        start = _date(original.get("sinceTimestamp"))
        for entry in data:
            if not isinstance(entry, dict):
                continue
            item = _observation(entry, n)
            if item and (start is None or item["time"] >= start):
                by_device.setdefault(device_id, []).append(item)
    if matched_windows:
        start, end = max(matched_windows, key=lambda x: x[0])
        result["requested_window_start"] = start.isoformat()
        result["requested_window_end"] = end.isoformat()
        result["requested_window_verified_from_source"] = True
        by_device = {
            did: [row for row in rows if start <= row["time"] <= end]
            for did, rows in by_device.items()
        }
    for did, rows in by_device.items():
        distinct = {(x["timestamp"], x["name"], x["value"], x["command"]): x for x in rows}
        by_device[did] = sorted(distinct.values(), key=lambda x: x["time"])

    def safe_row(row):
        if row is None:
            return None
        data = {"timestamp": row["timestamp"], "event_name": row["name"],
                "receipt_number": row["receipt"]}
        if row["value"] is not None:
            data["observed_value"] = row["value"]
        if row["issuer"]:
            data["recorded_command_issuer"] = row["issuer"]
        if row["reporter"]:
            data["reported_by"] = row["reporter"]
        return data

    focal = [x for x in by_device.get(focal_id, [])
             if x["name"] == req["field"] and x["value"] is not None]
    result["focal_report_count"] = len(focal)
    if focal:
        result["focal_first"] = safe_row(focal[0])
        result["focal_latest"] = safe_row(focal[-1])
    pairs = [(a, b) for a, b in zip(focal, focal[1:])
             if a["value"] == req["before"] and b["value"] == req["after"]]
    if pairs and (requested_hours is None or matched_windows):
        a, z = pairs[-1]
        result["focal_pair"] = {"before": safe_row(a), "after": safe_row(z)}
        result["status"] = "bounded_pair_observed"
        if focal[-1]["time"] > z["time"]:
            result["focal_later_report"] = safe_row(focal[-1])
    # A narrow positive-fact ledger: latest timestamped report for each
    # allowed operational field and latest issued commands on the SAME device.
    # This is not a controller-decision trace or exhaustive interval coverage.
    focal_rows = by_device.get(focal_id, [])
    last_by_field = {
        row["name"]: row for row in focal_rows
        if row["name"] in _CONTEXT_FIELDS and row["value"] is not None
    }
    result["focal_context"] = [
        safe_row(row) for row in sorted(
            last_by_field.values(), key=lambda row: row["time"]
        )[-5:]
    ]
    result["focal_commands"] = [
        safe_row(row) for row in focal_rows if row["command"]
    ][-2:]
    for did, rows in by_device.items():
        if did == focal_id or len(result["peer_reports"]) >= 3:
            continue
        states = [x for x in rows if x["name"] == req["field"] and x["value"]]
        if not states:
            continue
        prev = next((x for x in reversed(states[:-1]) if x["value"] != states[-1]["value"]), None)
        commands = [x for x in rows if x["command"]]
        result["peer_reports"].append({
            "device_id": did, "label": peer_labels.get(did, ""),
            "latest": safe_row(states[-1]), "previous_different": safe_row(prev),
            "latest_command": safe_row(commands[-1]) if commands else None,
            "latest_mode": safe_row(next((
                row for row in reversed(rows)
                if row["name"] == "thermostatMode" and row["value"] is not None
            ), None)),
            "not_focal_target": True,
        })
    return result


def _md(text):
    return re.sub(r"([\\\x60*_{}\[\]()#+!|>])", r"\\\1", str(text))


def verify_recent_transition(question, draft_answer, receipts, *, timezone_name=None):
    """Publish source-backed natural times; raw source evidence is unchanged."""
    evidence = temporal_transition_evidence(question, receipts)
    if evidence["status"] == "not_applicable":
        return {"status": "not_applicable", "answer": draft_answer}
    request = evidence["requested"]
    target = _md(request["target"])
    a, z = request["before"].upper(), request["after"].upper()
    pair = evidence["focal_pair"]

    def when(row):
        return _friendly_time(row["timestamp"], timezone_name) or "unknown time"

    if pair:
        lines = [
            f"**{target}:** The latest *observed* {a} → {z} pair in the "
            f"returned history is an {z} report on "
            f"**{when(pair['after'])}**, following an {a} report on "
            f"**{when(pair['before'])}**.",
        ]
        if pair["after"].get("reported_by"):
            lines.append(
                f"The {z} event was reported by "
                f"**{_md(pair['after']['reported_by'])}**. "
                "The reporter is not necessarily the initiator."
            )
        later = evidence["focal_later_report"]
        if later:
            lines.append(
                f"A later {request['field']} report was "
                f"**{_md(later['observed_value'].upper())}** "
                f"on **{when(later)}**."
            )
        lines.append(
            "These are discrete reported observations, not independently "
            "verified physical transition instants or exhaustive history."
        )
    else:
        lines = [f"**{target}:** I cannot verify its last {a} → {z} "
                 "transition from the inspectable original event rows."]
        first, latest = evidence["focal_first"], evidence["focal_latest"]
        if first and latest:
            lines.append(
                f"The {request['field']} source returned observations from "
                f"**{when(first)} ({first['observed_value']})** to "
                f"**{when(latest)} ({latest['observed_value']})**, "
                "without a verified before/after pair."
            )
    inventory = evidence["focal_inventory_state"]
    if inventory:
        snapshot = (f"**{request['field']} = {_md(inventory['value'].upper())}**"
                    + (f" at {_md(inventory['level_percent'])}% level"
                       if "level_percent" in inventory else ""))
        lines.append(
            f"**Inventory read during this request:** {snapshot}. "
            "This is a reported snapshot, not proof of an earlier event."
        )
    if (_RELATIVE_HOURS.search(question)
            and not evidence["requested_window_verified_from_source"]):
        lines.append(
            "The requested relative time window was not independently "
            "established from an original matching-lookback source."
        )
    if evidence["focal_truncated_reads"] or evidence["focal_limit_reached_reads"]:
        lines.append(
            "Some focal-device event responses were truncated or capped; "
            "their unseen rows cannot be treated as missing events."
        )
    # The publication contract must retain verified positive context even
    # when the requested before/after transition or its cause is unverified.
    # Do not inherit the model draft: it may contain a fabricated cause.
    if evidence["focal_context"]:
        def context_text(item):
            field, value = item["event_name"], item["observed_value"]
            unit = ("°C" if field in ("temperature", "heatingSetpoint", "coolingSetpoint")
                    else "%" if field in ("valveLevel", "humidity", "battery")
                    else " W" if field == "power" else "")
            return (f"{_md(field)} = **{_md(value)}{unit}** at "
                    f"**{when(item)}**")
        lines.append(
            "**Additional reported focal-device context (not a verified cause):** "
            + "; ".join(context_text(item) for item in evidence["focal_context"])
            + "."
        )
    if evidence["focal_commands"]:
        item = evidence["focal_commands"][-1]
        value = (f" (reported argument/value: {_md(item['observed_value'])})"
                 if item.get("observed_value") is not None else "")
        issuer = (f"; recorded issuer: {_md(item['recorded_command_issuer'])}"
                  if item.get("recorded_command_issuer") else "")
        lines.append(
            f"**Focal-device command record:** {_md(item['event_name'])} "
            f"at **{when(item)}**{value}{issuer}. "
            "A recorded issuer does not independently prove the trigger or effect."
        )
    for peer in evidence["peer_reports"][:2]:
        name = _md(peer["label"]) if peer["label"] else "Device " + peer["device_id"]
        last, previous = peer["latest"], peer["previous_different"]
        context = (f"**Separate device — {name}:** Its latest returned "
                   f"{request['field']} report was **{last['observed_value']} "
                   f"on {when(last)}**.")
        if previous:
            context += (f" A preceding different report was "
                        f"**{previous['observed_value']} at "
                        f"{when(previous)}**.")
        lines.append(context)
        mode = peer.get("latest_mode")
        if mode:
            lines.append(
                f"A separate **{name}** thermostatMode report was "
                f"**{_md(mode['observed_value'])} on {when(mode)}**. "
                "This is a device report, not evidence of the focal transition."
            )
        command = peer["latest_command"]
        if command:
            issuer = (f" (recorded issuer: {_md(command['recorded_command_issuer'])})"
                      if command.get("recorded_command_issuer") else "")
            lines.append(
                f"A command row for that separate device was "
                f"{_md(command['event_name'])} at "
                f"**{when(command)}**{issuer}; this does not "
                "establish what initiated the focal device's transition."
            )
    if re.search(
        r"\b(?:why|caused|cause|triggered|initiated|reason|"
        r"what\s+led\s+to|verify\s+what)\b", question, re.I
    ):
        lines.append(
            "**Cause:** The reporter of a state event, a recorded command "
            "issuer, and a notified listener have different roles. The "
            "event rows summarised here cannot independently establish "
            "who initiated the focal transition or a controller's "
            "internal decision. Additional original execution-specific "
            "sources, if returned, need separate evaluation."
        )
    return {
        "status": "bounded_pair_observed" if pair else "focal_transition_unverified",
        "answer": "\n\n".join(lines),
        "target_id": evidence["target_id"], "event_field": request["field"],
        "focal_returned_state_rows": evidence["focal_report_count"],
        "focal_context_fields_returned": len(evidence["focal_context"]),
        "focal_command_rows_preserved": len(evidence["focal_commands"]),
        "focal_later_report_preserved": evidence["focal_later_report"] is not None,
        "focal_inventory_snapshot_used": inventory is not None,
        "display_timezone": timezone_name if isinstance(timezone_name, str)
                            and timezone_name else "UTC",
        "display_times_are_minute_precision": True,
        "focal_truncated_reads": evidence["focal_truncated_reads"],
        "focal_limit_reached_reads": evidence["focal_limit_reached_reads"],
        "requested_window_verified_from_source": evidence["requested_window_verified_from_source"],
        "typed_projection": True,
        "physical_transition_or_cause_verified": False,
    }
