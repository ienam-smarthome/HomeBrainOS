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

from causal_command_provenance import correlate_command_producers
from causal_timeline import (
    build_causal_timeline_rows,
    explicitly_focused_event_rows,
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
    config = _configuration(evidence, app_id) if app_id else {"checked": False}
    logs = _logs(evidence, app_id, (start_command or {}).get("time") or "") if app_id else {"checked": False}
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

    return {
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
        "initiatorCandidate": sensor,
        "configuration": config,
        "executionLogs": logs,
        "locationMode": mode,
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
        ],
        "missing": missing,
        "ready": bool(start_command and sensor and config.get("checked") and logs.get("checked")),
    }


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
    return config.get("checked") is True and any(
        "mode" in str(item).casefold() for item in config.get("excerpts") or []
    )


def supports_one_pass_deep_synthesis(
    graph: dict[str, Any], original_user: str
) -> bool:
    """Skip exploratory model tool rounds only when all named checks are done.

    Explicit multi-part deep requests have a finite evidence checklist. A
    missing/ambiguous event, absent app, unconfigured candidate, unavailable
    log source or requested missing mode history stays in the model/MCP loop.
    This gate does NOT declare other upstream causes impossible; it declares
    that available evidence is sufficient for a calibrated answer.
    """
    if not graph.get("ready"):
        return False
    prompt = str(original_user or "").casefold()
    requirements = (
        re.search(r"\b(?:investigat|analy[sz]|diagnos|thorough|deep)\w*\b", prompt),
        re.search(r"\b(?:app|rule|automation|controll)\w*\b", prompt),
        re.search(r"\b(?:sensor|motion|occupancy|presence)\w*\b", prompt),
        re.search(r"\b(?:log|execution)\w*\b", prompt),
        re.search(r"\b(?:alternativ|other causes|manual|mode)\w*\b", prompt),
    )
    if not all(requirements):
        return False
    if needs_mode_history(graph, original_user):
        return False
    candidate = graph.get("initiatorCandidate") or {}
    return (
        candidate.get("configured") is True
        and candidate.get("status") == "strongly-correlated-configured-sensor"
    )


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
        + "\nEvidence rules: distinguish direct device command, upstream sensor "
        "correlation, observed handler notification, current configuration, "
        "native app logs and mere OFF-state timing. Never promote a sensor "
        "timestamp or an app's listener into a proven rule-branch execution. "
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
