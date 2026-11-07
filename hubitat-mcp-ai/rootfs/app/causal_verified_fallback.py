"""Generic source-attested OFF fallback after a failed synthesis repair.

Uses no model prose and does not interpret collector reception as sensor-event
time. Only current-turn focal source receipts can authorize publication.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from claim_evidence_contract import SCHEMA, Witness, EvidencePacket, validate_claims


def _time(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _clean(raw: Any) -> str:
    text = " ".join(str(raw or "").split())
    return "".join(c for c in text if c.isalnum() or c in " -_().")[:72]


def _fmt(dt: datetime) -> str:
    return dt.strftime("%d %b %Y %H:%M:%S") + " GMT"


def _ok(row: Any) -> bool:
    return (isinstance(row, Mapping) and row.get("success") is True
            and row.get("mutates") is not True)


def verified_failed_repair_answer(
    evidence: Sequence[Mapping[str, Any]], *, original_question: str,
) -> str | None:
    """Construct a bounded fact-only answer, never a negative cause verdict."""
    from causal_completion_policy import requested_transition_scope
    if requested_transition_scope(original_question) != "off":
        return None
    candidates = set()
    for r in evidence:
        if not _ok(r) or r.get("tool") != "homebrain_causal_secondary_correlation":
            continue
        d = r.get("details") or {}
        when = _time(d.get("requestedBoundary"))
        if d.get("transition") == "off" and when and _clean(d.get("subject")):
            candidates.add((_clean(d["subject"]), when))
    if len(candidates) != 1:
        return None
    name, focal = next(iter(candidates))
    # Use source-reported switch state boundaries, not a model's timeline
    # or a Historical Journal collector-received sensor timestamp.
    states = {}
    for r in evidence:
        if (not _ok(r) or r.get("tool") != "homebrain_device_history"
                or r.get("evidence_kind") not in (
                    "authoritative_device_event_history",
                    "deterministic_device_event_history")):
            continue
        d = r.get("details") or {}
        if _clean(d.get("label")) != name or d.get("attribute") != "switch":
            continue
        for e in d.get("boundaryEvents") or []:
            if not isinstance(e, Mapping) or e.get("isStateChange") is not True:
                continue
            t = _time(e.get("date"))
            state = e.get("value")
            reporter = _clean((e.get("producedBy") or {}).get("label"))
            if not t or state not in ("on", "off") or not reporter:
                continue
            key = (t, state)
            if key in states and states[key] != reporter:
                return None
            states[key] = reporter
    ordered = sorted(states)
    if ((focal, "off") not in ordered
            or any(t > focal and state == "off" for t, state in ordered)
            or any(t == focal and state != "off" for t, state in ordered)):
        return None
    before = [key for key in ordered if key[0] < focal]
    preceding = before[-1] if before and before[-1][1] == "on" else None
    witnesses = {"off": Witness("off", name, "switch", "reporter",
                               focal.isoformat(), "source-reported", "off", "focal")}
    claims = [{"kind": "observed_value", "entity": name,
               "attribute": "switch", "value": "off", "witness_ids": ["off"]}]
    if preceding:
        witnesses["on"] = Witness("on", name, "switch", "reporter",
                                  preceding[0].isoformat(), "source-reported",
                                  "on", "preceding-on")
        claims.append({"kind": "observed_interval", "witness_ids": ["on", "off"]})
    packet = EvidencePacket(witnesses, focal_event_keys=frozenset(
        {"focal", "preceding-on"}), labels={name: name})
    verdict = validate_claims({"schema": SCHEMA, "claims": claims}, packet)
    if not verdict.envelope_ok or verdict.rejected:
        return None
    facts = {row.claim["kind"]: row.facts for row in verdict.supported}
    if "observed_value" not in facts:
        return None
    parts = [
        "**Verified recorded OFF:** " + name + " reported OFF at "
        + _fmt(focal) + ". " + states[(focal, "off")]
        + " reported the state; this does not establish who initiated it."
    ]
    if "observed_interval" in facts:
        span = round(facts["observed_interval"]["seconds"])
        h, rem = divmod(span, 3600)
        m, sec = divmod(rem, 60)
        parts.append(
            "**Recorded ON-state interval:** " + _fmt(preceding[0])
            + " to " + _fmt(focal) + " (" + str(h) + "h "
            + str(m) + "m " + str(sec) + "s). This is recorded switch "
            "state, not proven physical operating time."
        )
    targets = set()
    for row in evidence:
        if not _ok(row) or row.get("evidence_kind") != "targeted_device_lookup":
            continue
        d = (row.get("details") or {}).get("reportedDeviceState") or {}
        if _clean(d.get("label")) == name and str(d.get("deviceId") or "").isdecimal():
            targets.add(str(d["deviceId"]))
    if len(targets) == 1:
        target = next(iter(targets))
        checked = []
        for row in evidence:
            if (not _ok(row)
                    or row.get("evidence_kind") != "authoritative_command_event_history"
                    or row.get("sub_tool") != "hub_list_device_events"):
                continue
            a = (row.get("arguments") or {}).get("args") or {}
            d = row.get("details") or {}
            es = d.get("events")
            if (str(a.get("deviceId")) != target or a.get("attribute") != "command-off"
                    or d.get("eventName") != "command-off" or not isinstance(es, list)
                    or len(es) != d.get("eventCount")):
                continue
            matching = []
            for e in es:
                if not isinstance(e, Mapping):
                    continue
                t = _time(e.get("date"))
                producer = e.get("producedBy") or {}
                if (t and abs((t - focal).total_seconds()) <= 2
                        and e.get("name") == "command-off"
                        and producer.get("type") == "app"):
                    matching.append(_clean(producer.get("label")))
            checked.append((len(es), sorted(set(matching))))
        if checked:
            count, matches = max(checked, key=lambda v: v[0])
            if matches:
                parts.append(
                    "**Hubitat command evidence:** A matching recorded off() "
                    "command was issued by " + ", ".join(matches)
                    + ". The underlying reason remains unverified."
                )
            else:
                parts.append(
                    "**Hubitat command evidence:** The bounded command-off read "
                    "returned " + str(count) + " records but no verified "
                    "matching focal command. This does not prove no command "
                    "occurred outside the checked source scope."
                )
    # Distinguish independently source-timed sensor events from partial
    # archive observations and empty direct MCP sensor windows.
    windows = set()
    observed = []
    for row in evidence:
        if (not _ok(row) or row.get("tool") != "hub_read_devices"
                or row.get("sub_tool") != "hub_list_device_events"
                or row.get("evidence_kind") != "authoritative_device_event_history"):
            continue
        a = (row.get("arguments") or {}).get("args") or {}
        d = row.get("details") or {}
        start, end = _time(a.get("since")), _time(a.get("until"))
        events = d.get("events")
        if (not start or not end or not start <= focal <= end
                or a.get("attribute") not in ("motion", "presence", "occupancy")
                or d.get("windowVerified") is not True
                or str(a.get("deviceId")) != str(d.get("deviceId"))
                or a.get("attribute") != d.get("attribute")
                or not isinstance(events, list) or len(events) != d.get("eventCount")):
            continue
        windows.add((str(a.get("deviceId")), start, end))
        for e in events:
            if not isinstance(e, Mapping):
                continue
            t = _time(e.get("date"))
            if t and start <= t <= end and e.get("name") == a.get("attribute"):
                observed.append(_clean(d.get("label")) + " " + str(a["attribute"])
                                + "=" + _clean(e.get("value")) + " at " + _fmt(t))
    if observed:
        parts.append("**Source-timed sensor observations:** " + "; ".join(
            sorted(set(observed))[:3]) + ". Timing alone is not proof of a trigger.")
    archive = []
    for row in evidence:
        if not _ok(row) or row.get("tool") != "homebrain_causal_secondary_correlation":
            continue
        d = row.get("details") or {}
        if _clean(d.get("subject")) != name:
            continue
        for sensor in ((d.get("historicalJournal") or {}).get("sensors") or []):
            if not isinstance(sensor, Mapping):
                continue
            for e in sensor.get("events") or []:
                if isinstance(e, Mapping) and e.get("timestampBasis") == "collector-received":
                    archive.append(_clean(sensor.get("label")) + " "
                                   + _clean(sensor.get("attribute")) + "="
                                   + _clean(e.get("value")))
    if archive:
        parts.append(
            "**Historical Journal:** " + "; ".join(sorted(set(archive))[:3])
            + " was retained at collector reception time, not independently "
            "verified as source-timed sensor activity before OFF."
        )
    if windows:
        parts.append(
            "**Sensor history scope:** " + str(len(windows))
            + " verified absolute MCP window(s) returned "
            + str(len(observed)) + " sensor-event rows. An empty "
            "window does not prove that no motion occurred."
        )
    log_windows = set()
    focal_log_windows = set()
    for row in evidence:
        if not _ok(row) or row.get("sub_tool") != "hub_get_logs":
            continue
        a = (row.get("arguments") or {}).get("args") or {}
        if a.get("mode") != "past":
            continue
        start, end = _time(a.get("since")), _time(a.get("until"))
        if start and end:
            key = (str(a.get("appId") or a.get("deviceId") or "all"), start, end)
            log_windows.add(key)
            if start <= focal <= end:
                focal_log_windows.add(key)
    if log_windows and not focal_log_windows:
        parts.append(
            "**App-log coverage:** The returned past-log queries were for "
            "other times, not the focal OFF instant. Their empty results "
            "cannot establish app execution or non-execution at this OFF."
        )
    elif focal_log_windows:
        parts.append(
            "**App-log coverage:** " + str(len(focal_log_windows))
            + " time-bounded log request(s) included the OFF instant; "
            "a checked request is not proof of a historical initiating action."
        )
    parts.append(
        "**Conclusion:** The initiating controller remains unverified. "
        "A reporting bridge, notified apps, partial history and collector-"
        "received sensor observations do not establish the OFF cause."
    )
    return "\n\n".join(parts)


__all__ = ["verified_failed_repair_answer"]
