"""Read-only evidence recovery immediately outside an empty recent event window.

A natural-language causal investigation is not answered simply by empty native
Hubitat event pages. With independently verified target identities, inspect a
small adjacent Historical Journal window and distinguish the requested
period from activity immediately before its boundary. This module is not
a tool router: it executes only an existing, time-bounded local journal read.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from group_journal_recovery import journal_incident_bounds
from unified_investigation_bridge import _attested_targets, _args, _valid_source_rows, _time


def _iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _native_switch_evidence(
    receipts: Sequence[Mapping[str, Any]], targets: Mapping[str, str],
    since: datetime, until: datetime,
) -> set[str]:
    """Cross-check native history and independently derived interval receipts.

    A missing low-level row projection cannot erase a confirmed native
    interval. Accept only scoped, successful, non-mutating observations.
    """
    observed: set[str] = set()
    for receipt in receipts:
        if receipt.get("success") is not True or receipt.get("mutates") is True:
            continue
        args = _args(receipt)
        details = receipt.get("details")
        if receipt.get("sub_tool") == "hub_list_device_events":
            ident = str(args.get("deviceId") or "")
            if ident not in targets:
                continue
            for event in _valid_source_rows(receipt):
                when = _time(event.get("date"))
                if (when is not None and since <= when <= until
                        and event.get("name") == "switch"
                        and str(event.get("value") or "").lower() in ("on", "off")):
                    observed.add(ident)
        if receipt.get("evidence_kind") != "deterministic_device_event_history":
            continue
        if not isinstance(details, Mapping):
            continue
        name = details.get("label")
        ids = [ident for ident, label in targets.items() if label == name]
        temporal = details.get("temporalAnalysis")
        if len(ids) != 1 or not isinstance(temporal, Mapping):
            continue
        for interval in (temporal.get("observedIntervals") or [])[:100]:
            if not isinstance(interval, Mapping):
                continue
            for key in ("start", "end"):
                when = _time(interval.get(key))
                if when is not None and since <= when <= until:
                    observed.add(ids[0])
    return observed


def _all_native_histories_empty(
    receipts: Sequence[Mapping[str, Any]], targets: Mapping[str, str],
    since: datetime, until: datetime,
) -> bool:
    """Require a device-specific *successful* native read for every target.

    A broad hub-logs query and a currently-OFF device attribute never prove
    inactivity. Even a source read returning 0 events proves only that a
    particular query returned no observations.
    """
    if _native_switch_evidence(receipts, targets, since, until):
        return False
    seen: set[str] = set()
    for receipt in receipts:
        if (receipt.get("tool") != "hub_read_devices"
                or receipt.get("sub_tool") != "hub_list_device_events"
                or receipt.get("success") is not True
                or receipt.get("mutates") is True):
            continue
        ident = str(_args(receipt).get("deviceId") or "")
        if ident not in targets:
            # A device history read without an independently resolved
            # identity could be another requested target. Do not silently
            # treat the surviving two identities as a complete three-light
            # investigation. Sensor/other unverified histories remain in
            # original model evidence but do not justify this shortcut.
            if ident.isdecimal():
                return False
            continue
        seen.add(ident)
        for event in _valid_source_rows(receipt):
            when = _time(event.get("date"))
            if (when is not None and since <= when <= until
                    and event.get("name") == "switch"
                    and str(event.get("value") or "").lower() in ("on", "off")):
                return False
    return bool(targets) and seen >= set(targets)


async def recover_recent_edge(
    *, journal: Any, recorder: Any, receipts: Sequence[Mapping[str, Any]],
    question: str, max_edge_minutes: int = 15,
) -> dict[str, Any]:
    result = {"status": "not-needed", "attempted": 0,
              "edge_events": 0, "in_window_events": 0}
    if not (journal and getattr(journal, "enabled", False)
            and getattr(journal, "_started", False)):
        result["status"] = "journal-unavailable"
        return result
    # Only explicit recent windows; fixed older date requests are not
    # silently expanded outside the dates the user specified.
    from group_journal_recovery import _RECENT
    if not _RECENT.search(question):
        result["status"] = "not-recent-query"
        return result
    scope = journal_incident_bounds(question, receipts)
    targets = _attested_targets(receipts, question)
    if scope is None or len(targets) < 2 or len(targets) > 5:
        result["status"] = "unverified-scope-or-target"
        return result
    strict_since, strict_until, _ = scope
    begin, end = _iso(strict_since), _iso(strict_until)
    if not _all_native_histories_empty(receipts, targets, begin, end):
        result["status"] = "native-switch-history-present-or-unchecked"
        return result
    edge = begin - timedelta(minutes=max(1, min(15, max_edge_minutes)))
    already = {str((r.get("arguments") or {}).get("device_id") or "")
               for r in receipts if r.get("evidence_kind") == "recent_edge_switch_context"}
    for device_id, label in sorted(targets.items()):
        if device_id in already:
            continue
        request = {
            "device_id": device_id, "attribute": "switch",
            "since": edge.isoformat(), "until": end.isoformat(), "limit": 100,
        }
        started = asyncio.get_running_loop().time()
        result["attempted"] += 1
        try:
            answer = await asyncio.to_thread(journal.query, **request)
            events: list[dict[str, Any]] = []
            for row in (answer.get("events") or [])[:100]:
                if (not isinstance(row, Mapping)
                        or row.get("stream") != "events"
                        or str(row.get("device_id") or "") != device_id
                        or row.get("attribute") != "switch"
                        or str(row.get("value") or "").lower() not in ("on", "off")
                        or row.get("timestamp_basis") not in ("source", "collector-received")):
                    continue
                stamp = _time(row.get("observed_at"))
                if stamp is None or not edge <= stamp <= end:
                    continue
                position = "requested-window" if stamp >= begin else "before-window"
                result["in_window_events" if position == "requested-window" else "edge_events"] += 1
                events.append({
                    "date": stamp.isoformat(), "value": str(row["value"]).lower(),
                    "timestamp_basis": row["timestamp_basis"],
                    "position": position, "device_id": device_id,
                    "label": label,
                })
            recorder.record(
                "homebrain_evidence_journal", request,
                success=True, effect="read", mutates=False,
                elapsed_ms=round((asyncio.get_running_loop().time()-started)*1000),
                supports_live_claim=bool(events),
                evidence_kind="recent_edge_switch_context",
                summary="Adjacent-source check for " + label
                        + ": " + str(len(events)) + " observed journal switch rows",
                details={
                    "deviceId": device_id, "label": label,
                    "observations": events,
                    "requestedWindow": {"since": begin.isoformat(), "until": end.isoformat()},
                    "edgeWindow": {"since": edge.isoformat(), "until": begin.isoformat()},
                    "gapCount": len(answer.get("gaps") or []),
                    "truncated": bool(answer.get("truncated") or answer.get("has_more")),
                    "coverageComplete": False, "emptyProvesNoActivity": False,
                })
        except (ValueError, TypeError, OSError, RuntimeError) as exc:
            result["errors"] = result.get("errors", 0) + 1
            recorder.record(
                "homebrain_evidence_journal", request, success=False,
                effect="read", mutates=False, elapsed_ms=0,
                supports_live_claim=False,
                evidence_kind="recent_edge_switch_context",
                summary="Adjacent journal source unavailable: " + type(exc).__name__,
                details={"deviceId": device_id, "coverageComplete": False},
            )
    result["status"] = "checked" if result["attempted"] else "already-checked"
    return result


def render_recent_edge(
    receipts: Sequence[Mapping[str, Any]], question: str,
) -> str | None:
    """Summarise state changes without fabricating sensor or app causes."""
    targets = _attested_targets(receipts, question)
    if len(targets) < 2:
        return None
    observations: list[dict[str, Any]] = []
    gaps = 0
    checked: set[str] = set()
    for receipt in receipts:
        if (receipt.get("evidence_kind") != "recent_edge_switch_context"
                or receipt.get("success") is not True
                or receipt.get("mutates") is True):
            continue
        details = receipt.get("details")
        if not isinstance(details, Mapping):
            continue
        ident = str(details.get("deviceId") or "")
        if ident not in targets:
            continue
        checked.add(ident)
        gap = details.get("gapCount")
        if type(gap) is int and gap > 0:
            gaps += gap
        for row in (details.get("observations") or [])[:100]:
            if (not isinstance(row, Mapping)
                    or str(row.get("device_id") or "") != ident
                    or row.get("position") not in ("before-window", "requested-window")
                    or row.get("timestamp_basis") not in ("source", "collector-received")):
                continue
            if _time(row.get("date")) is not None:
                observations.append(dict(row))
    if len(checked) != len(targets) or not observations:
        return None
    # Prefer original source-event timestamps; collector-received copies
    # within four seconds of the same device/state do not count twice.
    source = [r for r in observations if r["timestamp_basis"] == "source"]
    collector = [r for r in observations if r["timestamp_basis"] == "collector-received"]
    verified = sorted(source, key=lambda x: (_time(x["date"]), x["device_id"]))
    unpaired = [
        c for c in collector
        if not any(c["device_id"] == s["device_id"]
                   and c["value"] == s["value"]
                   and 0 <= (_time(c["date"])-_time(s["date"])).total_seconds() <= 4
                   for s in source)
    ]
    prior = [r for r in verified if r["position"] == "before-window"]
    inside = [r for r in verified if r["position"] == "requested-window"]
    if not prior and not inside and not unpaired:
        return None
    edges = prior[-30:] + inside[:30]
    groups: list[list[dict[str, Any]]] = []
    for row in edges:
        if (groups and row["value"] == groups[-1][0]["value"]
                and row["position"] == groups[-1][0]["position"]
                and row["device_id"] not in {e["device_id"] for e in groups[-1]}
                and 0 <= (_time(row["date"])-_time(groups[-1][0]["date"])).total_seconds() <= 2):
            groups[-1].append(row)
        else:
            groups.append([row])
    table = []
    for group in groups:
        names = ", ".join(r["label"] for r in group)
        table.append("| " + _time(group[0]["date"]).strftime("%H:%M:%S")
                     + " | " + names + " | " + group[0]["value"].upper()
                     + " | " + ("Before requested window" if group[0]["position"] == "before-window"
                               else "Inside requested window") + " |")
    strict_scope = journal_incident_bounds(question, receipts)
    native = set()
    if strict_scope is not None:
        native = _native_switch_evidence(receipts, targets,
                                         _iso(strict_scope[0]), _iso(strict_scope[1]))
    header = (
        "**Requested period:** "
        + ("Native device histories already contain switch observations for "
           + ", ".join(targets[i] for i in sorted(native))
           + ". The Historical Journal provides additional context, not the "
             "sole evidence of activity."
           if native else
           "The native switch-history reads did not establish source-timed "
           "switch transitions for the verified target set. The journal "
           "provides separate observations; absence in one source does not "
           "prove inactivity.")
        + (" Source-timed journal switch events were found inside the "
           "requested period." if inside else
           " No source-timed journal switch events were found inside the "
           "requested period.")
    )
    prior_note = (
        "\n\n**Immediately before the window:** Independently "
        "source-timestamped changes were recovered in the preceding "
        "15 minutes. These events are context, **not** activity inside "
        "the requested two-hour period." if prior else ""
    )
    caveat = (
        "\n\n" + str(len(unpaired)) + " additional collector-received "
        "observation(s) are not included as precise event times."
        if unpaired else ""
    )
    return (
        header + prior_note + "\n\n"
        "| UTC | Light | Switch report | Period |\n|---|---|---|---|\n"
        + "\n".join(table) + caveat
        + "\n\n**Cause remains unverified:** These are light-state reports, "
          "not sensor or automation execution records. Check the relevant "
          "motion/occupancy histories and controller decisions before "
          "identifying an initiator. Journal connection gaps: "
        + str(gaps) + " (counts may include the same shared outage across devices)."
    )


__all__ = ["recover_recent_edge", "render_recent_edge"]
