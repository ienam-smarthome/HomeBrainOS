"""Check occupancy causal diagnoses against the actual read-only event receipts.

A sampled inactive sensor edge does not prove that the sensor is an input of
the OFF rule, nor that the room was empty, nor that a timer ran throughout.
"""
from __future__ import annotations
from datetime import datetime
import re
from typing import Any
from occupancy_timing_correlation import summarize_supported_off_timing

_GHOST = re.compile(r"(?:false\s+(?:motion|presence|occupancy)|ghost(?:ing|\s+(?:motion|occupancy))|sensors?\s+(?:are|were)\s+(?:triggering\s+falsely|reporting\s+false))", re.I)
_CERTAIN = re.compile(r"(?:most\s+likely\s+cause|the\s+issue\s+is|because\s+(?:the\s+)?sensors?|working\s+exactly\s+as\s+configured|(?:automation|rule|timer)\s+(?:logic\s+)?(?:is|was)\s+(?:functioning|working)\s+correctly|every\s+observed\s+instance)", re.I)
_UNCERTAIN = re.compile(r"(?:not\s+(?:verified|established|confirmed)|cannot\s+(?:verify|establish)|possible,\s+not\s+verified)", re.I)


def _date(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _histories(evidence: list[dict[str, Any]], attribute: str) -> list[dict[str, Any]]:
    return [
        row["details"] for row in evidence if isinstance(row, dict)
        and row.get("success") is True
        and row.get("tool") == "homebrain_device_history"
        and isinstance(row.get("details"), dict)
        and row["details"].get("attribute") == attribute
    ]


def _longest_on(evidence: list[dict[str, Any]]) -> str:
    intervals = []
    for details in _histories(evidence, "switch"):
        temporal = details.get("temporalAnalysis") or {}
        for item in temporal.get("observedIntervals") or []:
            if (isinstance(item, dict)
                    and isinstance(item.get("durationSeconds"), (int, float))
                    and _date(item.get("start")) and _date(item.get("end"))):
                intervals.append(item)
    if not intervals:
        return ""
    longest = max(intervals, key=lambda x: x["durationSeconds"])
    begin, end = _date(longest["start"]), _date(longest["end"])
    seconds = max(0, round(longest["durationSeconds"]))
    h, rem = divmod(seconds, 3600)
    m, sec = divmod(rem, 60)
    return (f"The longest bounded ON interval was {begin:%H:%M:%S}"
            f"–{end:%H:%M:%S} ({h}h {m}m {sec}s)." if h else
            f"The longest bounded ON interval was {begin:%H:%M:%S}"
            f"–{end:%H:%M:%S} ({m}m {sec}s).")


def _confirmed_off(evidence: list[dict[str, Any]]) -> list[tuple[str, str, datetime, float]]:
    pairs = {}
    for details in _histories(evidence, "switch"):
        events = details.get("boundaryEvents") or []
        if not isinstance(events, list):
            continue
        states = [
            _date(e.get("date")) for e in events if isinstance(e, dict)
            and e.get("name") == "switch" and e.get("value") == "off"
            and _date(e.get("date"))
        ]
        for event in events:
            if not isinstance(event, dict) or event.get("name") != "command-off":
                continue
            producer = event.get("producedBy") or {}
            at = _date(event.get("date"))
            if (not isinstance(producer, dict) or producer.get("type") != "app"
                    or not str(producer.get("id") or "").isdigit() or not at):
                continue
            candidates = [(x - at).total_seconds() for x in states if 0 <= (x - at).total_seconds() <= 3]
            if candidates:
                app_id = str(producer["id"])
                key = (app_id, at.isoformat())
                pairs[key] = (app_id, str(details.get("label") or "Light"), at, min(candidates))
    return sorted(pairs.values(), key=lambda p: p[2])[-2:]


def _unlinked_sensor_histories(evidence: list[dict[str, Any]], controller_ids: set[str]) -> list[str]:
    names = set()
    for details in _histories(evidence, "motion"):
        events = details.get("boundaryEvents") or []
        if not isinstance(events, list) or not events:
            continue
        matched, has_listener_metadata = False, False
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get("triggered"), list):
                continue
            has_listener_metadata = True
            matched = matched or any(
                isinstance(t, dict) and str(t.get("appId") or "") in controller_ids
                for t in event["triggered"]
            )
        if has_listener_metadata and not matched and details.get("label"):
            names.add(str(details["label"]))
    return sorted(names)


def guard_unverified_occupancy_cause(
    message: str, evidence: list[dict[str, Any]]
) -> tuple[str, bool]:
    text = str(message or "")
    clean = text.replace("**", "").replace(chr(96), "")
    positive_timing = summarize_supported_off_timing(evidence)
    if not (_GHOST.search(clean) and _CERTAIN.search(clean)):
        # Preserve a cautious answer while surfacing direct positive timing.
        if (positive_timing
                and "supported inactivity mechanism" not in clean.casefold()
                and re.search(r"(?:cause not (?:verified|established)|cannot establish(?: the)? cause)", clean, re.I)):
            return positive_timing + "\n\n" + text, True
        return text, False
    if _UNCERTAIN.search(clean[:900]) and not re.search(
        r"(?:working exactly as configured|the issue is not)", clean, re.I
    ):
        return text, False

    confirmed = _confirmed_off(evidence)
    lines = []
    interval = _longest_on(evidence)
    if interval:
        lines.append("**Verified light history:** " + interval)
    if confirmed:
        parts = []
        for app_id, label, when, delay in confirmed:
            issued = when.strftime("%H:%M:%S.%f")[:-3]
            parts.append(
                f"App {app_id} issued OFF at {issued}; "
                f"{label} reported OFF {delay:.3f}s later"
            )
        lines.append("**Verified OFF commands:** " + ". ".join(parts) + ".")
    controller_ids = {entry[0] for entry in confirmed}
    unlinked = _unlinked_sensor_histories(evidence, controller_ids)
    if unlinked:
        lines.append(
            "**Sensor-source limitation:** The retained motion events for "
            + ", ".join(unlinked)
            + " do not identify the OFF-command app as a triggered listener. "
            "They cannot establish that these sensors controlled its timer."
        )
    if positive_timing:
        lines.append(positive_timing)
    lines.append(
        "**Cause not verified:** False or ghost motion remains a possibility, "
        "not a finding. The evidence does not establish that the room was "
        "physically empty, that a particular configured input stayed active, "
        "or that every timer branch executed correctly. The configured "
        "activation and keep-on sensors must be checked together against "
        "the actual OFF timing and app decisions. A cloned sensor is not "
        "independent occupancy evidence."
    )
    return "\n\n".join(lines), True


__all__ = ["guard_unverified_occupancy_cause"]
