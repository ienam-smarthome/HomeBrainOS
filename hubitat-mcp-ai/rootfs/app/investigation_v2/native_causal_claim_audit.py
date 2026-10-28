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
                incidents.append((lo,hi,group))
    if not incidents:
        return None
    # Do not merge slow-method WARN with generic WARN; the narrowest
    # newest generic interval is the incident being audited here.
    generic=[v for v in incidents if not re.search(
        r"\bmethod\s+[A-Za-z_]\w*\b",str(v[2].get("message","")),re.I)]
    if not generic:
        return None
    start,end,warn=sorted(generic,key=lambda v:(
        (v[1]-v[0]).total_seconds(),-v[1].timestamp()))[0]
    app_commands=[]
    device_events=[]
    app_summaries={}
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
    if not app_summaries:
        return None
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
        "warning_period":{
            "oldest":str(warn.get("oldest_returned")),
            "newest":str(warn.get("newest_returned")),
            "printed_timezone_alignment_verified":False},
        "device_caller_app_ids":sorted(app_summaries),
        "caller_identities_verified":True,
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


def evidence_safe_incident_explanation(packet: Mapping[str,Any]) -> str:
    warning=packet["warning_period"]
    caller=", ".join(packet["device_caller_app_ids"])
    pieces=[
        "**Source-grounded causal assessment**",
        "The returned generic warning at "+str(warning["oldest"])+
        " to "+str(warning["newest"])+
        " does not identify a specific driver method or app as its cause.",
        "Device-command issuers verified in bounded event history: app IDs "+
        caller+". These identities do not attribute the warning.",
        "Observed app commands within the warning interval: "+
        str(packet["app_commands_within_warning_interval"])+
        "; within a five-minute source-clock window: "+
        str(packet["app_commands_within_five_minutes"])+".",
    ]
    burst=packet.get("observed_command_bursts",[])
    if burst:
        b=burst[0]
        pieces.append("A separate command burst is observable: app "+
            str(b["appId"])+" issued "+
            str(b["count_in_burst"])+" "+
            str(b["command"])+" events between "+
            str(b["first"])+" and "+str(b["last"])+
            ". This pattern is not established as the warning's cause.")
    states=packet.get("device_events_within_two_seconds",[])
    if states:
        pieces.append("Source-clock-nearby device-reported events: "+
            ", ".join(str(x["name"])+"="+str(x["value"])
                      for x in states[:5])+
            ". Their appearance does not establish a blocking callback.")
    pieces.append("**Cause remains unverified.** No source-backed driver "
                  "execution path or independently measured attribution "
                  "supports ranking an app or network operation as the "
                  "most likely cause. Returned event rows can be capped; "
                  "source clock alignment is unverified.")
    return "\n\n".join(pieces)


__all__=["incident_attribution_packet","unsupported_causal_ranking",
         "evidence_safe_incident_explanation"]
