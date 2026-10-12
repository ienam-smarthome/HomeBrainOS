"""Adaptive, evidence-driven discovery for unexplained device transitions.

The planner deliberately separates three concepts:
1. Candidate discovery: cached device capabilities, rooms and configured links.
2. Observed correlation: bounded history reads and ordered event timestamps.
3. Causal attribution: requires actual command / execution provenance elsewhere.

It does NOT assume a specific device name, room layout, bridge or external app.
No Hubitat mutations, broad event scans, or invented source readings.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from device_state_summary import capability_names, device_attributes


MAX_EXTRA_SENSOR_READS = 10
SENSOR_BATCH_SIZE = 3
MAX_SENSOR_CANDIDATES = 64


def _norm(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split())


def _device_id(device: dict[str, Any]) -> str:
    return str(device.get("id") or device.get("deviceId") or "").strip()


def _label(device: dict[str, Any]) -> str:
    return str(device.get("label") or device.get("name") or "").strip()


def _source_trigger_names(
    known_automations: list[dict[str, Any]] | None,
    subject: str,
    transition: str,
) -> set[str]:
    """Configured automation topology is a SEARCH HINT, never proof of execution."""

    targets: set[str] = set()
    for automation in known_automations or []:
        if not isinstance(automation, dict):
            continue
        actions = automation.get("actions") or []
        if not any(
            isinstance(a, dict)
            and _norm(a.get("device") or a.get("label") or a.get("name")) == _norm(subject)
            and _norm(a.get("transition")) == _norm(transition)
            for a in actions
        ):
            continue
        for trigger in automation.get("triggers") or []:
            if isinstance(trigger, dict):
                for field in ("device", "label", "name"):
                    if _norm(trigger.get(field)):
                        targets.add(_norm(trigger[field]))
                for alias in trigger.get("aliases") or []:
                    if _norm(alias):
                        targets.add(_norm(alias))
        for derived in automation.get("derivedSensors") or []:
            if not isinstance(derived, dict):
                continue
            for source in derived.get("sources") or []:
                if isinstance(source, dict):
                    for field in ("device", "label", "name"):
                        if _norm(source.get(field)):
                            targets.add(_norm(source[field]))
    return targets


def plan_cross_integration_candidates(
    identities: list[dict[str, Any]],
    *,
    subject: str,
    subject_room: str,
    transition: str,
    tried_ids: set[str] | None = None,
    known_automations: list[dict[str, Any]] | None = None,
    max_candidates: int = MAX_SENSOR_CANDIDATES,
) -> list[dict[str, Any]]:
    """Plan broader occupancy investigation from a cached structural inventory.

    Unlike room-filter discovery, this also considers capability-backed sensor
    children assigned to bridge/integration rooms or another Hubitat room.
    Candidates must expose motion/presence, or advertise a matching capability
    without any known attribute shape; a device known to expose only lux/humidity
    is excluded even if its parent advertises generic MotionSensor capabilities.

    Results are suggestions for historical reads. Current attribute VALUES are
    not accepted as evidence of a historical event.
    """

    used = set(str(x) for x in (tried_ids or set()))
    subject_key = _norm(subject)
    room_key = _norm(subject_room)
    names = _source_trigger_names(known_automations, subject, transition)
    seen: set[str] = set()
    ranked: list[tuple[tuple[int, int, int, str], dict[str, Any]]] = []

    # Parent metadata may place an integration child outside the target's room.
    room_ids = {
        _device_id(d) for d in identities
        if isinstance(d, dict)
        and room_key
        and _norm(d.get("room") or d.get("roomName")) == room_key
    }
    for row in identities:
        if not isinstance(row, dict):
            continue
        id_ = _device_id(row)
        label = _label(row)
        if not id_ or not label or id_ in used or id_ in seen:
            continue
        if _norm(label) == subject_key:
            continue
        seen.add(id_)
        caps = {_norm(value).replace(" ", "") for value in capability_names(row)}
        has_motion = "motionsensor" in caps
        has_presence = "presencesensor" in caps
        if not (has_motion or has_presence):
            continue

        attributes = {
            _norm(k).replace(" ", "")
            for k in device_attributes(row)
        }
        if has_motion and "motion" in attributes:
            attribute, verified_shape = "motion", True
        elif has_presence and "presence" in attributes:
            attribute, verified_shape = "presence", True
        elif attributes:
            # This concrete child has a known non-occupancy attribute shape.
            continue
        else:
            # No current state shape; a historical attribute might still exist.
            attribute = "motion" if has_motion else "presence"
            verified_shape = False

        label_key = _norm(label)
        device_room = _norm(row.get("room") or row.get("roomName"))
        parent = str(row.get("parentDeviceId") or "").strip()
        alias_keys = {
            label_key,
            *(_norm(x) for x in row.get("aliases", []) if isinstance(x, str)),
        }
        configured = bool(names & alias_keys)
        if configured:
            tier = 0
            match_basis = "configured-trigger"
        elif room_key and room_key in label_key:
            tier = 1
            match_basis = "label-affinity"
        elif parent in room_ids:
            tier = 2
            match_basis = "parent-room"
        elif device_room and device_room == room_key:
            tier = 3
            match_basis = "room"
        else:
            tier = 4
            match_basis = "cross-room"
        # Prefer independent-looking physical sources over derived virtual
        # sensors when all other relationship evidence is equal.
        derived = int(any(
            term in label_key for term in ("virtual", "soft sensor", "derived")
        ))
        candidate = {
            "id": id_,
            "label": label,
            "room": row.get("room") or row.get("roomName"),
            "capabilities": sorted(capability_names(row)),
            "matchBasis": match_basis,
            "suggestedHistoryAttributes": [attribute],
            "exposedOccupancyAttribute": attribute,
            "attributeShapeVerified": verified_shape,
        }
        spec = {
            "name": label,
            "attribute": attribute,
            "candidate": candidate,
            "planTier": tier,
        }
        ranked.append(((tier, derived, int(not verified_shape), label_key), spec))
    ranked.sort(key=lambda item: item[0])
    return [row for _, row in ranked[:max(1, max_candidates)]]


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def rank_causal_hypotheses(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Sort actual candidate evidence; never upgrade correlation to causation.

    Clock sign is important: a sensor report after a light's ON transition
    cannot be described as a preceding trigger. Repeated aligned *before*
    events are considerably stronger than a single close timestamp. A bridge
    reporting path may introduce clock/transport ordering ambiguity.
    """

    hypotheses: list[dict[str, Any]] = []
    requested_time = _parse_time(analysis.get("requestedBoundary"))
    requested_role = "end" if analysis.get("transition") == "off" else "start"
    for sensor in analysis.get("sensors") or []:
        if not isinstance(sensor, dict):
            continue
        events = [
            e for e in sensor.get("relevantCorrelations") or []
            if isinstance(e, dict) and e.get("boundaryRole") == requested_role
        ]
        if not events or not sensor.get("label"):
            continue
        preceding = []
        following = []
        requested = None
        for event in events:
            try:
                delta = float(event["signedDeltaSeconds"])
            except (TypeError, ValueError, KeyError):
                continue
            if delta <= 0:
                preceding.append(event)
            else:
                following.append(event)
            event_time = _parse_time(event.get("subjectTransition"))
            if (
                requested_time is not None
                and event_time is not None
                and abs((event_time - requested_time).total_seconds()) <= 0.25
            ):
                requested = event
        requested_delta: float | None = None
        if requested is not None:
            try:
                requested_delta = float(requested["signedDeltaSeconds"])
            except (TypeError, ValueError, KeyError):
                pass
        if requested_delta is not None and -5.0 <= requested_delta <= 0:
            if len(preceding) >= 2:
                tier = "repeated-upstream-correlation"
                score = 80 + min(len(preceding), 10)
            else:
                tier = "single-upstream-correlation"
                score = 60
        elif requested_delta is not None and requested_delta > 0:
            tier = "reported-after-device"
            score = 20
        elif preceding:
            tier = "other-events-only"
            score = 10
        else:
            tier = "no-upstream-correlation"
            score = 0
        hypotheses.append({
            "label": sensor["label"],
            "tier": tier,
            "score": score,
            "requestedDeltaSeconds": requested_delta,
            "precedingMatches": len(preceding),
            "followingMatches": len(following),
            "totalRequestedTypeTransitions": int(analysis.get("transitionCount") or 0),
            "configuredRoute": any(
                isinstance(a, dict)
                and any(
                    str(t.get("sensorLabel") or "").casefold()
                    == str(sensor["label"]).casefold()
                    for t in (a.get("matchedTriggers") or [])
                    if isinstance(t, dict)
                )
                for a in analysis.get("knownAutomationMatches") or []
            ),
            "claimLevel": "temporal-correlation-only",
        })
    hypotheses.sort(
        key=lambda row: (-row["score"], -row["precedingMatches"], row["label"])
    )
    return hypotheses


