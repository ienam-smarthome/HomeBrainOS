"""Bounded read-only Historical Journal recovery for multi-device investigations.

The original HomeBrain agent owns reasoning/tool choice. This component is a
source-integrity recovery step when its verified target histories contain
commands/levels but lack incident-time switch-state observations. Journal
records retain collector reception vs independently timestamped event status.
No writes, external service access, invented IDs or claims of full coverage.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, time, timedelta
import re
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from investigation_v2.temporal_scope import explicit_incident_window
from unified_investigation_bridge import collect_unified_evidence

_CLOCK = re.compile(
    r"\b(?:between|from)\s+(\d{1,2}):(\d{2})\s*"
    r"(?:and|to|[-–])\s*(\d{1,2}):(\d{2})\b", re.I
)
_HUB_ZONE = re.compile(r"\b(?:timezone|time zone)\s+([A-Za-z_]+/[A-Za-z_]+)\b", re.I)
_RECENT = re.compile(
    r"\b(?:during|in|over|within|for)?\s*(?:the\s+)?"
    r"(?:last|past)\s+(\d{1,2}|one|two|three|four|six|twelve|twenty-four)"
    r"\s+(minutes?|hours?)\b", re.I
)
_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4,
                 "six": 6, "twelve": 12, "twenty-four": 24}



def _verified_zone(receipts: Sequence[Mapping[str, Any]], question: str) -> str | None:
    # Explicit GMT/UTC wording is independently adequate for absolute times.
    if re.search(r"\b(?:GMT|UTC)\b", question, re.I):
        return "UTC"
    for receipt in receipts:
        if (receipt.get("success") is True
                and receipt.get("evidence_kind") == "authoritative_hub_timezone"):
            match = _HUB_ZONE.search(str(receipt.get("summary") or ""))
            if match:
                try:
                    ZoneInfo(match.group(1))
                    return match.group(1)
                except (ValueError, KeyError):
                    pass
    return None


def journal_incident_bounds(
    question: str, receipts: Sequence[Mapping[str, Any]]
) -> tuple[str, str, str] | None:
    """Require explicit date + verified UTC or hub timezone, never guess."""
    recent = _RECENT.search(question)
    if recent:
        count = _WORD_NUMBERS.get(recent.group(1).casefold())
        if count is None:
            count = int(recent.group(1))
        seconds = count * (3600 if recent.group(2).lower().startswith("hour") else 60)
        if not 60 <= seconds <= 48 * 3600:
            return None
        end = datetime.now(timezone.utc)
        start = end - timedelta(seconds=seconds)
        return start.isoformat(), end.isoformat(), "UTC"
    zone_name = _verified_zone(receipts, question)
    if not zone_name:
        return None
    incident = explicit_incident_window(question, zone_name=zone_name)
    if incident is None or incident.interpretation.startswith(("today:", "yesterday:")):
        return None
    start = datetime.fromisoformat(incident.start_utc)
    end = datetime.fromisoformat(incident.end_utc)
    match = _CLOCK.search(question)
    if match:
        a, b, c, d = map(int, match.groups())
        if a >= 24 or c >= 24 or b >= 60 or d >= 60:
            return None
        zone = ZoneInfo(zone_name)
        day = start.astimezone(zone).date()
        start = datetime.combine(day, time(a, b), tzinfo=zone).astimezone(timezone.utc)
        end = datetime.combine(day, time(c, d), tzinfo=zone).astimezone(timezone.utc)
    if not start < end or (end-start).total_seconds() > 86400*8:
        return None
    return start.isoformat(), end.isoformat(), zone_name


async def recover_group_journal(
    *, journal: Any, recorder: Any,
    question: str, receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Query at most five independently name-resolved, missing switch targets.

    Does not retry completed journal reads or query an unscoped log stream.
    Uses the source journal's read-only query method; records explicit empty,
    truncated, and gap-bearing results rather than inferring inactivity.
    """
    report: dict[str, Any] = {
        "status": "not-needed", "attempted": 0, "source_observations": 0,
        "collector_observations": 0, "journal_gaps": 0,
    }
    facts = collect_unified_evidence(receipts, question)
    if facts is None:
        report["status"] = "no-verified-multi-target-evidence"
        return report
    missing = set(facts["missing_switch_history_for_targets"])
    if not missing:
        return report
    if journal is None or not getattr(journal, "enabled", False) or not getattr(journal, "_started", False):
        report["status"] = "journal-unavailable"
        return report
    scope = journal_incident_bounds(question, receipts)
    if scope is None:
        report["status"] = "incident-timezone-or-date-unverified"
        return report
    since, until, zone_name = scope
    report.update(status="checked", window={"since": since, "until": until, "zone": zone_name})
    existing = {
        str((r.get("arguments") or {}).get("device_id") or "")
        for r in receipts if r.get("evidence_kind") == "group_archived_switch_history"
    }
    for item in facts["target_coverage"][:5]:
        ident = str(item.get("device_id") or "")
        if (item.get("device_name") not in missing or not ident.isdecimal()
                or ident in existing):
            continue
        request = {"device_id": ident, "since": since, "until": until,
                   "attribute": "switch", "limit": 100}
        started = asyncio.get_running_loop().time()
        report["attempted"] += 1
        try:
            response = await asyncio.to_thread(journal.query, **request)
            entries = response.get("events") or []
            observations = []
            for row in entries[:100]:
                if (not isinstance(row, Mapping)
                        or row.get("stream") != "events"
                        or str(row.get("device_id")) != ident
                        or row.get("attribute") != "switch"
                        or str(row.get("value") or "").lower() not in ("on", "off")):
                    continue
                basis = str(row.get("timestamp_basis") or "")
                when = row.get("observed_at")
                if (basis not in ("source", "collector-received")
                        or not isinstance(when, str)):
                    continue
                try:
                    dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        continue
                except ValueError:
                    continue
                observations.append({
                    "device_id": ident, "attribute": "switch",
                    "value": str(row["value"]).lower(), "date": dt.isoformat(),
                    "timestamp_basis": basis,
                    "source": str(row.get("source") or "")[:60],
                })
                if basis == "source":
                    report["source_observations"] += 1
                else:
                    report["collector_observations"] += 1
            gap_count = len(response.get("gaps") or [])
            report["journal_gaps"] += gap_count
            recorder.record(
                "homebrain_evidence_journal", request, success=True,
                elapsed_ms=round((asyncio.get_running_loop().time()-started)*1000),
                summary=f"Archive device {ident}: {len(observations)} switch observations; "
                        f"{gap_count} overlapping recorded gaps",
                supports_live_claim=bool(observations),
                evidence_kind="group_archived_switch_history",
                effect="read", mutates=False,
                details={
                    "deviceId": ident, "observations": observations,
                    "returnedObservationCount": len(observations),
                    "evidenceReceiptSampleLimit": 20,
                    "receptionPatternSummary": reception_pattern,
                    "window": {"since": since, "until": until, "zone": zone_name},
                    "gapCount": gap_count,
                    "truncated": bool(response.get("truncated") or response.get("has_more")),
                    "coverageComplete": False, "emptyProvesNoActivity": False,
                },
            )
        except (ValueError, OSError, RuntimeError, TypeError) as error:
            report["errors"] = report.get("errors", 0) + 1
            recorder.record(
                "homebrain_evidence_journal", request, success=False,
                elapsed_ms=round((asyncio.get_running_loop().time()-started)*1000),
                summary="Bounded journal read unavailable: " + type(error).__name__,
                supports_live_claim=False, evidence_kind="group_archived_switch_history",
                effect="read", mutates=False,
                details={"deviceId": ident, "coverageComplete": False,
                         "reason": type(error).__name__},
            )
    return report


