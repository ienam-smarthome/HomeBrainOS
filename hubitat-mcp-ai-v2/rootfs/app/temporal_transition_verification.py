"""Bounded typed source verification of latest state-transition questions.

Output-only: no tool selection, new reads, writes or model round. A state
reported by ANOTHER device is never the requested device's transition.
Truncated original native MCP responses never prove missing events absent.
"""
from __future__ import annotations
from datetime import datetime, timezone
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
    normalized = value.lower() if isinstance(value, str) and value.lower() in allowed else None
    is_command = name.startswith("command-")
    if normalized is None and not is_command:
        return None
    producer = row.get("producedBy")
    issuer = _safe(producer.get("name")) if is_command and isinstance(producer, dict) else ""
    return {"time": parsed, "timestamp": stamp, "name": name,
            "value": normalized, "issuer": issuer,
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
        "focal_truncated_reads": 0, "focal_limit_reached_reads": 0,
        "peer_reports": [],
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
    by_device = {}
    peer_labels = {}
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
        return data

    focal = [x for x in by_device.get(focal_id, [])
             if x["name"] == req["field"] and x["value"] is not None]
    result["focal_report_count"] = len(focal)
    if focal:
        result["focal_first"] = safe_row(focal[0])
        result["focal_latest"] = safe_row(focal[-1])
    pairs = [(a, b) for a, b in zip(focal, focal[1:])
             if a["value"] == req["before"] and b["value"] == req["after"]]
    if pairs:
        a, z = pairs[-1]
        result["focal_pair"] = {"before": safe_row(a), "after": safe_row(z)}
        result["status"] = "bounded_pair_observed"
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
            "not_focal_target": True,
        })
    return result


def _md(text):
    return re.sub(r"([\\\x60*_{}\[\]()#+!|>])", r"\\\1", str(text))


def verify_recent_transition(question, draft_answer, receipts):
    """Replace unsupported precise latest/cause prose with source-only facts."""
    evidence = temporal_transition_evidence(question, receipts)
    if evidence["status"] == "not_applicable":
        return {"status": "not_applicable", "answer": draft_answer}
    request = evidence["requested"]
    target = _md(request["target"])
    a, z = request["before"].upper(), request["after"].upper()
    pair = evidence["focal_pair"]
    if pair:
        lines = [
            f"**{target}:** The latest *observed* {a} → {z} pair in the "
            f"inspectable returned rows is the {z} report at "
            f"**{pair['after']['timestamp']}**, preceded by a {a} report "
            f"at **{pair['before']['timestamp']}**.",
            "Those are discrete device reports, not independently verified "
            "physical transition instants or an exhaustive history.",
        ]
    else:
        lines = [f"**{target}:** I cannot verify its last {a} → {z} "
                 "transition from the inspectable original event rows."]
        first, latest = evidence["focal_first"], evidence["focal_latest"]
        if first and latest:
            lines.append(
                f"The {request['field']} source returned observations from "
                f"**{first['timestamp']} ({first['observed_value']})** to "
                f"**{latest['timestamp']} ({latest['observed_value']})**, "
                "without a verified before/after pair."
            )
    if evidence["focal_truncated_reads"] or evidence["focal_limit_reached_reads"]:
        lines.append(
            "Some focal-device event responses were truncated or capped; "
            "their unseen rows cannot be treated as missing events."
        )
    for peer in evidence["peer_reports"][:2]:
        name = _md(peer["label"]) if peer["label"] else "Device " + peer["device_id"]
        last, previous = peer["latest"], peer["previous_different"]
        context = (f"**Separate device — {name}:** Its latest returned "
                   f"{request['field']} report was **{last['observed_value']} "
                   f"at {last['timestamp']}**.")
        if previous:
            context += (f" A preceding different report was "
                        f"**{previous['observed_value']} at "
                        f"{previous['timestamp']}**.")
        lines.append(context)
        command = peer["latest_command"]
        if command:
            issuer = (f" (recorded issuer: {_md(command['recorded_command_issuer'])})"
                      if command.get("recorded_command_issuer") else "")
            lines.append(
                f"A command row for that separate device was "
                f"{_md(command['event_name'])} at "
                f"**{command['timestamp']}**{issuer}; this does not "
                "establish what initiated the focal device's transition."
            )
    lines.append(
        "**Cause:** The reporter of a state event, a recorded command issuer, "
        "and a notified listener have different roles. These receipts do not "
        "independently establish the cause of an unobserved focal transition "
        "or the controller's internal decision."
    )
    return {
        "status": "bounded_pair_observed" if pair else "focal_transition_unverified",
        "answer": "\n\n".join(lines),
        "target_id": evidence["target_id"], "event_field": request["field"],
        "focal_returned_state_rows": evidence["focal_report_count"],
        "focal_truncated_reads": evidence["focal_truncated_reads"],
        "focal_limit_reached_reads": evidence["focal_limit_reached_reads"],
        "typed_projection": True,
        "physical_transition_or_cause_verified": False,
    }