def has_strong_requested_correlated_candidate(analysis: dict[str, Any]) -> bool:
    """Evidence-sufficiency STOP for the exploration layer, not final proof."""

    return any(
        h["tier"] == "repeated-upstream-correlation"
        for h in rank_causal_hypotheses(analysis)
    )




def has_local_requested_off_correlation(
    analysis: dict[str, Any], *,
    max_abs_delta_seconds: float = 3.0,
) -> bool:
    """Stop broad cross-room search after checking a room-local OFF edge.

    This is NOT a verified causal explanation. It only says that the known
    local sensor evidence is relevant enough to provide a bounded, explicitly
    unresolved OFF investigation; additional unrelated sensors cannot by
    themselves establish the OFF command producer.
    """
    if str(analysis.get("transition") or "").lower() != "off":
        return False
    requested = _parse_time(analysis.get("requestedBoundary"))
    if requested is None:
        return False
    for sensor in analysis.get("sensors") or []:
        if not isinstance(sensor, dict):
            continue
        for event in sensor.get("relevantCorrelations") or []:
            if not isinstance(event, dict) or event.get("boundaryRole") != "end":
                continue
            boundary = _parse_time(event.get("subjectTransition"))
            if boundary is None:
                continue
            if abs((boundary - requested).total_seconds()) > .25:
                continue
            if str(event.get("eventValue") or "").casefold() not in {
                "inactive", "not present", "absent", "off", "closed"
            }:
                continue
            try:
                delta = float(event["signedDeltaSeconds"])
            except (TypeError, ValueError, KeyError):
                continue
            if abs(delta) <= max_abs_delta_seconds:
                return True
    return False


