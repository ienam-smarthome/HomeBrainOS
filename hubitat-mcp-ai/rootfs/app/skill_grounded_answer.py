"""Authoritative focal-event causal answer selected from typed Hubitat receipts.

Avoids relying on language-specific phrase filters to reject unsupported
upstream-controller attribution. This routine does not infer proof from an
app command; it describes strongest recorded evidence and precise gaps.
"""
from __future__ import annotations

from typing import Any

from datetime import datetime

from causal_evidence_graph import build_causal_evidence_graph
from causal_subject_prefetch import switch_transition_from_prompt
from skill_decision_summary import causal_skill_conclusion


def _name(value: Any) -> str:
    return str(value or "").strip()


def _focal_reporter(
    evidence: list[dict[str, Any]], subject: str, focal: str,
) -> str:
    """Accept equivalent source-typed history shapes, exact event boundary only."""
    try:
        target = datetime.fromisoformat(focal.replace("Z", "+00:00"))
    except ValueError:
        return ""
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = receipt.get("details") or {}
        if _name(details.get("label")).casefold() != subject.casefold():
            continue
        for key in ("boundaryEvents", "observedEvents", "correlationEvents", "events"):
            for event in details.get(key) or []:
                if not isinstance(event, dict):
                    continue
                if event.get("name") != "switch" or str(event.get("value")).casefold() != "on":
                    continue
                try:
                    stamp = datetime.fromisoformat(str(event.get("date") or "").replace("Z", "+00:00"))
                    if stamp.tzinfo is None or target.tzinfo is None:
                        continue
                    if abs((stamp - target).total_seconds()) > .002:
                        continue
                except (ValueError, TypeError):
                    continue
                producer = event.get("producedBy") or {}
                if isinstance(producer, dict):
                    label = _name(producer.get("label"))
                    if label:
                        return label
    return ""


def _focal_sensors(evidence: list[dict[str, Any]]) -> tuple[list[str], bool]:
    checked: list[str] = []
    any_aligned = False
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("tool") != "homebrain_causal_secondary_correlation":
            continue
        details = row.get("details") or {}
        sensors = details.get("sensors") or []
        for sensor in sensors:
            if not isinstance(sensor, dict):
                continue
            label = _name(sensor.get("label"))
            if label and label not in checked:
                checked.append(label)
            if sensor.get("relevantCorrelations"):
                any_aligned = True
    return checked[:6], any_aligned


