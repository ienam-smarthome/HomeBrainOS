"""Conservative, source-typed adapter from current-turn evidence to claim-v2.

It does not trust a model's event selection, infer complete history from a
successful read or promote Historical Journal reception into a source sensor
clock. Reuses the canonical claim_evidence_contract; no model or MCP calls.
Only a uniquely grounded causal focal OFF can generate a non-empty packet.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence
import re
from native_past_log_receipt import summarize_past_log_requests

from claim_evidence_contract import (
    SCHEMA, Coverage, EvidencePacket, Witness, validate_claims,
    coverage_from_verified_window_reads,
)

_SENSORS = frozenset({"motion", "presence", "occupancy"})


def _time(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _label(raw: Any) -> str:
    return re.sub(r"[\x00-\x1f\x7f|<>]", " ",
                  " ".join(str(raw or "").split()))[:72]


def _ok(row: Any) -> bool:
    return (isinstance(row, Mapping) and row.get("success") is True
            and row.get("mutates") is not True
            and row.get("effect") in ("read", None))


def _args(row: Mapping[str, Any]) -> Mapping[str, Any]:
    arguments = row.get("arguments") or {}
    if not isinstance(arguments, Mapping):
        return {}
    inner = arguments.get("args")
    return inner if isinstance(inner, Mapping) else arguments


def _latest_off_causal_question(question: str) -> bool:
    """Read-only historical causal intent, never proof of an OFF event."""
    from causal_completion_policy import requested_transition_scope

    q = str(question or "")
    return (
        requested_transition_scope(q) == "off"
        and bool(re.search(r"\b(?:last|latest|most\s+recent(?:ly)?)\b", q, re.I))
        and bool(re.search(r"\b(?:why|caus\w*|investigat\w*)\b", q, re.I))
    )


def _focal_and_target(
    evidence: Sequence[Mapping[str, Any]], *, original_question: str = "",
) -> tuple[str, str, datetime, str] | None:
    """Anchor to a trusted correlation OR unique device-history latest OFF."""
    targets: set[tuple[str, str]] = set()
    for row in evidence[:200]:
        if not _ok(row) or row.get("evidence_kind") != "targeted_device_lookup":
            continue
        data = row.get("details") or {}
        if not isinstance(data, Mapping):
            continue
        state = data.get("reportedDeviceState") or {}
        if not isinstance(state, Mapping):
            continue
        entity = str(state.get("deviceId") or "")
        name = _label(state.get("label"))
        if entity.isdecimal() and name:
            targets.add((entity, name))
    if len(targets) != 1:
        return None
    entity, name = next(iter(targets))

    hosts = set()
    for row in evidence[:200]:
        if not _ok(row) or row.get("tool") != "homebrain_causal_secondary_correlation":
            continue
        data = row.get("details") or {}
        if not isinstance(data, Mapping) or data.get("transition") != "off":
            continue
        boundary = _time(data.get("requestedBoundary"))
        label = _label(data.get("subject"))
        if boundary and label:
            hosts.add((label, boundary))
    if hosts:
        if len(hosts) != 1:
            return None
        label, boundary = next(iter(hosts))
        if label != name:
            return None
        return entity, name, boundary, "host-correlation"

    if (not _latest_off_causal_question(original_question)
            or name.casefold() not in str(original_question).casefold()):
        return None
    # Source history is a host-built projection of native Hubitat state
    # reports; it can verify a latest returned OFF without claiming complete
    # historical coverage or identifying an upstream initiating controller.
    off_instants = set()
    for row in evidence[:200]:
        if (not _ok(row) or row.get("tool") != "homebrain_device_history"
                or row.get("supports_live_claim") is False
                or row.get("evidence_kind") not in {
                    "authoritative_device_event_history",
                    "deterministic_device_event_history",
                }):
            continue
        data = row.get("details") or {}
        if (not isinstance(data, Mapping) or _label(data.get("label")) != name
                or data.get("attribute") != "switch"):
            continue
        for event in (data.get("boundaryEvents") or [])[:150]:
            if (not isinstance(event, Mapping)
                    or event.get("name") != "switch"
                    or event.get("isStateChange") is not True
                    or event.get("value") != "off"):
                continue
            when = _time(event.get("date"))
            producer = event.get("producedBy") or {}
            if (when and isinstance(producer, Mapping)
                    and producer.get("type") == "device"
                    and str(producer.get("id") or "").isdecimal()):
                off_instants.add(when)
    if not off_instants:
        return None
    return entity, name, max(off_instants), "source-history-latest-off"


def packet_from_evidence(
    evidence: Sequence[Mapping[str, Any]], *, original_question: str = "",
) -> EvidencePacket:
    """Trust no model prose, duplicate projected events or incomplete reads."""
    if not isinstance(evidence, (list, tuple)):
        return EvidencePacket({})
    scoped = [r for r in evidence[:200] if _ok(r)]
    focal = _focal_and_target(scoped, original_question=original_question)
    if not focal:
        return EvidencePacket({})
    ident, name, off_time, focal_origin = focal
    labels: dict[str, str] = {ident: name}

    states: dict[tuple[datetime, str], Mapping[str, Any]] = {}
    for row in scoped:
        if (row.get("tool") != "homebrain_device_history"
                or row.get("evidence_kind") not in {
                    "authoritative_device_event_history",
                    "deterministic_device_event_history",
                }):
            continue
        data = row.get("details") or {}
        if not isinstance(data, Mapping) or (
            _label(data.get("label")) != name
            or data.get("attribute") != "switch"
        ):
            continue
        for event in (data.get("boundaryEvents") or [])[:150]:
            if (not isinstance(event, Mapping)
                    or event.get("isStateChange") is not True
                    or event.get("name") != "switch"
                    or event.get("value") not in {"on", "off"}):
                continue
            instant = _time(event.get("date"))
            producer = event.get("producedBy") or {}
            if (not instant or not isinstance(producer, Mapping)
                    or not _label(producer.get("label"))):
                continue
            key = (instant, str(event["value"]))
            if key in states:
                prior = states[key].get("producedBy") or {}
                if _label(prior.get("label")) != _label(producer.get("label")):
                    return EvidencePacket({})  # conflict: don't choose one
            states[key] = event
    if ((off_time, "off") not in states
            or any(moment > off_time and state == "off"
                   for moment, state in states)
            or any(moment == off_time and state != "off"
                   for moment, state in states)):
        return EvidencePacket({})
    sorted_states = sorted(states, reverse=True)
    if not sorted_states:
        return EvidencePacket({})
    previous = next(
        (item for item in sorted_states[1:]
         if item[0] < off_time), None
    )
    # This intentionally includes preceding ON but not all older transitions
    # in the primary answer focus. Other OFFs are selected by code, not model.
    focus_keys = set()
    witnesses: dict[str, Witness] = {}
    eligible = set()
    state_counts = {"on": 0, "off": 0}
    for instant, state in sorted_states[:160]:
        state_counts[state] += 1
        wid = f"w_{state}{state_counts[state]}"
        ek = f"{ident}|switch|{instant.isoformat()}|{state}"
        witnesses[wid] = Witness(
            wid, ident, "switch", "reporter", instant.isoformat(),
            "source-reported", state, ek,
            source_class="hubitat-device-history",
        )
        if state == "off":
            eligible.add(ek)
        if (instant, state) == (off_time, "off") or (
            previous and (instant, state) == previous
        ):
            focus_keys.add(ek)

    # Canonical direct command history is the source of the pairing sample.
    # Do not mix derived/replayed commandEvents with native direct records.
    command_reads: list[tuple[datetime, Mapping[str, Any], Mapping[str, Any]]] = []
    for row in scoped:
        if (row.get("tool") != "hub_read_devices"
                or row.get("sub_tool") != "hub_list_device_events"
                or row.get("evidence_kind") != "authoritative_command_event_history"):
            continue
        args = _args(row)
        detail = row.get("details") or {}
        if (not isinstance(detail, Mapping)
                or str(args.get("deviceId") or "") != ident
                or args.get("attribute") != "command-off"
                or detail.get("eventName") != "command-off"):
            continue
        rows = detail.get("events")
        count = detail.get("eventCount")
        req_time = _time(row.get("timestamp"))
        lookback = args.get("hoursBack")
        if (not isinstance(rows, list)
                or not isinstance(count, int) or isinstance(count, bool)
                or count != len(rows)
                or not req_time or not isinstance(lookback, (int, float))
                or not 0 < lookback <= 24 * 366):
            continue
        command_reads.append((req_time, detail, args))

    coverage: dict[str, Coverage] = {
        c.coverage_id: c
        for c in coverage_from_verified_window_reads(scoped)
    }
    command_pairing_id = ""
    if command_reads:
        # Avoid false overlap from inconsistent duplicate returned pages.
        # Choose the read with most evidence, without merging unrelated
        # pages or claiming complete history/retention.
        req_time, detail, args = max(
            command_reads, key=lambda p: len(p[1].get("events") or [])
        )
        command_pairing_id = (
            f"{ident}|command-off|{req_time.isoformat()}"
        )
        coverage[command_pairing_id] = Coverage(
            command_pairing_id, ident, "native returned command-off records",
            (req_time - timedelta(hours=float(args["hoursBack"]))).isoformat(),
            req_time.isoformat(), pages_checked=1, complete=False,
            successful=True, matched_count=int(detail["eventCount"]),
            query_kind="command-off",
        )
        seen_cmd = {}
        for event in detail["events"]:
            if (not isinstance(event, Mapping)
                    or event.get("name") != "command-off"
                    or event.get("type") != "command"):
                continue
            t = _time(event.get("date"))
            by = event.get("producedBy") or {}
            if (not t or not isinstance(by, Mapping)
                    or by.get("type") != "app"
                    or not str(by.get("id") or "").isdecimal()):
                continue
            key = (t, str(by["id"]))
            seen_cmd[key] = event
        for i, (stamp, issuer) in enumerate(sorted(seen_cmd, reverse=True), 1):
            wid = f"w_c{i}"
            ek = f"{ident}|command-off|{stamp.isoformat()}|{issuer}"
            witnesses[wid] = Witness(
                wid, ident, "command-off", "command-issuer",
                stamp.isoformat(), "hubitat-command", "", ek,
                app_issuer=issuer, source_class="hubitat-device-history",
            )
            if any(abs((stamp - anchor[0]).total_seconds()) <= 2
                   for anchor in ((off_time, "off"), previous)
                   if anchor):
                focus_keys.add(ek)

    # Archive is a receipt of an observation, not proof of sensor edge time.
    journal_keys = set()
    archive_seen = set()
    candidate_counts = []
    for row in scoped:
        if row.get("tool") != "homebrain_causal_secondary_correlation":
            continue
        d = row.get("details") or {}
        if (not isinstance(d, Mapping)
                or _label(d.get("subject")) != name
                or _time(d.get("requestedBoundary")) != off_time):
            continue
        disposition = (d.get("sensorSelection") or {}).get("candidateDisposition")
        if isinstance(disposition, list) and disposition and all(
            isinstance(item, Mapping) and str(item.get("id") or "").isdecimal()
            for item in disposition
        ):
            # "probed" means selection-stage examination, not a verified
            # native history read. Expose these distinct counts explicitly.
            uniq = {str(item["id"]): str(item.get("reason") or "")
                    for item in disposition}
            candidate_counts.append((len(uniq), sum(
                reason == "probed" for reason in uniq.values())))
        journal = (d.get("historicalJournal") or {}).get("sensors") or []
        for sensor in journal[:32]:
            if not isinstance(sensor, Mapping):
                continue
            sid = str(sensor.get("deviceId") or "")
            attribute = str(sensor.get("attribute") or "")
            if not sid.isdecimal() or attribute not in _SENSORS:
                continue
            labels[sid] = _label(sensor.get("label")) or f"Device {sid}"
            for event in (sensor.get("events") or [])[:50]:
                if (not isinstance(event, Mapping)
                        or event.get("timestampBasis") != "collector-received"):
                    continue
                received = _time(event.get("observedAt"))
                val = str(event.get("value") or "")[:32]
                if not received or not val:
                    continue
                key = (sid, attribute, received, val)
                archive_seen.add(key)
    for i, (sid, attr, received, value) in enumerate(
        sorted(archive_seen, key=lambda x: x[2], reverse=True)[:48], 1
    ):
        wid = f"w_j{i}"
        ek = f"journal|{sid}|{attr}|{received.isoformat()}|{value}"
        witnesses[wid] = Witness(
            wid, sid, attr, "journal-reception", received.isoformat(),
            "collector-received", value, ek, source_class="historical-journal",
        )
        if abs((received - off_time).total_seconds()) <= 120:
            journal_keys.add(ek)

    native_keys = {
        (c.entity, c.query_kind, c.window_start, c.window_end)
        for c in coverage.values()
        if c.source == "verified native device-event page"
    }
    log_scope = summarize_past_log_requests(scoped, off_time.isoformat())

    sensor_stats = candidate_counts[0] if candidate_counts and len(
        set(candidate_counts)
    ) == 1 else (None, None)
    return EvidencePacket(
        witnesses=witnesses, coverage=coverage,
        focal_event_keys=frozenset(focus_keys),
        root_cause_verified=False, focal_time=off_time.isoformat(),
        focal_source=focal_origin,
        journal_reception_event_keys=frozenset(journal_keys),
        eligible_transition_keys=frozenset(eligible),
        labels=labels, candidate_sensor_count=sensor_stats[0],
        candidate_sensor_probed_count=sensor_stats[1],
        direct_sensor_windows_checked=len(native_keys),
        internal_configuration_inspected=False,
        log_reads_total=log_scope["past_log_requests"],
        log_reads_containing_focal=log_scope["bounded_log_requests_covering_focal"],
        log_request_coverage=log_scope,
    )


def witness_menu(packet: EvidencePacket, *, limit: int = 36) -> str:
    """Bounded, escaped model-facing witness menu; not enabled in prompts."""
    if not packet.focal_event_keys:
        return ""
    limit = max(1, min(64, int(limit)))
    output = []
    for wid, row in list(packet.witnesses.items())[:limit]:
        label = _label(packet.labels.get(row.entity, row.entity))
        output.append(
            f"{wid}|{label}|{row.event_class}={_label(row.value)}|"
            f"{row.time}|{row.role}|{row.clock_basis}|"
            f"{'focal' if row.event_key in packet.focal_event_keys else 'context'}"
        )
    return "\n".join(output)


def assess_evidence_shadow(
    evidence: Sequence[Mapping[str, Any]], *, original_question: str = "",
) -> dict[str, Any]:
    """Pure shadow sidecar: summaries only, no question/model prompt or writes.

    No first-answer truth score is claimed; no natural-language model claims
    are evaluated until such an envelope actually exists.
    """
    packet = packet_from_evidence(evidence, original_question=original_question)
    if not packet.focal_time:
        return {"schema": SCHEMA, "shadow_only": True,
                "focal_attested": False, "model_claims_assessed": False}
    claims = []
    off = next(
        (w for w in packet.witnesses.values()
         if w.event_class == "switch" and w.value == "off"
         and w.role == "reporter" and w.event_key in packet.focal_event_keys),
        None,
    )
    if off:
        claims.append({
            "kind": "observed_value", "entity": off.entity,
            "attribute": "switch", "value": "off", "witness_ids": [off.witness_id],
        })
    pairings = [
        (key, cov) for key, cov in packet.coverage.items()
        if cov.query_kind == "command-off" and cov.entity == off.entity
    ] if off else []
    if pairings:
        key, _ = pairings[0]
        claims.append({"kind": "transition_pairing", "entity": off.entity,
                       "coverage_id": key})
    verdict = validate_claims({"schema": SCHEMA, "claims": claims}, packet)
    paired = next(
        (r.facts for r in verdict.supported
         if r.claim.get("kind") == "transition_pairing"), None,
    )
    return {
        "schema": SCHEMA, "shadow_only": True,
        "focal_attested": off is not None,
        "focal_source": packet.focal_source,
        "model_claims_assessed": False,
        "host_claims_supported": len(verdict.supported),
        "host_claims_rejected": len(verdict.rejected),
        "reason_codes": sorted({r.reason for r in verdict.rejected}),
        "reported_off_count": len(packet.eligible_transition_keys),
        "returned_command_pairing": (
            {"off_transitions": paired["total"],
             "matching_recorded_commands": paired["matched"],
             "unmatched_in_returned_records": paired["unmatched"],
             "matching_tolerance_seconds": paired["threshold_seconds"],
             "historical_completeness_verified": False}
            if paired else None
        ),
        "archived_collector_observation_count": sum(
            w.role == "journal-reception" for w in packet.witnesses.values()
        ),
        "source_sensor_windows_checked": packet.direct_sensor_windows_checked,
        "candidate_sensors": packet.candidate_sensor_count,
        "candidate_sensors_marked_probed": packet.candidate_sensor_probed_count,
        "app_log_requests": packet.log_reads_total,
        "app_log_requests_covering_focal": packet.log_reads_containing_focal,
        "log_request_coverage": dict(packet.log_request_coverage),
        "relevant_app_rule_configuration_verified":
            packet.internal_configuration_inspected,
    }


__all__ = ["packet_from_evidence", "witness_menu", "assess_evidence_shadow",
           "_latest_off_causal_question"]
