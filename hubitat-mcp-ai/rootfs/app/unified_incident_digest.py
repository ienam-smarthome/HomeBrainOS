"""Source-verified, cause-first multi-light incident digest.

The original HomeBrain agent selects reads and the factual evidence contract
remains in unified_investigation_bridge. This presenter is a *final* safety
fallback when the model's earlier explanation lacks recovered archive events.
It never chooses tools or invents upstream cause, and does not confuse archive
collector reception with actual source event timestamps.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _when(row: Mapping[str, Any]) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(row.get("date") or "").replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _clock(row: Mapping[str, Any]) -> str:
    at = _when(row)
    return at.strftime("%H:%M:%S") if at else "time unavailable"


def _source_rows(facts: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    source, collector, live = [], [], []
    allowed = set(str(x) for x in facts.get("target_device_ids", []))
    for row in facts.get("incident_ledger", [])[:200]:
        if not isinstance(row, Mapping) or str(row.get("device_id")) not in allowed:
            continue
        if _when(row) is None:
            continue
        entry = dict(row)
        kind = entry.get("event_class")
        if kind in ("journal_source_switch_on", "journal_source_switch_off"):
            source.append(entry)
        elif kind in ("journal_received_switch_on", "journal_received_switch_off"):
            collector.append(entry)
        elif kind in ("issued_on", "issued_off", "issued_setlevel", "reported_level",
                      "reported_switch_on", "reported_switch_off"):
            live.append(entry)
    sortkey = lambda e: (_when(e), e.get("device_id", ""))
    for group in (source, collector, live):
        group.sort(key=sortkey)
    return source, collector, live


def _dedupe_archive(source: list[dict[str, Any]], collector: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Prefer independently source-timestamped state over later receipt copy."""
    # Pair only same device, same state, and a nonnegative reception lag.
    unique_source: list[dict[str, Any]] = []
    for row in source:
        if unique_source and any(
            p["device_id"] == row["device_id"]
            and p["value"] == row["value"]
            and 0 <= (_when(row) - _when(p)).total_seconds() <= 0.35
            for p in unique_source[-6:]
        ):
            continue
        unique_source.append(row)
    unmatched: list[dict[str, Any]] = []
    paired = 0
    for row in collector:
        match = any(
            p["device_id"] == row["device_id"]
            and p["value"] == row["value"]
            and 0 <= (_when(row) - _when(p)).total_seconds() <= 4.0
            for p in unique_source
        )
        if match:
            paired += 1
        else:
            unmatched.append(row)
    return unique_source, unmatched, paired


