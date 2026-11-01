"""Stage 8.8: deterministic evidence-first summary of ONE bounded archive read.

This is not AI, full-history certification, physical proof, or automation
attribution. It is computed only from the safe Stage 8.3/8.7 projection.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def summarize_bounded_archive(projection: dict[str, Any]) -> dict[str, Any]:
    """Return privacy-minimal, source-typed findings without making a new read."""
    if not isinstance(projection, dict) or projection.get("schema") != "homebrain-live-shadow-journal.v1":
        return {
            "schema": "homebrain-stage88-archive-brief.v1",
            "status": "invalid_source_projection",
            "findings": [],
            "historical_cause_established": False,
            "physical_outcome_verified": False,
            "production_publisher_approved": False,
            "additional_reads": 0,
            "cloud_requests": 0,
        }
    events = projection.get("events")
    if not isinstance(events, list):
        events = []
    states = [row for row in events if isinstance(row, dict)
              and row.get("record_kind", "reported_state_observation") == "reported_state_observation"]
    commands = [row for row in events if isinstance(row, dict)
                and row.get("record_kind") == "archived_native_command_record"]
    timed_states = []
    for row in states:
        raw = row.get("source_time_utc")
        if not isinstance(raw, str):
            continue
        try:
            dt = datetime.fromisoformat(raw)
        except (ValueError, TypeError):
            continue
        if dt.tzinfo is not None:
            timed_states.append((dt, row))
    timed_states.sort(key=lambda pair: pair[0])
    latest = timed_states[-1][1] if timed_states else None
    temporal = projection.get("temporal_integrity")
    temporal = temporal if isinstance(temporal, dict) else {}
    readthrough_count = sum(
        row.get("origin_class") == "native_history_readthrough_not_device_ack"
        for row in states
    )
    source_rows = len(states) + len(commands)
    findings = []
    if projection.get("status") != "bounded_archive_evidence":
        findings.append(
            "The bounded local archive read did not return a usable evidence page; "
            "this is not a finding of device inactivity."
        )
    else:
        findings.append(
            f"The local archive returned {source_rows} allowlisted observations for "
            "the selected device: "
            f"{len(states)} reported states and {len(commands)} "
            "native-history command records."
        )
        if latest is not None:
            attribute = latest.get("attribute")
            val = latest.get("reported_value")
            stamp = latest.get("source_time_utc")
            if attribute in ("switch", "motion", "presence", "level", "power") and type(val) in (str, int, float):
                findings.append(
                    f"The latest declared source-time state in this returned page "
                    f"is {attribute}={val} at {stamp}. This is a reported "
                    "observation, not proof of when the physical device changed."
                )
        if readthrough_count:
            findings.append(
                f"{readthrough_count} state observations were recovered by an "
                "earlier native-history read, not authenticated as new physical "
                "device contact when the journal stored them."
            )
        if not commands:
            findings.append(
                "No app-identifiable native command records appear in this "
                "bounded archive page. That does not prove no command was issued."
            )
        else:
            issuers = sorted({
                row["recorded_issuer_app_id"]
                for row in commands
                if isinstance(row.get("recorded_issuer_app_id"), str)
                and row["recorded_issuer_app_id"].isascii()
                and row["recorded_issuer_app_id"].isdecimal()
            })
            findings.append(
                f"{len(commands)} archived command records identify "
                f"{len(issuers)} distinct numeric issuing app IDs. "
                "Those records establish recorded command provenance only, "
                "not device receipt or actuation."
            )
        late = temporal.get("events_with_source_older_than_receipt_by_over_one_day")
        if type(late) is int and late > 0:
            findings.append(
                f"{late} returned observations have declared source timestamps "
                "more than one day before journal receipt. Replay, read-through "
                "collection and clock discrepancies cannot be distinguished "
                "by timestamp separation alone."
            )
        if projection.get("archive_has_more") is True or projection.get("archive_page_limit_reached") is True:
            findings.append(
                "The bounded archive page may be truncated; it does not "
                "establish the oldest or newest event in the complete history."
            )
        gaps = projection.get("collection_gaps")
        if isinstance(gaps, list) and gaps:
            findings.append(
                f"The journal reported {len(gaps)} collector gap intervals in "
                "this returned window. These do not certify coverage of the "
                "earlier incident."
            )
    verdict = (
        "The selected archive read does not establish which automation caused "
        "a reported state or connectivity loss. The original incident remains "
        "unattributed on these records."
    )
    next_step = (
        "For a past incident, seek an independently preserved, contemporaneous "
        "command or app-decision record with target and issuer, plus a "
        "command-correlated acknowledgement if physical execution matters. "
        "If none remains, keep the cause unresolved instead of repeating "
        "the same empty historical query."
    )
    return {
        "schema": "homebrain-stage88-archive-brief.v1",
        "status": "bounded_evidence_summary" if projection.get("status") == "bounded_archive_evidence" else "insufficient_archive_source",
        "findings": findings,
        "conclusion": verdict,
        "next_evidence": next_step,
        "source_scope": "this one retained, allowlisted, target-scoped archive page",
        "history_complete": False,
        "historical_cause_established": False,
        "physical_outcome_verified": False,
        "source_clock_authenticated": False,
        "production_publisher_approved": False,
        "additional_reads": 0,
        "cloud_requests": 0,
        "device_commands": 0,
    }


__all__ = ["summarize_bounded_archive"]
