"""Evidence-first user report; detailed immutable claim audit stays separate.

No LLM-authored free-form cause is copied as a verified finding. The host
renders source events and *possibilities* in conversational format, retaining
canonical record identifiers and complete command history in the audit output.
"""
from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from .evidence import CaseFile, EvidenceItem
from .read_loop import Hypothesis
from .temporal_scope import IncidentWindow


def _time(row: EvidenceItem, window: IncidentWindow | None) -> str:
    try:
        instant=datetime.fromisoformat(row.timestamp_utc)
        if window is not None:
            stamp=instant.astimezone(ZoneInfo(window.zone_name))
            return stamp.strftime("%d %b %H:%M:%S %Z")
        return instant.strftime("%d %b %H:%M:%S UTC")
    except (ValueError, TypeError):
        return "Time unavailable"


def _event(row: EvidenceItem) -> str:
    if row.stage=="command_issued":
        return row.action.replace("command-", "") + ("("+row.value+")" if row.value is not None else "()") + " issued"
    if row.stage=="state_reported":
        return row.action + (" = "+row.value if row.value is not None else "") + " reported"
    return row.action.replace("stored-setting:","Setting ")+(" = "+row.value if row.value is not None else "")


def _actor(row: EvidenceItem, case: CaseFile | None = None) -> str:
    if row.producer_id and case is not None:
        label = case.app_identities.get(row.producer_id)
        if label:
            return label + " (app #" + row.producer_id + ")"
    if row.producer_label and row.producer_id:
        return row.producer_label + " (#"+row.producer_id+")"
    if row.producer_id:
        return "Hubitat source #"+row.producer_id
    return "Source not identified"