def render_grounded_causal_answer(
    evidence: list[dict[str, Any]], question: str,
) -> str | None:
    """Return a deterministic source-grounded explanation for a narrow case.

    Gate: uniquely resolved focal ON state, a time-aligned earlier command
    from the exact subject, and no independently verified upstream actor.
    Other causal questions retain the normal model synthesis path.
    """
    if switch_transition_from_prompt(question) != "on":
        return None
    if "lockout" in str(question).casefold():
        return None
    verdict = causal_skill_conclusion(evidence, question)
    if not verdict or verdict.get("status") != "leading-recorded-candidate-unverified":
        return None
    command = verdict.get("command") or {}
    producer = _name(command.get("producer"))
    stamp = _name(command.get("timestamp"))
    focus = _name(verdict.get("focusTime"))
    delay = command.get("delaySeconds")
    if (
        not producer or not stamp or not focus
        or isinstance(delay, bool) or not isinstance(delay, (int, float))
        or delay < 0 or delay > 30
        or command.get("causationVerified") is not False
    ):
        return None
    graph = build_causal_evidence_graph(evidence, question)
    if graph.get("scope") != "single-observed-event":
        return None
    subject = _name(verdict.get("subject")) or "the requested device"
    boundary = graph.get("physicalStateBoundary") or {}
    reporter = (
        _name((boundary.get("reporter") or {}).get("label"))
        or _focal_reporter(evidence, subject, focus)
    )
    lines = [
        f"### Investigation — {subject}",
        (
            f"**Leading recorded explanation:** {producer} issued "
            f"{_name(command.get('command')) or 'a matching ON command'} "
            f"at {stamp}, **{delay:.3f} seconds before** the light was "
            "reported ON. This is the strongest recorded Hubitat command "
            "candidate, **not a confirmed cause**: delivery, upstream input "
            "and the physical response remain unverified."
        ),
        "**Time-ordered observations:**",
        f"- {stamp}: {producer} issued the recorded command.",
    ]
    for event in verdict.get("intervening") or []:
        lines.append(
            f"- {event.get('date')}: device reported "
            f"{_name(event.get('state')).upper()} (intervening transition)."
        )
    lines.append(
        f"- {focus}: device reported ON."
        + (f" Reporter: {reporter}." if reporter else "")
    )
    if reporter:
        lines.append(
            f"**Reporting versus initiating:** {reporter} reported the "
            "state to Hubitat. This identifies the reporting integration, "
            "not which upstream app, physical controller or person initiated it."
        )
    listeners = [
        _name(x.get("label"))
        for x in (boundary.get("listenersNotified") or [])
        if isinstance(x, dict) and _name(x.get("label"))
    ]
    if listeners:
        lines.append(
            "**Downstream notifications:** " + ", ".join(dict.fromkeys(listeners) )
            + ". A notified app can also have issued an earlier command; "
              "being a listener does not disprove its prior command."
        )
    checked_sensors, sensor_aligned = _focal_sensors(evidence)
    if checked_sensors:
        if sensor_aligned:
            lines.append(
                "**Sensors:** Time-aligned sensor evidence was returned; "
                "correlation requires an actual configured control path "
                "to be considered an initiating mechanism."
            )
        else:
            lines.append(
                "**Checked sensor histories:** " + ", ".join(checked_sensors)
                + " — no focal correlation established in their returned "
                  "bounded events. Other sensors and unretained events "
                  "are not ruled out."
            )
    # A status-neutral source note: a latest-N history page is not a
    # verified neighborhood around a focal historic event.
    scoped_reads = []
    for receipt in evidence:
        if not isinstance(receipt, dict):
            continue
        arguments = receipt.get("arguments") or {}
        args = arguments.get("args") if isinstance(arguments.get("args"), dict) else arguments
        if not isinstance(args, dict):
            continue
        if (
            receipt.get("sub_tool") == "hub_list_device_events"
            and str(args.get("attribute") or "") == "switch"
            and args.get("since") and args.get("until")
            and receipt.get("evidence_kind") == "focal_exact_state_history"
        ):
            scoped_reads.append(receipt)
    if scoped_reads:
        usable = any(
            row.get("success") is True and
            isinstance((row.get("details") or {}).get("events"), list)
            for row in scoped_reads
        )
        lines.append(
            "**Focal event-window coverage:** "
            + (
                "A timestamp-filtered state-event page was returned for the "
                "requested incident. An empty result would not independently "
                "prove historical source completeness."
                if usable else
                "An exact incident-window query was attempted, but its "
                "state-event content was not verified; intervening changes "
                "cannot be excluded."
            )
        )
    else:
        lines.append(
            "**Focal event-window coverage:** The returned latest-N "
            "history does not independently establish complete coverage "
            "of the minutes surrounding the incident."
        )
    if verdict.get("intervening"):
        lines.append(
            "**Important counterevidence:** An intervening OFF/ON sequence "
            "complicates interpreting the earlier command as an immediate "
            "cause. An independent controller action and a stale-state "
            "resynchronisation remain possible, not verified."
        )
    else:
        lines.append(
            "**Alternatives:** A separate reporting-integration input or "
            "state resynchronisation cannot be excluded without source-side "
            "execution and transport records."
        )
    coverage = verdict.get("sourceChecks") or {}
    scope = []
    scope.append(
        "producer app configuration query completed (historical settings/initiating inputs unverified)" if coverage.get("producerAppConfigChecked")
        else "producer app configuration not verified in this investigation"
    )
    scope.append(
        "producer execution-log query completed (its historic time-window coverage must be checked)" if coverage.get("producerAppLogsChecked")
        else "producer execution logs not verified in this investigation"
    )
    lines.append(
        "**Evidence limits:** " + "; ".join(scope)
        + ". Device-event history is bounded, and a recorded command "
          "is not an end-to-end acknowledgment."
    )
    lines.append(
        "**Most useful next checks (read-only):** Check the recorded "
        "command producer's upstream controller or MQTT command receipt "
        "around its command timestamp, then check the reporting "
        "integration's command/state history around the intervening "
        "OFF/ON sequence. Current app settings alone cannot prove "
        "historical execution."
    )
    return "\n\n".join(lines)


__all__ = ["render_grounded_causal_answer"]
