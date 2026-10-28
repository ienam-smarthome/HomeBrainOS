"""Evidence coverage measured against source windows, not successful tool counts.

A successful device-event read is not causal coverage when its newest-first
page is later than the actual slow-method warning. Parsed times are unzoned
wall-clock comparisons; cross-source clock alignment stays unverified.
This host layer suggests discriminating read filters. The model chooses tools.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any, Mapping, Sequence

_METHOD = re.compile(r"\bmethod\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.I)
_WALL = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?")


def _wall_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    found = _WALL.search(value[:55])
    if not found:
        return None
    try:
        day, clock, fractional = found.groups()
        return datetime.strptime(day + " " + clock, "%Y-%m-%d %H:%M:%S").replace(
            microsecond=int((fractional or "0").ljust(6, "0"))
        )
    except ValueError:
        return None


def _warning_ranges(witnesses: Sequence[Mapping[str, Any]],
                    focus: set[str]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    seen = set()
    for w in witnesses:
        if w.get("operation") != "hub_get_logs":
            continue
        data = w.get("source_data")
        summary = data.get("log_summary") if isinstance(data, dict) else None
        if not isinstance(summary, dict):
            continue
        for item in summary.get("warning_error_groups", [])[:30]:
            if not isinstance(item, dict) or str(item.get("source_id")) not in focus:
                continue
            oldest = _wall_time(item.get("oldest_returned"))
            newest = _wall_time(item.get("newest_returned"))
            if oldest is None or newest is None:
                continue
            if newest < oldest:
                oldest, newest = newest, oldest
            message = item.get("message", "")
            match = _METHOD.search(str(message))
            method = match.group(1) if match else None
            key = (oldest, newest, method)
            if key in seen:
                continue
            seen.add(key)
            groups.append({
                "start": oldest, "end": newest,
                "method": method, "read": w.get("read"),
                "start_text": item.get("oldest_returned"),
                "end_text": item.get("newest_returned"),
            })
    # Narrow, explicitly named method warnings are the best source-grounded
    # discriminator. Generic load warnings should not crowd them out.
    return sorted(groups, key=lambda x: (
        0 if x["method"] else 1,
        (x["end"] - x["start"]).total_seconds(),
        x["start"],
    ))


def _event_windows(witnesses: Sequence[Mapping[str, Any]],
                   focus: set[str]) -> list[dict[str, Any]]:
    windows = []
    for w in witnesses:
        if w.get("operation") != "hub_list_device_events":
            continue
        filters = w.get("read_filters")
        filters = filters if isinstance(filters, dict) else {}
        if str(filters.get("deviceId")) not in focus:
            continue
        data = w.get("source_data")
        if not isinstance(data, dict):
            continue
        events = data.get("events", [])
        times = sorted(t for t in (_wall_time(e.get("date") or e.get("time"))
                               for e in events if isinstance(e, dict)) if t)
        commands = [
            (e, _wall_time(e.get("date") or e.get("time")))
            for e in events if isinstance(e, dict)
            and str(e.get("name", "")).startswith("command-")
            and isinstance(e.get("producedBy"), dict)
            and e["producedBy"].get("appId")
        ]
        windows.append({
            "read": w.get("read"),
            "start": times[0] if times else None,
            "end": times[-1] if times else None,
            "command_times": [
                (e["name"], when, str(e["producedBy"]["appId"]))
                for e, when in commands if when
            ],
            "count": len(events) if isinstance(events, list) else 0,
            "filters": filters,
        })
    return windows


def gap_for_target(witnesses: Sequence[Mapping[str, Any]],
                   focus_ids: Sequence[str],
                   *, can_read_events: bool) -> dict[str, Any] | None:
    if not focus_ids or not can_read_events:
        return None
    focus = {str(i) for i in focus_ids}
    warnings = _warning_ranges(witnesses, focus)
    if not warnings:
        return None
    events = _event_windows(witnesses, focus)
    # Separate caller attribution from driver-method causation. A method
    # seen in a WARN record is not necessarily a callable device command:
    # never synthesize command-<method> when no such event was observed.
    chosen = None
    mechanism = None
    for warning in warnings:
        expanded_start = warning["start"] - timedelta(minutes=5)
        expanded_end = warning["end"] + timedelta(minutes=5)
        in_period = [
            (name, when, producer_id)
            for window in events
            for name, when, producer_id in window["command_times"]
            if expanded_start <= when <= expanded_end
        ]
        method = str(warning["method"] or "").casefold()
        direct_match = [
            cmd for cmd in in_period if
            not method or cmd[0].casefold() == "command-" + method
        ]
        if direct_match:
            # Command-to-warning association is source-supported, but cause
            # remains unverified. No additional issuer-history read is needed.
            continue
        if in_period and method:
            # Related apps are proven as callers, but this particular WARN
            # method is not an observed API command. Driver implementation
            # and app interactions remain an open mechanism question.
            if mechanism is None:
                mechanism = (warning, in_period)
            continue
        chosen = warning
        break
    # A source-reported internal slow method with independently attested
    # app-issued commands during its interval is more diagnostic than a
    # separate, later generic "excessive load" warning. Preserve that generic
    # warning as *unattributed*, but never let it erase verified app callers.
    # This prioritises evidence type and chronology, not the question wording.
    generic_unattributed = (
        chosen if chosen is not None and chosen["method"] is None else None
    )
    if mechanism is not None and (chosen is None or generic_unattributed is not None):
        warning, nearby = mechanism
        caller_ids = sorted({
            ident for _, _, ident in nearby if str(ident).isdecimal()
        })
        # The model can choose an app config read for a source-attested
        # caller, not another speculative command-runQ search.
        return {
            "kind": "target_driver_execution_mechanism_unverified",
            "focus_ids": sorted(focus),
            "method": warning["method"],
            "warning_window": {
                "oldest": warning["start_text"],
                "newest": warning["end_text"], "timezone_verified": False,
            },
            "actor_provenance_verified": bool(caller_ids),
            "observed_calling_app_ids": caller_ids[:8],
            "unattributed_generic_warning_window": (
                {"oldest": generic_unattributed["start_text"],
                 "newest": generic_unattributed["end_text"],
                 "timezone_verified": False}
                if generic_unattributed is not None else None
            ),
            "candidate_read": "hub_get_app_config" if caller_ids else None,
            "candidate_filters": {"appId": caller_ids[0]} if caller_ids else {},
            "materiality": (
                "Source events establish command issuers during the slow "
                "method period. Investigate the related app or device driver "
                "execution path; do not invent a command matching a method "
                "that appears only in a driver warning."),
            "limitation": (
                "An app command within the warning period does not prove "
                "which callback blocked or establish the driver's mechanism."),
        }
    if chosen is None:
        return None
    # Two independent facts must remain separate: source-attested apps have
    # issued commands to the device, but a generic load warning might have
    # NO command issuer recorded during its specific time window. A lack of
    # coincidence is not a lack of device callers and is not a proof that
    # any of those callers caused the generic runtime load.
    if chosen["method"] is None:
        verified_callers = sorted({
            issuer for window in events
            for _name, _stamp, issuer in window["command_times"]
            if issuer.isdecimal()
        })
        if verified_callers:
            return {
                "kind": "target_generic_warning_origin_unverified",
                "focus_ids": sorted(focus),
                "method": None,
                "warning_window": {
                    "oldest": chosen["start_text"],
                    "newest": chosen["end_text"],
                    "timezone_verified": False,
                },
                "device_command_issuers_verified": True,
                "incident_window_issuer_verified": False,
                "observed_calling_app_ids": verified_callers[:10],
                "candidate_read": "hub_get_logs",
                "candidate_filters": {
                    "mode": "past", "level": "warn", "limit": 200,
                },
                "candidate_alternatives": [
                    "hub_get_metrics", "hub_get_app_config",
                ],
                "materiality": (
                    "The device has separately attested command callers, but "
                    "none of the returned commands coincide with this generic "
                    "warning. A broader time-bounded WARN history might "
                    "recover a more diagnostic internal method warning; "
                    "independent performance or source evidence may help."
                ),
                "limitation": (
                    "No observed app command has been attributed to this "
                    "particular generic warning. Do not infer the command "
                    "issuer is unknown for the device or that previous "
                    "command issuers caused the runtime load."
                ),
            }
    expanded_start = chosen["start"] - timedelta(minutes=5)
    expanded_end = chosen["end"] + timedelta(minutes=5)
    overlaps = [
        window for window in events
        if window["start"] is not None and window["end"] is not None
        and window["start"] <= expanded_end and window["end"] >= expanded_start
    ]
    gap_kind = (
        "target_warning_actor_provenance_unchecked" if not events
        else ("target_warning_event_window_uncovered"
              if not overlaps else "target_warning_command_issuer_unverified")
    )
    return {
        "kind": gap_kind,
        "focus_ids": sorted(focus),
        "supporting_warning_reads": sorted({
            x["read"] for x in warnings
            if isinstance(x["read"], int)
        }),
        "method": chosen["method"],
        "warning_window": {
            "oldest": chosen["start_text"], "newest": chosen["end_text"],
            "timezone_verified": False,
        },
        "event_windows_checked": [{
            "read": w["read"],
            "oldest": w["start"].isoformat() if w["start"] else None,
            "newest": w["end"].isoformat() if w["end"] else None,
            "returned_events": w["count"],
            "filters": w["filters"],
        } for w in events[:5]],
        "candidate_read": "hub_list_device_events",
        "candidate_filters": {
            "deviceId": sorted(focus)[0],
            "hoursBack": 48,
            "limit": 50,
            # When an incident has NO caller commands at all, the filter
            # is only a possible probe; zero returned rows are inconclusive.
            **({"attribute": "command-" + chosen["method"]}
               if chosen["method"] else {}),
        },
        "candidate_filter_caveat": (
            "Example filters only: hoursBack must be adjusted to cover the "
            "source incident and is capped by the gateway; a filtered "
            "zero-row result does not prove no historical commands existed."),
        "materiality": (
            "Check whether a bounded command-name/time-window history can "
            "distinguish an app-issued command from a driver-internal stall."),
        "limitation": (
            "Source clock zones and completeness are unverified; command "
            "proximity is correlation, not proof of a causal mechanism."),
    }



def repeated_log_evidence(previous: Sequence[Mapping[str, Any]],
                          projected: Mapping[str, Any]) -> bool:
    """No newly observed WARN/ERROR group/time extent, not an exact-call dedup.

    A narrower query returning one subset already grouped in a broader source
    read does not independently corroborate the warning or add observations.
    Use exact group identity and contained time range; if bounds are missing,
    be conservative and never infer redundancy from message alone.
    """
    current = projected.get("log_summary")
    if not isinstance(current, dict):
        return False
    groups = current.get("warning_error_groups")
    if not isinstance(groups, list) or not groups:
        return False
    known: list[dict[str, Any]] = []
    for witness in previous:
        if witness.get("operation") != "hub_get_logs":
            continue
        data = witness.get("source_data")
        summary = data.get("log_summary") if isinstance(data, dict) else None
        if isinstance(summary, dict):
            known.extend(g for g in summary.get("warning_error_groups", [])
                         if isinstance(g, dict))
    if not known:
        return False
    for item in groups:
        if not isinstance(item, dict):
            return False
        start = _wall_time(item.get("oldest_returned"))
        end = _wall_time(item.get("newest_returned"))
        if start is None or end is None:
            return False
        if not any(
            item.get("source_type") == prior.get("source_type")
            and item.get("source_id") == prior.get("source_id")
            and item.get("message") == prior.get("message")
            and (prior_start := _wall_time(prior.get("oldest_returned"))) is not None
            and (prior_end := _wall_time(prior.get("newest_returned"))) is not None
            and prior_start <= start <= end <= prior_end
            and int(item.get("count", 0)) <= int(prior.get("count", 0))
            for prior in known
        ):
            return False
    return True



def repeated_event_evidence(previous: Sequence[Mapping[str, Any]],
                            projected: Mapping[str, Any],
                            *, scoped_device_id: str | None = None) -> bool:
    """A bounded event subset isn't new provenance if all rows were seen.

    The comparison requires fully retained projected rows; otherwise a
    truncated preview could conceal unseen events. Numeric issuer identity,
    event time and name form the comparison. Similar text alone is not enough.
    """
    events = projected.get("events")
    if not scoped_device_id or not isinstance(events, list) or not events:
        return False
    if projected.get("count") != len(events):
        return False
    def identity(row: Mapping[str, Any]) -> tuple[Any, ...] | None:
        issuer = row.get("producedBy")
        if not isinstance(issuer, Mapping):
            return None
        app = issuer.get("appId")
        device = issuer.get("deviceId")
        if app is None and device is None:
            return None
        return (
            row.get("name"), row.get("date"),
            ("app", str(app)) if app is not None else ("device", str(device)),
            row.get("value"),
        )
    observed = set()
    for witness in previous:
        if witness.get("operation") != "hub_list_device_events":
            continue
        filters = witness.get("read_filters")
        if not isinstance(filters, Mapping) or str(filters.get("deviceId")) != str(scoped_device_id):
            continue
        source = witness.get("source_data")
        if not isinstance(source, Mapping):
            continue
        for row in source.get("events", [])[:130]:
            if isinstance(row, Mapping):
                key = identity(row)
                if key is not None:
                    observed.add(key)
    return bool(observed) and all(
        isinstance(row, Mapping) and
        (key := identity(row)) is not None and key in observed
        for row in events
    )


def gateway_offers_operation(manifest: Mapping[str, Any],
                             discovered: Mapping[str, set[str]],
                             operation: str) -> bool:
    for name, tool in manifest.items():
        if not name.startswith("hub_read_"):
            continue
        enum = tool.input_schema.get("properties", {}).get("tool", {}).get("enum")
        if isinstance(enum, list) and operation in enum:
            return True
        if operation in discovered.get(name, set()):
            return True
    return False


def useful_discovery_fingerprint(source: Mapping[str, Any]) -> tuple[str, ...]:
    result = source.get("results")
    if not isinstance(result, list):
        return ()
    return tuple(sorted({
        str(item.get("gateway")) + ":" + str(item.get("tool"))
        for item in result
        if isinstance(item, dict)
        and isinstance(item.get("gateway"), str)
        and isinstance(item.get("tool"), str)
    }))


__all__ = ["gap_for_target", "gateway_offers_operation",
           "useful_discovery_fingerprint", "repeated_log_evidence",
           "repeated_event_evidence"]
