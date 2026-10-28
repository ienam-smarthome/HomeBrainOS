"""Source-first, incident-scoped explanation of a reported switch transition.

A current app sensor selection may guide investigation but does not establish
the historical effective settings, scheduling branch or physical actuation.
This module never uses names, question keywords or model-generated causes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .causal_evidence import command_state_pairs, focused_switch_command
from .evidence import CaseFile, EvidenceItem


def _moment(row: EvidenceItem) -> datetime:
    return datetime.fromisoformat(row.timestamp_utc)


def latest_switch_incident(case: CaseFile) -> dict[str, Any] | None:
    """Return a narrow, source-linked narrative and its verifiable references.

    No match means an unmatched latest switch report cannot be attributed to
    an older command. A reported command/state time pair is not execution
    evidence from the controlling app itself.
    """
    command, basis = focused_switch_command(case)
    if basis != "paired_latest_switch_transition" or command is None:
        return None
    matches = [p for p in command_state_pairs(case)
               if p.command_record_id == command.record_id]
    if not matches:
        return None
    pair = matches[0]
    reports = {r.record_id: r for r in case.records}
    report = reports.get(pair.state_record_id)
    if report is None:
        return None
    issuer = pair.issuer_app_id
    values = [
        f"**Most likely explanation (source-backed):** app #{issuer} issued "
        f"`{command.action}` at {command.timestamp_utc} UTC; device "
        f"#{pair.device_id} then reported `switch={report.value}` at "
        f"{report.timestamp_utc} UTC ({pair.interval_ms} ms later). "
        "The command issuer is verified from the device's command event; "
        "the state reporter is not the issuing controller."
    ]
    witness_ids = [command.record_id, report.record_id]
    config = [
        r for r in case.records
        if r.stage == "config_stored" and r.target_id == issuer
    ]
    inactive_action = next(
        (r for r in config if r.action == "stored-setting:inactiveAction"),
        None
    )
    if inactive_action is not None:
        values.append(
            "**Current controller configuration:** "
            f"app #{issuer} has `inactiveAction={inactive_action.value}`. "
            "This is a read-time setting, not the verified historical rule."
        )
    references = case.app_sensor_references.get(issuer or "", [])
    configured_motion = sorted({
        ident for entry in references
        if entry.get("key") in ("motionSensors", "motionSensor")
        for ident in entry.get("deviceIds", [])
        if isinstance(ident, str) and ident.isdecimal()
    }, key=int)
    moment = _moment(command)
    motion_rows = [
        r for r in case.records
        if r.stage == "state_reported" and r.action == "motion"
        and r.time_basis == "event_time"
        and r.target_id in configured_motion
        and r.value in ("inactive", "active")
        and 0 <= (moment - _moment(r)).total_seconds() <= 600
    ]
    # The last observed motion event, not an earlier convenient inactive
    # event, determines whether the available source supports inactivity.
    recent_by_id: dict[str, EvidenceItem] = {}
    for row in motion_rows:
        previous = recent_by_id.get(row.target_id or "")
        if previous is None or row.timestamp_utc > previous.timestamp_utc:
            recent_by_id[row.target_id or ""] = row
    for ident in configured_motion[:3]:
        latest = recent_by_id.get(ident)
        if latest is None:
            values.append(
                f"**Configured motion sensor #{ident}:** no motion observation "
                "within the preceding 10 minutes was recovered. This does "
                "not prove the sensor was inactive."
            )
            continue
        gap_ms = round((moment - _moment(latest)).total_seconds() * 1000)
        values.append(
            f"**Configured motion sensor #{ident}:** most recent recovered "
            f"observation before the command was `motion={latest.value}` "
            f"at {latest.timestamp_utc} UTC ({gap_ms / 1000:.3f} seconds "
            "before the command)."
        )
        witness_ids.append(latest.record_id)
    if inactive_action is not None and inactive_action.value == "off" and any(
            r.value == "inactive" for r in recent_by_id.values()):
        values.append(
            "**Interpretation:** the observed inactive motion and current "
            "inactive-off setting are consistent with a motion-controlled "
            "OFF, but do not verify the historical handler branch, "
            "timing configuration or keep-on conditions."
        )
    keep_on_ids = sorted({
        ident for entry in references
        if entry.get("key") in ("keepOnSensors", "keepOnSensor")
        for ident in entry.get("deviceIds", [])
        if isinstance(ident, str) and ident.isdecimal()
    }, key=int)
    if keep_on_ids:
        values.append(
            "**Keep-on sensor coverage:** current settings reference "
            + ", ".join("#" + x for x in keep_on_ids[:8])
            + "; the report cannot assume their historical state "
              "without timestamped observations at the incident."
        )
    if any(c.operation == "hub_get_logs" and
           c.query_target_id == issuer and not c.succeeded
           for c in case.coverage):
        values.append(
            f"**Execution log gap:** the read for app #{issuer} failed. "
            "This does not verify that its historical logs were empty "
            "or lost to a restart."
        )
    values.append(
        "**Remaining uncertainty:** physical light response, historical "
        "rule conditions and any unexplained scheduling delay are not "
        "independently verified."
    )
    return {
        "issuer_app_id": issuer,
        "target_id": pair.device_id,
        "command_id": command.record_id,
        "report_id": report.record_id,
        "interval_ms": pair.interval_ms,
        "recent_motion_observations": len(recent_by_id),
        "record_ids": witness_ids,
        "lines": values,
        "source_basis": "paired_latest_switch_transition",
        "root_cause_verified": False,
    }


__all__ = ["latest_switch_incident"]