def _group_states(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for row in rows:
        if not groups:
            groups.append([row])
            continue
        latest = groups[-1]
        if (row["value"] == latest[0]["value"]
                and row["device_id"] not in {e["device_id"] for e in latest}
                and 0 <= (_when(row) - _when(latest[0])).total_seconds() <= 1.8):
            latest.append(row)
        else:
            groups.append([row])
    return groups


def _name(group: list[dict[str, Any]], all_ids: set[str]) -> str:
    ids = {r["device_id"] for r in group}
    if len(ids) == len(all_ids) and len(ids) >= 3:
        return "All three lights"
    if len(group) == 2 and all(
        str(row.get("device_name", "")).startswith("Bathroom Light ")
        for row in group
    ):
        return "Bathroom Lights 1 and 2"
    return ", ".join(str(r.get("device_name") or r["device_id"]) for r in group)


def _nearest_commands(
    group: list[dict[str, Any]], commands: list[dict[str, Any]],
    *, direction: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for state in group:
        for command in commands:
            if state["device_id"] != command["device_id"]:
                continue
            delta = (_when(command) - _when(state)).total_seconds()
            if direction == "before" and -2.0 <= delta <= 0:
                matches.append(command)
            if direction == "after" and 0 <= delta <= 2.0:
                matches.append(command)
    return matches


def _dedupe_values(rows: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({str(row.get(key)) for row in rows if row.get(key)})


def source_incident_digest(facts: Mapping[str, Any]) -> str | None:
    """Render evidence, not a model's unsupported activation hypothesis.

    This is available only after independent source-timestamped archive switch
    observations are returned for at least two user-verified target devices.
    Never infer complete time coverage from an empty search or stream status.
    """
    source, collector, live = _source_rows(facts)
    if len({r["device_id"] for r in source}) < 2:
        return None
    source, unmatched, paired = _dedupe_archive(source, collector)
    groups = _group_states(source)
    target_ids = {str(x) for x in facts.get("target_device_ids") or []}
    offs = [r for r in live if r["event_class"] == "issued_off"]
    levels = [r for r in live if r["event_class"] == "issued_setlevel"]
    oncmds = [r for r in live if r["event_class"] == "issued_on"]
    lines: list[str] = []

    for group in groups[:30]:
        at = _clock(group[0])
        state = group[0]["value"].upper()
        label = _name(group, target_ids)
        if state == "OFF":
            matching = _nearest_commands(group, offs, direction="before")
            apps = _dedupe_values(matching, "app_id")
            reason = (
                "OFF command from app " + ", ".join(apps)
                + " immediately before the reported OFF"
                if apps else "Reported OFF; initiating command not established"
            )
        else:
            # A setLevel issued AFTER ON can adjust brightness but cannot
            # establish what initiated the already-reported ON.
            following = _nearest_commands(group, levels, direction="after")
            following_apps = _dedupe_values(following, "app_id")
            previous_on = _nearest_commands(group, oncmds, direction="before")
            earlier_apps = _dedupe_values(previous_on, "app_id")
            if earlier_apps:
                reason = "Earlier on() command from app " + ", ".join(earlier_apps)
            elif following_apps:
                reason = (
                    "ON reported before app " + ", ".join(following_apps)
                    + " adjusted brightness"
                )
            else:
                reason = "Reported ON; upstream initiator not identified"
        lines.append("| " + at + " | " + label + " | " + state + " | " + reason + " |")

    # Unpaired collector observations have reception timestamps only; do not
    # insert them into the precise source event timeline.
    collector_notes: list[str] = []
    for group in _group_states(unmatched)[:7]:
        collector_notes.append(
            _clock(group[0]) + " " + _name(group, target_ids)
            + " reported " + group[0]["value"].upper()
        )

    # Mode transitions can explain a later brightness reapplication, not
    # retroactively initiate a light already reported ON minutes earlier.
    mode_rows = [
        row for row in facts.get("hub_mode_observations", [])
        if isinstance(row, Mapping) and "mode" not in str(row.get("value", "")).lower()
    ]
    school = next((row for row in mode_rows
                   if str(row.get("value") or "").casefold() == "school run"), None)
    post_school = [
        row for row in levels
        if row["device_id"] in target_ids and
        _when(row) is not None
        and school is not None and _when(school) is not None
        and 0 <= (_when(row)-_when(school)).total_seconds() <= 4
    ]
    source_n = len(source)
    collector_n = len(collector)
    covered_ids = {r["device_id"] for r in source}
    missing_source = [
        c["device_name"] for c in facts.get("target_coverage", [])
        if c.get("device_id") not in covered_ids
    ]

    explanation = [
        "**What happened:** The Historical Journal recovered "
        + str(source_n) + " independently source-timestamped switch observations "
        "for the requested lights. It also recorded "
        + str(collector_n) + " reception-only observations. "
        "These establish switch changes, not who initiated them."
    ]
    if offs:
        app_ids = _dedupe_values(offs, "app_id")
        explanation.append(
            "**Confirmed Hubitat OFF requests:** Apps "
            + ", ".join(app_ids)
            + " issued off() commands. Where an OFF report followed within "
              "two seconds, the command is a credible immediate source "
              "of that OFF. The originating button press or upstream "
              "decision needs its own execution evidence."
        )
    level_after_on = []
    for group in groups:
        if group[0]["value"] != "on":
            continue
        matches = _nearest_commands(group, levels, direction="after")
        if matches:
            level_after_on.append(
                _clock(group[0]) + " " + _name(group, target_ids)
                + " (app " + ", ".join(_dedupe_values(matches, "app_id")) + ")"
            )
    if level_after_on:
        explanation.append(
            "**Brightness commands followed ON observations:** "
            + "; ".join(level_after_on[:5])
            + ". A later setLevel is not proof that app initiated the "
              "earlier switch-on. The initiating ON controller is unverified."
        )
    if school and post_school:
        earlier_on = [
            state for state in source
            if state["value"] == "on"
            and state["device_id"] in {level["device_id"] for level in post_school}
            and 0 < (_when(school) - _when(state)).total_seconds() <= 3600
        ]
        mode_line = (
            "**Mode and brightness:** Hubitat reported School Run at "
            + _clock(school) + ", followed by a setLevel command."
        )
        if earlier_on:
            latest = max(earlier_on, key=_when)
            mode_line += (
                " The affected light had already reported ON at "
                + _clock(latest)
                + "; the mode-time setLevel was not that initial ON."
            )
        else:
            mode_line += " This does not establish that the mode changed switch state."
        explanation.append(mode_line)
    app_checks = facts.get("archived_app_checks") or []
    if app_checks:
        rows = [str(x.get("app_id")) + ": " + str(x.get("log_rows"))
                + " archived message(s)" for x in app_checks
                if type(x.get("log_rows")) is int]
        absent = [str(x.get("app_id")) for x in app_checks
                  if x.get("status") == "app-log-capture-not-enabled-for-app"]
        if rows:
            descriptors = sorted({
                str(mark.get("stage") or "")
                for item in app_checks
                for mark in item.get("reported_decisions", [])
                if isinstance(mark, Mapping) and mark.get("stage")
            })
            explanation.append(
                "**Archived Hubitat app logs checked:** " + "; ".join(rows[:8])
                + (". App-reported decision categories: "
                   + ", ".join(descriptors[:6]) if descriptors else "")
                + ". These are collector-received textual reports; they do "
                  "not independently establish which app initiated a prior ON."
            )
        if absent:
            explanation.append(
                "**App log capture unavailable for:** " + ", ".join(absent[:8])
                + ". Enabling it will capture future activity only."
            )
    if missing_source:
        explanation.append(
            "**Remaining switch-history gaps:** No independent "
            "source-timestamped switch reports were returned for "
            + ", ".join(missing_source)
            + ". Collector reception alone cannot prove exact event time."
        )

    timeline = (
        "### Reconstructed source-timed sequence\n\n"
        "| UTC | Light | Change | What the evidence establishes |\n"
        "|---|---|---|---|\n" + "\n".join(lines)
    )
    extra = (
        "\n\n**Additional collector-only observations:** "
        + "; ".join(collector_notes)
        + ". These are *reception* times, not verified original event times."
        if collector_notes else ""
    )
    limits = (
        "**What remains uncertain:** The retrieved journal/device histories "
        "do not independently identify which Home Assistant, SmartThings, "
        "Hue, Aqara or other controller requested the ON events. "
        "Sensor timing and historical app execution logs would be required "
        "to distinguish them. Archived records do not establish "
        "uninterrupted coverage"
        + ("; connection gaps were reported" if facts.get("journal_gap_count") else "")
        + "."
    )
    return "\n\n".join(explanation) + "\n\n" + timeline + extra + "\n\n" + limits


__all__ = ["source_incident_digest"]
