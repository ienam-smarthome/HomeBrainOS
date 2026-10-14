"""Evidence-only fallback when a model's causal repair still fails validation.

Do not promote correlation, `physical` state-event metadata, a reporting
bridge, or an empty bounded app-log read into a proven initiating actor.
This fallback is intentionally brief but retains a useful, auditable observed
focal boundary instead of returning a conflicting, high-confidence story.
"""
from __future__ import annotations

from typing import Any
import re

from causal_evidence_graph import build_causal_evidence_graph


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
            "This is not proof that every potential command path was absent."
        )
    lines.extend([
        "**Candidate triggers:** Nearby occupancy, motion, controller and "
        "button events are correlations only; their precise time ordering "
        "does not prove an initiating automation.",
        "**Why this answer is limited:** The initial model explanation and "
        "its one repair did not meet the causal evidence checks. "
        "HomeBrain has therefore withheld unsupported causal attribution. "
        "Further targeted, time-aligned controller/rule or upstream "
        "integration evidence is needed.",
    ])
    return "\n\n".join(lines)


__all__ = ["render_failed_causal_synthesis"]
