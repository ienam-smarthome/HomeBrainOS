"""Render a bounded, source-attributed historical lockout incident.

The host owns the source/evidence assertions; it must never conflate a journal
collector-received OFF with a native Hubitat switch timestamp, or replace an
unverified command/lockout decision with a confident model narrative.

Only render after the requested app, subject, device history, journal, and
bounded app-log scopes were read successfully. This is a generic evidence
classification contract: known native facts, observed collector facts, and
unverified causal effects remain separate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import re


def _instant(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def _name(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return re.sub(r"[\x00-\x1f<>]", "", text)[:100]


def _best_journal_off(
    entries: list[dict[str, Any]], *, light_id: str, anchor: datetime,
) -> tuple[datetime, str] | None:
    options = []
    for item in entries:
        if not isinstance(item, dict) or item.get("kind") != "light":
            continue
        if str(item.get("deviceId") or "") != str(light_id):
            continue
        for record in item.get("observations") or []:
            if not isinstance(record, dict):
                continue
            if str(record.get("value") or "").casefold() != "off":
                continue
            stamp = _instant(record.get("observedAt"))
            if stamp is None:
                continue
            offset = (stamp-anchor).total_seconds()
            if 0 <= offset <= 5:
                options.append((offset, stamp, str(record.get("timestampBasis") or "unknown")))
    if not options:
        return None
    _, stamp, basis = min(options)
    return stamp, basis


def _journal_buttons(
    entries: list[dict[str, Any]], *, anchor: datetime,
) -> list[str]:
    observations = []
    for item in entries:
        if not isinstance(item, dict) or item.get("kind") != "button":
            continue
        for record in item.get("observations") or []:
            if not isinstance(record, dict):
                continue
            stamp = _instant(record.get("observedAt"))
            if stamp is None or abs((stamp-anchor).total_seconds()) > 4:
                continue
            observations.append((
                abs((stamp-anchor).total_seconds()),
                f"- Journal controller {_name(item.get('label') or item.get('deviceId'))} "
                f"(device {_name(item.get('deviceId'))}) reported button "
                f"{_name(record.get('value'))} at {stamp.isoformat(timespec='milliseconds')} "
                f"({_name(record.get('timestampBasis'))}; not a native hardware clock).",
            ))
    return [row for _, row in sorted(observations)[:3]]


def _journal_motion(
    entries: list[dict[str, Any]], *, after: datetime,
) -> list[str]:
    observations = []
    for item in entries:
        if not isinstance(item, dict) or item.get("kind") != "sensor":
            continue
        for record in item.get("observations") or []:
            if not isinstance(record, dict) or str(record.get("value") or "").casefold() != "active":
                continue
            stamp = _instant(record.get("observedAt"))
            if stamp is None:
                continue
            gap = (stamp-after).total_seconds()
            if not 0 <= gap <= 180:
                continue
            observations.append((
                gap,
                f"- Journal motion ACTIVE: {_name(item.get('label'))} "
                f"(device {_name(item.get('deviceId'))}) "
                f"at {stamp.isoformat(timespec='milliseconds')} "
                f"({_name(record.get('timestampBasis'))}, {gap:.1f}s after the "
                "journal OFF receipt; activation eligibility **not verified**).",
            ))
    return [line for _, line in sorted(observations)[:4]]


def render_bounded_focal_reconstruction(
    prompt: str, receipts: list[dict[str, Any]],
) -> str | None:
    """Complete only one explicit, independently scoped historical focal read.

    Do not suppress other requested tasks, skip failed source reads or claim a
    missing native observation was impossible. Preserve all source-level
    unknowns, particularly incomplete Historical Journal capture windows.
    """
    if re.search(
        r"\b(?:and also|as well as|in addition|also (?:check|analyse|analyze|investigate|review)|"
        r"plus (?:check|analyse|analyze|investigate|review))\b", str(prompt), re.I,
    ):
        return None
    facts = None
    for receipt in reversed(receipts):
        if not isinstance(receipt, dict) or receipt.get("tool") != (
            "homebrain_motion_lockout_investigation"
        ):
            continue
        if receipt.get("success") is True:
            facts = receipt.get("details")
        break
    if not isinstance(facts, dict):
        return None
    selection = facts.get("focalSelection") or {}
    target = _instant(selection.get("explicitTargetUtc"))
    if target is None or not facts.get("appId") or not facts.get("lightDeviceId"):
        return None
    sources = {
        row.get("source"): row
        for row in (facts.get("sources") or [])
        if isinstance(row, dict) and isinstance(row.get("source"), str)
    }
    if not (
        sources.get("bounded-light-device-history", {}).get("success") is True
        and sources.get("targeted-native-controller-history", {}).get(
            "readSucceeded"
        ) is True
        and sources.get("present-day-app-configuration", {}).get(
            "available"
        ) is True
        and sources.get("bounded-app-execution-logs", {}).get(
            "readSucceeded"
        ) is True
        and sources.get("Historical Journal", {}).get(
            "deviceScopesChecked", 0
        ) > 0
    ):
        return None

    lookback = facts.get("nativeHistoryLookback") or {}
    history_hours = int(lookback.get("hoursBackRequested") or 24)
    journal = facts.get("journal") or []
    selected = _instant(selection.get("selectedOff"))
    fused = facts.get("crossSourceFocalProvenance") or {}
    candidate = fused.get("candidate")
    candidate = candidate if isinstance(candidate, dict) else {}
    native_commands = facts.get("nativeFocalCommandProducers") or []
    current = facts.get("currentConfiguration") or {}
    duration = current.get("configuredDurationMinutes")
    mode = current.get("triggerMode")
    logs = sources.get("bounded-app-execution-logs") or {}
    gaps = int(facts.get("journalGapWindowsReported") or 0)

    lines = [
        "### Requested historical OFF — evidence reconstruction",
        f"**Requested clock:** {target.isoformat()} UTC (converted from the user's dated clock; not itself event proof).",
        f"**Native history scope:** {history_hours} hours requested for the light and physical button. "
        "A successful history call does **not** prove the upstream source retained every event.",
    ]
    if lookback.get("defaultWindowWouldMissFocal"):
        lines.append(
            "**Coverage finding:** The default 24-hour query would have excluded "
            "this requested event at the time of this investigation. "
            "A longer native-history window was requested."
        )
    if lookback.get("requestedBeyondMaxLookback"):
        lines.append(
            "**Limit:** The requested event is older than the supported "
            "168-hour native lookback; upstream event coverage cannot be proven."
        )

    lines.append("")
    lines.append("**Independent native evidence**")
    if candidate and fused.get("nativeButtonCommandVerified") is True:
        lines.append(
            f"- Physical button {_name(candidate.get('physicalButtonNumber'))} on "
            f"device {_name(candidate.get('physicalButtonDeviceId'))}: "
            f"{_name(candidate.get('nativePhysicalPressAtUtc'))} "
            "(native physical source)."
        )
        lines.append(
            f"- Native OFF command at {_name(candidate.get('nativeOffCommandAtUtc'))} "
            f"from app {_name(candidate.get('commandProducerAppId'))} "
            f"({_name(candidate.get('commandProducerLabel'))}); "
            f"{candidate.get('buttonToCommandMilliseconds')} ms after the native press."
        )
    else:
        rows = [
            item for item in native_commands
            if isinstance(item, dict) and item.get("commandAt")
        ]
        if rows:
            for item in rows[:2]:
                lines.append(
                    f"- Native OFF command retained at {_name(item.get('commandAt'))}: "
                    f"producer app {_name(item.get('producerAppId'))} "
                    "(independently observed command history)."
                )
            lines.append("- A matching native physical controller event could not be jointly verified in this read.")
        else:
            lines.append(
                f"- No matching native OFF command appears in the returned {history_hours}-hour "
                "command-history rows. **This does not prove no OFF command occurred.**"
            )
            lines.append(
                "- No native physical button press was independently matched "
                "to an OFF command in this read."
            )
    if selected is not None:
        lines.append(
            f"- Native light OFF state retained at {selected.isoformat(timespec='milliseconds')} "
            f"(device {_name(facts.get('lightDeviceId'))})."
        )
    else:
        lines.append(
            f"- No native light OFF state transition for this clock appears "
            "in the returned switch history; the journal cannot supply its original timestamp."
        )

    lines.append("")
    lines.append("**Historical Journal (collector observations, not native source clocks)**")
    journal_off = _best_journal_off(
        journal, light_id=str(facts["lightDeviceId"]), anchor=target,
    )
    if journal_off:
        stamp, basis = journal_off
        lines.append(
            f"- Light OFF observed at {stamp.isoformat(timespec='milliseconds')} "
            f"({basis}). It supports an observed OFF, but is **not** an "
            "independently verified native state-event timestamp."
        )
    else:
        lines.append("- No matching collector-received OFF was retained for the requested scope.")
    lines.extend(_journal_buttons(journal, anchor=target))
    if journal_off:
        motion_lines = _journal_motion(journal, after=journal_off[0])
        lines.extend(motion_lines or [
            "- No post-OFF motion observations were found in these returned journal rows; "
            "coverage is incomplete."
        ])
    if gaps:
        lines.append(
            f"- **Capture gaps:** {gaps} recorded journal gap window(s); "
            "absence of other sensor events or light ON events is not exhaustive proof."
        )

    lines.append("")
    lines.append(f"**App {_name(facts.get('appId'))} motion lockout**")
    lines.append(
        f"- Current stored duration: **{duration} minutes**."
        if isinstance(duration, int) else
        "- Current stored duration: not verified."
    )
    lines.append(
        f"- Current stored trigger mode: {_name(mode)}."
        if mode else
        "- Current stored trigger mode and configured physical button role: not verified from returned settings."
    )
    lines.append(
        f"- Bounded app-execution logs: {int(logs.get('returnedRows') or 0)} returned rows. "
        "Their absence does **not** establish that no handler ran."
    )
    lines.append(
        "- **Historical decision, timer start, motion-trigger eligibility, "
        "and effective inhibition remain unverified.** No Hubitat configuration or device was changed."
    )
    return "\n".join(lines)


__all__ = ["render_bounded_focal_reconstruction"]
