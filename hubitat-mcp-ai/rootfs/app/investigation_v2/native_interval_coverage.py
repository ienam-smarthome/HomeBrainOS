"""Semantic completeness evidence for time-bounded source-reported intervals.

A full actuator cycle needs TWO attested state transitions: a start and
a later corresponding end. A schedule command, current battery, or today's
device mode must never substitute for those events.

This does NOT select MCP tools or route questions. It assesses the user's
explicit interval requirement against source receipts, and gives the AI a
bounded evidence coverage description for choosing its own further READs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping, Sequence

def requires_complete_interval(question: str) -> bool:
    if not isinstance(question,str):
        return False
    q=" ".join(question.casefold().split())
    # These words establish an explicit evidentiary obligation, not a tool
    # router or a device category. Without such an obligation this checker
    # must never change a general status/health/audit response.
    return bool(re.search(r"\b(?:complete|full)\b.{0,50}\bcycle\b|"
                          r"\bcycle\b.{0,50}\b(?:complete|full)\b",q))

_TRANSITIONS={
    "thermostatOperatingState":({"heating"},{"idle"}),
    "switch":({"on"},{"off"}),
    "motion":({"active"},{"inactive"}),
    "contact":({"open"},{"closed"}),
    "presence":({"present"},{"not present","absent"}),
}

def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value,str):
        return None
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError,ValueError,OverflowError):
        return None

def complete_interval_coverage(
    question: str,
    witnesses: Sequence[Mapping[str,Any]],
    focus_ids: Sequence[str],
) -> dict[str,Any] | None:
    if not requires_complete_interval(question) or len(set(focus_ids))!=1:
        return None
    focus=str(focus_ids[0])
    events=[]
    reads=[]
    sample_windows=[]
    for w in witnesses[:20]:
        if w.get("operation")!="hub_list_device_events":
            continue
        if str(w.get("read_filters",{}).get("deviceId") or "")!=focus:
            continue
        source=w.get("source_data")
        if not isinstance(source,Mapping):
            continue
        read=w.get("read")
        if type(read) is not int:
            continue
        reads.append(read)
        sample_windows.append({
            "read":read,
            "oldest_returned":source.get("oldest_returned"),
            "newest_returned":source.get("newest_returned"),
            "returned_rows":source.get("returned_event_rows"),
            "source_complete":False,
        })
        for e in source.get("events",[])[:200]:
            if not isinstance(e,Mapping):
                continue
            attr=str(e.get("name") or "")
            if attr not in _TRANSITIONS:
                continue
            producer=e.get("producedBy")
            if isinstance(producer,Mapping):
                ident=producer.get("deviceId")
                if ident is not None and str(ident)!=focus:
                    continue
                if producer.get("appId") is not None:
                    # App-side commands/setpoints are *not* reported
                    # physical device-state events.
                    continue
            stamp=_timestamp(e.get("date"))
            if stamp is None:
                continue
            value=str(e.get("value") or "").casefold()
            starts,ends=_TRANSITIONS[attr]
            if value not in starts and value not in ends:
                continue
            events.append((stamp,attr,value,str(e.get("date")),read))
    events.sort(key=lambda e:(e[0],e[4]))
    pending={}
    found=[]
    for stamp,attr,value,raw,read in events:
        starts,ends=_TRANSITIONS[attr]
        if value in starts:
            pending[attr]=(stamp,raw,read,value)
        elif value in ends and attr in pending:
            prev,prev_raw,prev_read,prev_value=pending.pop(attr)
            if stamp<=prev:
                continue
            found.append({
                "attribute":attr,
                "start":{"read":prev_read,"name":attr,
                         "date":prev_raw,"value":prev_value},
                "end":{"read":read,"name":attr,
                       "date":raw,"value":value},
                "duration_seconds":int((stamp-prev).total_seconds()),
                "source_state_observations_only":True,
            })
    found.sort(key=lambda row:row["end"]["date"],reverse=True)
    complete=bool(found)
    return {
        "status":"complete_source_reported_interval_observed"
                 if complete else "complete_interval_not_established",
        "explicit_interval_requirement":True,
        "target_device_id":focus,
        "complete_interval_count":len(found),
        "most_recent_complete_interval":found[0] if complete else None,
        "source_reads":reads,
        "source_windows":sample_windows[-4:],
        "limitations":"Bounded event history; source-reported device states "
                      "are not independent physical confirmation. "
                      "This does not establish upstream controller inputs "
                      "or the physical reason for an action.",
        "next_evidence":(
            "A complete state interval is observed. Investigate the "
            "controlling automation's decision and independently verified "
            "input sensor events before concluding why it happened."
            if complete else
            "No paired start/end state observations were returned. "
            "Seek a wider or distinct target-device history and an "
            "independent controller/input source before concluding; "
            "a scheduled OFF command alone is not a full operating cycle."),
    }


def incomplete_interval_answer(coverage: Mapping[str,Any] | None) -> str | None:
    if coverage is None or coverage.get("status")!="complete_interval_not_established":
        return None
    windows=coverage.get("source_windows") or []
    row=windows[-1] if windows else {}
    oldest=row.get("oldest_returned")
    newest=row.get("newest_returned")
    shown=(f" The returned device history spans {oldest} to {newest}, "
           "which is a bounded sample, not the complete history."
           if oldest and newest else
           " The available target history was not sufficient to reconstruct it.")
    return (
        "**Unable to verify a complete cycle.** The source events retrieved "
        "do not contain a matching operating-start and later operating-stop "
        "state for this device. A scheduled OFF command or present-day "
        "device reading alone cannot establish a complete cycle."
        +shown+" Consequently I cannot reliably identify the most recent "
        "complete cycle, which input requested it, why demand ended, or "
        "whether the full sequence behaved correctly. The next useful "
        "evidence is a wider independently scoped device-event history "
        "and the controlling app's decision/input history."
    )


def interval_reasoning_evidence(
    coverage: Mapping[str,Any] | None,
    witnesses: Sequence[Mapping[str,Any]],
) -> dict[str,Any] | None:
    """Make a proven interval eligible for the existing cited AI reasoning.

    A relative-time interval request has no user calendar date, so the
    dated-incident extractor cannot by itself provide an evidence packet.
    This packet is based ONLY on an independently observed start and end,
    plus events from the same source device near that interval.
    """
    if not isinstance(coverage,Mapping):
        return None
    if coverage.get("status")!="complete_source_reported_interval_observed":
        return None
    interval=coverage.get("most_recent_complete_interval")
    if not isinstance(interval,Mapping):
        return None
    begin=_timestamp(interval["start"]["date"])
    end=_timestamp(interval["end"]["date"])
    if begin is None or end is None or end<=begin:
        return None
    from datetime import timedelta
    scope=str(coverage.get("target_device_id") or "")
    examples=[]
    seen=set()
    for w in witnesses[:20]:
        if w.get("operation")!="hub_list_device_events":
            continue
        if str(w.get("read_filters",{}).get("deviceId") or "")!=scope:
            continue
        read=w.get("read")
        if type(read) is not int:
            continue
        data=w.get("source_data")
        if not isinstance(data,Mapping):
            continue
        for event in data.get("events",[])[:200]:
            if not isinstance(event,Mapping):
                continue
            stamp=_timestamp(event.get("date"))
            if (stamp is None or
                    not begin-timedelta(minutes=10)<=stamp<=end+timedelta(minutes=5)):
                continue
            name=event.get("name")
            if not isinstance(name,str):
                continue
            if (name not in _TRANSITIONS and
                    name not in ("heatingSetpoint","thermostatSetpoint",
                                 "thermostatMode","level","position")
                    and not name.startswith("command-")):
                continue
            producer=event.get("producedBy")
            kind="unattributed"
            source_name=""
            if isinstance(producer,Mapping):
                if producer.get("appId") is not None:
                    if not str(producer["appId"]).isdecimal():
                        continue
                    kind="issuing_app"
                elif producer.get("deviceId") is not None:
                    if str(producer["deviceId"])!=scope:
                        continue
                    kind="target_device"
                source_name=str(producer.get("name") or "")[:80]
            key=(read,name,str(event["date"]))
            if key in seen:
                continue
            seen.add(key)
            example={
                "read":read,"name":name,"date":str(event["date"]),
                "source_name":source_name,"source_kind":kind,
            }
            if event.get("value") is not None:
                example["value"]=str(event["value"])[:90]
            examples.append(example)
    examples.sort(key=lambda row:row["date"])
    # Anchor the start and end before preserving potentially dense
    # commands or telemetry, and cap without dropping the crucial pair.
    anchors=[]
    for endpoint in ("start","end"):
        item=interval[endpoint]
        anchor=next((row for row in examples
                     if row["read"]==item["read"]
                     and row["name"]==item["name"]
                     and row["date"]==item["date"]),None)
        if anchor is None:
            return None
        anchors.append(anchor)
    chosen=anchors + [
        row for row in examples
        if row not in anchors
    ][:16]
    chosen.sort(key=lambda row:row["date"])
    return {
        "target_device_id":scope,
        "incident_period":{
            "start_utc_interpreted":(begin-timedelta(hours=2)).isoformat(),
            "end_utc_interpreted":(end+timedelta(hours=2)).isoformat(),
            "source":"verified_device_state_interval",
            "hub_timezone_verified":False,
        },
        "scoped_event_reads":list(coverage.get("source_reads") or []),
        "incident_answer_evidence_present":True,
        "material_event_count":len(chosen),
        "material_event_examples":chosen,
        "controller_decision_log_examples":[],
        "controller_decision_log_count":0,
        "limits":"A complete source-reported device operating interval is "
                 "observed, but the app's cause and input sensors are "
                 "not automatically established.",
    }


__all__=["requires_complete_interval","complete_interval_coverage",
         "incomplete_interval_answer","interval_reasoning_evidence"]
