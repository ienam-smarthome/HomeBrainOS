"""Generic upstream-evidence frontier for source-scoped historical investigations.

Device histories identify source-reported transitions and commands, not which
external motion sensor, controller, scene or automation originally caused them.
This module audits what categories of independent evidence have actually been
read; it never selects, authorises or executes a tool, nor invents input IDs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .temporal_scope import explicit_incident_window

_INPUTS = frozenset(("motion", "presence", "occupancy", "contact"))
_COMMANDS = frozenset(("command-on", "command-setLevel", "command-toggle"))


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def upstream_evidence_frontier(
    witnesses: Sequence[Mapping[str, Any]], focus_ids: Sequence[str],
    question: str = "",
) -> dict[str, Any] | None:
    """Detect missing upstream corroboration from actual, typed READ receipts.

    Activate only after at least two independently scoped target histories
    contain material state observations. No question-word routing: the
    evidence configuration, not a phrase such as 'why', activates the gap.
    """
    focus = {str(x) for x in focus_ids if str(x).isdecimal()}
    if not focus:
        return None
    incident = explicit_incident_window(question, zone_name="UTC") if question else None
    target_reads: set[str] = set()
    inputs: dict[str, int] = {}
    target_on: list[dict[str, Any]] = []
    logs: list[int] = []
    configs: list[int] = []
    for witness in witnesses[:32]:
        op = witness.get("operation")
        read = witness.get("read")
        if type(read) is not int:
            continue
        filters = witness.get("read_filters")
        filters = filters if isinstance(filters, Mapping) else {}
        ident = str(filters.get("deviceId") or "")
        source = witness.get("source_data")
        if not isinstance(source, Mapping):
            continue
        if op == "hub_get_logs":
            logs.append(read)
            continue
        if op == "hub_get_app_config":
            configs.append(read)
            continue
        if op != "hub_list_device_events":
            continue
        events = source.get("events")
        if not isinstance(events, list):
            continue
        if ident not in focus:
            if ident.isdecimal() and any(
                    isinstance(e, Mapping) and e.get("name") in _INPUTS
                    and _timestamp(e.get("date")) is not None
                    for e in events[:100]):
                inputs[ident] = read
            continue
        observed = [e for e in events[:100] if isinstance(e, Mapping)
                    and _timestamp(e.get("date")) is not None
                    and (incident is None or incident.contains(e.get("date")))]
        if any(e.get("name") == "switch" for e in observed):
            target_reads.add(ident)
        commands = [e for e in observed if e.get("name") in _COMMANDS
                    and isinstance(e.get("producedBy"), Mapping)
                    and str(e["producedBy"].get("appId") or "").isdecimal()]
        for e in observed:
            if e.get("name") != "switch" or str(e.get("value") or "").lower() != "on":
                continue
            instant = _timestamp(e["date"])
            preceding = any(
                0 <= (instant - _timestamp(c["date"])).total_seconds() <= 2
                for c in commands)
            target_on.append({
                "read": read, "device_id": ident, "date": e["date"],
                "matching_preceding_on_or_level_command_in_sample": preceding,
            })
    if len(target_reads) < 2 or not target_on:
        return None
    # A target device's event stream and a current app-settings page are NOT
    # independent sensor history or app execution decision logs.
    missing = []
    if not inputs:
        missing.append("independent_input_sensor_history")
    if not logs:
        missing.append("historical_execution_or_hub_logs")
    if not missing:
        return None
    unpaired = [x for x in target_on if not x[
        "matching_preceding_on_or_level_command_in_sample"]]
    return {
        "status": "upstream_evidence_gap",
        "verified_target_device_ids": sorted(target_reads),
        "reported_on_observations": len(target_on),
        "reported_on_without_preceding_issuer_command_in_returned_samples": len(unpaired),
        "examples": unpaired[:5],
        "independent_input_history_read_ids": sorted(inputs.values()),
        "execution_log_read_ids": sorted(logs),
        "configuration_metadata_read_ids": sorted(configs),
        "missing_evidence_classes": missing,
        "recommended_model_choices": [
            "Resolve relevant input devices from verified room or dependency "
            "membership, then choose independently permitted input event reads.",
            "Inspect a source-attested controlling app's incident-time INFO "
            "execution logs and relevant hub events/mode timeline.",
            "Where no Hubitat ON command is present in the bounded sample, "
            "consider a controller outside Hubitat as a hypothesis only; "
            "do not claim Home Assistant, Hue, Aqara, or SmartThings caused it "
            "without independent traces.",
        ],
        "read_execution": "model_chosen_live_read_only; host_does_not_execute_hint",
        "limits": "A missing event in capped history does not prove it never "
                  "occurred. Correlated sensor and switch timestamps are not "
                  "proof of physical causality or an automation's internal decision.",
    }


__all__ = ["upstream_evidence_frontier"]
