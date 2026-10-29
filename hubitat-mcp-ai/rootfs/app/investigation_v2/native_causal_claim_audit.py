"""Independent temporal evidence audit for model-originated causal conclusions.

This module is not a question-intent router or a device rule. It audits
observed warning windows, scoped commands, and device state events. It also
prevents unsubstantiated causal ranking from being published as a conclusion.
No tool actions, source code exposure, or permission decisions occur here.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Mapping, Sequence
from .native_evidence_coverage import _wall_time
from .native_incident_cooccurrence import incident_state_cooccurrences
from .native_incident_command_temporal import incident_command_temporal_leads

# Claim-strength cues are assessed *after* the model answers, not for
# interpreting the user's request or selecting a tool. They identify
# causal attribution or ranking that cannot be independently supported.
_CAUSAL_ASSERTION=re.compile(
    r"\b(?:most\s+(?:material|likely|plausible|probable)\s+(?:offender|"
    r"cause|driver|contributor|mechanism)|primary\s+(?:cause|driver|offender)|"
    r"(?:likely|main)\s+drivers?\s+(?:of|are)|"
    r"(?:is|was)\s+(?:most\s+)?(?:plausibly|likely)\s+driven\s+by|"
    r"(?:is|was)\s+(?:caused|triggered)\s+by|"
    r"(?:is|was)\s+responsible\s+for)\b",re.I)


def incident_attribution_packet(
    witnesses: Sequence[Mapping[str, Any]], focus_ids: Sequence[str],
) -> dict[str, Any] | None:
    focus={str(k) for k in focus_ids if str(k).isdecimal()}
    if not focus:
        return None
    incidents=[]
    for witness in witnesses:
        if witness.get("operation")!="hub_get_logs":
            continue
        d=witness.get("source_data")
        summary=d.get("log_summary") if isinstance(d,dict) else None
        if not isinstance(summary,dict):
            continue
        for group in summary.get("warning_error_groups",[])[:35]:
            if not isinstance(group,dict) or str(group.get("source_id")) not in focus:
                continue
            lo=_wall_time(group.get("oldest_returned"))
            hi=_wall_time(group.get("newest_returned"))
            if lo is not None and hi is not None:
                if lo>hi:lo,hi=hi,lo
                # A grouped log entry is a collection of source-reported
                # occurrences, not a continuously running incident.
                samples=sorted(
                    t for t in (
                        _wall_time(stamp)
                        for stamp in group.get("sample_timestamps",[])[:48]
                        if isinstance(stamp,str))
                    if t is not None)
                if samples:
                    lo=hi=samples[-1]
                incidents.append((lo,hi,group))
    if not incidents:
        return None
    # Do not merge slow-method WARN with generic WARN; the narrowest
    # newest generic interval is the incident being audited here.
    # Source classification, not question-word routing: the canonical
    # attribution contract below applies specifically to the generic
    # high-load warning. Other WARN classes need their own source schema.
    generic=[v for v in incidents if "excessive hub load" in
             str(v[2].get("message","")).casefold()]
    if not generic:
        return None
    distinct_slow_methods=[
        v for v in incidents
        if re.search(r"\bmethod\s+[A-Za-z_]\w*\b",
                     str(v[2].get("message","")),re.I)
    ]
    start,end,warn=sorted(generic,key=lambda v:(
        0 if v[2].get("sample_timestamps") else 1,
        (v[1]-v[0]).total_seconds(),-v[1].timestamp()))[0]
    occurrence=(
        end.isoformat() if warn.get("sample_timestamps") else None
    )
    warning_batch={
        "sampled_rows":warn.get("count"),
        "sampled_unique_timestamps":warn.get("sample_unique_timestamp_count"),
        "oldest_returned":warn.get("oldest_returned"),
        "newest_returned":warn.get("newest_returned"),
        "individual_timestamps_capped":bool(
            warn.get("sample_timestamps_capped")),
        "not_a_continuous_incident":True,
    }
    app_commands=[]
    device_events=[]
    app_summaries={}
    event_read_ids=[]
    projected_source_rows=0
    omitted=0
    for witness in witnesses:
        if witness.get("operation")!="hub_list_device_events":
            continue
        filters=witness.get("read_filters",{})
        if not isinstance(filters,dict) or str(filters.get("deviceId")) not in focus:
            continue
        d=witness.get("source_data",{})
        if not isinstance(d,dict):
            continue
        if isinstance(witness.get("read"),int):
            event_read_ids.append(witness["read"])
        projected_source_rows+=len(d.get("events",[]))
        omitted+=int(d.get("event_rows_omitted_from_model") or 0)
        for row in d.get("issuer_apps",[])[:12]:
            if isinstance(row,dict):
                app_id=str(row.get("appId") or "")
                if app_id.isdecimal():
                    app_summaries.setdefault(app_id,row)
        for row in d.get("events",[])[:130]:
            if not isinstance(row,dict):continue
            stamp=_wall_time(row.get("date") or row.get("time"))
            if stamp is None:continue
            name=str(row.get("name") or "")
            producer=row.get("producedBy")
            producer=producer if isinstance(producer,dict) else {}
            aid=str(producer.get("appId") or "")
            did=str(producer.get("deviceId") or "")
            if name.startswith("command-") and aid.isdecimal():
                app_commands.append((stamp,aid,name))
            elif did in focus:
                device_events.append((stamp,name,str(row.get("value") or "")))
    # An incident with no app-issued commands is still a real incident.
    # Never interpret zero source rows as proof that no app issued commands.
    # Remove duplicate rows from overlapping source event reads.
    app_commands=sorted(set(app_commands))
    device_events=sorted(set(device_events))
    # "Same warning time" is a SOURCE-WALL-CLOCK comparison, never proof
    # of shared timezone or causation. Return exact separation if known.
    incident_commands=[c for c in app_commands
                       if start<=c[0]<=end]
    recent_commands=[c for c in app_commands
                     if abs((c[0]-end).total_seconds())<=300]
    nearest=min((abs((c[0]-end).total_seconds()),c)
                for c in app_commands) if app_commands else None
    coincident_device=[(t,n,v) for t,n,v in device_events
                       if abs((t-end).total_seconds())<=2]
    # Observe contiguous high-frequency commands only in the actually
    # retained event rows. A count by command name across days is NOT
    # a loop within one burst. Bound sampling to avoid hallucinating.
    bursts=[]
    by_kind={}
    for stamp,aid,name in app_commands:
        by_kind.setdefault((aid,name),[]).append(stamp)
    for (aid,name),times in sorted(by_kind.items()):
        group=[]
        for when in times:
            if group and (when-group[-1]).total_seconds()>2:
                if len(group)>=4:
                    bursts.append((aid,name,group[0],group[-1],len(group)))
                group=[]
            group.append(when)
        if len(group)>=4:
            bursts.append((aid,name,group[0],group[-1],len(group)))
    bursts.sort(key=lambda b:(-b[4],b[2]))
    return {
        "incident_type":"generic_device_warning",
        "separate_diagnostic_method_warnings_present":bool(distinct_slow_methods),
        "separate_diagnostic_method_warning_count":len(distinct_slow_methods),
        "warning_period":{
            "oldest":occurrence or str(warn.get("oldest_returned")),
            "newest":occurrence or str(warn.get("newest_returned")),
            "printed_timezone_alignment_verified":False},
        "warning_occurrence_selected":occurrence,
        "warning_group_sample":warning_batch,
        "warning_state_correlations":incident_state_cooccurrences(
            witnesses, sorted(focus)),
        "warning_command_temporal_leads":incident_command_temporal_leads(
            witnesses, sorted(focus)),
        "device_caller_app_ids":sorted(app_summaries),
        "device_caller_names":{
            k:str(app_summaries[k].get("name") or "")[:70]
            for k in sorted(app_summaries)
        },
        "caller_identities_verified":bool(app_summaries),
        "warning_read_ids":sorted({
            w.get("read") for w in witnesses
            if isinstance(w.get("read"),int)
            and w.get("operation")=="hub_get_logs"
            and any(isinstance(g,dict)
                    and str(g.get("source_id")) in focus
                    and "excessive hub load" in str(g.get("message","")).casefold()
                    for g in w.get("source_data",{}).get("log_summary",{})
                              .get("warning_error_groups",[]))
        }),
        "event_read_ids":sorted(set(event_read_ids)),
        "scoped_event_history_available":bool(event_read_ids),
        "app_commands_within_warning_interval":len(incident_commands),
        "app_commands_within_five_minutes":len(recent_commands),
        "nearest_app_command_gap_seconds":(
            round(nearest[0],3) if nearest is not None else None),
        "nearest_app_command":{
            "appId":nearest[1][1],
            "command":nearest[1][2],
            "timestamp":nearest[1][0].isoformat()
        } if nearest else None,
        "device_events_within_two_seconds":[{
            "name":name,"value":value[:50],"timestamp":stamp.isoformat()
        } for stamp,name,value in coincident_device[:10]],
        "observed_command_bursts":[{
            "appId":aid,"command":name,"count_in_burst":count,
            "first":lo.isoformat(),"last":hi.isoformat(),
            "gap_from_warning_end_seconds":round(abs((end-hi).total_seconds()),2)
        } for aid,name,lo,hi,count in bursts[:8]],
        "observed_device_event_rows":len(device_events),
        "observed_command_rows":len(app_commands),
        "projected_event_rows":projected_source_rows,
        "events_omitted_from_projected_rows":omitted,
        "causal_conclusion_strength":"unattributed",
        "independent_executed_method_or_cpu_attribution":False,
        "interpretation_limit":(
            "Prior command bursts and contemporaneous device state changes "
            "are observations, not proof of who/what caused a generic WARN. "
            "A source clock may differ and a bounded history can omit commands. "
            "Do not rank apps or callbacks by contribution without "
            "discriminating runtime evidence."),
    }


def unsupported_causal_ranking(
    narrative: str, packet: Mapping[str,Any]|None,
) -> bool:
    """Fail closed for an asserted ranking about an unattributed incident.

    This is a final-claim safety gate. It does not choose investigation tools
    and does not classify the user's question. Ordinary observations
    ("11 refresh commands at 18:15") remain publishable.
    """
    return bool(
        packet is not None
        and packet.get("causal_conclusion_strength") == "unattributed"
        and packet.get("independent_executed_method_or_cpu_attribution") is False
        and _CAUSAL_ASSERTION.search(narrative or "")
    )


def incident_claim_ledger(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Deterministic, source-receipt-backed facts with explicit uncertainty.

    This ledger validates only the fixed observations it derives. It does not
    assert that arbitrary free-text LLM claims have been verified. Future
    structured model claims can reference these IDs and be checked before
    publication.
    """
    log_reads=list(packet.get("warning_read_ids",[]))
    event_reads=list(packet.get("event_read_ids",[]))
    exists=bool(packet.get("scoped_event_history_available"))
    state_count=len(packet.get("device_events_within_two_seconds",[]))
    return [
        {"id":"warning_observed","status":"verified",
         "evidence_reads":log_reads,
         "observation":"generic source-reported excessive-load warning"},
        {"id":"device_command_issuers","status":(
             "verified_in_bounded_sample"
             if packet.get("caller_identities_verified") else "not_established"),
         "evidence_reads":event_reads,
         "app_ids":list(packet.get("device_caller_app_ids",[]))},
        {"id":"warning_window_command_overlap","status":(
             "bounded_sample_observation" if exists else "not_checked"),
         "evidence_reads":event_reads+log_reads,
         "observed_commands":packet.get("app_commands_within_warning_interval"),
         "clock_alignment_verified":False,
         "history_complete":False},
        {"id":"device_state_near_warning","status":(
             "bounded_sample_observation" if exists else "not_checked"),
         "evidence_reads":event_reads+log_reads,
         "observed_state_events":state_count,
         "clock_alignment_verified":False},
        {"id":"generic_warning_root_cause","status":"unverified",
         "evidence_reads":log_reads+event_reads,
         "reason":"No independent runtime/source method-to-CPU attribution."},
    ]


