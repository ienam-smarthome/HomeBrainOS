"""Evidence-first causal graph for a *single observed* device transition.

This is a normalized, source-tagged factual inventory, NOT an assertion that
two temporally adjacent events are causally linked. The graph is generic across
switch/dimmer apps, configured motion/presence sensors, mode events, native
execution logs and controller command history. Future sources can add facts
without adding answer templates for individual apps or devices.

Every relationship has a role and strength: observed / confirmed direct
command / notified handler / configured / temporal correlation / unresolved.
A closing OFF transition is not attributed to an app merely because that app
was the proven issuer of the preceding ON command.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from focal_evidence_reconciliation import reconcile_focal_archived_sensor_evidence
from causal_completion_policy import evaluate_causal_completion
from causal_hypothesis_evaluation import evaluate_off_hypotheses
from causal_command_provenance import correlate_command_producers
from causal_timeline import (
    build_causal_timeline_rows,
    explicitly_focused_event_rows,
    has_explicit_focal_clock,
)
from natural_datetime import normalize_iso_offset


def _time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(normalize_iso_offset(str(value)))
    except (TypeError, ValueError):
        return None


def _eq_time(first: Any, second: Any, tolerance: float = .5) -> bool:
    a, b = _time(first), _time(second)
    if not a or not b:
        return False
    try:
        return abs((a - b).total_seconds()) <= tolerance
    except TypeError:
        return False


def _args(receipt: dict[str, Any]) -> dict[str, Any]:
    payload = receipt.get("arguments") or {}
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("args")
    return nested if isinstance(nested, dict) else payload


def _tool(receipt: dict[str, Any]) -> str:
    return str(receipt.get("sub_tool") or receipt.get("tool") or "")


def _working(receipt: dict[str, Any]) -> bool:
    return isinstance(receipt, dict) and receipt.get("success") is True


def _focus(evidence: list[dict[str, Any]], question: str) -> dict[str, Any] | None:
    selected = explicitly_focused_event_rows(evidence, question)
    if len(selected) == 1:
        return selected[0]
    # A dated historical ON can be absent from the latest-N temporal intervals
    # even when a second, exact-window native gateway read recovers it. Only
    # trust a typed, successfully retained state-event receipt from the focal
    # source planner. Never manufacture a missing light transition from an
    # earlier command or from the user's requested clock alone.
    recovered = []
    for receipt in evidence:
        if (
            not _working(receipt)
            or receipt.get("evidence_kind") not in {"focal_exact_state_history", "focal_archived_state_history"}
        ):
            continue
        details = receipt.get("details") or {}
        requested = _time(details.get("requestedOn"))
        subject = str(details.get("label") or "").strip()
        if not requested or not subject or subject.casefold() not in question.casefold():
            continue
        minute_only = bool(details.get("requestedMinuteOnly"))
        for item in details.get("events") or []:
            if not isinstance(item, dict):
                continue
            when = _time(item.get("date"))
            if item.get("name") != "switch" or item.get("value") != "on" or when is None:
                continue
            if receipt.get("evidence_kind") == "focal_archived_state_history" and item.get("timestampBasis") != "source":
                continue
            delta = (when - requested).total_seconds()
            if (0 <= delta < 60) if minute_only else abs(delta) <= .002:
                recovered.append({
                    "subject": subject, "start": str(item.get("date")),
                    "end": "", "durationSeconds": None,
                    "open": True, "material": True,
                    "observedFrom": receipt.get("evidence_kind"),
                })
    unique = {
        (str(row["subject"]), str(row["start"])): row
        for row in recovered
    }
    if len(unique) == 1:
        return next(iter(unique.values()))
    if len(unique) > 1:
        return None  # multiple ONs in requested minute: need clarification
    # An explicit historical timestamp must NEVER silently bind to a
    # different newer interval, even when that is the sole remaining row.
    if has_explicit_focal_clock(question):
        return None
    # An unfocused multi-interval question cannot be turned into an invented
    # single-event explanation. One observed interval alone can be summarized.
    all_rows = build_causal_timeline_rows(evidence)
    return all_rows[0] if len(all_rows) == 1 else None


def select_focal_sensor_events(
    data: dict[str, Any], focus: dict[str, Any],
    *, limit: int = 8, max_delta_seconds: float = 3.0,
) -> list[dict[str, Any]]:
    """Retain event history around both interval boundaries, not 50 raw rows.

    Preserve native triggered[] listener metadata and event names without
    turning a listener into command provenance. The recorder will redact and
    size-bound the rows again before storage.
    """
    events = data.get("events")
    if not isinstance(events, list):
        return []
    boundaries = [_time(focus.get("start")), _time(focus.get("end"))]
    ranked: list[tuple[float, dict[str, Any]]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        at = _time(event.get("date") or event.get("timestamp"))
        if at is None:
            continue
        deltas = [
            abs((at - boundary).total_seconds())
            for boundary in boundaries if boundary is not None
        ]
        if not deltas or min(deltas) > max_delta_seconds:
            continue
        normalized = {
            "date": str(event.get("date") or event.get("timestamp") or ""),
            "name": str(event.get("name") or event.get("attribute") or ""),
            "value": str(event.get("value") or ""),
        }
        subscribers = event.get("triggered")
        if isinstance(subscribers, list):
            normalized["triggered"] = [
                {
                    "appId": item.get("appId") or item.get("id"),
                    "handler": item.get("handler"),
                }
                for item in subscribers
                if isinstance(item, dict)
            ][:10]
        ranked.append((min(deltas), normalized))
    ranked.sort(key=lambda pair: pair[0])
    return [entry for _, entry in ranked[:max(1, int(limit))]]


def _sensor_fact(
    evidence: list[dict[str, Any]],
    focus: dict[str, Any],
    command: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not command:
        return None
    command_at = _time(command.get("time"))
    if not command_at:
        return None
    app_id = str((command.get("producer") or {}).get("id") or "")
    matched: list[tuple[float, dict[str, Any]]] = []
    for receipt in evidence:
        if not _working(receipt) or receipt.get("tool") != "homebrain_causal_trigger_correlation":
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict):
            continue
        if app_id and str(_args(receipt).get("appId") or "") != app_id:
            continue
        if not _eq_time(details.get("stateBoundary"), focus.get("start"), tolerance=.6):
            continue
        motion_at = _time(details.get("sensorEvent"))
        if not motion_at:
            continue
        try:
            delta = (command_at - motion_at).total_seconds()
        except TypeError:
            continue
        if delta < 0 or delta > 2:
            # A sensor event after the command cannot be its initiator.
            continue
        device_id = str(_args(receipt).get("deviceId") or "")
        notifications = []
        end_event = None
        end_time = _time(focus.get("end"))
        for sensor_receipt in evidence:
            if not _working(sensor_receipt) or _tool(sensor_receipt) != "hub_list_device_events":
                continue
            if str(_args(sensor_receipt).get("deviceId") or "") != device_id:
                continue
            sensor_details = sensor_receipt.get("details") or {}
            for event in sensor_details.get("events") or []:
                if not isinstance(event, dict):
                    continue
                for item in event.get("triggered") or []:
                    if not isinstance(item, dict):
                        continue
                    if (
                        str(item.get("appId") or item.get("id") or "") == app_id
                        and _eq_time(event.get("date"), details.get("sensorEvent"))
                    ):
                        notifications.append({
                            "appId": app_id, "handler": str(item.get("handler") or "")
                        })
                when = _time(event.get("date"))
                if (
                    when is not None and end_time is not None
                    and str(event.get("value") or "").casefold()
                    in {"inactive", "not present", "absent", "closed", "off"}
                ):
                    gap = (end_time - when).total_seconds()
                    if 0 <= gap <= 3:
                        end_event = {
                            "time": when.isoformat(),
                            "value": str(event.get("value") or ""),
                            "beforeEndMs": round(gap * 1000, 1),
                            "relationship": "temporal-correlation-only",
                            "offCommandProducer": "not-established",
                        }
        fact = {
            "entity": str(details.get("label") or ""),
            "deviceId": device_id,
            "attribute": str(details.get("attribute") or _args(receipt).get("attribute") or ""),
            "observedValue": "active",
            "time": motion_at.isoformat(),
            "beforeCommandMs": round(delta * 1000, 1),
            "configured": details.get("configured") is True,
            "notifiedAppHandler": notifications[0] if notifications else None,
            "status": (
                "strongly-correlated-configured-sensor"
                if details.get("configured") is True
                else "temporal-correlation-only"
            ),
            "source": "hub_list_device_events + homebrain_causal_trigger_correlation",
            "notProofOfInternalDecision": True,
            "endEvent": end_event,
        }
        matched.append((delta, fact))
    return sorted(matched, key=lambda item: item[0])[0][1] if matched else None


def _configuration(evidence: list[dict[str, Any]], app_id: str) -> dict[str, Any]:
    for receipt in reversed(evidence):
        if not _working(receipt) or _tool(receipt) != "hub_get_app_config":
            continue
        if str(_args(receipt).get("appId") or "") != app_id:
            continue
        details = receipt.get("details") or {}
        excerpts = details.get("configured") or []
        # Configuration is not historical execution. Preserve at most three
        # already-sanitized excerpts from the host's own targeted app read.
        return {
            "checked": True,
            "appId": app_id,
            "excerpts": [str(e)[:240] for e in excerpts[:3] if isinstance(e, str)],
            "provesExecution": False,
        }
    return {"checked": False, "appId": app_id, "excerpts": [], "provesExecution": False}


def _logs(evidence: list[dict[str, Any]], app_id: str, event_at: str) -> dict[str, Any]:
    stamp = _time(event_at)
    for receipt in reversed(evidence):
        if not _working(receipt) or _tool(receipt) != "hub_get_logs":
            continue
        if str(_args(receipt).get("appId") or "") != app_id:
            continue
        details = receipt.get("details") or {}
        since = _time(_args(receipt).get("since") or details.get("scopedSince"))
        until = _time(_args(receipt).get("until") or details.get("scopedUntil"))
        if stamp is None or since is None or until is None:
            continue
        if not since <= stamp <= until:
            continue
        count = details.get("logCount")
        if count is None and isinstance(details.get("logs"), list):
            count = len(details["logs"])
        return {
            "checked": True,
            "appId": app_id,
            "matchingWindow": True,
            "observedRows": count if isinstance(count, int) else None,
            "window": [since.isoformat(), until.isoformat()],
            "result": (
                "zero-observed-entries" if count == 0 else
                "entries-present" if isinstance(count, int) and count > 0 else
                "result-count-unknown"
            ),
            "internalDecisionProven": False,
        }
    return {"checked": False, "appId": app_id, "matchingWindow": False,
            "internalDecisionProven": False}


def _mode(evidence: list[dict[str, Any]], focus: dict[str, Any]) -> dict[str, Any]:
    target = _time(focus.get("start"))
    for receipt in reversed(evidence):
        if not _working(receipt):
            continue
        if receipt.get("evidence_kind") != "authoritative_location_event_history":
            continue
        details = receipt.get("details") or {}
        events = details.get("events") or details.get("observedEvents")
        if not isinstance(events, list):
            continue
        modes = []
        for event in events:
            if not isinstance(event, dict) or str(event.get("name") or "") != "mode":
                continue
            moment = _time(event.get("date"))
            if not moment or not target:
                continue
            if moment <= target:
                modes.append((moment, str(event.get("value") or "")))
        most_recent = max(modes, default=None, key=lambda item: item[0])
        nearby = (
            any(abs((target - moment).total_seconds()) <= 2 for moment, _ in modes)
            if target else None
        )
        return {
            "checked": True,
            "lastObservedBeforeEvent": (
                {"time": most_recent[0].isoformat(), "value": most_recent[1]}
                if most_recent else None
            ),
            "transitionObservedNearEvent": nearby,
            "coverage": "returned-rows-only",
            "cannotRuleOutEarlierModeInfluence": True,
        }
    return {"checked": False, "coverage": "not-checked"}


def _command(
    evidence: list[dict[str, Any]], focus: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    matched = []
    for row in correlate_command_producers(evidence):
        if not _eq_time(row.get("intervalStart"), focus.get("start"), tolerance=.002):
            continue
        if row.get("competingCommands"):
            # Multiple command producers: retain ambiguity rather than naming
            # only whichever command happens to be nearest.
            continue
        if row.get("boundaryRole") in {"start", "end"}:
            matched.append(row)
    start = next((row for row in matched if row["boundaryRole"] == "start"), None)
    end = next((row for row in matched if row["boundaryRole"] == "end"), None)

    def project(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not row:
            return None
        command = row.get("command") or {}
        return {
            "action": row.get("action"),
            "time": command.get("date"),
            "method": command.get("method"),
            "display": command.get("display") or command.get("description"),
            "producer": row.get("producer"),
            "commandBeforeStateMs": command.get("commandToStateMs"),
            "status": "confirmed-direct-command-producer",
            "source": "Hubitat command-event producedBy",
            "notProofOfUpstreamInitiator": True,
        }

    return project(start), project(end)



def _observed_state_boundary(
    evidence: list[dict[str, Any]], focus: dict[str, Any],
    *, transition: str = "on",
) -> dict[str, Any] | None:
    """Identify each bridge/reporting device and downstream event listeners.

    Device state event producedBy identifies the reporting origin, not the
    controller or human who initiated the action. The triggered[] field lists
    notified apps only and cannot be promoted into command ownership.
    """
    for receipt in evidence:
        if not _working(receipt) or receipt.get("tool") != "homebrain_device_history":
            continue
        details = receipt.get("details") or {}
        if str(details.get("label") or "") != str(focus.get("subject") or ""):
            continue
        for event in [
            *(details.get("boundaryEvents") or []),
            *(details.get("observedEvents") or []),
        ]:
            if (
                not isinstance(event, dict)
                or str(event.get("name") or "") != "switch"
                or str(event.get("value") or "").casefold() != transition
                or not _eq_time(
                    event.get("date"),
                    focus.get("start" if transition == "on" else "end"),
                    tolerance=.002,
                )
            ):
                continue
            producer = event.get("producedBy") or {}
            if not isinstance(producer, dict):
                producer = {}
            return {
                "event": str(event.get("date") or ""),
                "eventType": str(event.get("type") or ""),
                "reporter": {
                    "id": str(producer.get("id") or ""),
                    "label": str(producer.get("label") or ""),
                    "type": str(producer.get("type") or ""),
                },
                "listenersNotified": [
                    {
                        "appId": str(row.get("appId") or ""),
                        "label": str(row.get("name") or row.get("label") or ""),
                        "handler": str(row.get("handler") or ""),
                    }
                    for row in (event.get("triggered") or [])
                    if isinstance(row, dict)
                ][:8],
                "status": "observed-state-boundary",
                "reporterNotNecessarilyInitiator": True,
                "listenersNotNecessarilyCommandIssuers": True,
            }
    # Scoped native source projection may be the only retained reporter after
    # a latest-N history page evicts the requested switch boundary.
    for receipt in evidence:
        if (
            not _working(receipt)
            or receipt.get("evidence_kind") != "focal_exact_state_history"
        ):
            continue
        details = receipt.get("details") or {}
        if str(details.get("label") or "") != str(focus.get("subject") or ""):
            continue
        for event in details.get("events") or []:
            if (
                not isinstance(event, dict)
                or event.get("name") != "switch"
                or str(event.get("value") or "").casefold() != transition
                or not _eq_time(
                    event.get("date"),
                    focus.get("start" if transition == "on" else "end"),
                    tolerance=.002,
                )
            ):
                continue
            reporter = event.get("producedBy") or {}
            return {
                "event": str(event.get("date") or ""),
                "eventType": "reported-switch-state",
                "reporter": {
                    "id": str(reporter.get("id") or ""),
                    "label": str(reporter.get("label") or ""),
                    "type": str(reporter.get("type") or ""),
                },
                "listenersNotified": [],
                "status": "observed-state-boundary",
                "reporterNotNecessarilyInitiator": True,
                "listenersNotNecessarilyCommandIssuers": True,
            }
    return None


def _physical_boundary(
    evidence: list[dict[str, Any]], focus: dict[str, Any],
) -> dict[str, Any] | None:
    """Backward-compatible ON-boundary view for existing graph consumers."""
    return _observed_state_boundary(evidence, focus, transition="on")


def _controller_candidate(
    evidence: list[dict[str, Any]], focus: dict[str, Any],
) -> dict[str, Any] | None:
    """Project controller correlations without erasing *signed* event order."""
    requested = _time(focus.get("start"))
    if requested is None:
        return None
    matched = []
    for receipt in evidence:
        if (
            not _working(receipt)
            or receipt.get("tool") != "homebrain_causal_secondary_correlation"
        ):
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict):
            continue
        if str(details.get("subject") or "") != str(focus.get("subject") or ""):
            continue
        for controller in details.get("controllers") or []:
            if not isinstance(controller, dict):
                continue
            relevant = controller.get("relevantAlignments") or []
            requested_rows = [
                row for row in relevant
                if isinstance(row, dict)
                and row.get("boundaryRole") == "start"
                and _eq_time(row.get("subjectTransition"), focus.get("start"), .002)
            ]
            if not requested_rows:
                continue
            requested_row = min(
                requested_rows,
                key=lambda item: abs(float(item.get("signedDeltaSeconds") or 0)),
            )
            try:
                delta = float(requested_row.get("signedDeltaSeconds"))
            except (ValueError, TypeError):
                continue
            # One controller can correlate repeatedly over different starts.
            # Repeated near-time associations increase the strength of a
            # hypothesis but cannot prove the upstream button->light mapping.
            repeats = len({
                str(row.get("subjectTransition") or "")
                for row in relevant if isinstance(row, dict)
                and row.get("boundaryRole") == "start"
            })
            matched.append({
                "label": str(controller.get("label") or ""),
                "attribute": str(controller.get("attribute") or ""),
                "event": str(requested_row.get("controllerEvent") or ""),
                "eventValue": requested_row.get("eventValue"),
                "signedDeltaMs": round(delta * 1000, 1),
                "recordedOrder": (
                    "controller-event-after-light-state"
                    if delta > 0 else
                    "controller-event-before-light-state"
                    if delta < 0 else "simultaneous-within-clock-resolution"
                ),
                "repeatedAlignedStarts": repeats,
                "source": "homebrain_causal_secondary_correlation",
                "status": (
                    "repeated-temporal-association" if repeats >= 2
                    else "single-temporal-association"
                ),
                "directControllerToDeviceMappingProven": False,
                "clockOrTransportSkewNotExcluded": True,
            })
    if not matched:
        return None
    # Competing equally aligned controllers are ambiguous, not a unique
    # initiating event; do not select a winner based on mere milliseconds.
    matched.sort(key=lambda item: (
        -item["repeatedAlignedStarts"],
        abs(item["signedDeltaMs"]),
    ))
    best = matched[0]
    if len(matched) > 1 and (
        best["repeatedAlignedStarts"] == matched[1]["repeatedAlignedStarts"]
        and abs(best["signedDeltaMs"] - matched[1]["signedDeltaMs"]) <= 100
    ):
        return {
            "status": "ambiguous-multiple-controller-candidates",
            "candidates": matched[:3],
            "directControllerToDeviceMappingProven": False,
        }
    return best




def _controller_history_coverage(
    evidence: list[dict[str, Any]],
    focus: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Compare one proposed controller against *all observed* ON boundaries.

    Counts are about available evidence, not exhaustive real-world history.
    A controller associated with three recent starts does not explain a fourth
    start with independent confirmed command provenance.
    """
    if not candidate or candidate.get("status") != "repeated-temporal-association":
        return None
    intervals = build_causal_timeline_rows(evidence)
    observed_starts = {
        str(row.get("start") or "") for row in intervals if row.get("start")
    }
    if not observed_starts:
        return None
    match_times: set[str] = set()
    for receipt in evidence:
        if (
            not _working(receipt)
            or receipt.get("tool") != "homebrain_causal_secondary_correlation"
        ):
            continue
        details = receipt.get("details") or {}
        if str(details.get("subject") or "") != str(focus.get("subject") or ""):
            continue
        for controller in details.get("controllers") or []:
            if str(controller.get("label") or "") != candidate.get("label"):
                continue
            for event in controller.get("relevantAlignments") or []:
                if not isinstance(event, dict) or event.get("boundaryRole") != "start":
                    continue
                try:
                    delta = abs(float(event.get("signedDeltaSeconds")))
                except (ValueError, TypeError):
                    continue
                if delta > .35 or str(event.get("eventValue")) != str(candidate.get("eventValue")):
                    continue
                start = _time(event.get("subjectTransition"))
                if start is None:
                    continue
                match_times.update({
                    key for key in observed_starts if _eq_time(key, start.isoformat(), .002)
                })
    alternatives = []
    for item in correlate_command_producers(evidence):
        if item.get("boundaryRole") != "start" or item.get("competingCommands"):
            continue
        interval = str(item.get("intervalStart") or "")
        if interval not in observed_starts or interval in match_times:
            continue
        producer = item.get("producer") or {}
        if str(producer.get("type") or "").casefold() == "app":
            alternatives.append({
                "on": interval,
                "producer": str(producer.get("label") or ""),
                "appId": str(producer.get("id") or ""),
                "role": "confirmed-different-direct-command",
            })
    return {
        "observedStartCount": len(observed_starts),
        "alignedObservedStartCount": len(match_times),
        "unmatchedObservedStartCount": len(observed_starts - match_times),
        "confirmedOtherCommandStarts": alternatives[:5],
        "scope": "returned-observed-intervals-only",
        "notAnExhaustiveHistory": True,
        "doesNotProveUnmatchedMeansNoControllerUse": True,
    }



