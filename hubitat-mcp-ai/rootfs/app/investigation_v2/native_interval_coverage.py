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

__all__=["requires_complete_interval","complete_interval_coverage",
         "incomplete_interval_answer"]
