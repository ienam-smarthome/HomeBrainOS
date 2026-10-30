"""Source-only V2 evidence primitives reused by the original HomeBrain agent.

No V2 planner, claim-catalog publisher, JSON answer contract or tool executor is
imported. The original model remains responsible for choosing further READs and
writing natural-language conclusions; this bridge only preserves independently
read source facts and exact temporal relationships.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
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


_EXPLICIT_CLOCK_RANGE = re.compile(
    r"\b(?:between|from)\s+(\d{1,2}):(\d{2})\s*"
    r"(?:and|to|[-–])\s*(\d{1,2}):(\d{2})\b", re.I)


def _in_user_period(when: datetime, question: str, incident: Any) -> bool:
    if incident is not None and not incident.contains(when.isoformat()):
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
                if when is None or not _in_user_period(when, question, incident):
                    continue
                all_events.append({**e, "device_id": device_id,
                                   "read": index, "when": when})
        else:
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
    state_links.sort(key=lambda e: (_time(e["time"]), e["device_name"]))
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
        "source_event_packet": packet or {},
        "transition_relationships": state_links[:100],
        "transition_count": len(state_links),
        "transition_rows_omitted": max(0, len(state_links) - 100),
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
    # Source event receipts may be lengthy. Put directional comparisons
    # first: their order proves that a brightness command occurring AFTER
    # a source-reported ON cannot have initiated that earlier ON.
    source = evidence["source_event_packet"]
    compact = {
        "target_names": evidence["user_target_names"],
        "target_read_ids": evidence["target_device_ids"],
        "transition_relationships": evidence["transition_relationships"][:40],
        "transition_count": evidence["transition_count"],
        "transition_rows_omitted": evidence["transition_rows_omitted"],
        "hub_mode_observations": evidence["hub_mode_observations"],
        "independently_read_input_ids": evidence["independently_read_input_ids"],
        "missing_independent_input_history": evidence["missing_independent_input_history"],
        "log_query_count": evidence["log_query_count"],
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
    r"(?im)^#{2,5}\s*\**(?:chronological (?:timeline|events)|"
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