def _post_on_commands(
    evidence: list[dict[str, Any]], focus: dict[str, Any],
    *, max_after_seconds: float = 5.0,
) -> list[dict[str, Any]]:
    """Identify commands issued AFTER the physical ON-state report.

    An app calling setLevel after a bridge-reported ON is a response/adjustment,
    not evidence that the app initiated the earlier ON transition. Timestamp
    order and command producer are retained, even if no level value was read.
    """
    boundary = _time(focus.get("start"))
    if boundary is None:
        return []
    commands = []
    for receipt in evidence:
        if not _working(receipt):
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict):
            continue
        if receipt.get("tool") == "homebrain_device_history":
            if str(details.get("label") or "") != str(focus.get("subject") or ""):
                continue
            events = details.get("commandEvents") or []
        elif _tool(receipt) == "hub_list_device_events":
            if str(_args(receipt).get("attribute") or "") != "command-setLevel":
                continue
            events = details.get("events") or []
        else:
            continue
        for event in events:
            if not isinstance(event, dict):
                continue
            when = _time(event.get("date"))
            if when is None:
                continue
            try:
                delta = (when - boundary).total_seconds()
            except TypeError:
                continue
            name = str(event.get("name") or "")
            if not (0 <= delta <= max_after_seconds and name == "command-setLevel"):
                continue
            producer = event.get("producedBy") or {}
            commands.append({
                "time": when.isoformat(),
                "afterOnMs": round(delta * 1000, 1),
                "command": str(event.get("description") or ""),
                "producer": dict(producer) if isinstance(producer, dict) else {},
                "relationship": "post-on-brightness-command",
                "notTheOriginalOnCommand": True,
                "source": "Hubitat command-setLevel event",
            })
    unique = {}
    for item in commands:
        unique[(item["time"], item["command"])] = item
    return sorted(unique.values(), key=lambda item: item["afterOnMs"])[:5]


