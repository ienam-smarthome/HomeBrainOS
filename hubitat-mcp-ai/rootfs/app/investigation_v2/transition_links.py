"""Source-grounded incident relationships shared by planning, retrieval and reports.

A temporal relationship is a reason to INVESTIGATE, not evidence of physical
execution or causation. Work only from canonical typed case-file observations.
No device names, automation keywords, write tools or inferred source actors.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from .evidence import CaseFile, EvidenceItem

ADVERSE_ACTIONS = frozenset({"healthStatus", "networkStatus", "deviceHealth"})


@dataclass(frozen=True)
class IncidentLink:
    command: EvidenceItem
    reported_state: EvidenceItem | None
    adverse_state: EvidenceItem
    seconds_to_adverse: float


def _seconds(before: EvidenceItem, after: EvidenceItem) -> float:
    return (datetime.fromisoformat(after.timestamp_utc)
            - datetime.fromisoformat(before.timestamp_utc)).total_seconds()


def incident_links(
    case: CaseFile, *, max_state_seconds: float = 60,
    max_adverse_seconds: float = 600,
) -> list[IncidentLink]:
    """Link event-attested commands with subsequent SAME-target observations.

    Return candidates sorted by incident time. Missing a matching report is
    not evidence that no command executed. Network/MQTT client connected
    status is not treated as independent physical-device health.
    """
    records = case.records
    reports = [r for r in records if r.stage == "state_reported" and r.target_id]
    output: list[IncidentLink] = []
    for cmd in records:
        if cmd.stage != "command_issued" or not cmd.target_id:
            continue
        adverse = [
            r for r in reports if r.target_id == cmd.target_id
            and r.action in ADVERSE_ACTIONS
            and str(r.value).lower() in ("offline", "disconnected", "stale")
            and 0 <= _seconds(cmd, r) <= max_adverse_seconds
        ]
        if not adverse:
            continue
        bad = min(adverse, key=lambda r: r.timestamp_utc)
        expected = ("off" if cmd.action == "command-off" else
                    "on" if cmd.action == "command-on" else None)
        confirming = [
            r for r in reports if expected is not None
            and r.target_id == cmd.target_id
            and r.action == "switch" and r.value == expected
            and 0 <= _seconds(cmd, r) <= max_state_seconds
        ]
        state = min(confirming, key=lambda r: r.timestamp_utc) if confirming else None
        output.append(IncidentLink(cmd, state, bad, _seconds(cmd, bad)))
    return sorted(output, key=lambda item: (
        item.command.timestamp_utc, item.adverse_state.timestamp_utc))


__all__ = ["IncidentLink", "incident_links"]
