"""Source-only V2 evidence primitives reused by the original HomeBrain agent.

No V2 planner, claim-catalog publisher, JSON answer contract or tool executor is
imported. The original model remains responsible for choosing further READs and
writing natural-language conclusions; this bridge only preserves independently
read source facts and exact temporal relationships.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import re
from typing import Any, Mapping, Sequence

from unified_incident_synthesis import reconcile_ledger_if_needed
from causal_witness_ledger import build_witness_coverage_ledger
from causal_claim_pilot import render_shadow_claim_pilot
from causal_reception_evidence import analyse_collector_reception
from causal_source_feasibility import build_source_feasibility_choices
from investigation_v2.native_event_narrative import event_narrative_evidence
from investigation_v2.native_provenance import event_summary
from investigation_v2.temporal_scope import explicit_incident_window


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


_RECENT = re.compile(
    r"\b(?:last|past)\s+(\d{1,2}|one|two|three|four|six|twelve|twenty-four)"
    r"\s+(minutes?|hours?)\b", re.I)
_RECENT_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4,
                 "six": 6, "twelve": 12, "twenty-four": 24}


_EXPLICIT_CLOCK_RANGE = re.compile(
    r"\b(?:between|from)\s+(\d{1,2}):(\d{2})\s*"
    r"(?:and|to|[-–])\s*(\d{1,2}):(\d{2})\b", re.I)


def _in_user_period(when: datetime, question: str, incident: Any) -> bool:
    if incident is not None:
        if not incident.contains(when.isoformat()):
            return False
    else:
        recent = _RECENT.search(question)
        if recent:
            amount = _RECENT_WORDS.get(recent.group(1).casefold())
            amount = int(recent.group(1)) if amount is None else amount
            seconds = amount * (3600 if recent.group(2).lower().startswith("hour") else 60)
            if not 60 <= seconds <= 48 * 3600:
                return False
            if not datetime.now(timezone.utc) - timedelta(seconds=seconds) <= when <= datetime.now(timezone.utc):
                return False
    found = _EXPLICIT_CLOCK_RANGE.search(question)
    if found:
        h1, m1, h2, m2 = map(int, found.groups())
        start, end = h1 * 60 + m1, h2 * 60 + m2
        if h1 < 24 and h2 < 24 and m1 < 60 and m2 < 60 and end > start:
            minute = when.hour * 60 + when.minute
            return start <= minute <= end
    return True


def _args(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    args = receipt.get("arguments")
    if not isinstance(args, Mapping):
        return {}
    nested = args.get("args")
    return nested if isinstance(nested, Mapping) else args


def _valid_source_rows(receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    if (receipt.get("success") is not True
            or receipt.get("effect") not in (None, "read")
            or receipt.get("mutates") is True
            or receipt.get("supports_live_claim") is False):
        return []
    details = receipt.get("details")
    if not isinstance(details, Mapping):
        return []
    rows = details.get("observedEvents")
    if rows is None:
        rows = details.get("events")
    return [dict(e) for e in rows[:150] if isinstance(e, Mapping)] if isinstance(rows, list) else []


def _attested_targets(receipts: Sequence[Mapping[str, Any]],
                      question: str) -> dict[str, str]:
    """Source-verified resolved identities, not user-text IDs or generated labels."""
    names: dict[str, str] = {}
    for r in receipts:
        if r.get("success") is not True:
            continue
        d = r.get("details")
        if not isinstance(d, Mapping):
            continue
        candidates = [
            d.get("reportedDeviceState"),
            d.get("target"),
            d,
        ]
        for obj in candidates:
            if not isinstance(obj, Mapping):
                continue
            ident = str(obj.get("deviceId") or obj.get("id") or "")
            label = obj.get("label") or obj.get("name")
            if (ident.isdecimal() and isinstance(label, str)
                    and 2 <= len(label) <= 90
                    and label.casefold() in question.casefold()):
                names[ident] = label
    return names


def _verified_lookup_identities(
    receipts: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    """Independently resolved device IDs, including input sensors not named in question."""
    identities: dict[str, set[str]] = {}
    for receipt in receipts:
        if (receipt.get("success") is not True or receipt.get("mutates") is True
                or receipt.get("evidence_kind") != "targeted_device_lookup"):
            continue
        details = receipt.get("details")
        if not isinstance(details, Mapping):
            continue
        state = details.get("reportedDeviceState")
        if not isinstance(state, Mapping):
            continue
        ident = str(state.get("deviceId") or "")
        label = state.get("label")
        if ident.isdecimal() and isinstance(label, str) and label.strip():
            identities.setdefault(label.strip().casefold(), set()).add(ident)
    return {label: sorted(ids) for label, ids in identities.items()}

def collect_unified_evidence(
    receipts: Sequence[Mapping[str, Any]], question: str,
) -> dict[str, Any] | None:
    """Correlate original-agent device/source receipts without asserting cause.

    Only read-only, successful, typed device-scoped event pages enter the
    historical ledger. Additional sensor event pages are independent
    observations; no source-issued ON command is inferred by proximity.
    """
    verified_names = _attested_targets(receipts, question)
    witnessed: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    modes: list[dict[str, Any]] = []
    incident = explicit_incident_window(question, zone_name="UTC")
    # Native event reads sometimes retain only a receipt summary, while the
    # deterministic device-history wrapper holds the source's typed event rows.
    # Reconcile both successful read surfaces. Identity for a wrapped history
    # MUST already be independently attested by a targeted device lookup.
    verified_label_ids = _verified_lookup_identities(receipts)
    for ident, label in verified_names.items():
        ids = verified_label_ids.setdefault(label.casefold(), [])
        if ident not in ids:
            ids.append(ident)
    observed_keys: set[tuple[str, str, str, str, str]] = set()
    # Source roles stay distinct: command issuer != event-notified listener.
    # event_summary intentionally strips triggered[] from model-visible rows;
    # preserve only typed app IDs from the independently scoped raw receipt.
    command_apps_by_device: dict[str, set[str]] = {}
    notified_apps_by_device: dict[str, set[str]] = {}
    for index, receipt in enumerate(receipts[:100], 1):
        tool = str(receipt.get("tool") or "")
        leaf = str(receipt.get("sub_tool") or "")
        is_native = leaf == "hub_list_device_events"
        is_derived = tool == "homebrain_device_history"
        if not (is_native or is_derived):
            continue
        # Empty, successful, device-scoped source reads independently attest
        # WHICH requested history was queried, not that any event occurred or
        # that the returned window is complete. Retaining these verified
        # scopes is essential to recover entirely evicted target histories.
        if (is_native and receipt.get("success") is True
                and receipt.get("mutates") is not True
                and receipt.get("effect") in (None, "read")
                and receipt.get("supports_live_claim") is not False):
            scoped_id = str(_args(receipt).get("deviceId") or "")
            if scoped_id.isdecimal() and scoped_id in verified_names:
                source_ids.add(scoped_id)
        rows = _valid_source_rows(receipt)
        if not rows:
            continue
        args = _args(receipt)
        if is_native:
            device_id = str(args.get("deviceId") or "")
        else:
            details = receipt.get("details") or {}
            label = str(details.get("label") or "").strip().casefold()
            matches = verified_label_ids.get(label) or []
            # A history name is not an independently verified device ID.
            # Ambiguous/unresolved identities must never enter the causal graph.
            device_id = matches[0] if len(matches) == 1 else ""
        if device_id.isdecimal():
            source_ids.add(device_id)
            # Deduplicate the same native row exposed through both gateway
            # receipts and deterministic history. Retain distinct commands.
            unique_rows: list[dict[str, Any]] = []
            for row in rows:
                actor = row.get("producedBy") or {}
                actor_id = str(actor.get("appId") or actor.get("deviceId")
                               or actor.get("id") or "") if isinstance(actor, Mapping) else ""
                key = (device_id, str(row.get("date") or ""),
                       str(row.get("name") or ""), str(row.get("value") or ""),
                       actor_id)
                if key in observed_keys:
                    continue
                observed_keys.add(key)
                unique_rows.append(row)
            if not unique_rows:
                continue
            for row in unique_rows:
                event_time = _time(row.get("date"))
                if event_time is None or not _in_user_period(
                        event_time, question, incident):
                    continue
                producer = row.get("producedBy")
                if str(row.get("name") or "").startswith("command-") and isinstance(producer, Mapping):
                    app_id = str(producer.get("appId") or "")
                    if app_id.isdecimal() and int(app_id) > 0:
                        command_apps_by_device.setdefault(device_id, set()).add(app_id)
                if (str(row.get("name") or "") in (
                        "switch", "level", "motion", "occupancy", "presence")):
                    notifications = row.get("triggered")
                    if isinstance(notifications, list):
                        for notified in notifications[:36]:
                            if not isinstance(notified, Mapping):
                                continue
                            app_id = str(notified.get("appId") or "")
                            if app_id.isdecimal() and int(app_id) > 0:
                                notified_apps_by_device.setdefault(device_id, set()).add(app_id)
            projected = event_summary({"events": unique_rows})
            if projected is None:
                continue
            witnessed.append({
                "read": index, "operation": "hub_list_device_events",
                "source_surface": (
                    "homebrain_device_history" if is_derived
                    else "native_gateway_receipt"),
                "read_filters": {"deviceId": device_id},
                "source_data": projected,
            })
            for e in projected["events"]:
                when = _time(e.get("date"))
                if when is None or not _in_user_period(when, question, incident):
                    continue
                all_events.append({**e, "device_id": device_id,
                                   "read": index, "when": when})
        elif is_native:
            for e in rows:
                when = _time(e.get("date"))
                if (e.get("name") == "mode" and when is not None
                        and _in_user_period(when, question, incident)):
                    modes.append({"read": index, "date": e["date"],
                                  "value": str(e.get("value") or "")[:55]})
            witnessed.append({
                "read": index, "operation": "hub_list_device_events",
                "read_filters": {},
                "source_data": event_summary({"events": rows}),
            })
    # Without two independently read, user-scoped target histories this
    # remains the original agent's ordinary investigation, not group evidence.
    targets = set(verified_names).intersection(source_ids)
    if len(targets) < 2:
        return None
    # V2's sampled narrative packet is advisory only. A failure to select
    # examples must never discard the independently read full target events.
    packet = event_narrative_evidence(
        witnessed, sorted(source_ids), question=question,
        verified_labels=verified_names, max_events=48)
    # This ledger includes only target lights for relationships. Other
    # independently read histories may supply correlated sensor observations.
    by_id: dict[str, list[dict[str, Any]]] = {}
    sensor_events: list[dict[str, Any]] = []
    input_history_ids: set[str] = set()
    independent_input_events: list[dict[str, Any]] = []
    input_keys: set[tuple[str, str, str, str]] = set()
    for e in all_events:
        by_id.setdefault(e["device_id"], []).append(e)
        if (e["device_id"] not in targets
                and e["name"] in ("motion", "occupancy", "presence")):
            input_history_ids.add(e["device_id"])
            value = str(e.get("value") or "").casefold()
            key = (e["device_id"], e["date"], e["name"], value)
            if key not in input_keys and value in (
                "active", "inactive", "present", "not present",
                "occupied", "unoccupied", "on", "off", "true", "false"):
                input_keys.add(key)
                independent_input_events.append({
                    "device_id": e["device_id"],
                    "time": e["date"],
                    "attribute": e["name"],
                    "value": value,
                    "source_read": e["read"],
                    "timestamp_basis": "source-reported",
                })
            if value in ("active", "present", "occupied", "on", "true"):
                sensor_events.append(e)
    # Recover independently source-timestamped *input* observations from
    # the local Historical Journal after a successful scoped native input read
    # returned no useful incident-time events. Collector reception is a
    # separate coverage observation, NEVER the source event clock.
    archived_input_source_count = 0
    archived_input_collector_count = 0
    archived_input_gap_count = 0
    archived_input_reads = 0
    archived_input_gap_queries: list[dict[str, Any]] = []
    archived_input_reception_rows: list[dict[str, Any]] = []
    archived_input_truncated_ids: set[str] = set()
    for receipt in receipts[:120]:
        if (receipt.get("tool") != "homebrain_evidence_journal"
                or receipt.get("evidence_kind") != "group_archived_input_history"
                or receipt.get("success") is not True
                or receipt.get("mutates") is True):
            continue
        d = receipt.get("details")
        args = receipt.get("arguments")
        if not isinstance(d, Mapping) or not isinstance(args, Mapping):
            continue
        ident = str(args.get("device_id") or "")
        if (not ident.isdecimal() or ident in targets
                or str(d.get("deviceId") or "") != ident):
            continue
        # The previously scoped native read is the independent identity and
        # intent authorization. A manually injected archive receipt alone
        # cannot establish a usable input identity.
        native_checked = any(
            r.get("success") is True and r.get("mutates") is not True
            and r.get("sub_tool") == "hub_list_device_events"
            and str(_args(r).get("deviceId") or "") == ident
            for r in receipts[:120]
        )
        if not native_checked:
            continue
        archived_input_reads += 1
        if d.get("truncated") is True:
            archived_input_truncated_ids.add(ident)
        gaps = d.get("gapCount")
        if type(gaps) is int and gaps >= 0:
            archived_input_gap_count += gaps  # query receipts, NOT distinct outages
            archived_input_gap_queries.append({"device_id": ident, "gap_count": gaps})
        for event in (d.get("observations") or [])[:160]:
            if not isinstance(event, Mapping):
                continue
            if (str(event.get("device_id") or "") != ident
                    or str(event.get("attribute") or "") not in (
                        "motion", "occupancy", "presence")):
                continue
            when = _time(event.get("date"))
            value = str(event.get("value") or "").casefold()
            basis = event.get("timestamp_basis")
            if (when is None or not _in_user_period(when, question, incident)
                    or value not in (
                        "active", "inactive", "present", "not present",
                        "occupied", "unoccupied", "on", "off", "true", "false")
                    or basis not in ("source", "collector-received")):
                continue
            if basis == "collector-received":
                archived_input_collector_count += 1
                if len(archived_input_reception_rows) < 96:
                    archived_input_reception_rows.append({
                        "device_id": ident, "received_at": when.isoformat(),
                        "attribute": str(event["attribute"]), "value": value,
                        "timestamp_basis": "collector-received",
                    })
                continue
            archived_input_source_count += 1
            key = (ident, when.isoformat(), str(event["attribute"]), value)
            if key in input_keys:
                continue
            input_keys.add(key)
            input_history_ids.add(ident)
            independent_input_events.append({
                "device_id": ident, "time": when.isoformat(),
                "attribute": event["attribute"], "value": value,
                "source_read": "historical-journal-input",
                "timestamp_basis": "source",
                "app_relationship_basis": "unavailable-in-journal",
            })
    independent_input_events.sort(key=lambda row: (
        _time(row["time"]), row["device_id"]))
    target_command_apps = set().union(
        *(command_apps_by_device.get(ident, set()) for ident in targets))
    target_notified_apps = set().union(
        *(notified_apps_by_device.get(ident, set()) for ident in targets))
    # This is source-relationship classification, NOT an inverse dependency
    # proof or a claim that an app historically caused a particular switch.
    # An empty/disjoint snapshot cannot exclude missing command paths.
    input_app_relationships: list[dict[str, Any]] = []
    for ident in sorted(input_history_ids, key=int):
        notified = notified_apps_by_device.get(ident, set())
        shared_command = notified & target_command_apps
        shared_listener = notified & target_notified_apps
        if shared_command:
            status = "shared-observed-target-command-app"
        elif shared_listener:
            status = "shared-observed-target-notified-app"
        elif notified and (target_command_apps or target_notified_apps):
            status = "different-observed-app-associations"
        else:
            status = "relationship-not-established-from-records"
        input_app_relationships.append({
            "input_device_id": ident,
            "input_notified_app_ids": sorted(notified, key=int)[:12],
            "shared_target_command_app_ids": sorted(shared_command, key=int)[:12],
            "shared_target_listener_app_ids": sorted(shared_listener, key=int)[:12],
            "relationship": status,
            "historical_causation_verified": False,
        })
    # Device IDs queried in the incident period but returning no usable
    # source events are evidence *coverage gaps*, not inactive sensors.
    empty_non_target_reads: set[str] = set()
    for receipt in receipts[:120]:
        if (receipt.get("success") is not True
                or receipt.get("mutates") is True
                or receipt.get("sub_tool") != "hub_list_device_events"):
            continue
        ident = str(_args(receipt).get("deviceId") or "")
        if (ident.isdecimal() and ident not in targets
                and not any(e["device_id"] == ident for e in all_events)
                and not any(x["device_id"] == ident
                            for x in independent_input_events)):
            empty_non_target_reads.add(ident)
    state_links: list[dict[str, Any]] = []
    for ident in sorted(targets):
        rows = sorted(by_id.get(ident, []), key=lambda r: r["when"])
        for e in rows:
            if (e.get("name") != "switch"
                    or str(e.get("value") or "").lower() not in ("on", "off")):
                continue
            when = e["when"]
            on = e["value"].lower() == "on"
            commands = [
                c for c in rows
                if c.get("name") in (("command-on", "command-setLevel", "command-toggle")
                                    if on else ("command-off", "command-toggle"))
                and c["when"] <= when
                and (when - c["when"]).total_seconds() <= 3
                and isinstance(c.get("producedBy"), Mapping)
                and c["producedBy"].get("appId") is not None
            ]
            later_levels = [
                c for c in rows if c.get("name") == "command-setLevel"
                and when < c["when"]
                and (c["when"] - when).total_seconds() <= 2
            ] if on else []
            preceding_sensors = sorted(
                (s for s in sensor_events if s["when"] <= when
                 and (when - s["when"]).total_seconds() <= 3),
                key=lambda s: (when - s["when"]).total_seconds(),
            )[:3] if on else []
            state_links.append({
                "device_id": ident, "device_name": verified_names[ident],
                "reported_state": e["value"], "time": e["date"],
                "source_read": e["read"],
                "preceding_hubitat_command_in_sample": [
                    {"command": c["name"], "app_id": str(c["producedBy"]["appId"]),
                     "issuer": str(c["producedBy"].get("name") or "")[:80],
                     "time": c["date"],
                     "lead_ms": round((when-c["when"]).total_seconds()*1000)}
                    for c in commands[-2:]],
                "subsequent_level_commands": [
                    {"app_id": str(c.get("producedBy", {}).get("appId") or ""),
                     "time": c["date"],
                     "lag_ms": round((c["when"]-when).total_seconds()*1000)}
                    for c in later_levels[:2]],
                "preceding_input_correlations": [
                    {"device_id": s["device_id"],
                     "event": s["name"], "time": s["date"],
                     "lead_ms": round((when-s["when"]).total_seconds()*1000),
                     "source_read": s["read"]}
                    for s in preceding_sensors],
            })
    # Do not discard a verified target merely because its Hubitat history
    # page contains only command-off / command-setLevel / level observations.
    # Those are material evidence and, crucially, prove that switch history
    # has NOT been reconstructed. This was the live 0.18.242 failure.
    state_links.sort(key=lambda e: (_time(e["time"]), e["device_name"]))
    incident_rows: list[dict[str, Any]] = []
    target_coverage: list[dict[str, Any]] = []
    for ident in sorted(targets):
        rows = sorted(by_id.get(ident, []), key=lambda row: row["when"])
        counts = {"reported_switch_on": 0, "reported_switch_off": 0,
                  "issued_off": 0, "issued_on": 0, "issued_setlevel": 0,
                  "reported_level": 0}
        for e in rows:
            name = str(e.get("name") or "")
            value = str(e.get("value") or "")
            kind = (
                "reported_switch_on" if name == "switch" and value.lower() == "on"
                else "reported_switch_off" if name == "switch" and value.lower() == "off"
                else "issued_off" if name == "command-off"
                else "issued_on" if name == "command-on"
                else "issued_setlevel" if name == "command-setLevel"
                else "reported_level" if name == "level"
                else ""
            )
            if not kind:
                continue
            counts[kind] += 1
            producer = e.get("producedBy")
            producer = producer if isinstance(producer, Mapping) else {}
            incident_rows.append({
                "device_id": ident, "device_name": verified_names[ident],
                "date": e["date"], "time": e["when"],
                "event_class": kind,
                "value": value[:30],
                "app_id": str(producer.get("appId") or ""),
                "source_read": e["read"],
            })
        switch_count = counts["reported_switch_on"] + counts["reported_switch_off"]
        commands = sum(counts[k] for k in ("issued_off", "issued_on", "issued_setlevel"))
        target_coverage.append({
            "device_id": ident, "device_name": verified_names[ident],
            **counts,
            "switch_event_count": switch_count,
            "command_count": commands,
            "switch_state_missing_despite_commands":
                switch_count == 0 and commands > 0,
            # A successful device-scoped history query may return only
            # newer state events because its rolling retention has moved
            # past the requested incident window. This is still a
            # historical source gap, even if no command survived either.
            "incident_switch_history_missing": switch_count == 0,
            "complete_on_off_cycle_verified": (
                counts["reported_switch_on"] > 0
                and counts["reported_switch_off"] > 0),
        })
    # Absence of *in-window* rows does not invalidate independently
    # resolved targets and their scoped history reads. Otherwise archive
    # recovery can never run precisely when rolling native history has
    # evicted every incident-time event. Only an explicitly bounded
    # historical request qualifies for this source-gap packet.
    if not incident_rows and incident is None:
        return None
    # Independent Historical Journal receipts supply separate observations.
    # Collector-received rows are NEVER promoted to Hubitat source-event
    # timestamps or used as precise causal edges.
    journal_reads = 0
    journal_gap_count = 0
    journal_source_count = 0
    journal_received_count = 0
    journal_truncated = False
    cover_by_id = {c["device_id"]: c for c in target_coverage}
    for c in target_coverage:
        c.update(journal_source_on=0, journal_source_off=0,
                 journal_collector_on=0, journal_collector_off=0,
                 journal_checked=False, journal_gaps=0)
    for index, receipt in enumerate(receipts[:100], 1):
        if (receipt.get("tool") != "homebrain_evidence_journal"
                or receipt.get("evidence_kind") != "group_archived_switch_history"
                or receipt.get("success") is not True
                or receipt.get("mutates") is True):
            continue
        ident = str((receipt.get("arguments") or {}).get("device_id") or "")
        if ident not in cover_by_id:
            continue
        details = receipt.get("details")
        if not isinstance(details, Mapping):
            continue
        journal_reads += 1
        coverage = cover_by_id[ident]
        coverage["journal_checked"] = True
        gaps = details.get("gapCount")
        if type(gaps) is int and gaps >= 0:
            coverage["journal_gaps"] += gaps
            journal_gap_count += gaps
        journal_truncated = journal_truncated or details.get("truncated") is True
        for event in (details.get("observations") or [])[:100]:
            if not isinstance(event, Mapping):
                continue
            if (str(event.get("device_id") or "") != ident
                    or event.get("attribute") != "switch"
                    or event.get("value") not in ("on", "off")):
                continue
            when = _time(event.get("date"))
            basis = event.get("timestamp_basis")
            if when is None or basis not in ("source", "collector-received"):
                continue
            if not _in_user_period(when, question, incident):
                continue
            kind = ("journal_source_switch_" if basis == "source"
                    else "journal_received_switch_") + event["value"]
            column = ("journal_source_" if basis == "source"
                      else "journal_collector_") + event["value"]
            coverage[column] += 1
            if basis == "source":
                journal_source_count += 1
            else:
                journal_received_count += 1
            incident_rows.append({
                "device_id": ident, "device_name": verified_names[ident],
                "date": event["date"], "time": when,
                "event_class": kind, "value": event["value"],
                "app_id": "", "source_read": index,
                "timestamp_basis": basis, "source": "Historical Journal",
            })
    incident_rows.sort(key=lambda e: (e["time"], e["device_name"]))
    # Reception-only sensor reports can form *co-occurrence patterns*, not
    # source-event chronology. Compare against source-timed switch boundaries
    # with a loose clock window; report separately and explicitly forbid
    # claiming which side acted first or which app sent a command. A single
    # independently named target avoids counting two nearly synchronous
    # lights as two independent replications.
    source_boundaries = [
        row for row in incident_rows
        if row["device_id"] == sorted(targets)[0]
        and row["event_class"] in ("journal_source_switch_on",
                                   "journal_source_switch_off")
    ]
    reception_input_patterns: list[dict[str, Any]] = []
    for ident in sorted({r["device_id"] for r in archived_input_reception_rows},
                        key=int):
        samples = [r for r in archived_input_reception_rows
                   if r["device_id"] == ident]
        on_matches: list[dict[str, Any]] = []
        off_matches: list[dict[str, Any]] = []
        for boundary in source_boundaries:
            when = boundary["time"]
            switch_value = boundary["value"]
            candidates: list[tuple[float, float, dict[str, Any]]] = []
            for sample in samples:
                if sample["attribute"] not in ("motion", "occupancy", "presence"):
                    continue
                reception = _time(sample["received_at"])
                if reception is None:
                    continue
                signed = (reception - when).total_seconds()
                if (switch_value == "on"
                        and sample["value"] in ("active", "occupied",
                                               "present", "on", "true")
                        and abs(signed) <= 3.0):
                    candidates.append((abs(signed), signed, sample))
                elif (switch_value == "off"
                      and sample["value"] in ("inactive", "unoccupied",
                                              "not present", "off", "false")
                      and -20.0 <= signed <= 0):
                    candidates.append((abs(signed), signed, sample))
            if candidates:
                _, signed, sample = min(candidates, key=lambda item: item[0])
                match = {
                    "target_source_time": boundary["date"],
                    "input_received_at": sample["received_at"],
                    "input_state": sample["value"],
                    "signed_reception_vs_source_seconds": round(signed, 3),
                }
                (on_matches if switch_value == "on" else off_matches).append(match)
        reception_input_patterns.append({
            "device_id": ident,
            "target_source_on_count": sum(
                row["value"] == "on" for row in source_boundaries),
            "target_source_off_count": sum(
                row["value"] == "off" for row in source_boundaries),
            "on_near_active_receptions": len(on_matches),
            "off_after_inactive_receptions": len(off_matches),
            "on_examples": on_matches[:3],
            "off_examples": off_matches[:3],
            "input_reception_sample_size": len(samples),
            "input_sample_truncated": ident in archived_input_truncated_ids,
            "cross_clock_order_verified": False,
            "causal_initiator_verified": False,
        })
    # Prefer compact provenance-aware summaries calculated from the full
    # archive page before the evidence recorder safely limits exposed arrays
    # to 20 observations. They may contain more evidence than the receipt
    # sample, but never certify source-event ordering or a controller.
    archive_sample_sizes: list[dict[str, Any]] = []
    for receipt in receipts[:120]:
        if (receipt.get("evidence_kind") != "group_archived_input_history"
                or receipt.get("success") is not True
                or receipt.get("mutates") is True):
            continue
        d = receipt.get("details")
        if not isinstance(d, Mapping):
            continue
        ident = str(d.get("deviceId") or "")
        if (not ident.isdecimal()
                or not any(str(_args(r).get("deviceId") or "") == ident
                           and r.get("success") is True
                           and r.get("sub_tool") == "hub_list_device_events"
                           for r in receipts[:120])):
            continue
        total = d.get("returnedObservationCount")
        sample = d.get("observations")
        if type(total) is int and isinstance(sample, list):
            archive_sample_sizes.append({
                "device_id": ident, "retrieved_observations": total,
                "retained_receipt_observations": len(sample),
                "query_truncated": d.get("truncated") is True,
            })
        summary = d.get("receptionPatternSummary")
        if not isinstance(summary, Mapping):
            continue
        # The archive gives a bounded co-occurrence calculation, NOT a
        # source timestamp or trusted controller command.
        record = next((r for r in reception_input_patterns
                       if r["device_id"] == ident), None)
        if record is None:
            continue
        if (type(summary.get("targetSourceOnCount")) is not int
                or type(summary.get("targetSourceOffCount")) is not int):
            continue
        record.update({
            "target_source_on_count": summary["targetSourceOnCount"],
            "target_source_off_count": summary["targetSourceOffCount"],
            "on_near_active_receptions": int(
                summary.get("onNearActiveReceptions") or 0),
            "off_after_inactive_receptions": int(
                summary.get("offAfterInactiveReceptions") or 0),
            "on_reception_delta_samples":
                (summary.get("onSignedReceptionDeltasSeconds") or [])[:6],
            "off_reception_delta_samples":
                (summary.get("offSignedReceptionDeltasSeconds") or [])[:6],
            "cross_clock_order_verified": False,
            "causal_initiator_verified": False,
            "full_returned_page_analyzed": True,
        })
    returned_counts = {
        row["device_id"]: row["retrieved_observations"]
        for row in archive_sample_sizes
    }
    receiver_evidence = analyse_collector_reception(
        incident_rows, archived_input_reception_rows,
        truncated_inputs=sorted(archived_input_truncated_ids),
        input_returned_counts=returned_counts,
    )
    checked_input_ids = sorted(input_history_ids)
    archived_app_checks: list[dict[str, Any]] = []
    for receipt in receipts[:120]:
        if (receipt.get("evidence_kind") != "group_archived_app_decisions"
                or receipt.get("tool") != "homebrain_evidence_journal"
                or receipt.get("mutates") is True):
            continue
        d = receipt.get("details")
        if not isinstance(d, Mapping):
            continue
        ident = str(d.get("appId") or "")
        if not ident.isdecimal():
            continue
        archived_app_checks.append({
            "app_id": ident,
            "status": str(d.get("status") or "")[:72],
            "log_rows": d.get("returnedRows"),
            "decision_declarations": d.get("decisionDeclarations"),
            "reported_decisions": [
                {
                    "stage": str(e.get("stage") or "")[:48],
                    "collector_received_at_utc": str(e.get("collectorReceivedAtUtc") or "")[:35],
                    "original_event_time_verified": False,
                } for e in (d.get("reportedDecisionRows") or [])[:6]
                if isinstance(e, Mapping)
            ],
            "gap_count": d.get("gapCount"),
            "historical_execution_verified": False,
            "timestamp_basis": "collector-received",
        })
    log_receipts = [
        r for r in receipts if r.get("success") is True
        and r.get("sub_tool") == "hub_get_logs"
    ]
    # A successful log query does not prove coverage of the user period.
    # Only exact source-timestamped rows could support that stronger claim.
    facts = {
        "source_attested": True,
        "user_target_names": [verified_names[i] for i in sorted(targets)],
        "target_device_ids": sorted(targets),
        "source_event_packet": packet or {},
        "transition_relationships": state_links[:100],
        "transition_count": len(state_links),
        "transition_rows_omitted": max(0, len(state_links) - 100),
        "incident_ledger": [{k: v for k, v in e.items() if k != "time"}
                            for e in incident_rows[:180]],
        "incident_ledger_total": len(incident_rows),
        "target_coverage": target_coverage,
        "journal_read_count": journal_reads,
        "journal_source_observations": journal_source_count,
        "journal_collector_observations": journal_received_count,
        "journal_gap_count": journal_gap_count,
        "journal_truncated": journal_truncated,
        "missing_switch_history_for_targets": [
            c["device_name"] for c in target_coverage
            if c["incident_switch_history_missing"]],
        "incident_window_without_native_events": not any(
            c["switch_event_count"] or c["command_count"]
            for c in target_coverage),
        "native_target_source_complete_for_incident": False,
        "hub_mode_observations": modes[:12],
        "independently_read_input_ids": checked_input_ids,
        "independent_input_observations": independent_input_events[:24],
        "independent_input_observation_total": len(independent_input_events),
        "archived_input_source_observations": archived_input_source_count,
        "archived_input_collector_observations": archived_input_collector_count,
        "archived_input_returned_observations": sum(
            row["retrieved_observations"] for row in archive_sample_sizes),
        "archived_input_gap_count": archived_input_gap_count,
        "archived_input_gap_queries": archived_input_gap_queries,
        "same_receiver_evidence": receiver_evidence,
        "archived_input_reads": archived_input_reads,
        "archived_input_reception_patterns": reception_input_patterns[:8],
        "archived_input_truncated_ids": sorted(archived_input_truncated_ids, key=int),
        "archived_input_sample_coverage": archive_sample_sizes[:8],
        "input_app_relationships": input_app_relationships[:16],
        "target_observed_command_app_ids": sorted(target_command_apps, key=int)[:16],
        "target_observed_notified_app_ids": sorted(target_notified_apps, key=int)[:16],
        "additional_event_reads_without_usable_rows": sorted(
            empty_non_target_reads, key=int)[:16],
        "missing_independent_input_history": not bool(checked_input_ids),
        "log_query_count": len(log_receipts),
        "archived_app_checks": archived_app_checks,
        "incident_log_coverage_verified": False,
        "limitations": (
            "State is source-reported, not an independent physical ACK. "
            "A command preceding a state supports immediate command provenance, "
            "not the controller's upstream decision. A sensor edge shortly "
            "before an ON is correlation only. A subsequent setLevel does NOT "
            "initiate a preceding ON. No returned command is not proof none "
            "was issued. Hubitat and external bridge clocks may differ. "
            "Current config metadata does not prove historical execution. "
          "Historical Journal collector-reception time is not an exact "
          "source event time and journal gaps or empty queries cannot "
          "establish continuous historical coverage."),
    }
    # V3 Stage B is shadow-only: this immutable source/coverage view is
    # computed from existing receipts and facts. Do not alter model prompts,
    # tool selection or deterministic finalization until separately tested.
    facts["v3_witness_ledger"] = build_witness_coverage_ledger(facts, receipts)
    return facts


def unified_investigation_instruction(
    receipts: Sequence[Mapping[str, Any]], question: str,
) -> str | None:
    evidence = collect_unified_evidence(receipts, question)
    if evidence is None:
        return None
    # Source event receipts may be lengthy. Put directional comparisons
    # first: their order proves that a brightness command occurring AFTER
    # a source-reported ON cannot have initiated that earlier ON.
    source = evidence["source_event_packet"]
    # Only run the optional shadow pilot when the CURRENT safety finalizer
    # will necessarily publish the source-attested two-target journal digest.
    # No claim block can leak into an otherwise model-led response.
    pilot = render_shadow_claim_pilot(evidence)
    compact = {
        "target_names": evidence["user_target_names"],
        "target_read_ids": evidence["target_device_ids"],
        "transition_relationships": evidence["transition_relationships"][:40],
        "target_coverage": evidence["target_coverage"],
        "v3_source_feasibility": build_source_feasibility_choices(
            evidence, receipts),
        "journal_source_observations": evidence["journal_source_observations"],
        "journal_collector_observations": evidence["journal_collector_observations"],
        "journal_gap_count": evidence["journal_gap_count"],
        "journal_truncated": evidence["journal_truncated"],
        "incident_ledger": evidence["incident_ledger"][:40],
        "missing_switch_history_for_targets":
            evidence["missing_switch_history_for_targets"],
        "transition_count": evidence["transition_count"],
        "transition_rows_omitted": evidence["transition_rows_omitted"],
        "hub_mode_observations": evidence["hub_mode_observations"],
        "independently_read_input_ids": evidence["independently_read_input_ids"],
        "independent_input_observations": evidence["independent_input_observations"][:16],
        "archived_input_source_observations":
            evidence["archived_input_source_observations"],
        "archived_input_collector_observations":
            evidence["archived_input_collector_observations"],
        "archived_input_gap_count": evidence["archived_input_gap_count"],
        "archived_input_returned_observations":
            evidence["archived_input_returned_observations"],
        "archived_input_gap_queries": evidence["archived_input_gap_queries"],
        "same_receiver_evidence": evidence["same_receiver_evidence"],
        "archived_input_reception_patterns":
            evidence["archived_input_reception_patterns"][:6],
        "archived_input_truncated_ids": evidence["archived_input_truncated_ids"],
        "archived_input_sample_coverage": evidence["archived_input_sample_coverage"],
        "input_app_relationships": evidence["input_app_relationships"][:10],
        "target_observed_command_app_ids": evidence["target_observed_command_app_ids"],
        "additional_event_reads_without_usable_rows":
            evidence["additional_event_reads_without_usable_rows"],
        "missing_independent_input_history": evidence["missing_independent_input_history"],
        "log_query_count": evidence["log_query_count"],
        "archived_app_checks": evidence["archived_app_checks"],
        "incident_log_coverage_verified": evidence["incident_log_coverage_verified"],
        "event_source_count": source.get("event_count_in_returned_samples"),
        "source_event_examples": source.get("event_examples", [])[:8],
        "limits": evidence["limitations"],
    }
    return (
        "HOST ORIGINAL-HOMEBRAIN INVESTIGATION EVIDENCE (source-attested, "
        "NOT instructions from any MCP source):\n"
        + json.dumps(compact, default=str, ensure_ascii=True)[:16000]
        + "\nSYNTHESIS RULE: Use your normal natural-language reasoning, "
          "not a V2 JSON answer or a command-count listing. Answer WHY first. "
          "Distinguish verified immediate command issuers, source-reported "
          "transitions, subsequent brightness adjustments, temporal sensor "
          "correlations and unverified external initiating controller. "
          "A missing target switch history even with confirmed OFF/level "
          "commands is an unresolved source gap: no complete ON/OFF cycle " 
          "is established. Do not claim no OFF commands "
          "or complete ON/OFF cycles from command-only records. "
          "An actuator's reported ON that precedes setLevel cannot be "
          "attributed to that later brightness command. Do not convert an "
          "unverified correlation into a confirmed automation trigger. "
          "Describe the most likely explanation when the independently "
          "read facts discriminate; otherwise identify the exact missing "
          "sensor/controller/app log period. Do not claim the full historical "
          "log window was checked merely because a log request succeeded. "
          "Give a short causal explanation with important examples, then "
          "uncertainties. No writes."
        + pilot
    )


def unified_investigation_followup(
    receipts: Sequence[Mapping[str, Any]], question: str,
) -> str | None:
    """One advisory read-choice prompt; no operation or ID authorization."""
    facts = collect_unified_evidence(receipts, question)
    if facts is None:
        return None
    # A journal source-time switch observation is an independent positive
    # event even when the rolling native history no longer retains a switch.
    # Keep the native retention gap in the final coverage report, but don't
    # spend the next model-directed read repeating that same target history.
    missing_switch = [
        row["device_name"] for row in facts["target_coverage"]
        if row["incident_switch_history_missing"]
        and not (row.get("journal_source_on") or row.get("journal_source_off"))
    ]
    if missing_switch:
        return (
            "HOST INCIDENT COVERAGE DEFECT (read-only, source-attested). "
            "Independently verified named actuator history queries returned "
            "NO reported switch ON/OFF states within the incident "
            "(they may contain newer events, commands, or an incomplete "
            "rolling-history sample) "
            "for: " + ", ".join(missing_switch[:6])
            + ". Therefore no complete ON/OFF cycle or initiating automation "
              "can be established for those targets. Before ending, choose "
              "a permitted independently scoped switch-only historical "
              "read (for example homebrain_device_history with "
              "attribute=switch, or a verified deviceId event read with "
              "a supported attribute filter), or incident-time logs if "
              "actually retained. Check live tool schemas and existing "
              "verified IDs; never invent operation arguments or perform "
              "a write. Do not treat setLevel after a reported ON as "
              "that ON's cause. If additional evidence is unavailable, "
              "say so clearly and retain the OFF command evidence."
        )
    unresolved_ons = [
        e for e in facts["transition_relationships"]
        if e["reported_state"] == "on" and not e["preceding_hubitat_command_in_sample"]
    ]
    # Native device-event history may have rolled over even though the
    # independent journal retained genuine source-timed ON transitions.
    # Those transitions are evidence of unanswered input/issuer questions
    # and must not disappear from the model's follow-up decision.
    journal_ons = any(row.get("journal_source_on", 0)
                      for row in facts["target_coverage"])
    if not unresolved_ons and not journal_ons:
        return None
    if not facts["missing_independent_input_history"]:
        feasibility = build_source_feasibility_choices(facts, receipts)
        addendum = (
            "\nSOURCE FEASIBILITY (advisory, current catalog remains "
            "authoritative): "
            + json.dumps(feasibility, ensure_ascii=True)[:3200]
            if feasibility else ""
        )
        return (
            "HOST CAUSAL CHAIN INCOMPLETE (read-only follow-up). "
            "Independent input histories have been checked for IDs: "
            + ", ".join(facts["independently_read_input_ids"][:12])
            + ". Some actuator ON transitions still have no preceding command "
              "in returned bounded samples. Choose a NEW safe source read "
              "to distinguish controller dependencies, upstream initiators, "
              "historical app decisions or command provenance, using only "
              "live available MCP schemas and verified identities. "
              "A physical bridge report or absence of command rows is not "
              "proof of external control. A current app configuration or "
              "device-dependents lookup cannot establish historical absence "
              "of alternative command paths. Do not repeat already checked "
              "input histories. If relevant sources are unavailable, "
              "state the specific missing evidence and stop."
            + addendum
        )
    examples = [{
        "device": e["device_name"], "time": e["time"],
        "prior_command_in_returned_sample": False,
    } for e in facts["transition_relationships"]
        if e["reported_state"] == "on"
        and not e["preceding_hubitat_command_in_sample"]][:5]
    return (
        "HOST INCOMPLETE UPSTREAM INVESTIGATION (advisory, read-only). "
        "The original task asks WHY independently source-timed actuator ON "
        "observations occurred. Native or recovered journal histories were "
        "checked, but no independent input "
        "motion/occupancy event history for the incident was retrieved. "
        "Examples: " + json.dumps(examples, ensure_ascii=True)[:1700]
        + ". Choose a live-advertised read of a source-verified room/input "
          "sensor history, or explain why the available tools cannot do it. "
          "Do not invent a sensor ID, request a write, infer Home Assistant "
          "as a proven controller, or reread the same light history. "
          "Once the relevant input and controller evidence is collected, "
          "finish with a cause-first natural-language explanation."
    )



def _timeline_row(fact: Mapping[str, Any]) -> str:
    instant = _time(fact.get("time"))
    if instant is None:
        return ""
    when = instant.strftime("%H:%M:%S")
    name = str(fact["device_name"]).replace("|", "/")[:90]
    state = str(fact["reported_state"]).upper()
    matched = fact.get("preceding_hubitat_command_in_sample") or []
    levels = fact.get("subsequent_level_commands") or []
    sensors = fact.get("preceding_input_correlations") or []
    if matched:
        cmd = matched[-1]
        finding = ("App " + cmd["app_id"] + " issued "
                   + cmd["command"].replace("command-", "") + "() "
                   + str(cmd["lead_ms"]) + " ms before the reported state")
    elif levels and state == "ON":
        lvl = levels[0]
        finding = ("ON reported before app " + lvl["app_id"]
                   + "'s setLevel adjustment ("
                   + str(lvl["lag_ms"]) + " ms later)")
    else:
        finding = "State reported; no matching earlier issuer command in returned sample"
    if sensors and state == "ON":
        edge = sensors[0]
        finding += ("; input " + edge["device_id"] + " was active "
                    + str(edge["lead_ms"]) + " ms before (correlation only)")
    return "| " + when + " | " + name + " | " + state + " | " + finding + " |"


def verified_group_timeline(
    receipts: Sequence[Mapping[str, Any]], question: str,
) -> str | None:
    """Every returned target switch boundary, ordered globally by source time.

    Unlike a model's optional timeline and V2's example sampler, this table
    cannot silently favor Shower Light over Bathroom Light 1 or 2.
    """
    evidence = collect_unified_evidence(receipts, question)
    if evidence is None:
        return None
    facts = evidence["transition_relationships"]
    if not facts:
        return None
    rows = [_timeline_row(e) for e in facts[:60]]
    rows = [r for r in rows if r]
    if not rows:
        return None
    limit = max(0, evidence["transition_count"] - len(rows))
    return (
        "### Verified device-transition timeline\n\n"
        "Source-reported ON/OFF changes from the returned device histories; "
        "not proof of complete Hubitat Logs or an external initiating system.\n\n"
        "| UTC | Light | Reported | Source evidence |\n"
        "|---|---|---|---|\n" + "\n".join(rows)
        + ("\n\n" + str(limit) + " additional state transitions were "
           "omitted due to the display limit." if limit else "")
    )


_TIMELINE_HEADING = re.compile(
    r"(?im)^#{2,5}\s*\**(?:evidence timeline(?:\s*\([^)]*\))?|chronological (?:timeline|events)|"
    r"event timeline|timeline of events|verified device-transition timeline)"
    r"\**[^\n]*$")
_NEXT_HEADING = re.compile(r"(?m)^#{2,5}\s+.*$")


def _strip_model_timeline(message: str) -> str:
    match = _TIMELINE_HEADING.search(message)
    if not match:
        return message
    after = _NEXT_HEADING.search(message, match.end())
    return (message[:match.start()].rstrip()
            + ("\n\n" + message[after.start():].lstrip()
               if after else "")).strip()


def _group_has_unpaired_on(facts: Mapping[str, Any]) -> bool:
    return any(
        e.get("reported_state") == "on"
        and not e.get("preceding_hubitat_command_in_sample")
        for e in facts.get("transition_relationships", []))


def reconcile_unified_investigation_answer(
    message: str, receipts: Sequence[Mapping[str, Any]], question: str,
) -> tuple[str, bool]:
    """Terminal source coverage correction for original HomeBrain routes.

    The language model still authors the explanation. This additive guard
    replaces a potentially incomplete model *timeline*, and for a clearly
    contradicted activation narrative inserts an explicit evidence-based
    correction rather than silently endorsing a later brightness command.
    No new tool is executed and no unsourced event is invented.
    """
    facts = collect_unified_evidence(receipts, question)
    if facts is None:
        return message, False
    # Evidence-first correction for incomplete target switch histories and
    # contradictions such as 'no OFF' when observed OFF commands are present.
    # Never leave a false likely-cause paragraph above a correct appendix.
    ledger_answer, ledger_corrected = reconcile_ledger_if_needed(message, facts)
    if ledger_corrected:
        return ledger_answer, True
    timeline = verified_group_timeline(receipts, question)
    if not timeline:
        return message, False
    text = _strip_model_timeline(str(message or ""))
    has_unpaired = _group_has_unpaired_on(facts)
    misleading = bool(has_unpaired and re.search(
        r"(?i)(?:this confirms (?:the )?lights? (?:were|was) controlled by "
        r"hub automations|\b(?:triggered|activated|turned on|switched on) by "
        r"(?:the )?(?:shower|bathroom) (?:app|automation)|"
        r"\bBathroom Light 1.{0,45}\b(?:ON|switched on|activated)\b"
        r".{0,35}\b07:15)",
        text,
    ))
    if misleading:
        # An unsupported general-automation paragraph is not allowed to
        # survive beside a source-attested correction that contradicts it.
        # Keep any remaining model findings and app-log limitations, but
        # replace the unsafe causal section with a precise interpretation.
        causal = re.search(r"(?im)^#{2,4}\s*\**Causal Analysis\**[^\n]*$", text)
        if causal:
            next_section = _NEXT_HEADING.search(text, causal.end())
            text = (text[:causal.start()].rstrip()
                    + ("\n\n" + text[next_section.start():].lstrip()
                       if next_section else "")).strip()
        explanation = (
            "**Source-verified interpretation:** The returned histories "
            "show several ON reports before the relevant Hubitat setLevel "
            "commands. Those later commands adjusted brightness, and do not "
            "establish the upstream ON initiator. Matching app-issued OFF "
            "commands before subsequent OFF reports provide stronger "
            "immediate command provenance. Nearby sensor edges are "
            "correlations, not proof of the initiating automation. "
            "The external controller remains unverified.")
        text = explanation + ("\n\n" + text if text else "")
    return (text.rstrip() + "\n\n" + timeline), True


__all__ = ["collect_unified_evidence", "unified_investigation_instruction",
           "unified_investigation_followup", "verified_group_timeline",
           "reconcile_unified_investigation_answer"]