def _end_sensor_correlations(
    evidence: list[dict[str, Any]], focus: dict[str, Any]
) -> list[dict[str, Any]]:
    """Describe inactive-sensor timings at OFF without assigning the OFF actor."""
    if not focus.get("end"):
        return []
    output = []
    seen = set()
    for receipt in evidence:
        if (
            not _working(receipt)
            or receipt.get("tool") != "homebrain_causal_secondary_correlation"
        ):
            continue
        details = receipt.get("details") or {}
        if str(details.get("subject") or "") != str(focus.get("subject") or ""):
            continue
        for sensor in details.get("sensors") or []:
            if not isinstance(sensor, dict):
                continue
            for row in [
                *(sensor.get("oppositeCorrelations") or []),
                *(sensor.get("relevantCorrelations") or []),
            ]:
                if (
                    not isinstance(row, dict)
                    or row.get("boundaryRole") != "end"
                    or not _eq_time(row.get("subjectTransition"), focus["end"], .002)
                ):
                    continue
                try:
                    signed = float(row.get("signedDeltaSeconds"))
                except (TypeError, ValueError):
                    continue
                fingerprint = (str(sensor.get("label")), row.get("sensorEvent"))
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                output.append({
                    "sensor": sensor.get("label"),
                    "attribute": row.get("attribute"),
                    "value": row.get("eventValue"),
                    "time": row.get("sensorEvent"),
                    "signedDeltaMs": round(signed * 1000, 1),
                    "producer": row.get("producedBy"),
                    "relationship": "inactive-sensor-off-temporal-correlation",
                    "offCommandProducerEstablished": False,
                    "externalAutomationIdentityEstablished": False,
                })
    output.sort(key=lambda row: abs(row["signedDeltaMs"]))
    return output[:4]


