"""Conservative one-off automation authorization for model-selected native writes.

This is a denial-only temporal safety boundary, not a planner or tool router.
It never grants MCP permission or chooses a device, date, action or rule engine.
MCP source documents remain authoritative; unknown semantics fail closed.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any


OWNED = re.compile(
    r"^HB one-shot \| .+ \(One-time (?P<date>\d{4}-\d{2}-\d{2}) "
    r"(?P<hour>\d{2}:\d{2})\)$"
)
_RECUR = re.compile(
    r"\b(?:daily|every\s+(?:day|morning|afternoon|evening|night|"
    r"week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"weekdays?|weekends?|each\s+(?:day|week|night)|recurr?ing|repeat(?:edly)?)\b",
    re.I,
)
_ONE = re.compile(
    r"\b(?:one[ -]?(?:off|time)|once|just\s+this\s+time|"
    r"tomorrow|tonight|today|after\s+\d+\s*(?:minutes?|mins?|hours?|hrs?)|"
    r"in\s+\d+\s*(?:minutes?|mins?|hours?|hrs?))\b",
    re.I,
)
_CLOCK = re.compile(
    r"\b(?:at|by)\s+\d{1,2}(?:(?::|\.)\d{2})?\s*(?:am|pm)\b"
    r"|\b(?:at|by)\s+\d{1,2}:\d{2}\b",
    re.I,
)


def requested_temporal_scope(question: str) -> str:
    """A conservative deny-only signal. Ambiguity never authorizes a write."""
    if _RECUR.search(question):
        return "recurring"
    if _ONE.search(question) or _CLOCK.search(question):
        return "one_off"
    return "unknown"


def native_rule_call(name: str, arguments: dict[str, Any]) -> tuple[str, dict] | None:
    if name in ("hub_set_visual_rule", "hub_set_rule"):
        return name, arguments
    if (isinstance(arguments, dict)
            and arguments.get("tool") in ("hub_set_visual_rule", "hub_set_rule")
            and isinstance(arguments.get("args"), dict)):
        return arguments["tool"], arguments["args"]
    return None


def decode_mcp_payload(value: Any) -> Any:
    """Parse current original native MCP wrappers; never infer missing data."""
    for _ in range(6):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                return None
            continue
        if isinstance(value, dict):
            if value.get("isError") is True or value.get("success") is False:
                return None
            if isinstance(value.get("content"), list):
                rows = [r.get("text") for r in value["content"]
                        if isinstance(r, dict) and r.get("type") == "text"]
                if len(rows) == 1:
                    value = rows[0]
                    continue
            for key in ("structuredContent", "result", "mcp_result"):
                if isinstance(value.get(key), (dict, str)):
                    value = value[key]
                    break
            else:
                return value
            continue
        return value
    return None


def _source_read(receipts: list[dict], tools: set[str]) -> list[dict]:
    values = []
    for record in receipts:
        if record.get("success") is not True:
            continue
        name = record.get("name")
        args = record.get("arguments")
        if isinstance(args, dict) and isinstance(args.get("tool"), str):
            name = args["tool"]
        if name not in tools:
            continue
        decoded = decode_mcp_payload(record.get("response"))
        if isinstance(decoded, dict):
            values.append(decoded)
    return values


def verified_native_parent(receipts: list[dict], parent_id: int) -> bool:
    """Require the installed hub's typed app identity, never a screenshot ID."""
    for source in _source_read(receipts, {"hub_get_app_config", "hub_list_apps"}):
        apps = source.get("apps") if isinstance(source.get("apps"), list) else [
            source.get("app", source)
        ]
        for app in apps:
            if not isinstance(app, dict):
                continue
            if str(app.get("id", app.get("appId"))) != str(parent_id):
                continue
            meta = app.get("appType")
            if (isinstance(meta, dict) and meta.get("namespace") == "hubitat"
                    and meta.get("name") == "Rule Machine"):
                return True
    return False


def verified_native_switch(receipts: list[dict], device_id: str, command: str) -> bool:
    """The current request must have read the exact device's actual commands."""
    for source in _source_read(receipts, {"hub_get_device"}):
        if str(source.get("id", source.get("deviceId"))) != str(device_id):
            continue
        commands = source.get("commands")
        if isinstance(commands, list) and any(
            (row.get("name") if isinstance(row, dict) else row) == command
            for row in commands
        ):
            return True
    return False