def has_repeated_requested_controller_candidate(
    analysis: dict[str, Any],
    *,
    max_abs_delta_seconds: float = 0.35,
    min_repeated_starts: int = 2,
) -> bool:
    """Stop *unrelated* cross-room searches after a repeated button pattern.

    Stop is discovery sufficiency, not proof of a native bridge binding.
    A qualifying controller must align the specifically requested ON boundary,
    match multiple distinct starts with the same button value, and be uniquely
    stronger than competing controllers. The event may be reported after ON:
    signed timestamp ordering is retained for synthesis and attribution.
    Room-local occupancy histories are checked before calling this function.
    """
    if str(analysis.get("transition") or "") != "on":
        return False
    requested = _parse_time(analysis.get("requestedBoundary"))
    if requested is None:
        return False

    qualifiers: list[tuple[int, float, str]] = []
    for controller in analysis.get("controllers") or []:
        if not isinstance(controller, dict):
            continue
        candidates = []
        for event in controller.get("relevantAlignments") or []:
            if not isinstance(event, dict) or event.get("boundaryRole") != "start":
                continue
            moment = _parse_time(event.get("subjectTransition"))
            if moment is None:
                continue
            try:
                delta = float(event["signedDeltaSeconds"])
            except (ValueError, TypeError, KeyError):
                continue
            if abs(delta) > max_abs_delta_seconds:
                continue
            candidates.append((moment, delta, str(event.get("eventValue") or "")))

        focal = [
            (at, delta, value)
            for at, delta, value in candidates
            if abs((at - requested).total_seconds()) <= .25
        ]
        if not focal:
            continue
        focal.sort(key=lambda item: abs(item[1]))
        _, focal_delta, focal_button = focal[0]
        matching_boundaries = {
            at.isoformat() for at, _, value in candidates
            if value == focal_button
        }
        if len(matching_boundaries) >= min_repeated_starts:
            qualifiers.append((
                len(matching_boundaries),
                abs(focal_delta),
                str(controller.get("label") or ""),
            ))

    qualifiers.sort(key=lambda row: (-row[0], row[1]))
    if not qualifiers:
        return False
    if len(qualifiers) > 1 and qualifiers[0][0] == qualifiers[1][0]:
        # Two equally repeated button-controller candidates remain ambiguous.
        return False
    return True


def render_ranked_clue(analysis: dict[str, Any]) -> str | None:
    """Prominent useful clue while keeping the exact initiator unverified."""

    rows = analysis.get("hypotheses")
    if not isinstance(rows, list):
        rows = rank_causal_hypotheses(analysis)
    upstream = next(
        (r for r in rows if isinstance(r, dict) and r.get("tier") in {
            "repeated-upstream-correlation", "single-upstream-correlation"
        }),
        None,
    )
    if upstream is None:
        return None
    label = str(upstream.get("label") or "").strip()
    delta = upstream.get("requestedDeltaSeconds")
    if not label or not isinstance(delta, (float, int)):
        return None
    repeated = int(upstream.get("precedingMatches") or 0)
    time = f"{abs(delta):.2f}".rstrip("0").rstrip(".")
    state = "occupancy activity" if analysis.get("transition") == "on" else "occupancy inactivity"
    preface = (
        "**Best-supported upstream clue:** "
        f"{label} reported {state} about {time}s before "
        "the requested device transition."
    )
    if repeated > 1:
        preface += (
            f" It also preceded {repeated - 1} other recent matching transitions "
            "within the correlation window."
        )
    return (
        preface
        + " This is timestamp evidence of a plausible relationship, NOT proof "
        "that this sensor or an external automation issued the command; "
        "reporting/clock delays and missing external automation traces remain."
    )