def _off_provenance(
    evidence: list[dict[str, Any]],
    focus: dict[str, Any],
    command: dict[str, Any] | None,
    correlations: list[dict[str, Any]],
) -> dict[str, Any]:
    """A separate OFF causal hypothesis, never inherited from ON.

    Distinguish a bounded successful empty command page from an exhaustive
    assertion that Hubitat or external controllers did not issue any command.
    App logs are scoped to OFF time; current configuration never proves that
    a specific timer actually ran.
    """
    if not focus.get("end"):
        return {
            "observed": False, "status": "no-recorded-off-transition",
            "commandHistory": {"checked": False, "result": "not-applicable"},
        }
    reported = _observed_state_boundary(evidence, focus, transition="off")
    local_sensor_history_coverage: dict[str, Any] = {}
    windowed_sensor_retrieval: list[dict[str, Any]] = []
    for receipt in reversed(evidence):
        if (
            receipt.get("tool") == "homebrain_causal_secondary_correlation"
            and str((receipt.get("details") or {}).get("subject") or "")
                == str(focus.get("subject") or "")
        ):
            local_sensor_history_coverage = dict(
                (receipt.get("details") or {}).get("localSensorHistoryCoverage") or {}
            )
            windowed_sensor_retrieval = list(
                (receipt.get("details") or {}).get("focalWindowRetrieval") or []
            )
            break
    history: dict[str, Any] = {
        "checked": False, "result": "not-checked",
        "scope": "bounded-returned-event-page",
    }
    for row in reversed(evidence):
        if _tool(row) != "hub_list_device_events":
            continue
        args = _args(row)
        if str(args.get("attribute") or "") != "command-off":
            continue
        details = row.get("details") or {}
        if str(details.get("label") or "") != str(focus.get("subject") or ""):
            continue
        if row.get("success") is not True:
            history.update(result="unavailable")
        else:
            count = details.get("eventCount")
            if not isinstance(count, int):
                events = details.get("events")
                count = len(events) if isinstance(events, list) else None
            history.update(
                checked=True, eventCount=count,
                result=(
                    "zero-recorded-command-off-events" if count == 0
                    else "recorded-command-off-events" if isinstance(count, int)
                    else "count-not-reported"
                ),
            )
        break

    matched = [
        row for row in correlate_command_producers(evidence)
        if row.get("boundaryRole") == "end"
        and _eq_time(row.get("intervalStart"), focus["start"], tolerance=.002)
        and _eq_time(row.get("stateBoundary"), focus["end"], tolerance=.002)
    ]
    competing = any(bool(row.get("competingCommands")) for row in matched)
    producer = command.get("producer") if command else None
    source_id = (
        str(producer.get("id") or "")
        if isinstance(producer, dict)
        and str(producer.get("type") or "").casefold() == "app" else ""
    )
    app_config = _configuration(evidence, source_id) if source_id else {"checked": False}
    app_logs = _logs(evidence, source_id, str(focus["end"])) if source_id else {"checked": False}
    listener = next((
        row for row in ((reported or {}).get("listenersNotified") or [])
        if "light" in str(row.get("handler") or "").casefold()
        or "switch" in str(row.get("handler") or "").casefold()
    ), None)
    listener_id = str((listener or {}).get("appId") or "")
    # Logging from an OFF listener is distinct from direct command provenance.
    listener_logs = (
        _logs(evidence, listener_id, str(focus["end"]))
        if listener_id and listener_id != source_id else {"checked": False}
    )
    archived_app_logs: dict[str, Any] = {}
    for receipt in reversed(evidence):
        if receipt.get("tool") != "homebrain_archived_app_log_reconciliation":
            continue
        args = receipt.get("arguments") or {}
        candidate_app_id = str(args.get("appId") or "")
        if not candidate_app_id or candidate_app_id not in {source_id, listener_id}:
            continue
        start_time = _time(args.get("since"))
        end_time = _time(args.get("until"))
        focal_time = _time(focus["end"])
        if not (start_time and end_time and focal_time
                and start_time <= focal_time <= end_time):
            continue
        details = receipt.get("details")
        if isinstance(details, dict):
            archived_app_logs = dict(details)
        break
    archived_sensors = reconcile_focal_archived_sensor_evidence(
        evidence, subject=str(focus.get("subject") or ""),
        off_time=str(focus.get("end") or ""),
    )
    if competing:
        certainty = "ambiguous-multiple-command-producers"
    elif command:
        certainty = "confirmed-direct-command-producer"
    elif correlations:
        certainty = "temporal-sensor-correlation-only"
    else:
        certainty = "observed-off-with-unidentified-initiator"
    return {
        "observed": True,
        "time": focus["end"],
        "state": reported,
        "directCommand": command,
        "commandHistory": history,
        "status": certainty,
        "sensorCorrelations": correlations,
        "sensorHistoryCoverage": local_sensor_history_coverage,
        "windowedSensorRetrieval": windowed_sensor_retrieval,
        "archivedAppLogReconciliation": archived_app_logs,
        "archivedSensorEvidence": archived_sensors,
        "appProducerContext": {
            "appId": source_id,
            "configuration": app_config,
            "executionLogs": app_logs,
            "currentConfigDoesNotProveExecutedConditions": True,
        },
        "notifiedListenerContext": {
            "appId": listener_id,
            "notified": bool(listener_id),
            "notNecessarilyProducer": True,
            "configuration": (
                _configuration(evidence, listener_id)
                if listener_id else {"checked": False}
            ),
            "executionLogs": listener_logs,
        },
        "internalTimerExecutionVerified": False,
        "externalAutomationIdentityVerified": False,
        "uncertainties": [
            "A nearby inactive sensor event does not identify the OFF actor.",
            "An empty command-off page is bounded evidence, not proof no "
            "command or external bridge automation existed.",
            "The app configured for OFF handling need not have executed its "
            "inactivity timer for this specific transition.",
        ] if not command else [
            "Direct OFF command ownership does not prove the upstream sensor "
            "or timer condition that caused the app to act.",
        ],
    }


