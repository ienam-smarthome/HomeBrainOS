"""Evidence-only fallback when a model's causal repair still fails validation.

Do not promote correlation, `physical` state-event metadata, a reporting
bridge, or an empty bounded app-log read into a proven initiating actor.
This fallback is intentionally brief but retains a useful, auditable observed
focal boundary instead of returning a conflicting, high-confidence story.
"""
from __future__ import annotations

from typing import Any
from datetime import datetime
import re

from causal_evidence_graph import build_causal_evidence_graph
from skill_investigation import build_skill_investigation



def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else None
    except ValueError:
        return None


def _focal_sensor_correlations(
    evidence: list[dict[str, Any]], subject: str,
    focal_time: str, boundary_role: str,
) -> list[str]:
    """Signed, bounded correlations for the *one* requested transition."""
    focus = _parse_time(focal_time)
    if focus is None:
        return []
    matches: list[tuple[float, str]] = []
    seen: set[tuple[str, str]] = set()
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("tool") != "homebrain_causal_secondary_correlation":
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict) or details.get("subject") != subject:
            continue
        for sensor in (details.get("sensors") or [])[:25]:
            if not isinstance(sensor, dict) or not sensor.get("label"):
                continue
            rows = sensor.get(
                "relevantCorrelations" if boundary_role == "start"
                else "oppositeCorrelations"
            ) or []
            aligned = set()
            for row in rows[:25]:
                if not isinstance(row, dict) or row.get("boundaryRole") != boundary_role:
                    continue
                start = _parse_time(row.get("subjectTransition"))
                at = _parse_time(row.get("sensorEvent"))
                if start is None or at is None:
                    continue
                if abs((start - focus).total_seconds()) > .002:
                    continue
                delta = (at - focus).total_seconds()
                if abs(delta) > 3:
                    continue
                key = (str(sensor["label"]), at.isoformat())
                if key in seen:
                    continue
                seen.add(key)
                aligned.update(str(other.get("subjectTransition") or "")
                               for other in rows if isinstance(other, dict))
                relation = "before" if delta < 0 else "after" if delta > 0 else "at"
                matches.append((
                    abs(delta),
                    f"{sensor['label']} reported {row.get('eventValue') or 'an event'} "
                    f"at {at.isoformat()}, {abs(delta):.3f} seconds {relation} "
                    "the light transition. This is temporal correlation, "
                    "not a confirmed command from the sensor."
                ))
    matches.sort(key=lambda item: item[0])
    return [sentence for _, sentence in matches[:3]]


def render_failed_causal_synthesis(
    evidence: list[dict[str, Any]],
    original_user: str,
) -> str | None:
    graph = build_causal_evidence_graph(evidence, original_user)
    if graph.get("scope") != "single-observed-event":
        return None
    focus = graph.get("focus") or {}
    if not isinstance(focus, dict):
        return None
    subject = str(focus.get("subject") or "The requested device")
    asking_off = re.search(
        r"(?i)\b(?:turn|turned|switch|switched|going|went)\s+off\b",
        str(original_user or ""),
    ) is not None
    transition = "off" if asking_off else "on"
    time = str(focus.get(transition) or "")
    if not time:
        return None
    boundaries = graph.get("transitionEvidence") or {}
    if transition == "off":
        physical = (boundaries.get("off") or {}).get("state") or {}
        actor = graph.get("offCommand") or {}
    else:
        physical = graph.get("physicalStateBoundary") or {}
        actor = graph.get("directCommand") or {}
    reporter = physical.get("reporter") or {}
    lines = [
        "### Investigation result — initiating cause unresolved",
        f"**Recorded transition:** {subject} switched {transition.upper()} at {time}.",
    ]
    if isinstance(reporter, dict) and reporter.get("label"):
        lines.append(
            f"**Reported by:** {reporter['label']}. This identifies the "
            "Hubitat event reporting source, not the upstream controller."
        )
    # A strict direct-command match may be absent even when the same exact
    # subject has a verified preceding command outside the two-second window.
    # Preserve that strongest *recorded candidate* on safety fallback; never
    # promote it to confirmed delivery or causation.
    skill_projection = (
        build_skill_investigation(evidence, original_user)
        if transition == "on" else None
    )
    prior_facts = [
        row for row in (skill_projection or {}).get("facts", [])
        if row.get("kind") == "preceding_hubitat_command"
    ]
    preceding = prior_facts[0] if prior_facts else None
    if isinstance(actor, dict) and actor.get("producer"):
        producer = actor.get("producer") or {}
        name = str(producer.get("label") or "an attributed Hubitat source")
        lines.append(
            f"**Command record:** The evidence graph associates a direct "
            f"command with {name}. The reason it issued the command still "
            "requires separately verified rule or controller evidence."
        )
    else:
        lines.append(
            "**Command record:** No matching direct command producer was "
            "established for this transition in the bounded Hubitat data. "
            "This refers to strict command-to-state matching, not to absence "
            "of preceding commands or other potential command paths."
        )
    if preceding:
        lines.append(
            "**Leading recorded command candidate (not confirmed cause):** "
            f"{preceding.get('producer') or 'Hubitat app'} issued "
            f"{preceding.get('command') or 'a matching command'} at "
            f"{preceding.get('time')}. The command preceded the state report "
            f"by {preceding.get('delaySeconds')} seconds. Its actual delivery "
            "and causal effect remain unverified."
        )
    for fact in (skill_projection or {}).get("facts", []):
        if fact.get("kind") != "intervening_state_changes":
            continue
        events = fact.get("events") or []
        if events:
            order = ", ".join(
                f"{row.get('state', '').upper()} at {row.get('date')}"
                for row in events[:4]
            )
            lines.append(
                "**Intervening state reports:** " + order
                + ". These complicate a simple delayed-command explanation "
                  "but do not themselves establish an external controller."
            )
    correlations = _focal_sensor_correlations(
        evidence, subject, time, "end" if asking_off else "start",
    )
    if correlations:
        lines.append("**Time-aligned sensor evidence:** " + " ".join(correlations))
    else:
        lines.append(
            "**Candidate triggers:** No uniquely verified initiating "
            "sensor or controller was established in this bounded investigation."
        )
    listeners = physical.get("listenersNotified") or []
    if isinstance(listeners, list) and listeners:
        names = list(dict.fromkeys(
            str(item.get("label") or "") for item in listeners
            if isinstance(item, dict) and item.get("label")
        ))[:3]
        if names:
            lines.append("**Downstream listeners:** " + ", ".join(names)
                         + ". Notification does not prove command initiation.")
    lines.extend([
        "**Why this answer is limited:** The initial model explanation and "
        "its one repair did not meet the causal evidence checks. "
        "HomeBrain has therefore withheld unsupported causal attribution. "
        "Further targeted, time-aligned controller/rule or upstream "
        "integration evidence is needed.",
    ])
    return "\n\n".join(lines)


__all__ = ["render_failed_causal_synthesis"]