def validate_one_off_native_switch(
    payload: dict, receipts: list[dict], *, now: datetime | None = None
) -> str | None:
    """Validate one source-attested native dated Switch candidate before approval.

    A strict portable subset of the later V1 MCP 5.1.6 native document. This
    does not assert that a future execution or router effect occurred.
    """
    if payload.get("operation") != "create":
        return "One-off request requires a one-time native CREATE, not an edit or recurring rule"
    args = payload.get("args")
    if not isinstance(args, dict) or set(args) != {"parent_id", "name", "changes"}:
        return "Native Rule Machine create must include parent_id, name and atomic changes"
    parent_id, name, changes = args["parent_id"], args["name"], args["changes"]
    if type(parent_id) is not int or parent_id <= 0:
        return "Native Rule Machine parent ID is invalid"
    match = OWNED.fullmatch(name) if isinstance(name, str) else None
    if match is None:
        return "One-off native rule must have an exact HB one-shot ownership name and date"
    if not verified_native_parent(receipts, parent_id):
        return "Native Rule Machine parent identity is unverified by a fresh typed app read"
    if not isinstance(changes, list) or len(changes) != 2:
        return "One-off rule must contain exactly one dated trigger and one Switch action"
    try:
        trig, act = changes
        if trig["part"] != "trigger" or act["part"] != "action":
            raise ValueError("wrong change order")
        trigger, action = trig["value"], act["value"]
        if trigger["capability"] != "Certain Time (and optional date)":
            raise ValueError("not a dated Certain Time trigger")
        if action["type"] != "switchActs" or action["subtype"] != "getOnOffSwitch":
            raise ValueError("unsupported Switch action")
        tf = {f["name"]: (f["type"], f["value"]) for f in trigger["fields"]}
        af = {f["name"]: (f["type"], f["value"]) for f in action["fields"]}
        if (len(tf) != len(trigger["fields"]) or len(af) != len(action["fields"])
                or set(tf) != {"time#", "atTime#", "date#", "atDate#"}
                or set(af) != {"onOffSwitch.#", "onOff.#"}):
            raise ValueError("wrong or repeated typed fields")
        if (tf["time#"] != ("enum", "A specific time")
                or tf["date#"] != ("bool", True)
                or tf["atDate#"] != ("date", match.group("date"))
                or tf["atTime#"][0] != "time"):
            raise ValueError("dated trigger fields are inconsistent")
        when = datetime.strptime(tf["atTime#"][1], "%Y-%m-%dT%H:%M:%S.%f%z")
        if (when.strftime("%Y-%m-%d") != match.group("date")
                or when.strftime("%H:%M") != match.group("hour")
                or when.second != 0 or when.microsecond != 0):
            raise ValueError("time, date and owned rule label disagree")
        ids = af["onOffSwitch.#"]
        state = af["onOff.#"]
        if (ids[0] != "capability.switch" or not isinstance(ids[1], list)
                or len(ids[1]) != 1 or
                not isinstance(ids[1][0], str) or
                re.fullmatch(r"[1-9]\d*", ids[1][0]) is None
                or state[0] != "bool" or type(state[1]) is not bool):
            raise ValueError("invalid native switch action")
        if not verified_native_switch(receipts, ids[1][0],
                                      "on" if state[1] else "off"):
            return "Native one-off target or on/off command lacks a fresh exact-device MCP read"
        clock = now if now is not None else datetime.now(timezone.utc)
        if clock.tzinfo is None or when.astimezone(timezone.utc) <= (
            clock.astimezone(timezone.utc) + timedelta(seconds=60)
        ):
            return "One-off rule's absolute date/time has passed or is too close to safely create"
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return "Native one-off rule is not a validated dated single-action Switch document"
    return None


def rule_pre_dispatch_issue(
    question: str, name: str, arguments: dict, receipts: list[dict],
    *, now: datetime | None = None,
) -> str | None:
    """Denial-only temporal contract, never an approval credential."""
    selected = native_rule_call(name, arguments)
    if selected is None or requested_temporal_scope(question) != "one_off":
        return None
    writer, params = selected
    if writer == "hub_set_visual_rule":
        return (
            "This request is one-off, but Visual Rules Builder has no verified "
            "calendar-dated one-shot trigger in the installed reference; its "
            "timeOfDay trigger repeats daily. NO rule was submitted. Inspect "
            "the native Rule Machine dated create contract or request clarification."
        )
    return validate_one_off_native_switch(params, receipts, now=now)
