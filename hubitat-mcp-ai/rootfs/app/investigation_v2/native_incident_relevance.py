"""User-question coverage of a *dated* device incident in Native V2.

An operation count and a successful read are NOT evidence that the historical
question was answered. An attested command outside the incident period is not
a cause of the incident. Only already approved, target-scoped MCP READ receipts
may contribute. This is an evidence-quality gate, not question intent routing,
a device-name-specific fix, a tool-call planner or a write authorisation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from .temporal_scope import explicit_incident_window

# Narrow user-relevant event types. An IP refresh, driver watchdog status,
# app configuration or unrelated later command doesn't tell us why a light
# stayed on during a different period. These are generic observation kinds.
_MATERIAL_EVENTS = frozenset({
    "switch", "level", "motion", "presence", "occupancy",
    "illuminance", "contact", "power",
})
_MATERIAL_COMMANDS = frozenset({
    "on", "off", "setlevel", "toggle", "dim", "startlevelchange",
    "stoplevelchange",
})


def _event_time(text: Any) -> datetime | None:
    if not isinstance(text, str) or len(text) > 64:
        return None
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(timezone.utc)


def dated_incident_evidence(
    question: str,
    witnesses: Sequence[Mapping[str, Any]],
    focus_ids: Sequence[str],
) -> dict[str, Any] | None:
    """Return an answer-quality observation, not a causal conclusion.

    Use a two-hour clock tolerance on each end of an explicitly requested
    UTC-interpreted interval, rather than implying Hubitat's timezone is
    verified. For a narrower event window than this a READ may still have
    returned no material rows: an absent record never proves no event occurred.
    """
    if len(set(focus_ids)) != 1:
        return None
    incident = explicit_incident_window(question, zone_name="UTC")
    if incident is None or not incident.interpretation.startswith((
            "overnight range", "inclusive calendar date range")):
        return None
    focus = str(focus_ids[0])
    start = datetime.fromisoformat(incident.start_utc) - timedelta(hours=2)
    end = datetime.fromisoformat(incident.end_utc) + timedelta(hours=2)
    scoped_reads = []
    material = []
    unrelated_command_rows = 0
    later_command_rows = 0
    for receipt in list(witnesses)[:32]:
        if receipt.get("operation") != "hub_list_device_events":
            continue
        filters = receipt.get("read_filters")
        if not isinstance(filters, Mapping) or str(filters.get("deviceId")) != focus:
            continue
        data = receipt.get("source_data")
        if not isinstance(data, Mapping) or not isinstance(data.get("events"), list):
            continue
        read = receipt.get("read")
        if type(read) is not int:
            continue
        scoped_reads.append(read)
        for event in data["events"][:100]:
            if not isinstance(event, Mapping):
                continue
            name = event.get("name")
            dt = _event_time(event.get("date"))
            if not isinstance(name, str) or dt is None:
                continue
            kind = name.split("command-", 1)[-1].casefold() if name.startswith("command-") else None
            relevant_kind = (name in _MATERIAL_EVENTS or
                             kind in _MATERIAL_COMMANDS)
            if not relevant_kind:
                continue
            if start <= dt <= end:
                material.append({
                    "read": read, "name": name, "date": str(event.get("date"))[:64],
                })
            elif kind in _MATERIAL_COMMANDS:
                unrelated_command_rows += 1
                if dt > end:
                    later_command_rows += 1
    if not scoped_reads:
        return None
    # Avoid leaking hundreds of rows into model context.
    return {
        "target_device_id": focus,
        "incident_period": {
            "start_utc_interpreted": incident.start_utc,
            "end_utc_interpreted": incident.end_utc,
            "clock_tolerance_hours": 2,
            "hub_timezone_verified": False,
        },
        "scoped_event_reads": scoped_reads[:8],
        "material_event_count": len(material),
        "material_event_examples": material[:6],
        "outside_incident_command_rows": unrelated_command_rows,
        "later_command_rows": later_command_rows,
        "incident_answer_evidence_present": bool(material),
        "limits": ("Absence of material events in the bounded return is not "
                   "proof that the events did not happen."),
    }


def natural_incident_gap_answer(
    question: str,
    witnesses: Sequence[Mapping[str, Any]],
    name_lookups: Sequence[Mapping[str, Any]],
    focus_ids: Sequence[str],
) -> tuple[str, dict[str, Any]] | None:
    """Return a useful, name-first missing-evidence answer, never raw IDs."""
    coverage = dated_incident_evidence(question, witnesses, focus_ids)
    if not coverage or coverage["incident_answer_evidence_present"]:
        return None
    name = "the device"
    for lookup in name_lookups:
        if (lookup.get("status") == "unique"
                and isinstance(lookup.get("query"), str)
                and lookup["query"].strip()):
            name = lookup["query"].strip()[:100]
            break
    answer = (
        f"**I couldn't determine why {name} behaved that way during "
        "the period you asked about.** The returned history did not "
        "include relevant state changes or commands from that period. "
        "I can't reliably tell which control or sensor kept it active.")
    if coverage["later_command_rows"]:
        answer += (
            " The command counts shown in the technical results include "
            "activity from later dates, which does not explain this incident.")
    answer += (
        " The next useful check is the controlling automation's "
        "execution history alongside the relevant sensor events.")
    return answer, coverage


__all__ = ["dated_incident_evidence", "natural_incident_gap_answer"]
