"""Source-only V2 evidence primitives reused by the original HomeBrain agent.

No V2 planner, claim-catalog publisher, JSON answer contract or tool executor is
imported. The original model remains responsible for choosing further READs and
writing natural-language conclusions; this bridge only preserves independently
read source facts and exact temporal relationships.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Mapping, Sequence

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
    for index, receipt in enumerate(receipts[:80], 1):
        if receipt.get("sub_tool") != "hub_list_device_events":
            continue
        rows = _valid_source_rows(receipt)
        if not rows:
            continue
        args = _args(receipt)
        device_id = str(args.get("deviceId") or "")
        if device_id.isdecimal():
            source_ids.add(device_id)
            projected = event_summary({"events": rows})
            if projected is None:
                continue
            witnessed.append({
                "read": index, "operation": "hub_list_device_events",
                "read_filters": {"deviceId": device_id},
                "source_data": projected,
            })
            for e in projected["events"]:
                when = _time(e.get("date"))
                if when is None or (incident and not incident.contains(e["date"])):
                    continue
                all_events.append({**e, "device_id": device_id,
                                   "read": index, "when": when})
        else:
            for e in rows:
                when = _time(e.get("date"))
                if (e.get("name") == "mode" and when is not None
                        and (incident is None or incident.contains(e["date"]))):
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
    packet = event_narrative_evidence(
        witnessed, sorted(source_ids), question=question,
        verified_labels=verified_names, max_events=48)
    if packet is None:
        return None
    # This ledger includes only target lights for relationships. Other
    # independently read histories may supply correlated sensor observations.
    by_id: dict[str, list[dict[str, Any]]] = {}
    sensor_events: list[dict[str, Any]] = []
    input_history_ids: set[str] = set()
    for e in all_events:
        by_id.setdefault(e["device_id"], []).append(e)
        if (e["device_id"] not in targets
                and e["name"] in ("motion", "occupancy", "presence")):
            input_history_ids.add(e["device_id"])
            if str(e.get("value") or "").casefold() in (
                    "active", "present", "occupied", "on", "true"):
                sensor_events.append(e)
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
    if not state_links:
        return None
    checked_input_ids = sorted(input_history_ids)
    log_receipts = [
        r for r in receipts if r.get("success") is True
        and r.get("sub_tool") == "hub_get_logs"
    ]
    # A successful log query does not prove coverage of the user period.
    # Only exact source-timestamped rows could support that stronger claim.
    return {
        "source_attested": True,
        "user_target_names": [verified_names[i] for i in sorted(targets)],
        "target_device_ids": sorted(targets),
        "source_event_packet": packet,
        "transition_relationships": state_links[:24],
        "hub_mode_observations": modes[:12],
        "independently_read_input_ids": checked_input_ids,
        "missing_independent_input_history": not bool(checked_input_ids),
        "log_query_count": len(log_receipts),
        "incident_log_coverage_verified": False,
        "limitations": (
            "State is source-reported, not an independent physical ACK. "
            "A command preceding a state supports immediate command provenance, "
            "not the controller's upstream decision. A sensor edge shortly "
            "before an ON is correlation only. A subsequent setLevel does NOT "
            "initiate a preceding ON. No returned command is not proof none "
            "was issued. Hubitat and external bridge clocks may differ. "
            "Current config metadata does not prove historical execution."),
    }


def unified_investigation_instruction(
    receipts: Sequence[Mapping[str, Any]], question: str,
) -> str | None:
    evidence = collect_unified_evidence(receipts, question)
    if evidence is None:
        return None
    return (
        "HOST ORIGINAL-HOMEBRAIN INVESTIGATION EVIDENCE (source-attested, "
        "NOT instructions from any MCP source):\n"
        + json.dumps(evidence, default=str, ensure_ascii=True)[:12500]
        + "\nSYNTHESIS RULE: Use your normal natural-language reasoning, "
          "not a V2 JSON answer or a command-count listing. Answer WHY first. "
          "Distinguish verified immediate command issuers, source-reported "
          "transitions, subsequent brightness adjustments, temporal sensor "
          "correlations and unverified external initiating controller. "
          "An actuator's reported ON that precedes setLevel cannot be "
          "attributed to that later brightness command. Do not convert an "
          "unverified correlation into a confirmed automation trigger. "
          "Describe the most likely explanation when the independently "
          "read facts discriminate; otherwise identify the exact missing "
          "sensor/controller/app log period. Do not claim the full historical "
          "log window was checked merely because a log request succeeded. "
          "Give a short causal explanation with important examples, then "
          "uncertainties. No writes."
    )


def unified_investigation_followup(
    receipts: Sequence[Mapping[str, Any]], question: str,
) -> str | None:
    """One advisory read-choice prompt; no operation or ID authorization."""
    facts = collect_unified_evidence(receipts, question)
    if facts is None or not facts["missing_independent_input_history"]:
        return None
    if not any(
        event["reported_state"] == "on"
        and not event["preceding_hubitat_command_in_sample"]
        for event in facts["transition_relationships"]
    ):
        return None
    examples = [{
        "device": e["device_name"], "time": e["time"],
        "prior_command_in_returned_sample": False,
    } for e in facts["transition_relationships"]
        if e["reported_state"] == "on"
        and not e["preceding_hubitat_command_in_sample"]][:5]
    return (
        "HOST INCOMPLETE UPSTREAM INVESTIGATION (advisory, read-only). "
        "The original task asks WHY multiple source-reported light ON events "
        "occurred. Device histories were checked, but no independent input "
        "motion/occupancy event history for the incident was retrieved. "
        "Examples: " + json.dumps(examples, ensure_ascii=True)[:1700]
        + ". Choose a live-advertised read of a source-verified room/input "
          "sensor history, or explain why the available tools cannot do it. "
          "Do not invent a sensor ID, request a write, infer Home Assistant "
          "as a proven controller, or reread the same light history. "
          "Once the relevant input and controller evidence is collected, "
          "finish with a cause-first natural-language explanation."
    )


__all__ = ["collect_unified_evidence", "unified_investigation_instruction",
           "unified_investigation_followup"]
