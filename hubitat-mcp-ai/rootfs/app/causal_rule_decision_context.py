"""Bounded explanation of WHY a proven lighting automation issued a command.

Command-event producedBy is direct action provenance. App configuration is NOT
execution proof. App logs can document a trigger when timestamp-aligned, while
current sensor health never proves the state at the historical command time.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from causal_command_provenance import (
    correlate_command_producers,
    focal_transition_boundary,
)
from device_state_summary import device_attributes, room_name


def _timestamp(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if re.search(r"[+-]\d{4}$", raw):
        raw = raw[:-5] + raw[-5:-2] + ":" + raw[-2:]
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        date = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return date if date.tzinfo is not None else date.replace(tzinfo=timezone.utc)


def proven_lighting_command(
    evidence: list[dict[str, Any]], *, transition: str = "on"
) -> dict[str, Any] | None:
    """Select an exact command→switch boundary from a lighting app.

    Restrict the extra work to proven lighting producers: named lighting rules
    or apps whose setLevel command activated the light. Custom apps need not
    be named 'Lighting'; generic button rules keep the existing fast path.
    """

    requested = focal_transition_boundary(evidence, transition)
    rows = []
    for row in correlate_command_producers(evidence):
        producer = row.get("producer") or {}
        subject = str(row.get("subject") or "")
        label = str(producer.get("label") or "")
        app_id = str(producer.get("id") or "")
        if not (
            row.get("action") == transition
            and row.get("boundaryRole") == ("start" if transition == "on" else "end")
            and str(producer.get("type") or "").lower() == "app"
            and app_id.isdecimal()
            and "light" in subject.casefold()
            and (
                re.search(r"\b(?:lighting|room lighting|low light)\b", label, re.I)
                or (row.get("command") or {}).get("semantics") == "level-switch-command"
            )
        ):
            continue
        if requested and _timestamp(row.get("stateBoundary")) != _timestamp(requested):
            continue
        command_time = _timestamp((row.get("command") or {}).get("date"))
        if command_time:
            rows.append((command_time, row))
    return max(rows, key=lambda item: item[0])[1] if rows else None


def app_log_window(row: dict[str, Any]) -> dict[str, Any] | None:
    command_time = _timestamp((row.get("command") or {}).get("date"))
    if command_time is None:
        return None
    # Filter on Hubitat's timezone-aware event time; do not shift its local
    # +01:00 timestamp by formatting it as if already UTC.
    return {
        "appId": str((row.get("producer") or {}).get("id")),
        "since": (command_time - timedelta(seconds=12)).astimezone(
            timezone.utc
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "until": (command_time + timedelta(seconds=6)).astimezone(
            timezone.utc
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "limit": 60,
    }


def _clean_configuration_entry(raw: str) -> str | None:
    """Hide editor-only evaluation flags and corrupt UI form serialization."""

    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not text or len(text) > 500:
        return None
    if re.search(
        r"nametypevalue|%device%|%value%|%text%|private\s+booleanboolean",
        text, re.I,
    ):
        return None
    # (T), [TRUE], and the "(0)" value next to a lux threshold are
    # *displayed editor state*, never proof of an event-time evaluation.
    text = re.sub(r"\s*\[(?:TRUE|FALSE)\]", "", text, flags=re.I)
    text = re.sub(r"(?<=\w)\([TF]\)(?=\W|$)", "", text, flags=re.I)
    text = re.sub(
        r"\(-?\d+(?:\.\d+)?\)(?=\s+is\s*(?:<=|>=|<|>|=))",
        "", text,
    )
    return re.sub(r"\s+", " ", text).strip() or None


def configured_mode_triggers(configured: list[str]) -> list[str]:
    """Parse only actual mode-trigger phrases from the current configuration."""

    for line in configured:
        match = re.search(
            r"\bmode\s+(?:changes?\s+to|becomes?|switched\s+to)\s+"
            r"([A-Za-z][A-Za-z ,'-]{0,120})",
            str(line), re.I,
        )
        if not match:
            continue
        raw = re.sub(r"\s+or\s+", ",", match.group(1), flags=re.I)
        modes = [item.strip(" ,.") for item in raw.split(",")]
        return list(dict.fromkeys(item for item in modes if len(item) >= 3))[:8]
    return []


def _mode_is_observed(message: str, mode: str) -> bool:
    """Require a real change-shaped log statement, not a generic mode mention."""

    escaped = re.escape(mode)
    patterns = (
        rf"\bmode\s+(?:changed|changes|switched|set)\s+(?:from\s+.+?\s+)?to\s+{escaped}\b",
        rf"\bmode\s+(?:became|becomes)\s+{escaped}\b",
        rf"\bis\s+now\s+in\s+{escaped}\s+mode\b",
    )
    return any(re.search(pattern, message, re.I) for pattern in patterns)


def mode_transition_correlations(
    data: dict[str, Any],
    command_row: dict[str, Any],
    configured: list[str],
) -> list[str]:
    """Correlate independently logged mode changes; never claim rule execution.

    Reject native log times lacking timezone offsets, which can mean UTC or
    local clock depending on Hubitat firmware.
    """

    modes = configured_mode_triggers(configured)
    command_time = _timestamp((command_row.get("command") or {}).get("date"))
    if not modes or command_time is None:
        return []
    logs = data.get("logs")
    if not isinstance(logs, list):
        return []
    matched: list[tuple[datetime, str]] = []
    for event in logs:
        if not isinstance(event, dict):
            continue
        raw_stamp = str(
            event.get("time") or event.get("timestamp") or event.get("date") or ""
        ).strip()
        if not re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", raw_stamp):
            continue
        stamp = _timestamp(raw_stamp)
        if stamp is None or not 0 <= (command_time - stamp).total_seconds() <= 12:
            continue
        message = str(event.get("message") or "")
        for mode in modes:
            if _mode_is_observed(message, mode):
                matched.append((stamp, mode))
                break
    matched.sort(key=lambda item: item[0])
    return list(dict.fromkeys(
        f"- {stamp.astimezone(command_time.tzinfo).strftime('%H:%M:%S')} — "
        f"Hub log recorded a change to {mode} mode."
        for stamp, mode in matched
    ))[:3]


def configuration_text(data: dict[str, Any]) -> tuple[list[str], str]:
    """Extract human-readable rule sections; never return raw app settings."""

    page = data.get("page") if isinstance(data.get("page"), dict) else {}
    sections = page.get("sections")
    if not isinstance(sections, list):
        return [], ""
    snippets: list[str] = []
    searchable: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").strip()
        for paragraph in section.get("paragraphs") or []:
            if not isinstance(paragraph, str):
                continue
            item = _clean_configuration_entry(paragraph)
            if item is None:
                continue
            searchable.append(item)
            if (
                re.search(
                    r"\b(?:trigger|event|require|condition|expression|mode|motion|presence|"
                    r"illuminance|lux|action|sensor|brightness|dimmer|level|schedule|time)\b", item, re.I
                )
                and len(snippets) < 5
            ):
                snippets.append(f"{title}: {item}" if title else item)
        for item in section.get("inputs") or []:
            if not isinstance(item, dict) or item.get("type") == "password":
                continue
            label = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            value = item.get("value")
            if value is True or isinstance(value, (dict, list)):
                value = None
            input_text = " ".join(
                piece for piece in (label, description, str(value) if value is not None else "")
                if piece
            )
            input_text = _clean_configuration_entry(input_text)
            if input_text is not None and len(input_text) <= 400:
                searchable.append(input_text)
                if re.search(r"\b(?:trigger|event|condition|mode|motion|presence|illuminance|lux)\b", input_text, re.I) and len(snippets) < 5:
                    snippets.append(f"{title}: {input_text}" if title else input_text)
    return list(dict.fromkeys(snippets))[:5], "\n".join(searchable).casefold()


def _log_date(row: dict[str, Any]) -> datetime | None:
    value = row.get("time") or row.get("timestamp") or row.get("date")
    return _timestamp(value)


def execution_log_lines(
    data: dict[str, Any],
    command_row: dict[str, Any],
) -> list[str]:
    """Show only same-app, event-aligned logs. Do not invent event causes."""

    command_time = _timestamp((command_row.get("command") or {}).get("date"))
    if command_time is None:
        return []
    logs = data.get("logs")
    if not isinstance(logs, list):
        return []
    selected: list[tuple[datetime, str]] = []
    for entry in logs:
        if not isinstance(entry, dict):
            continue
        stamp = _log_date(entry)
        if stamp is None or not (-12 <= (stamp - command_time).total_seconds() <= 6):
            continue
        message = str(entry.get("message") or "").strip()
        if not message or len(message) > 300:
            continue
        if not re.search(r"\b(?:triggered|event|condition|expression|mode|evaluat|action)\b", message, re.I):
            continue
        selected.append((stamp, message))
    return [
        f"- {timestamp.astimezone(command_time.tzinfo).strftime('%H:%M:%S')} — {message}"
        for timestamp, message in sorted(selected)[:5]
    ]


def referenced_sensor_identities(
    config_search_text: str,
    identities: list[dict[str, Any]],
    subject_room: str,
) -> list[dict[str, Any]]:
    """Use only exact canonical sensor labels/IDs appearing in the config."""

    if not config_search_text:
        return []
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in identities:
        if not isinstance(item, dict):
            continue
        device_id = str(item.get("id") or item.get("deviceId") or "")
        label = str(item.get("label") or item.get("name") or "").strip()
        room = room_name(item)
        if not device_id.isdecimal() or len(label) < 7 or (
            subject_room and room and room.casefold() != subject_room.casefold()
        ):
            continue
        if label.casefold() not in config_search_text:
            continue
        capabilities = {
            re.sub(r"[^a-z]", "", str(cap).casefold())
            for cap in item.get("capabilities") or []
        }
        observed = {
            re.sub(r"[^a-z]", "", str(key).casefold())
            for key in device_attributes(item)
        }
        if not (
            capabilities.intersection({
                "motionsensor", "presencesensor", "illuminancemeasurement",
                "contactsensor", "temperaturesensor", "relativehumiditymeasurement",
            })
            or observed.intersection({
                "motion", "presence", "illuminance", "contact",
                "temperature", "humidity",
            })
        ):
            continue
        if device_id not in seen:
            seen.add(device_id)
            matches.append(dict(item))
    return matches[:4]


def linked_sensor_health_warning(
    referenced: list[dict[str, Any]],
    live_devices: list[dict[str, Any]],
) -> list[str]:
    """Current health context only; never retroactively infer rule evaluation."""

    by_id = {
        str(d.get("id") or d.get("deviceId")): d
        for d in live_devices if isinstance(d, dict)
    }
    lines = []
    for selected in referenced:
        item_id = str(selected.get("id") or selected.get("deviceId") or "")
        device = by_id.get(item_id)
        if device is None:
            lines.append(
                f"- {selected.get('label') or selected.get('name')}: current "
                "sensor health could not be verified."
            )
            continue
        attrs = device_attributes(device)
        states = {str(key).casefold(): str(value).casefold() for key, value in attrs.items()}
        parent_id = str(device.get("parentDeviceId") or selected.get("parentDeviceId") or "")
        parent = by_id.get(parent_id)
        checked = [(device, states)]
        if parent_id:
            if parent is None:
                lines.append(
                    f"- {selected.get('label') or selected.get('name')}: "
                    f"linked parent {parent_id} health not available in this room read."
                )
                continue
            parent_states = {
                str(k).casefold(): str(v).casefold()
                for k, v in device_attributes(parent).items()
            }
            checked.append((parent, parent_states))
        for row, values in checked:
            offline = (
                values.get("healthstatus") == "offline"
                or values.get("sensorstatus") == "offline"
                or values.get("mqttstatus") in {"offline", "connecting", "failed", "disconnected"}
                or "connecting" in values.get("hapstatus", "")
            )
            if offline:
                label = row.get("label") or row.get("name") or row.get("id")
                lines.append(
                    f"- {label}: **currently offline/connecting**; related sensor "
                    "values may be retained rather than fresh."
                )
                break
    return list(dict.fromkeys(lines))[:4]


def render_rule_decision_context(
    *,
    app_name: str,
    app_id: str,
    configured: list[str],
    logs: list[str],
    sensor_warnings: list[str],
    mode_events: list[str] | None = None,
) -> str:
    lines = ["### Why the automation decided to act"]
    if logs:
        lines.append(
            "**Execution evidence:** Hubitat recorded these entries from the "
            f"command-producing app ({app_name}, ID {app_id}) near the ON command:"
        )
        lines.extend(logs)
    else:
        lines.append(
            "**Trigger not independently verified:** No timestamp-aligned "
            "rule-execution or condition-evaluation log was obtained."
        )
    if mode_events:
        lines.append(
            "**Independent mode-change correlation (event-time hub logs):**"
        )
        lines.extend(mode_events)
        lines.append(
            "This matches a configured mode trigger in time, but does not "
            "independently prove the rule's condition values at that moment."
        )
    if configured:
        lines.append(
            "**Configured triggers/conditions (current configuration, not proof "
            "of the historical evaluation):**"
        )
        for entry in configured:
            kind = (
                "Trigger" if re.search(
                    r"\bmode\s+(?:changes?|becomes?|switched)",
                    entry, re.I,
                ) else "Condition/action" if re.search(
                    r"\b(?:if|then|required expression)\b", entry, re.I,
                ) else "Rule detail"
            )
            lines.append(f"- **{kind}:** {entry}")
    else:
        lines.append(
            "The app's trigger/condition details could not be verified from "
            "the available configuration page."
        )
    if sensor_warnings:
        lines.append(
            "**Sensor health now (not necessarily at the event time):**"
        )
        lines.extend(sensor_warnings)
        lines.append(
            "The current connection state cannot establish whether a retained "
            "sensor value caused the rule's historical decision."
        )
    elif configured:
        lines.append(
            "The actual sensor values used during this event have not been verified."
        )
    return "\n".join(lines)