def format_investigation_report(
    case: CaseFile, hypotheses: list[Hypothesis], stop_reason: str,
    window: IncidentWindow | None = None,
) -> str:
    """Compact report, not a new source of verified claims.

    Local time follows hub zone including DST. Ranking model proposals does
    not upgrade them to confirmed causes; confidence derives from record IDs.
    """
    records=[r for r in case.records if r.stage in ("command_issued","state_reported")]
    commands=[r for r in records if r.stage=="command_issued"]
    lines=["**Finding**"]
    if not records:
        lines.append("No timestamped command or state record was recovered for the requested incident. This does **not** prove that nothing happened.")
    else:
        lines.append(
            f"Recovered {len(commands)} issued command(s) and "
            f"{len(records)-len(commands)} reported state observation(s). "
            "These support a partial sequence, not a proven single root cause."
        )
    if window is not None:
        lines.append(f"Requested window: {window.start_utc} to {window.end_utc} "
                     f"(UTC; local hub zone {window.zone_name}).")
    relevant=[c for c in case.coverage if c.operation=="hub_list_device_events"]
    if window is not None and relevant:
        if (any(c.requested_window_reached is False for c in relevant if c.succeeded)
                and not any(c.requested_window_reached is True for c in relevant)):
            lines.append("**Coverage warning:** returned history pages did not reach the incident start. No incident event must be treated as absent.")
        elif not any(c.requested_window_reached is True for c in relevant):
            lines.append("**Coverage warning:** the returned history has not established that the incident start was reached.")
    if not any(c.source_complete is True for c in case.coverage):
        lines.append("The historical source is not independently proven complete.")

    lines.append("")
    lines.append("**Recorded timeline** (commands and reported states are different evidence)")
    if records:
        if window is not None:
            names = {datetime.fromisoformat(row.timestamp_utc)
                     .astimezone(ZoneInfo(window.zone_name)).tzname()
                     for row in records}
            if len(names) > 1 and "BST" in names and "GMT" in names:
                lines.append("Times are local. UK clocks went back from BST to GMT on 25 October; the repeated hour is shown with its timezone.")
        known = sum(bool(row.producer_id) for row in records)
        show_source = known * 4 >= len(records)
        if not show_source:
            lines.append("**Source note:** Issuing apps are not identified for most returned records. Missing source metadata is not evidence of manual control.")
        lines.extend(
            ["| Local time | Observation | Source |", "|---|---|---|"]
            if show_source else
            ["| Local time | Observation |", "|---|---|"]
        )
        priority = [row for row in records
                    if row.stage == "command_issued"
                    or row.action in ("switch", "level", "networkStatus")]
        chosen = priority if len(priority)<=14 else priority[:6]+priority[-8:]
        for row in chosen:
            cols = f"| {_time(row,window)} | {_event(row)}"
            lines.append(cols + (f" | {_actor(row,case)} |" if show_source else " |"))
        if len(chosen) < len(records):
            lines.append(f"{len(records)-len(chosen)} additional observations appear in the technical report.")
    else:
        lines.append("No incident records were recovered from the queried sources.")

    lines.extend(["", "**Most useful lead**"])
    pairs=[(a,b) for i,a in enumerate(commands) for b in commands[i+1:]
           if a.target_id and a.target_id==b.target_id
           and a.action=="command-off" and b.action in ("command-on","command-setLevel")
           and a.producer_id and b.producer_id and a.producer_id!=b.producer_id
           and 0<(datetime.fromisoformat(b.timestamp_utc)-datetime.fromisoformat(a.timestamp_utc)).total_seconds()<=3600]
    if pairs:
        # Focus on the user's incident, not the first eligible pair in an
        # indiscriminate chronological scan. For broad dated overnight windows,
        # events closest to the interval's midpoint are most useful leads;
        # faster ON/level reversal breaks equal-distance ties.
        if window is not None:
            start=datetime.fromisoformat(window.start_utc)
            end=datetime.fromisoformat(window.end_utc)
            focus=start+(end-start)/2
            pairs.sort(key=lambda pair: (
                abs((datetime.fromisoformat(pair[1].timestamp_utc)-focus).total_seconds()),
                (datetime.fromisoformat(pair[1].timestamp_utc) -
                 datetime.fromisoformat(pair[0].timestamp_utc)).total_seconds(),
            ))
        else:
            pairs.sort(key=lambda pair: datetime.fromisoformat(pair[1].timestamp_utc), reverse=True)
        earlier,later=pairs[0]
        lines.append(
            f"**Possible competing controllers:** {_actor(earlier,case)} issued OFF at "
            f"{_time(earlier,window)}; {_actor(later,case)} then issued "
            f"{later.action.replace('command-','')} at {_time(later,window)}. "
            "This makes automation interference worth checking, but it does not prove the later command turned the physical light on."
        )
    elif commands:
        lines.append("The command sequence is available, but no directly linked competing-controller sequence is yet established.")
    else:
        lines.append("No issued command supports identifying the initiating controller.")
    set_levels = [row for row in commands if row.action == "command-setLevel"]
    if set_levels:
        lines.append(
            "A `setLevel()` command on a dimmable light commonly turns it ON while "
            "setting brightness, including when it was previously OFF. Here it "
            "shows the controller's intent, not independent confirmation that "
            "the bulb actually lit."
        )
    offs = [row for row in commands if row.action == "command-off"]
    if offs:
        last_off = offs[-1]
        lines.append(
            f"Another OFF was issued at {_time(last_off,window)}. "
            "Without a subsequent independently reported switch state, "
            "we cannot establish that the bulb obeyed it."
        )
    offline = [row for row in records if row.action == "networkStatus" and row.value == "offline"]
    online = [row for row in records if row.action == "networkStatus" and row.value == "online"]
    if offline:
        nearest = next((on for on in online if
                        on.timestamp_utc > offline[0].timestamp_utc), None)
        lines.append(
            f"A network-offline state was reported at {_time(offline[0],window)}"
            + (f", followed by an online report at {_time(nearest,window)}"
               if nearest else "")
            + ". This warrants checking connectivity but does not prove "
              "that a later command failed."
        )

    backed=[h for h in hypotheses if h.supporting_record_ids or h.conflicting_record_ids]
    if backed:
        lines.extend(["","**Competing explanations (provisional)**"])
        for h in backed[:3]:
            lines.append(f"- {h.explanation} (source links: "
                         f"{', '.join(h.supporting_record_ids[:3]) or 'conflicting only'}; "
                         "a hypothesis is not proof of its physical outcome).")
    lines.extend(["","**What remains unverified**"])
    lines.append("The initiating trigger, the effective historical rule conditions, and the physical bulb state are not established solely by these records.")
    if stop_reason not in ("model_finished","round_budget_reached","no_new_usable_evidence"):
        lines.append(f"Investigation stopped early ({stop_reason.replace('_',' ')}); some relevant reads may be missing.")
    if stop_reason == "no_new_usable_evidence":
        lines.append("The extra reads returned no new usable evidence; the investigation stopped rather than repeating an expensive AI planning round.")
    if stop_reason == "no_approved_discriminating_reads":
        lines.append("The model could not obtain another approved, useful read. Check the bounded read rejection reasons in Investigation details; this is not evidence that the relevant hub data does not exist.")
    lines.extend(["","**What would settle it**"])
    if pairs:
        ids=sorted({a.producer_id for p in pairs for a in p if a.producer_id})
        lines.append("- Inspect the execution logs and effective source/configuration of the controlling Hubitat apps "
                     +", ".join("#"+x for x in ids)+", especially their actions between the listed commands.")
    elif commands:
        lines.append("- Map the recorded command source IDs to their controlling apps and compare relevant execution logs and conditions.")
    else:
        lines.append("- Recover the source history for the requested dates, including pages reaching the start, before drawing conclusions.")
    lines.append("- Check subsequent switch/level reports and physical observation before treating an OFF command as successful.")
    lines.append("- Cross-check bridge or external-platform activity and hub restart/network records where available.")
    lines.append("")
    lines.append("Detailed commands, source IDs, validation flags and read coverage remain in **Investigation details**.")
    return "\n".join(lines)


__all__=["format_investigation_report"]
