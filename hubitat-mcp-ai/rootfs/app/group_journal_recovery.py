"""Bounded read-only Historical Journal recovery for multi-device investigations.

The original HomeBrain agent owns reasoning/tool choice. This component is a
source-integrity recovery step when its verified target histories contain
commands/levels but lack incident-time switch-state observations. Journal
records retain collector reception vs independently timestamped event status.
No writes, external service access, invented IDs or claims of full coverage.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, time
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


__all__ = ["journal_incident_bounds", "recover_group_journal"]
