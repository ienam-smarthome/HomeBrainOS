"""Guard against turning a performance warning into a proven lighting cause.

A long-running handler observed in one sampled log row is real performance
evidence, but does not prove that later app-issued OFF commands were delayed.
Use already retained, app-originated OFF / switch-OFF pairs and *listener-linked*
motion history to describe the observed latency before offering a diagnosis.
Never infer a timer configuration or physical vacancy from a state transition.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from occupancy_timing_correlation import correlate_occupancy_off_timing
from observed_long_method_guard import observed_long_method_warnings


_UNSUPPORTED_LATENCY_VERDICT = re.compile(
    r"(?is)(?:"
    r"most\s+likely\s+cause.{0,220}?(?:severe\s+execution\s+delay|handler|latency|hang)"
    r"|the\s+light\s+stays\s+on\s+because.{0,180}?(?:fail|delay|hang|slow)"
    r"|smoking\s+gun.{0,200}?(?:handler|latency|execution|129)"
    r"|(?:conclusion|root\s+cause)\s*:.{0,180}?(?:hang|fail|delay)"
    r")"
)


def _clock(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def _display_clock(value: Any) -> str:
    stamp = _clock(value)
    return stamp.strftime("%H:%M:%S.%f")[:-3] if stamp else "unverified-time"


def _on_windows(evidence: list[dict[str, Any]], light: str) -> list[dict[str, Any]]:
    """Use typed closed intervals; never assume newest-N represents 24h."""
    windows: dict[tuple[str, str], dict[str, Any]] = {}
    for receipt in evidence:
        if (not isinstance(receipt, dict) or receipt.get("success") is not True
                or receipt.get("tool") != "homebrain_device_history"):
            continue
        details = receipt.get("details") or {}
        if (not isinstance(details, dict) or details.get("attribute") != "switch"
                or str(details.get("label") or "") != light):
            continue
        for window in (details.get("temporalAnalysis") or {}).get("observedIntervals") or []:
            if not isinstance(window, dict):
                continue
            start, end = _clock(window.get("start")), _clock(window.get("end"))
            if start and end and end > start:
                windows[(start.isoformat(), end.isoformat())] = window
    return list(windows.values())


def guard_observed_off_latency_causality(
    message: str, evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Replace a confident, unsupported perf->OFF cause only with direct facts.

    This is deliberately narrow: if source-linked inactivity/OFF pairs do not
    exist, ordinary model answers and other claim guards remain in charge.
    The warning and OFF pairs must relate to the same observed app.
    """
    original = str(message or "")
    if not _UNSUPPORTED_LATENCY_VERDICT.search(
        re.sub(r"[*_`]", "", original)
    ):
        return original, False
    correlations = correlate_occupancy_off_timing(evidence)
    warnings = observed_long_method_warnings(evidence)
    selected_app = None
    selected_rows: list[dict[str, Any]] = []
    for app in sorted(warnings):
        rows = [
            row for row in correlations
            if row.get("appId") == app
            and isinstance(row.get("inactiveToCommandSeconds"), (int, float))
            and isinstance(row.get("ackSeconds"), (int, float))
            and row.get("verifiedAssociation") == "controller-is-event-listener"
        ]
        rows.sort(key=lambda row: _clock(row.get("commandAt")) or
                  datetime.min.replace(tzinfo=timezone.utc))
        if len(rows) < 2:
            continue
        last = rows[-2:]
        # Require two close measured gaps: this shows a consistent input-to-
        # command pattern, not a multi-minute late OFF. No fixed 30s constant.
        if abs(last[0]["inactiveToCommandSeconds"]
               - last[1]["inactiveToCommandSeconds"]) > 2:
            continue
        selected_app, selected_rows = app, last
        break
    if not selected_rows:
        return original, False

    lines = [
        "**Observed behaviour (source-linked):** Two OFF sequences were recorded. "
        "They provide positive evidence of a consistent input-inactive-to-OFF "
        "gap; neither establishes physical absence.",
    ]
    for row in selected_rows:
        lines.append(
            f"- {row['lastObservedInactiveSensor']} became inactive at "
            f"{_display_clock(row['inactiveAt'])}; App {selected_app} issued "
            f"OFF at {_display_clock(row['commandAt'])} "
            f"({row['inactiveToCommandSeconds']:.3f}s later). "
            f"{row['light']} reported OFF {row['ackSeconds']:.3f}s "
            "after that command."
        )
    durations = warnings[selected_app].get("durations_ms") or []
    methods = warnings[selected_app].get("methods") or ()
    stamps = warnings[selected_app].get("timestamps") or []
    if durations:
        duration = max(durations)
        method_text = ", ".join(methods) if methods else "a method"
        stamp = (
            f" at {max(stamps)} (log timezone not independently verified)"
            if stamps else ""
        )
        lines.append(
            f"**Separate performance warning:** App {selected_app}'s "
            f"{method_text} ran for {duration:,}ms ({duration/1000:.3f}s)"
            f"{stamp}. This is a real long-running handler observation, but "
            "it does not show that either recorded OFF command was delayed."
        )
    target = selected_rows[0].get("light") or ""
    windows = _on_windows(evidence, target)
    if windows:
        longest = max(
            windows,
            key=lambda w: (
                (_clock(w["end"]) - _clock(w["start"])).total_seconds()
            ),
        )
        start, end = _clock(longest["start"]), _clock(longest["end"])
        duration_s = round((end - start).total_seconds())
        lines.append(
            f"**Longest returned closed ON interval:** "
            f"{_display_clock(longest['start'])}–"
            f"{_display_clock(longest['end'])} "
            f"({duration_s // 60}m {duration_s % 60}s). "
            "ON duration alone does not demonstrate time spent empty."
        )
    lines.append(
        "**Assessment:** The two measured OFF responses fit an "
        f"approximately {sum(r['inactiveToCommandSeconds'] for r in selected_rows)/2:.1f}s "
        "observed inactivity-to-command pattern. Whether that reflects "
        "the installed configured timer requires a verified source/configuration "
        "interpretation. The WARN is worth investigating separately; the "
        "current receipts do **not** demonstrate that its slow execution "
        "caused the later ON durations or OFF timing. A state listener is "
        "not necessarily an initiator of an ON transition, and an app "
        "command recorded *after* ON cannot be used as proof it initiated ON. "
        "Device history remains bounded and may omit earlier events. "
        "**Root cause not independently verified.**"
    )
    return "\n\n".join(lines), True


__all__ = ["guard_observed_off_latency_causality"]