def build_causal_evidence_graph(
    evidence: list[dict[str, Any]], original_user: str
) -> dict[str, Any]:
    """Normalize one focal device event into an auditable, typed evidence graph."""
    focus = _focus(evidence, original_user)
    if not focus:
        return {
            "schema": "causal-evidence-graph/v1",
            "scope": "ambiguous-or-unobserved-event",
            "ready": False,
            "missing": ["unique-observed-device-event"],
        }
    start_command, end_command = _command(evidence, focus)
    app_id = str(((start_command or {}).get("producer") or {}).get("id") or "")
    sensor = _sensor_fact(evidence, focus, start_command)
    physical_boundary = _physical_boundary(evidence, focus)
    controller_candidate = _controller_candidate(evidence, focus)
    controller_coverage = _controller_history_coverage(
        evidence, focus, controller_candidate
    )
    post_on_commands = _post_on_commands(evidence, focus)
    end_sensor_correlations = _end_sensor_correlations(evidence, focus)
    off_provenance = _off_provenance(
        evidence, focus, end_command, end_sensor_correlations
    )
    config = _configuration(evidence, app_id) if app_id else {"checked": False}
    logs = _logs(evidence, app_id, (start_command or {}).get("time") or "") if app_id else {"checked": False}
    notified = (physical_boundary or {}).get("listenersNotified") or []
    reactive_app_id = next((
        str(row.get("appId") or "")
        for row in notified
        if isinstance(row, dict) and (
            "light" in str(row.get("handler") or "").casefold()
            or "switch" in str(row.get("handler") or "").casefold()
        )
    ), "")
    reactive_config = (
        _configuration(evidence, reactive_app_id)
        if reactive_app_id else {"checked": False}
    )
    reactive_logs = (
        _logs(evidence, reactive_app_id, focus.get("start") or "")
        if reactive_app_id else {"checked": False}
    )
    # Positive, source-tagged command evidence from the subject's prefetched
    # history is enough; it need not be fetched again under an event sub-tool.
    # Negative findings still require an actual scoped command-history read.
    post_on_history_checked = bool(post_on_commands) or any(
        _working(item)
        and _tool(item) == "hub_list_device_events"
        and str(_args(item).get("attribute") or "") == "command-setLevel"
        for item in evidence
    )
    alternate_sensors_checked = any(
        _working(item)
        and item.get("tool") == "homebrain_causal_secondary_correlation"
        for item in evidence
    )
    physical_evidence_complete = bool(
        (physical_boundary or {}).get("eventType") == "physical"
        and (controller_candidate or {}).get("status") == "repeated-temporal-association"
        and reactive_config.get("checked")
        and reactive_config.get("excerpts")
        and reactive_logs.get("checked")
        and post_on_history_checked
        and alternate_sensors_checked
    )
    mode = _mode(evidence, focus)
    missing = []
    if not start_command:
        missing.append("direct-command-producer")
    if app_id and not config.get("checked"):
        missing.append("controlling-app-configuration")
    if not sensor:
        missing.append("configured-or-correlated-upstream-sensor-event")
    if app_id and not logs.get("checked"):
        missing.append("focal-app-execution-log-window")

    graph = {
        "schema": "causal-evidence-graph/v1",
        "scope": "single-observed-event",
        "focus": {
            "subject": focus.get("subject"),
            "on": focus.get("start"),
            "off": focus.get("end") or None,
            "durationSeconds": focus.get("durationSeconds"),
            "status": "observed-device-event-history",
            "sourceCoverage": "bounded-recorded-events",
        },
        "directCommand": start_command,
        "physicalStateBoundary": physical_boundary,
        "controllerCandidate": controller_candidate,
        "controllerCoverage": controller_coverage,
        "postOnCommands": post_on_commands,
        "offSensorCorrelations": end_sensor_correlations,
        "initiatorCandidate": sensor,
        "configuration": config,
        "executionLogs": logs,
        "reactiveApp": {
            "appId": reactive_app_id,
            "wasNotified": bool(reactive_app_id),
            "notificationIsNotDirectCommand": True,
            "configuration": reactive_config,
            "executionLogs": reactive_logs,
        },
        "postOnCommandHistoryChecked": post_on_history_checked,
        "otherSensorEvidenceChecked": alternate_sensors_checked,
        "physicalEvidenceComplete": physical_evidence_complete,
        "locationMode": mode,
        "transitionEvidence": {
            "on": {
                "state": physical_boundary,
                "directCommand": start_command,
                "triggerCandidate": sensor or controller_candidate,
                "producerVerified": bool(start_command),
                "confidence": (
                    "confirmed-direct-command" if start_command
                    else "strong-controller-association"
                    if (controller_candidate or {}).get("status") ==
                        "repeated-temporal-association"
                    else "unresolved"
                ),
                "appConfiguration": config,
                "executionLogs": logs,
            },
            "off": off_provenance,
        },
        "offCommand": end_command,
        "offAttribution": (
            "confirmed-direct-command" if end_command else
            "unresolved-no-proven-off-command"
        ) if focus.get("end") else "not-observed",
        "causalLimits": [
            "A configured sensor's timestamp before an app command is a strong "
            "initiator hypothesis, not a logged internal rule decision.",
            "The app's direct command ownership does not rule out upstream manual "
            "input, mode context, or a separate upstream automation.",
            "An inactive sensor event preceding OFF is temporal end correlation; "
            "without OFF command provenance it does not prove the rule's OFF logic.",
            "Listener metadata proves app notification, not that a handler's "
            "conditions passed or issued a command.",
            "An app's setLevel command recorded AFTER the physical ON report "
            "is a brightness correction/reaction candidate, not an originating "
            "ON command. Sensor inactivity near OFF does not identify an Aqara, "
            "Hue, Hubitat or other external automation without its own logs.",
            "A reporting bridge's producedBy on the physical state event proves "
            "where the state report came from, not who pressed the control.",
            "Do not claim a controller matched ALL observed ON runs unless "
            "controllerCoverage.alignedObservedStartCount equals the actual "
            "observedStartCount; other confirmed command producers are material "
            "exceptions to a universal initiating-button explanation.",
            "A button event reported *after* the light state cannot be proven "
            "as the earlier Hubitat-side trigger by timestamp correlation alone; "
            "transport/report ordering may differ, so label repeated short-skew "
            "matches as a likely association, not confirmed causality.",
        ],
        "missing": missing,
        "ready": bool(start_command and sensor and config.get("checked") and logs.get("checked")),
    }

    graph["offHypotheses"] = evaluate_off_hypotheses(graph)
    return graph


