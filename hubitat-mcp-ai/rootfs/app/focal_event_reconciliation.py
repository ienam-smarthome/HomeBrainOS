"""Request-local reconciliation of independently scoped device event receipts.

The model receives several overlapping Hubitat history windows. A late
command-on-only query must not make an earlier source-timed command-off from a
bounded all-attribute window disappear. This module combines witnessed events
for ONE independently verified device; it writes nothing and never certifies
physical hardware operation or completeness of sampled telemetry.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Mapping


def _args(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("arguments")
    if not isinstance(raw, dict):
        return {}
    inner = raw.get("args")
    return inner if isinstance(inner, dict) else raw


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, OverflowError):
        return None
    return t.astimezone(timezone.utc) if t.tzinfo else None


def _positive_id(value: Any) -> str | None:
    text = str(value or "")
    return text if text.isdecimal() and int(text) > 0 else None


def _target(request: str, receipts: list[dict[str, Any]]) -> tuple[str, str] | None:
    matches: dict[str, str] = {}
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if (row.get("evidence_kind") != "targeted_device_lookup"
                or row.get("sub_tool") != "hub_list_devices"
                or row.get("mutates") is True
                or row.get("effect") not in (None, "read")):
            continue
        state = (row.get("details") or {}).get("reportedDeviceState")
        if not isinstance(state, dict):
            continue
        ident = _positive_id(state.get("deviceId"))
        label = str(state.get("label") or "").strip()
        if not ident or not label or len(label) > 150:
            continue
        args = _args(row)
        if str(args.get("labelFilter") or "").casefold() != label.casefold():
            continue
        pattern = r"(?<![\w-])" + re.escape(label) + r"(?![\w-])"
        found = False
        for match in re.finditer(pattern, request, re.I):
            prior = re.search(
                r"([A-Za-z][A-Za-z0-9-]*)\s+$", request[:match.start()]
            )
            if prior and prior.group(1)[0].isupper():
                continue
            found = True
        if found:
            matches[ident] = label
    if len(matches) != 1:
        return None
    return next(iter(matches.items()))


def reconcile_focal_device_events(
    request: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Combine positive events only; missing events are not absence evidence."""
    target = _target(request, receipts)
    if target is None:
        return None
    ident, label = target
    events: dict[tuple[str, str, str], dict[str, Any]] = {}
    sources: set[str] = set()
    truncated = False
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("mutates") is True or row.get("effect") not in (None, "read"):
            continue
        details = row.get("details")
        if not isinstance(details, dict):
            continue
        args = _args(row)
        sub = row.get("sub_tool")
        source = None
        if (row.get("tool") == "hub_read_devices"
                and sub == "hub_list_device_events"
                and _positive_id(args.get("deviceId")) == ident):
            source = "native-id-scoped-history"
        elif (row.get("tool") == "homebrain_device_history"
              and str(args.get("name") or "").casefold() == label.casefold()
              and str(details.get("label") or "").casefold() == label.casefold()):
            source = "label-scoped-history"
        if not source:
            continue
        # A validated scoped receipt is a bounded observation, even if the
        # returned page is incomplete, truncated or lacks command events.
        sources.add(source)
        if details.get("observedEventsTruncated") is True:
            truncated = True
        # The same authorized native gateway uses observedEvents for a
        # bounded mixed history and events for an attribute-filtered command
        # page. Both are positive witnesses; deduplicate by source time.
        raw = [
            ev
            for field in ("observedEvents", "events")
            for ev in (
                details.get(field) if isinstance(details.get(field), list) else []
            )[:200]
        ]
        for ev in raw[:400]:
            if not isinstance(ev, dict):
                continue
            when = _datetime(ev.get("date"))
            if when is None:
                continue
            name = str(ev.get("name") or "")
            if name not in ("switch", "power") and not re.fullmatch(
                r"command-[A-Za-z][\w-]{0,100}", name
            ):
                continue
            kind = "command" if name.startswith("command-") else "report"
            if kind == "command" and str(ev.get("type") or "").lower() != "command":
                continue
            value = str(ev.get("value") or "").lower()
            if name == "switch" and value not in ("on", "off"):
                continue
            if name == "power":
                try:
                    watts = float(ev.get("value"))
                    if not (0 <= watts <= 1e7):
                        continue
                except (ValueError, TypeError, OverflowError):
                    continue
                value = str(watts)
            actor = ev.get("producedBy")
            actor = actor if isinstance(actor, dict) else {}
            app_id = None
            if kind == "command":
                if str(actor.get("type") or "").lower() == "app":
                    app_id = _positive_id(actor.get("appId") or actor.get("id"))
                elif "type" not in actor:
                    # Native Hubitat command records sometimes provide
                    # producedBy.appId without producedBy.type.
                    app_id = _positive_id(actor.get("appId"))
            key = (when.isoformat(), name, value)
            item = {
                "atUtc": when.isoformat(), "name": name, "kind": kind,
                "value": value if kind == "report" else None,
                "issuerAppId": app_id,
                "issuerAppLabel": str(
                    actor.get("label") or actor.get("name") or ""
                )[:100] if app_id else None,
                "evidenceClass": "reported-command" if kind == "command"
                else "reported-measurement-or-state",
            }
            old = events.get(key)
            if old is None or (app_id and not old.get("issuerAppId")):
                events[key] = item
    if not sources:
        return None
    all_events = sorted(events.values(), key=lambda x: x["atUtc"])
    if not all_events:
        return None
    commands = [x for x in all_events if x["kind"] == "command"]
    switches = [x for x in all_events if x["name"] == "switch"]
    power = [x for x in all_events if x["name"] == "power"]
    cycle = None
    prev = None
    for report in switches:
        if report["value"] == "on":
            prev = report
        elif report["value"] == "off" and prev is not None:
            start = _datetime(prev["atUtc"])
            stop = _datetime(report["atUtc"])
            if start and stop and stop >= start:
                cycle = {
                    "reportedOnAtUtc": prev["atUtc"],
                    "reportedOffAtUtc": report["atUtc"],
                    "reportedOnDurationSeconds": round(
                        (stop - start).total_seconds(), 3
                    ),
                    "physicalOperatingDurationVerified": False,
                }
            prev = None
    # Only a bounded recent subset of observed events is sent. Project both
    # command directions independently so any single-event late read cannot
    # erase opposite-polarity source records.
    return {
        "schema": "homebrain-focal-evidence-reconciliation.v1",
        "deviceId": ident,
        "deviceLabel": label,
        "sourceClassesRead": sorted(sources),
        "sourceHistoryComplete": False,
        "truncatedSourceObserved": truncated,
        "latestCompleteReportedSwitchInterval": cycle,
        "attestedCommands": commands[-14:],
        "reportedSwitchEvents": switches[-12:],
        "reportedPowerSamples": power[-16:],
        "physicalPlantOperationVerified": False,
        "negativeClaimGuidance": (
            "This packet contains only positive records from bounded source "
            "pages. If it shows command-off, do not claim the OFF command is "
            "missing. A recent command-on-only page cannot negate earlier "
            "command-off evidence. Power samples are discrete reports: "
            "do not call the earliest returned nonzero sample the first "
            "actual physical operation. Do not infer compressor runtime "
            "or an internal controller decision. Reported ON/OFF interval "
            "is switch-state duration, not proven physical operating time. "
            "When app decision logs are empty or incomplete, only the "
            "recorded command issuer, not the internal trigger, is known."
        ),
    }


def render_focal_device_evidence(
    request: str, receipts: list[dict[str, Any]],
) -> str | None:
    packet = reconcile_focal_device_events(request, receipts)
    if packet is None:
        return None
    return (
        "CURRENT-TURN RECONCILED DEVICE SOURCE FACTS (not a model answer):\n"
        + json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
        + "\nReconcile your final natural-language conclusions with these "
          "attested records. Prefer positive commands over claims of missing "
          "commands from narrower reads. Distinguish state intervals from "
          "bounded power telemetry and real hardware operation."
    )


__all__ = [
    "reconcile_focal_device_events", "render_focal_device_evidence",
]
