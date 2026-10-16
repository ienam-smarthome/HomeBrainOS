"""Evidence-faithful fallback for an open-ended incident investigation.

When a model invents a different named device and the claim-grounding guard
rightly rejects it, retain a short *supported* partial report about the one
device actually read this turn. This is not a free-form causal conclusion.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any


_OPEN_SELECTION = re.compile(
    r"^\s*(?:please\s+)?(?:choose|select|pick|find|identify)\s+"
    r"(?:a|an|one|some|the most recent|the latest|recent)\b",
    re.I,
)
_INVESTIGATION = re.compile(
    r"\b(?:investigat\w*|unexpected|event|state\s+change|"
    r"timeline|reconstruct|explain|causes?)\b", re.I,
)


def is_open_ended_incident_request(question: str) -> bool:
    question = str(question or "")
    return bool(_OPEN_SELECTION.search(question) and _INVESTIGATION.search(question))


def render_grounded_incident_fallback(
    question: str,
    evidence: list[dict[str, Any]],
) -> str | None:
    """Return only directly read identity and reported event facts.

    Multiple subject histories, a missing matching targeted identity, and
    missing observed event dates fail closed. `triggered` is a subscriber
    list, never the actor who initiated a state change.
    """
    if not is_open_ended_incident_request(question):
        return None
    verified_targets: dict[str, str] = {}
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("evidence_kind") != "targeted_device_lookup":
            continue
        state = (receipt.get("details") or {}).get("reportedDeviceState")
        if isinstance(state, dict):
            ident = str(state.get("deviceId") or "")
            name = str(state.get("label") or "")
            if ident.isdigit() and name and len(name) <= 120:
                verified_targets[ident] = name

    candidates: dict[str, tuple[str, list[dict[str, Any]], bool]] = {}
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("evidence_kind") != "deterministic_device_event_history":
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict):
            continue
        label = str(details.get("label") or "")
        verified_id = next(
            (ident for ident, name in verified_targets.items() if name == label),
            None,
        )
        events = details.get("observedEvents")
        if verified_id and isinstance(events, list):
            candidates[verified_id] = (
                label, [row for row in events[:40] if isinstance(row, dict)],
                bool(details.get("observedEventsTruncated")
                     or details.get("historySourceIntegrityVerified") is False),
            )
    if len(candidates) != 1:
        return None
    ident, (label, events, incomplete) = next(iter(candidates.items()))
    observed: list[tuple[datetime, dict[str, Any]]] = []
    for event in events:
        if event.get("isStateChange") is not True:
            continue
        try:
            stamp = datetime.fromisoformat(
                str(event.get("date") or "").replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            continue
        if stamp.tzinfo is None:
            continue
        observed.append((stamp, event))
    if not observed:
        return None
    observed.sort(key=lambda pair: pair[0], reverse=True)
    recent = observed[:3]
    lines = [
        f"**Supported partial investigation: {label} (device {ident}).**",
        "The model's attempted conclusion named a different, unverified "
        "device, so HomeBrain has discarded that conclusion. The following "
        "facts come from the device actually examined this turn:",
    ]
    for stamp, event in recent:
        attribute = str(event.get("name") or "state")[:55]
        value = str(event.get("value") if event.get("value") is not None else "unknown")[:60]
        producer = event.get("producedBy")
        source = (
            str(producer.get("label") or "")[:100]
            if isinstance(producer, dict) else ""
        )
        lines.append(
            f"- {stamp.isoformat()}: {attribute}={value}"
            + (f"; reported via {source}" if source else "")
            + "."
        )
    lines.append(
        "These are Hubitat reports, not proof of the initiating controller. "
        "Apps named in event subscriber lists are not necessarily command "
        "producers. A specific cause has not been established."
    )
    if incomplete:
        lines.append(
            "The bounded event sample is incomplete or its source integrity "
            "is unverified; earlier transitions may be missing."
        )
    lines.append(
        "To resolve the incident, compare the event's precise time against "
        "controller/button history, controlling app configuration, and "
        "source-scoped execution logs. No devices or rules were changed."
    )
    return "\n".join(lines)


__all__ = ["is_open_ended_incident_request", "render_grounded_incident_fallback"]
