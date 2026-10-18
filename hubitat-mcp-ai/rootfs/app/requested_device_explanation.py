"""Read-only, single-subject explanation fallback for model device drift.

This is not a guessed historical conclusion. It is a source-scoped summary
that makes uncertainty explicit when a model moves from the user's requested
device to a different log-source device.
"""
from __future__ import annotations

import re
from typing import Any


def render_requested_device_explanation(
    question: str, evidence: list[dict[str, Any]],
    unrelated_label: str,
) -> str | None:
    question = str(question or "")
    if (
        not re.match(r"(?i)^\s*(?:explain|compare|distinguish|describe)\b", question)
        or re.search(
            r"(?<![\w-])" + re.escape(str(unrelated_label or "")) + r"(?![\w-])",
            question, re.IGNORECASE,
        )
    ):
        return None
    targets: dict[str, str] = {}
    for item in evidence:
        if not isinstance(item, dict) or item.get("success") is not True:
            continue
        if item.get("evidence_kind") != "targeted_device_lookup":
            continue
        details = item.get("details")
        state = details.get("reportedDeviceState") if isinstance(details, dict) else None
        if not isinstance(state, dict):
            continue
        device_id = str(state.get("deviceId") or "")
        label = str(state.get("label") or "").strip()
        if (
            device_id.isdigit() and 2 < len(label) <= 120
            and re.search(r"(?<![\w-])" + re.escape(label) + r"(?![\w-])",
                          question, re.IGNORECASE)
        ):
            targets[device_id] = label
    if len(targets) != 1:
        return None
    device_id, label = next(iter(targets.items()))
    state = None
    for item in evidence:
        if not isinstance(item, dict) or item.get("success") is not True:
            continue
        details = item.get("details")
        row = details.get("reportedDeviceState") if isinstance(details, dict) else None
        if isinstance(row, dict) and str(row.get("deviceId") or "") == device_id:
            state = row.get("reportedAttributes") or {}
            break
    if not isinstance(state, dict):
        state = {}

    event_pages = [
        item for item in evidence
        if isinstance(item, dict) and item.get("success") is True
        and str(item.get("sub_tool") or "") == "hub_list_device_events"
        and str(((item.get("arguments") or {}).get("args") or {}).get("deviceId") or "")
        == device_id
    ]
    command_pages = [
        item for item in event_pages
        if str(((item.get("arguments") or {}).get("args") or {}).get("attribute") or "")
        .casefold().startswith("command-")
    ]
    command_rows: list[dict[str, Any]] = []
    for page in command_pages:
        details = page.get("details")
        if isinstance(details, dict) and isinstance(details.get("events"), list):
            command_rows.extend(
                row for row in details["events"] if isinstance(row, dict)
            )
    incomplete = any(
        isinstance(item.get("details"), dict)
        and (item["details"].get("observedEventsTruncated")
             or item["details"].get("historySourceIntegrityVerified") is False)
        for item in evidence
        if isinstance(item, dict) and item.get("success") is True
        and item.get("tool") == "homebrain_device_history"
        and str((item.get("details") or {}).get("label") or "").casefold() == label.casefold()
    )
    date = re.search(r"\b\d{1,2}\s+[A-Za-z]+\s+20\d{2}\b", question)
    period = date.group(0) if date else "the requested historical time"
    lines = [
        f"**Evidence-focused explanation — {label} (device {device_id}).**",
        "- **switch=off:** Hubitat recorded a reported device state. This alone does not identify the command issuer.",
        "- **command-off:** A recorded invocation of off() on that Hubitat device; its producer may identify an app or UI actor. This does not prove the physical switch acknowledged it.",
        "- **Automation execution log:** Evidence an app logged an execution step within the retained, searched interval; configuration alone does not establish historical execution.",
        "- **Physical acknowledgement:** Independent device/energy/telemetry evidence of an actual physical change, not just a command or cached attribute.",
    ]
    if state.get("switch") is not None:
        lines.append(
            f"**Observed current reported state:** switch={str(state['switch'])[:35]}. "
            "A current state value cannot establish the cause of a past event."
        )
    if command_pages:
        lines.append(
            f"**Command history queried:** {len(command_pages)} targeted source "
            f"read(s) for device {device_id}, {len(command_rows)} command event(s) "
            "returned in the recorded bounded queries. The event timestamps "
            "and producers must match the requested historical boundary before "
            "an issuer is attributed."
        )
    else:
        lines.append("**Command history:** no dedicated command-event read is recorded this turn.")
    if event_pages:
        lines.append(
            f"**Device event source:** {len(event_pages)} targeted event "
            "page(s) were queried. Newest-first paging does not prove the "
            "historical interval is fully retained."
        )
    if incomplete:
        lines.append("**History integrity:** the reported event sample is truncated or not independently complete.")
    lines.append(
        f"**Status for {period}:** the material provided does not establish "
        "a verified historical automation command, a matched state transition "
        "with complete command provenance, or physical acknowledgement. "
        "These questions remain unresolved. No device action was taken."
    )
    return "\n".join(lines)


__all__ = ["render_requested_device_explanation"]
