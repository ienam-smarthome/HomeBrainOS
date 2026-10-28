"""General, typed causal-evidence associations; NEVER a root-cause oracle.

A command-off immediately followed by switch=off attests a command and a
separate reported transition. It does not prove physical actuation, that an
automation's internal logic evaluated true, or complete command history.
No Hubitat IDs, names, device kinds, or question wording are hardcoded.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .evidence import CaseFile, EvidenceItem


@dataclass(frozen=True)
class CommandStatePair:
    command_record_id: str
    state_record_id: str
    device_id: str
    issuer_app_id: str | None
    state_reporter_id: str | None
    command_utc: str
    state_utc: str
    interval_ms: int
    relation: str = "command_precedes_report"
    physical_action_verified: bool = False
    internal_rule_decision_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def command_state_pairs(
    case: CaseFile, *, max_interval_seconds: float = 2.0,
) -> list[CommandStatePair]:
    """One-to-one link for same-device OFF/ON command and later reported state.

    Rejects wrong target, unknown switch value, non-source clocks, reverse
    chronology, gaps longer than the bound and reused state observations.
    Purely source-time-temporal association, never inferred causality.
    """
    if not isinstance(max_interval_seconds, (int, float)) or not (
        0 <= max_interval_seconds <= 60
    ):
        raise ValueError("Command/state interval must be between 0 and 60 seconds")
    reports = [
        r for r in case.records
        if (r.stage == "state_reported" and r.action == "switch"
            and r.target_id and r.time_basis == "event_time"
            and str(r.value).lower() in ("on", "off"))
    ]
    used: set[str] = set()
    pairs: list[CommandStatePair] = []
    for cmd in case.records:
        if (cmd.stage != "command_issued" or cmd.time_basis != "event_time"
                or cmd.target_id is None
                or cmd.action not in ("command-on", "command-off")):
            continue
        expected = cmd.action.removeprefix("command-")
        command_at = datetime.fromisoformat(cmd.timestamp_utc)
        compatible: list[tuple[float, EvidenceItem]] = []
        for state in reports:
            if (state.record_id in used or state.target_id != cmd.target_id
                    or str(state.value).lower() != expected):
                continue
            delta = (datetime.fromisoformat(state.timestamp_utc)
                     - command_at).total_seconds()
            if 0 <= delta <= max_interval_seconds:
                compatible.append((delta, state))
        if not compatible:
            continue
        seconds, report = min(
            compatible, key=lambda item: (item[0], item[1].record_id))
        used.add(report.record_id)
        pairs.append(CommandStatePair(
            command_record_id=cmd.record_id,
            state_record_id=report.record_id,
            device_id=cmd.target_id,
            issuer_app_id=cmd.producer_id,
            state_reporter_id=report.producer_id,
            command_utc=cmd.timestamp_utc,
            state_utc=report.timestamp_utc,
            interval_ms=round(seconds * 1000),
        ))
    return pairs


def command_history_coverage(case: CaseFile, device_id: str) -> dict[str, Any]:
    """Source-scoped command-history availability, never absence of commands."""
    pages = [
        c for c in case.coverage
        if c.operation == "hub_list_device_events" and c.query_target_id == device_id
    ]
    filtered = [c for c in pages if c.succeeded
                and c.requested_filters.get("attribute") == "switch"]
    unfiltered = [c for c in pages if c.succeeded and "attribute" not in c.requested_filters]
    observed_commands = sum(
        r.stage == "command_issued" and r.target_id == device_id
        for r in case.records
    )
    reasons: list[str] = []
    if filtered and not unfiltered:
        reasons.append("command_events_excluded_by_filter")
    if not unfiltered:
        reasons.append("unfiltered_command_history_not_observed")
    elif not any(c.source_complete is True for c in unfiltered):
        reasons.append("command_history_source_completeness_unverified")
    if not pages:
        reasons.append("device_history_not_read")
    return {
        "device_id": device_id,
        "filtered_read_count": len(filtered),
        "unfiltered_read_count": len(unfiltered),
        "observed_command_records": observed_commands,
        "unfiltered_source_complete": any(c.source_complete is True for c in unfiltered),
        "issues": reasons,
        "no_command_proven": False,  # A zero count in a bounded page is not global absence.
    }


def causal_evidence_bundle(case: CaseFile, device_id: str) -> dict[str, Any]:
    """Machine-readable input to native tools, replay scoring and explanation."""
    if not isinstance(device_id, str) or not device_id.isdecimal():
        raise ValueError("A host-verified numeric device identity is required")
    return {
        "contract_version": 1,
        "target_id": device_id,
        "command_state_pairs": [
            pair.to_dict() for pair in command_state_pairs(case)
            if pair.device_id == device_id
        ],
        "command_history": command_history_coverage(case, device_id),
        "causal_verdict": "not_established",
        "source_complete": False,
        "physical_action_verified": False,
    }


__all__ = [
    "CommandStatePair", "command_state_pairs",
    "command_history_coverage", "causal_evidence_bundle",
]
