"""Short, evidence-backed answers for exact single-device factual questions.

The full V2 case and source coverage remain available in Investigation details.
An event reporting source is not promoted to a controlling automation.
"""
from __future__ import annotations

from datetime import datetime
import re

from .evidence import CaseFile


def _utc(stamp: str) -> str:
    try:
        return datetime.fromisoformat(stamp).strftime("%d %b %H:%M:%S UTC")
    except (TypeError, ValueError):
        return "time unavailable"


def factual_report(case: CaseFile, objective: str, device_label: str | None) -> tuple[str, tuple[str, ...]]:
    if objective not in ("status", "history"):
        raise ValueError("Unsupported factual objective")
    label = re.sub(r"[^\w .()/-]", "", str(device_label or "Verified device"))[:85]
    snapshot = case.device_snapshots[-1] if case.device_snapshots else {}
    attrs = snapshot.get("attributes", {}) if isinstance(snapshot, dict) else {}
    attrs = attrs if isinstance(attrs, dict) else {}
    switch = attrs.get("switch")
    state = str(switch).casefold() if type(switch) is str else None
    if state not in ("on", "off"):
        state = None
    lines: list[str] = []
    displayed: list[str] = []
    if objective == "status":
        if state is None:
            lines.append(f"**{label}:** Current ON/OFF state could not be verified from the returned Hubitat device snapshot.")
        else:
            lines.append(f"**{label} is reported {state.upper()}.** This is the current Hubitat read-time switch state, not independent proof of physical operation.")
        if attrs.get("networkStatus") is not None:
            lines.append(f"Hubitat networkStatus={attrs['networkStatus']} (a reported attribute, not physical reachability proof).")
        if not case.device_snapshots:
            lines.append("The current device read did not return a usable verified snapshot.")
        return "\n\n".join(lines), ()
    switches = [row for row in case.records
                if row.stage == "state_reported" and row.action == "switch"
                and row.value in ("on", "off")]
    switches.sort(key=lambda row: row.timestamp_utc)
    if switches:
        lines.append(f"**Most recent reported ON/OFF history for {label}:**")
        for wanted in ("on", "off"):
            matches = [row for row in switches if row.value == wanted]
            if matches:
                latest = matches[-1]
                actor = f"Hubitat reporting source #{latest.producer_id}" if latest.producer_id else "unidentified reporting source"
                lines.append(f"- Last {wanted.upper()} report: **{_utc(latest.timestamp_utc)}**, {actor} (not necessarily the controlling automation).")
                displayed.append(latest.record_id)
            else:
                lines.append(f"- No {wanted.upper()} report returned in this source page; this does not establish that no such event occurred.")
        latest = switches[-1]
        lines.append(f"Latest retrieved switch report: {latest.value.upper()} at {_utc(latest.timestamp_utc)}.")
    else:
        lines.append(f"**{label}:** No timestamped ON/OFF reports were returned by the authorised history read. That does not prove no change occurred.")
    if state:
        lines.append(f"Current Hubitat read-time switch state: **{state.upper()}**; this is separate from historical events.")
    history_sources = [c for c in case.coverage if c.operation == "hub_list_device_events"]
    if not history_sources:
        lines.append("Switch-event history was not retrieved; no historical conclusion is supported.")
    elif not any(c.source_complete is True for c in history_sources):
        lines.append("Historical source completeness is unverified, even if the returned page was not truncated.")
    return "\n\n".join(lines), tuple(displayed)


__all__ = ["factual_report"]