def _reception_pattern_summary(
    observations: Sequence[Mapping[str, Any]],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Bounded cross-clock co-occurrence, never precise source chronology.

    Compute over the complete retrieved page *before* the request evidence
    recorder redacts arrays to 20 rows for safe API presentation.
    """
    ids = facts.get("target_device_ids") or []
    if not ids:
        return {}
    target_id = str(ids[0])
    bounds = []
    for row in (facts.get("incident_ledger") or [])[:180]:
        if (row.get("device_id") != target_id
                or row.get("event_class") not in (
                    "journal_source_switch_on", "journal_source_switch_off")):
            continue
        try:
            t = datetime.fromisoformat(str(row["date"]).replace("Z", "+00:00"))
            if t.tzinfo is not None:
                bounds.append((t.astimezone(timezone.utc),
                               "on" if row["event_class"].endswith("_on") else "off"))
        except (ValueError, TypeError):
            continue
    if not bounds:
        return {}
    input_receptions = []
    for event in observations[:200]:
        if (event.get("timestamp_basis") != "collector-received"
                or event.get("attribute") not in ("motion", "occupancy", "presence")):
            continue
        try:
            t = datetime.fromisoformat(str(event["date"]).replace("Z", "+00:00"))
            if t.tzinfo is None:
                continue
        except (ValueError, TypeError):
            continue
        input_receptions.append((t.astimezone(timezone.utc),
                                 str(event.get("value") or "").casefold()))
    on_matches = []
    off_matches = []
    for when, state in bounds:
        near = []
        for received, value in input_receptions:
            signed = (received - when).total_seconds()
            if (state == "on" and value in (
                    "active", "present", "occupied", "on", "true")
                    and abs(signed) <= 3.0):
                near.append(signed)
            elif (state == "off" and value in (
                    "inactive", "not present", "unoccupied", "off", "false")
                    and -20.0 <= signed <= 0):
                near.append(signed)
        if near:
            (on_matches if state == "on" else off_matches).append(
                round(min(near, key=abs), 3))
    return {
        "targetSourceOnCount": sum(state == "on" for _, state in bounds),
        "targetSourceOffCount": sum(state == "off" for _, state in bounds),
        "onNearActiveReceptions": len(on_matches),
        "offAfterInactiveReceptions": len(off_matches),
        "onSignedReceptionDeltasSeconds": on_matches[:8],
        "offSignedReceptionDeltasSeconds": off_matches[:8],
        "crossClockOrderVerified": False,
        "causalInitiatorVerified": False,
    }


async def recover_input_journal(
    *, journal: Any, recorder: Any,
    question: str, receipts: Sequence[Mapping[str, Any]],
    max_devices: int = 3,
) -> dict[str, Any]:
    """Recover previously queried but empty input histories from the Journal.

    Only device IDs whose individual, read-only Hubitat event history was
    independently queried and returned no usable incident-time rows are
    eligible. This is a source-recovery operation, NOT sensor discovery:
    without a real source observation, an ID is never called a sensor.
    """
    report: dict[str, Any] = {
        "status": "not-needed", "attempted": 0, "source_observations": 0,
        "collector_observations": 0, "journal_gaps": 0,
    }
    facts = collect_unified_evidence(receipts, question)
    if not facts:
        return report
    candidates = [
        str(i) for i in facts.get("additional_event_reads_without_usable_rows", [])
        if str(i).isdecimal() and int(i) > 0
    ]
    if not candidates:
        return report
    if journal is None or not getattr(journal, "enabled", False) or not getattr(journal, "_started", False):
        report["status"] = "journal-unavailable"
        return report
    scope = journal_incident_bounds(question, receipts)
    if scope is None:
        report["status"] = "incident-timezone-or-date-unverified"
        return report
    since, until, zone_name = scope
    previously_checked = {
        str((r.get("arguments") or {}).get("device_id") or "")
        for r in receipts if r.get("evidence_kind") == "group_archived_input_history"
    }
    report["status"] = "checked"
    # Query all attributes on each *independently scoped device ID*. The
    # existing journal captures motion, occupancy and presence under different
    # names; do not guess an attribute or use an unscoped room-wide read.
    for ident in candidates[:max(1, min(3, int(max_devices)))]:
        if ident in previously_checked:
            continue
        request = {
            "device_id": ident, "since": since, "until": until,
            "limit": 160,
        }
        started = asyncio.get_running_loop().time()
        report["attempted"] += 1
        try:
            response = await asyncio.to_thread(journal.query, **request)
            observations = []
            for row in (response.get("events") or [])[:160]:
                if (not isinstance(row, Mapping)
                        or row.get("stream") != "events"
                        or str(row.get("device_id") or "") != ident):
                    continue
                attribute = str(row.get("attribute") or "").casefold()
                value = str(row.get("value") or "").casefold()
                if (attribute not in ("motion", "occupancy", "presence")
                        or value not in (
                            "active", "inactive", "present", "not present",
                            "occupied", "unoccupied", "on", "off",
                            "true", "false")):
                    continue
                basis = str(row.get("timestamp_basis") or "")
                when = row.get("observed_at")
                if basis not in ("source", "collector-received") or not isinstance(when, str):
                    continue
                try:
                    stamp = datetime.fromisoformat(when.replace("Z", "+00:00"))
                    if stamp.tzinfo is None:
                        continue
                    stamp = stamp.astimezone(timezone.utc)
                    if not (datetime.fromisoformat(since) <= stamp <= datetime.fromisoformat(until)):
                        continue
                except (ValueError, OverflowError):
                    continue
                observations.append({
                    "device_id": ident, "attribute": attribute,
                    "value": value, "date": stamp.isoformat(),
                    "timestamp_basis": basis,
                    "source": str(row.get("source") or "")[:60],
                })
                if basis == "source":
                    report["source_observations"] += 1
                else:
                    report["collector_observations"] += 1
            gap_count = len(response.get("gaps") or [])
            report["journal_gaps"] += gap_count
            # The recorder bounds public observation arrays at 20. Preserve
            # deterministic counts calculated over the full returned page,
            # so a noisy input cannot hide most of its own correlations.
            reception_pattern = _reception_pattern_summary(observations, facts)
            recorder.record(
                "homebrain_evidence_journal", request, success=True,
                elapsed_ms=round((asyncio.get_running_loop().time() - started)*1000),
                summary=(
                    f"Archive input device {ident}: {len(observations)} "
                    f"observations; {gap_count} recorded gaps"
                ),
                supports_live_claim=bool(observations),
                evidence_kind="group_archived_input_history",
                effect="read", mutates=False,
                details={
                    "deviceId": ident, "observations": observations,
                    "window": {"since": since, "until": until, "zone": zone_name},
                    "gapCount": gap_count,
                    "truncated": bool(response.get("truncated") or response.get("has_more")),
                    "coverageComplete": False, "emptyProvesNoActivity": False,
                },
            )
        except (ValueError, OSError, RuntimeError, TypeError) as error:
            report["errors"] = report.get("errors", 0) + 1
            recorder.record(
                "homebrain_evidence_journal", request, success=False,
                elapsed_ms=round((asyncio.get_running_loop().time() - started)*1000),
                summary="Bounded archived input read unavailable: " + type(error).__name__,
                supports_live_claim=False,
                evidence_kind="group_archived_input_history",
                effect="read", mutates=False,
                details={"deviceId": ident, "coverageComplete": False,
                         "reason": type(error).__name__},
            )
    return report

__all__ = ["journal_incident_bounds", "recover_group_journal", "recover_input_journal"]
