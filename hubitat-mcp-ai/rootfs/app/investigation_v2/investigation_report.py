"""Evidence-first user report; detailed immutable claim audit stays separate.

No LLM-authored free-form cause is copied as a verified finding. The host
renders source events and *possibilities* in conversational format, retaining
canonical record identifiers and complete command history in the audit output.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re
from zoneinfo import ZoneInfo
from .evidence import CaseFile, EvidenceItem
from .read_loop import Hypothesis
from .temporal_scope import IncidentWindow
from .transition_links import incident_links


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
    # Present source-backed current status regardless of AI availability.
    # A read-time attribute is not a historical state transition.
    if case.device_snapshots:
        attrs = case.device_snapshots[-1].get("attributes", {})
        if isinstance(attrs, dict):
            brief = [f"{k}={attrs[k]}" for k in (
                "switch", "networkStatus", "healthStatus", "deviceHealth",
                "mqttStatus",
            ) if k in attrs and type(attrs[k]) in (str, int, float, bool)]
            if brief:
                lines.append("**Current reported status:** " + ", ".join(brief)
                             + " (Hubitat read-time snapshot).")
    switches = [row for row in records if row.stage == "state_reported"
                and row.action == "switch"]
    if switches:
        latest = max(switches, key=lambda row: row.timestamp_utc)
        lines.append(
            "**Latest switch report:** "
            f"{latest.value} at {_time(latest, window)} "
            f"(reported by {_actor(latest,case)}). "
            "This event identifies the reporting source, not necessarily "
            "the initiating automation."
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

    # Compare the source-reported lastSeen to the actual oldest returned
    # event. This is a coverage gap, not evidence that a particular event did
    # not occur. A malformed or ambiguous date cannot create a claim.
    if case.device_snapshots and records:
        attrs = case.device_snapshots[-1].get("attributes", {})
        last_seen = attrs.get("lastSeen") if isinstance(attrs, dict) else None
        if isinstance(last_seen, str):
            match = re.fullmatch(
                r"((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) "
                r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
                r"\d{1,2} \d{2}:\d{2}:\d{2}) (BST|GMT) (\d{4})",
                last_seen,
            )
            if match:
                try:
                    local = datetime.strptime(
                        match.group(1) + " " + match.group(3),
                        "%a %b %d %H:%M:%S %Y",
                    ).replace(tzinfo=ZoneInfo("Europe/London"))
                    oldest = min(records, key=lambda row: row.timestamp_utc)
                    earliest = datetime.fromisoformat(oldest.timestamp_utc)
                    if (local.tzname() == match.group(2)
                            and local.astimezone(timezone.utc) < earliest):
                        lines.append(
                            "**History gap:** reported lastSeen is "
                            f"{last_seen}, but the earliest retrieved "
                            f"event is {_time(oldest, window)}. "
                            "This source page does not establish the "
                            "intervening history or the physical failure cause."
                        )
                except (ValueError, TypeError, OverflowError):
                    pass

    lines.append("")
    if case.device_snapshots:
        latest = case.device_snapshots[-1]
        attrs = latest.get("attributes", {})
        if isinstance(attrs, dict) and attrs:
            lines.extend(["", "**Current device snapshot (read-time, not a historical event)**",
                          ", ".join(f"{key}={value}" for key, value in attrs.items())])
            if "mqttStatus" in attrs:
                lines.append("An MQTT client reporting connected is not proof the physical device is reachable.")
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
        # Even when most state reports have no known issuer, preserve
        # attribution for a concrete issued command.
        show_source = (known * 4 >= len(records)
                       or any(row.producer_id for row in commands))
        clock_heading = "Local time" if window is not None else "UTC time"
        if not show_source:
            lines.append("**Source note:** Issuing apps are not identified for most returned records. Missing source metadata is not evidence of manual control.")
        lines.extend(
            [f"| {clock_heading} | Observation | Source |", "|---|---|---|"]
            if show_source else
            [f"| {clock_heading} | Observation |", "|---|---|"]
        )
        priority = [row for row in records
                    if row.stage == "command_issued"
                    or row.action in ("switch", "level", "networkStatus",
                                      "mqttStatus", "healthStatus", "deviceHealth")]
        if priority:
            # Do not let repeated health statuses hide earlier MQTT changes
            # or an issued command. Source rows remain fully available in
            # the technical answer.
            critical = [r for r in priority if r.stage == "command_issued"
                        or r.action in ("switch", "level", "networkStatus")]
            mqtt = [r for r in priority if r.action == "mqttStatus"]
            health = [r for r in priority if r.action in ("deviceHealth", "healthStatus")]
            # Retain the newest as well as oldest switch reports.
            important = (critical[:4] + critical[-4:]
                         if len(critical) > 8 else critical)
            focused = important + mqtt[:6] + (
                health[:1] + health[-1:] if len(health)>2 else health
            )
            selected = {r.record_id for r in focused}
            chosen = [r for r in records if r.record_id in selected][:14]
        else:
            # Preserve a useful timeline when events only contain health
            # or connectivity reports; do not create a blank table.
            chosen = records if len(records)<=8 else records[:3]+records[-3:]
        for row in chosen:
            cols = f"| {_time(row,window)} | {_event(row)}"
            lines.append(cols + (f" | {_actor(row,case)} |" if show_source else " |"))
        health_flips = [r for r in records if r.action == "deviceHealth"]
        if len(health_flips) >= 4:
            values = {r.value for r in health_flips}
            alternating = all(a.value != b.value for a,b in
                              zip(health_flips, health_flips[1:]))
            if values == {"stale", "unknown"} and alternating:
                lines.append(
                    f"**Repeated status changes:** {len(health_flips)} "
                    "deviceHealth observations alternated between stale "
                    "and unknown. This does not establish fresh contact "
                    "from the physical device."
                )
        if len(chosen) < len(records):
            lines.append(f"{len(records)-len(chosen)} additional observations appear in the technical report.")
    else:
        lines.append("No incident records were recovered from the queried sources.")
    if window is None and records:
        lines.append("Times above are UTC; original source-clock timestamps remain in Investigation details.")

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
            "This makes automation interference worth checking, but it does not prove the later command turned the device physically changed state."
        )
    elif commands:
        lines.append("The command sequence is available, but no directly linked competing-controller sequence is yet established.")
    else:
        lines.append("No issued command supports identifying the initiating controller.")
    # Use the same source-grounded relationship index as controller discovery.
    # Matching records are NOT a causal or independent physical proof.
    for link in incident_links(case):
        cmd, reported, failure = link.command, link.reported_state, link.adverse_state
        if cmd.action != "command-off" or reported is None:
            continue
        lines.append(
            "**Incident-linked sequence:** "
            f"{_actor(cmd,case)} issued OFF at {_time(cmd,window)}, "
            f"a switch=off state was reported at {_time(reported,window)}, "
            f"and {failure.action}={failure.value} was reported at "
            f"{_time(failure,window)}. This is consistent with an "
            "OFF-related loss of contact but does not independently prove "
            "the physical failure mechanism or network dependency."
        )
        break
    set_levels = [row for row in commands if row.action == "command-setLevel"]
    if set_levels:
        lines.append(
            "A `setLevel()` command on a dimmable light commonly turns it ON while "
            "setting brightness, including when it was previously OFF. Here it "
            "shows the controller's intent, not independent confirmation that "
            "the device actually changed state."
        )
    offs = [row for row in commands if row.action == "command-off"]
    if offs:
        last_off = offs[-1]
        # A reported switch transition after an issued OFF is relevant
        # evidence, even though it is not independent physical confirmation.
        reports = [row for row in switches
                   if row.target_id == last_off.target_id
                   and row.timestamp_utc >= last_off.timestamp_utc]
        off_reports = [row for row in reports if row.value == "off"]
        if off_reports:
            first = min(off_reports, key=lambda row: row.timestamp_utc)
            lines.append(
                f"Another OFF was issued at {_time(last_off,window)} and a subsequent "
                f"switch=off was reported at {_time(first,window)}. "
                "This is a Hubitat state report, not independent physical "
                "proof that the equipment or its network connection changed."
            )
        else:
            lines.append(
                f"Another OFF was issued at {_time(last_off,window)}. "
                "No subsequent switch=off report was recovered from these "
                "incomplete sources; physical execution remains unverified."
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
    if (window is not None and len([c for c in case.coverage
                if c.operation == "hub_list_device_events" and c.succeeded]) >= 2):
        lines.append("Two bounded history requests were compared. This reduces reliance "
                     "on a single response but does not establish that Hubitat history is complete.")
    # Configuration is read-time evidence, never retrospectively verified
    # historical rule behaviour. Projected values are already allowlisted.
    settings = [row for row in case.records if row.stage == "config_stored"]
    if settings:
        lines.extend(["", "**Current stored controller settings (not 12 October configuration)**"])
        for row in settings[:8]:
            lines.append(
                f"- {_actor(row,case)}: {_event(row)} "
                "(read-time stored setting; not proof of historical execution)"
            )
        if len(settings) > 8:
            lines.append(f"{len(settings)-8} additional projected settings are in Investigation details.")
    lines.extend(["","**What remains unverified**"])
    lines.append("The initiating trigger, the effective historical rule conditions, and the actual physical device state are not established solely by these records.")
    if stop_reason not in ("model_finished","round_budget_reached","no_new_usable_evidence"):
        lines.append(f"Investigation stopped early ({stop_reason.replace('_',' ')}); some relevant reads may be missing.")
    if stop_reason == "no_new_usable_evidence":
        lines.append("The extra reads returned no new usable evidence; the investigation stopped rather than repeating an expensive AI planning round.")
    if stop_reason == "no_approved_discriminating_reads":
        lines.append("The model could not obtain another approved, useful read. Check the bounded read rejection reasons in Investigation details; this is not evidence that the relevant hub data does not exist.")
    failed = [c for c in case.coverage if not c.succeeded]
    if failed:
        lines.extend(["", "**Failed source reads**"])
        for item in failed[:4]:
            lines.append(
                f"- {item.operation} for target {item.query_target_id or 'unspecified'}: "
                f"{item.failure_code or 'cause unavailable'}; no source evidence was established by this read."
            )
        if len(failed) > 4:
            lines.append(f"{len(failed)-4} additional failed reads appear in Investigation details.")
    lines.extend(["","**What would settle it**"])
    if pairs:
        ids=sorted({a.producer_id for p in pairs for a in p if a.producer_id})
        lines.append("- Inspect the execution logs and effective source/configuration of the controlling Hubitat apps "
                     +", ".join("#"+x for x in ids)+", especially their actions between the listed commands.")
    elif commands:
        lines.append("- Map the recorded command source IDs to their controlling apps and compare relevant execution logs and conditions.")
    else:
        lines.append("- Recover earlier device messages and state transitions reaching the start of the fault, not only recent health reports.")
    lines.append("- Check device last-contact and switch reports, plus physical/network reachability, before treating a command as successful.")
    lines.append("- Cross-check bridge or external-platform activity and hub restart/network records where available.")
    lines.append("")
    lines.append("Detailed commands, source IDs, validation flags and read coverage remain in **Investigation details**.")
    return "\n".join(lines)


__all__=["format_investigation_report"]