def evidence_safe_incident_explanation(packet: Mapping[str,Any]) -> str:
    """Publish only source-attested facts, never a fluent unverified ranking."""
    warning=packet["warning_period"]
    names=packet.get("device_caller_names",{})
    callers=[
        ((str(names.get(aid))+" (app "+str(aid)+")")
         if names.get(aid) else "app "+str(aid))
        for aid in packet.get("device_caller_app_ids",[])
    ]
    pieces=[
        "**What caused the warning? Not yet established.**",
        ("The hub reported a generic excessive-load warning for the device "
         + ("at the latest sampled occurrence "
            if packet.get("warning_occurrence_selected")
            else "in the sampled group from ")
         + str(warning["oldest"])
         + ("" if packet.get("warning_occurrence_selected")
            else " to "+str(warning["newest"]))
         + ". The sampled message does not identify a driver method, "
         "app, or measured CPU contribution."),
    ]
    grouped=packet.get("warning_group_sample",{})
    if packet.get("warning_occurrence_selected") and grouped:
        count=grouped.get("sampled_rows")
        if type(count) is int and count == 1:
            pieces.append(
                "Only one warning row appears in the returned sample at "
                +str(grouped.get("oldest_returned"))+
                ". A single sampled warning cannot establish whether "
                "the load continued before or afterwards.")
        else:
            pieces.append(
                "This is one observed warning timestamp in a sampled group of "
                +str(count or "unknown")+
                " warning rows spanning "+str(grouped.get("oldest_returned"))+
                " to "+str(grouped.get("newest_returned"))+
                ". Gaps between sampled warnings are not evidence of "
                "continuous load.")
    if callers:
        pieces.append("Verified command issuers in the sampled device "
                      "history: "+", ".join(callers)+
                      ". Command issuance is not evidence that any of "
                      "these apps caused the warning.")
    else:
        pieces.append("No calling app is independently identified in this "
                      "bounded device-event sample. This does not establish "
                      "that the device has no callers, and does not revoke "
                      "caller identities attested in separate investigations.")
    if packet.get("scoped_event_history_available"):
        pieces.append(
            "The bounded device-event sample contains "+
            str(packet.get("app_commands_within_warning_interval",0))+
            (" app-issued commands at the selected warning timestamp and "
             if packet.get("warning_occurrence_selected") else
             " app-issued commands within the printed warning window and ")+
            str(packet.get("app_commands_within_five_minutes",0))+
            " within five minutes of that timestamp by source wall-clock time. "
            "The event sample may omit records and the log/event "
            "clock alignment is not independently verified.")
    else:
        pieces.append("No device-scoped event history was recovered, so "
                      "commands around the incident have not been checked.")
    # Source-grounded incident relevance: a fresh nearby command sequence
    # takes precedence over an unrelated high-count burst many hours away.
    # App-issued commands, device states and WARN logs remain distinct.
    temporal=packet.get("warning_command_temporal_leads")
    latest_cluster=None
    if isinstance(temporal,Mapping):
        clusters=temporal.get("warning_clusters")
        if isinstance(clusters,list) and clusters:
            latest_cluster=clusters[-1]
    near_commands=(
        latest_cluster.get("commands_in_window_with_edges",0)
        if isinstance(latest_cluster,Mapping) else 0)
    if isinstance(latest_cluster,Mapping) and near_commands:
        issue_rows=latest_cluster.get("warning_rows")
        pieces.append(
            "**Most relevant source-timed activity lead:** "+
            str(issue_rows)+" sampled warning rows occurred from "+
            str(latest_cluster.get("first_warning_timestamp"))+" to "+
            str(latest_cluster.get("last_warning_timestamp"))+
            " ("+str(latest_cluster.get("span_ms"))+
            " ms of reported timestamps). These are a short cluster of "
            "warning records, not independently proven separate CPU overload "
            "episodes. In that window (including "+
            str(latest_cluster.get("command_edge_tolerance_ms",2000))+
            " ms at each edge), "+str(near_commands)+
            " app-issued commands were observed in the returned device history.")
        for actor in latest_cluster.get("app_issuers",[])[:4]:
            if not isinstance(actor,Mapping):
                continue
            app_id=str(actor.get("app_id") or "")
            name=str(names.get(app_id) or "")
            label=(name+" (app "+app_id+")") if name else "App "+app_id
            command_types=actor.get("command_counts")
            command_types=command_types if isinstance(command_types,Mapping) else {}
            pieces.append(
                label+" issued "+str(actor.get("observed_commands"))+
                " commands: "+", ".join(
                    str(k)+" ×"+str(v)
                    for k,v in list(command_types.items())[:6])+".")
        close=latest_cluster.get("sample_commands",[])
        if isinstance(close,list):
            closest=sorted((cmd for cmd in close if isinstance(cmd,Mapping)),
                           key=lambda cmd:cmd.get("nearest_warning_gap_ms",float("inf")))
            for cmd in closest[:3]:
                pieces.append(
                    "Source-timed command observation: app "+
                    str(cmd.get("app_id"))+" "+str(cmd.get("command"))+
                    " at "+str(cmd.get("timestamp"))+
                    " was recorded "+str(cmd.get("nearest_warning_gap_ms"))+
                    " ms "+str(cmd.get("command_relative_to_warning"))+
                    " its nearest sampled warning.")
        pieces.append(
            "The near-warning app commands are a stronger *investigation lead* "
            "than distant historical activity, but timestamp order and "
            "coincidence alone do not verify which callback, if any, "
            "caused the load warning.")
    bursts=packet.get("observed_command_bursts",[])
    if bursts and not near_commands:
        b=bursts[0]
        gap=b.get("gap_from_warning_end_seconds")
        timing=((" (approximately "+str(round(gap/60,1))+
                 " minutes from the warning by source wall clock)")
                if isinstance(gap,(int,float)) else "")
        pieces.append(
            "One separate activity lead: "+
            str(b["count_in_burst"])+" "+str(b["command"])+
            " events from app "+str(b["appId"])+" between "+
            str(b["first"])+" and "+str(b["last"])+timing+
            ". A burst observed at another time is not a proven "
            "contributor to this incident.")
    states=packet.get("device_events_within_two_seconds",[])
    if states:
        pieces.append("The device's source-reported state events near the "
                      "warning include "+
                      ", ".join(str(x["name"])+"="+str(x["value"])
                                for x in states[:5])+
                      ". These are time-associated observations, not proof "
                      "of the initiating callback or network activity.")
    correlation=packet.get("warning_state_correlations")
    if isinstance(correlation, Mapping):
        matched=correlation.get("warnings_with_nearby_state_in_returned_sample", 0)
        analyzed=correlation.get("analyzed_warning_occurrences", 0)
        occurrences=correlation.get("instances", [])
        if isinstance(occurrences, list) and analyzed:
            pieces.append(
                "**Across individually observed warning occurrences:** "
                +str(matched)+" of "+str(analyzed)+
                " sampled warnings had a device-state event within "
                +str(correlation.get("window_tolerance_ms", 2000))+
                " ms by the printed source clocks. Repeated READs of the "
                "same warning are counted once. A same-time device state is "
                "not an app command, and does not prove a driver callback "
                "caused the load.")
            latest=occurrences[0] if occurrences else {}
            states=latest.get("coincident_states",[]) if isinstance(latest,dict) else []
            if states:
                source_state=states[0]
                pieces.append(
                    "At the latest warning, "+str(source_state.get("name"))+
                    "="+str(source_state.get("value"))+
                    " was reported "+str(source_state.get("reported_absolute_gap_ms"))+
                    " ms from the warning timestamp; source-clock "
                    "alignment and the initiating mechanism remain unverified.")
    pieces.append(
        "**Remaining evidence gap:** The internal driver/app execution path, "
        "the source of the status changes, and measured hub CPU impact "
        "at the warning time were not independently established. "
        "A complete driver source or incident-time runtime profile would "
        "help discriminate possible mechanisms. No changes were made.")
    return "\n\n".join(pieces)


def source_bound_incident_required(packet: Mapping[str,Any]|None) -> bool:
    """Use a claim ledger—not model wording—to set publication authority."""
    return bool(
        packet and packet.get("incident_type")=="generic_device_warning"
        and packet.get("causal_conclusion_strength")=="unattributed"
        and not packet.get("separate_diagnostic_method_warnings_present")
        and packet.get("independent_executed_method_or_cpu_attribution") is False
    )


__all__=["incident_attribution_packet","unsupported_causal_ranking",
         "evidence_safe_incident_explanation","incident_claim_ledger",
         "source_bound_incident_required"]
