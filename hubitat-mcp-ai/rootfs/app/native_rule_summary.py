"""Source-scoped natural language summaries of saved native Rule Machine rules.

These summaries describe *configuration only*. Action order is not proof of
run order in a conditional rule, nor is a clock time proof of a dated trigger.
Every displayed device ID and action parameter must come from a typed,
privacy-filtered field in the single native document read.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

_SETTING_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.#-]{0,75}$")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DEVICE = re.compile(r"^[1-9]\d{0,8}$")
_SECRET = re.compile(r"(?i)(?:password|secret|token|api.?key|credential|pin|authorization)")


def _setting(row: Any) -> dict[str, Any] | None:
    """Match the native reader's conservative simple-setting projection."""
    if not isinstance(row, dict):
        return None
    name, typ = row.get("name"), row.get("type")
    if (not isinstance(name, str) or not _SETTING_NAME.fullmatch(name)
            or _SECRET.search(name) or not isinstance(typ, str)
            or not _SETTING_NAME.fullmatch(typ)):
        return None
    raw = row.get("value")
    if isinstance(raw, str) and (len(raw) > 100 or _SECRET.search(raw)):
        return None
    if type(raw) not in (bool, int, float, str, type(None)):
        return None
    ids = row.get("device_ids", [])
    if (not isinstance(ids, list) or len(ids) > 24 or
            any(not isinstance(i, (str, int)) or not _DEVICE.fullmatch(str(i))
                for i in ids)):
        return None
    return {"name": name, "type": typ, "value": raw,
            "device_ids": [str(i) for i in ids]}


def _text(row: dict[str, Any] | None, typ: str) -> str | None:
    if not isinstance(row, dict) or row.get("type") != typ:
        return None
    value = row.get("value")
    return value if isinstance(value, str) and value else None


def _minutes(settings: dict[str, dict[str, Any]], action_id: str) -> str | None:
    """Only a saved hrs:min:sec Wait field can support duration prose."""
    selector = settings.get(f"delayAct.{action_id}")
    if _text(selector, "enum") != "hrs:min:sec":
        return None
    parts: list[tuple[str, str]] = []
    for key, label in (("delayHor", "hour"), ("delayMin", "minute"), ("delaySec", "second")):
        setting = settings.get(f"{key}.{action_id}")
        if not isinstance(setting, dict) or setting.get("type") not in ("number", "decimal"):
            continue
        raw = setting.get("value")
        if type(raw) in (float, int) and 0 <= raw <= 1440 and raw == int(raw) and raw != 0:
            number = int(raw)
            parts.append((str(number), label + ("" if number == 1 else "s")))
    return " ".join(f"{num} {unit}" for num, unit in parts) if parts else None


def describe_native_rule(
    data: Any, *, app_id: str,
    methods: list[tuple[str, str]],
) -> str | None:
    """Summarise simple source-backed native actions; return None if unqualified.

    Does not interpret conditional expression graphs or infer past firing,
    scheduled job health, physical device changes, or one-time semantics.
    """
    if not isinstance(data, dict) or str(data.get("rule_id") or "") != str(app_id):
        return None
    rows, triggers = data.get("settings"), data.get("triggers")
    if (not isinstance(rows, list) or len(rows) > 256
            or not isinstance(triggers, dict) or len(triggers) > 100
            or not isinstance(methods, list) or len(methods) > 100):
        return None
    safe = [_setting(row) for row in rows]
    settings = {row["name"]: row for row in safe if row is not None}
    if len(settings) != len([row for row in safe if row is not None]):
        return None

    lines = ["**Saved Rule Machine configuration**"]
    clock_notes: list[str] = []
    for key in sorted(triggers, key=lambda k: int(k) if str(k).isdigit() else 99999):
        if not isinstance(key, str) or not key.isdigit():
            return None
        original = triggers[key]
        if not isinstance(original, str) or len(original) > 160 or _SECRET.search(original):
            return None
        val = _text(settings.get(f"atTime{key}"), "time")
        clock = val if val is not None and _TIME.fullmatch(val) else None
        trigger_date = _text(settings.get(f"atDate{key}"), "date")
        date_mark = settings.get(f"date{key}")
        if trigger_date is not None:
            try:
                date.fromisoformat(trigger_date)
            except ValueError:
                trigger_date = None
        dated = (
            trigger_date is not None
            and isinstance(date_mark, dict)
            and date_mark.get("type") == "bool"
            and date_mark.get("value") is True
        )
        if clock is not None and dated:
            text = f"On **{trigger_date} at {clock}** (saved dated trigger)"
        elif clock is not None:
            text = f"At **{clock}** (no dated one-time trigger verified)"
            clock_notes.append("A one-time date was not established by this read; recurrence remains unverified.")
        else:
            # Display bounded source text without claiming time semantics.
            text = f"Trigger {key}: saved event \u201c{original}\u201d (timing semantics not verified)"
        lines.append(f"- **Trigger:** {text}")
    if not triggers:
        lines.append("- **Trigger:** None returned; automatic execution is not established.")

    lines.append("")
    lines.append("**Saved action order**")
    if data.get("conditions") not in ({}, None) or data.get("expressions") not in ({}, None):
        lines.append("Actions may be conditional; their execution path is not verified.")
    if not methods:
        lines.append("No actions returned.")
    for index, (action_id, method) in enumerate(methods, 1):
        if not _DEVICE.fullmatch(action_id) or not isinstance(method, str):
            return None
        if method == "getOnOffSwitch":
            direction = settings.get(f"onOff.{action_id}")
            targets = settings.get(f"onOffSwitch.{action_id}")
            if (isinstance(direction, dict)
                    and direction.get("type") == "bool"
                    and type(direction.get("value")) is bool
                    and isinstance(targets, dict)
                    and targets.get("type") == "capability.switch"
                    and targets.get("device_ids")):
                onoff = "ON" if direction["value"] else "OFF"
                ids = ", ".join(targets["device_ids"])
                action = f"Set switch **{onoff}** \u2014 device ID(s) **{ids}**"
            else:
                action = "Switch action \u2014 target or ON/OFF value not verified"
        elif method == "getWaitEvents":
            amount = _minutes(settings, action_id)
            action = (
                f"Wait \u2014 **{amount} configured**"
                if amount else "Wait for event \u2014 duration not verified"
            )
        else:
            action = f"Native action \u201c{method}\u201d \u2014 semantics not interpreted"
        lines.append(f"{index}. {action} (action {action_id})")

    lines.append("")
    if clock_notes:
        lines.append("**Date caution:** " + " ".join(dict.fromkeys(clock_notes)))
    withheld = sum(v is None for v in safe)
    lines.append(
        f"**Source coverage:** {len(triggers)} trigger(s), {len(methods)} ordered "
        f"action(s), {len(rows)} setting(s) returned; {withheld} settings "
        "redacted or unsupported. Unrelated editor controls omitted from this summary."
    )
    health = data.get("nativeHealth")
    if isinstance(health, dict):
        flags = [f"{k}={health[k]}" for k in ("paused", "stopped", "broken")
                 if type(health.get(k)) is bool]
        if flags:
            lines.append("**Reported rule flags:** " + ", ".join(flags) +
                         " (not an execution test).")
    lines.append(
        "**Not verified:** a scheduled future job, successful execution, or "
        "actual device/network effect. This was a read-only configuration inspection."
    )
    return "\n".join(lines)