def needs_mode_history(graph: dict[str, Any], original_user: str) -> bool:
    """One optional targeted follow-up; never demand a whole-hub audit."""
    if graph.get("scope") != "single-observed-event":
        return False
    if graph.get("locationMode", {}).get("checked"):
        return False
    prompt = str(original_user or "").casefold()
    if not re.search(r"\b(?:alternativ(?:e|es)|mode|other causes|other triggers)\b", prompt):
        return False
    config = graph.get("configuration") or {}
    if not config.get("checked"):
        config = ((graph.get("reactiveApp") or {}).get("configuration") or {})
    return config.get("checked") is True and any(
        "mode" in str(item).casefold() for item in config.get("excerpts") or []
    )


def supports_one_pass_deep_synthesis(
    graph: dict[str, Any], original_user: str
) -> bool:
    """Declare completion by observed facts and checked source classes.

    A verified OFF actor is NOT a prerequisite: an unidentified OFF after
    checking bounded command history, relevant app context and local sensors
    is a valid completed result. No "alternative/manual/mode" keyword test.
    """
    decision = evaluate_causal_completion(
        graph, original_user,
        mode_history_required=needs_mode_history(graph, original_user),
    )
    return decision["complete"] is True


def render_causal_evidence_graph(
    evidence: list[dict[str, Any]], original_user: str,
) -> str | None:
    """Compact deterministic facts, direction and gaps for the final model."""
    graph = build_causal_evidence_graph(evidence, original_user)
    if graph.get("scope") != "single-observed-event":
        return None
    return (
        "HOST STRUCTURED CAUSAL EVIDENCE GRAPH (authoritative for fact "
        "provenance, not a pre-decided causal verdict):\n"
        + json.dumps(graph, ensure_ascii=False, default=str, separators=(",", ":"))
        + "\nEvidence rules: distinguish direct device command, physical "
        "bridge reporting, upstream sensor/controller correlation, app-handler "
        "notification, current configuration and native app logs. Preserve "
        "signed event ordering and treat controller events recorded after the "
        "state change as probable association ONLY when repeated, never as "
        "a confirmed Hubitat-side earlier command. Never promote a sensor "
        "timestamp or an app's listener into a proven rule-branch execution. "
        "The ON and OFF transitionEvidence objects have independent actors, "
        "logs, trigger candidates and uncertainty. Never identify OFF as likely "
        "caused by an inactive sensor merely from time alignment, even when "
        "ON is well explained. Only an OFF-aligned command verifies the direct "
        "OFF producer; the specific upstream timer or sensor remains separately "
        "unverified. Empty OFF-command pages are bounded observations, not "
        "proof of no external command. "
        "Report unavailable sources as gaps; if a configured inactive timer "
        "and OFF event timing appear inconsistent, do not invent an OFF cause."
    )


__all__ = [
    "build_causal_evidence_graph",
    "needs_mode_history",
    "render_causal_evidence_graph",
    "select_focal_sensor_events",
    "supports_one_pass_deep_synthesis",
]
