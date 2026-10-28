"""Attested target relevance and source-backed fallback for native V2.

Question wording never selects a route. Focus IDs only come from verified
identity or typed source evidence; stale snapshots are not physical proof.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any, Mapping, Sequence
from .native_source_adapters import safe_string

_CORE=("healthStatus","deviceHealth","networkStatus","mqttStatus",
       "lastSeen","lastMessage","lastContact","dataAgeSeconds",
       "lastActivity","lastError","telePeriod","status","switch","power")

def _attrs(data: Mapping[str,Any]) -> dict[str,Any]:
    entries=data.get("attributes")
    return {row["name"]:row.get("value") for row in entries
            if isinstance(row,dict) and isinstance(row.get("name"),str)} if isinstance(entries,list) else {}

def read_fingerprint(operation: str, projected: Mapping[str,Any]) -> str | None:
    """Only current device attributes: never dedup events, logs, or configs."""
    if operation!="hub_get_device" or not isinstance(projected.get("attributes"),list):
        return None
    identity=projected.get("id")
    attrs=_attrs(projected)
    if not isinstance(identity,(str,int)) or not attrs:
        return None
    value=json.dumps([str(identity),attrs],sort_keys=True,default=str)
    return hashlib.sha256(value.encode()).hexdigest()

def focused_highlights(witnesses: Sequence[Mapping[str,Any]],
                       focus_ids: Sequence[str], *, max_chars:int=4500)->list[str]:
    focus={str(v) for v in focus_ids if str(v).isdecimal()}
    if not focus:return []
    primary=[]
    secondary=[]
    seen=set()
    fingerprints=set()
    def add(line:str, important:bool=True)->None:
        if line not in seen and sum(map(len,primary+secondary))+len(line)<=max_chars:
            seen.add(line)
            (primary if important else secondary).append(line)
    for w in witnesses[:16]:
        data=w.get("source_data")
        if not isinstance(data,dict):continue
        op=w.get("operation")
        ref="Read #"+str(w.get("read"))
        if op=="hub_get_device" and str(data.get("id")) in focus:
            attrs=_attrs(data)
            if not attrs:
                # The configuration and sectioned-details operations are
                # independent evidence, not failed current-attribute reads.
                # Preserve bounded structural metadata to guide a distinct
                # driver/source investigation instead of hiding it.
                mode=data.get("device_mode")
                if mode:
                    pieces=[]
                    info=data.get("device_identity")
                    if isinstance(info,dict) and info:
                        pieces.append("driver identity="+safe_string(info,220))
                    source=data.get("driver_source_metadata")
                    if isinstance(source,dict) and source:
                        pieces.append("driver source availability="+safe_string(source,130))
                    names=data.get("preference_names")
                    if isinstance(names,list) and names:
                        pieces.append("preference field names="+safe_string(names[:8],180))
                    sections=data.get("section_read_status")
                    if isinstance(sections,dict) and sections:
                        pieces.append("section status="+safe_string(sections,170))
                    if pieces:
                        add(f"{ref}: device {data.get('id')} {mode} returned "
                            + "; ".join(pieces)
                            + " (metadata only; not driver-code execution proof).")
                continue
            fingerprint=read_fingerprint(op,data)
            if fingerprint in fingerprints:continue
            fingerprints.add(fingerprint)
            facts=[f"{k}={safe_string(attrs[k],95)}" for k in _CORE if k in attrs]
            add(f"{ref}: {safe_string(data.get('label') or data.get('name'),80)} (ID {data['id']}) reports "+ "; ".join(facts)+".")
        elif op=="hub_list_device_events":
            events=data.get("events")
            if not isinstance(events,list):continue
            scoped=str(w.get("read_filters",{}).get("deviceId")) in focus
            selected=[e for e in events[:80] if isinstance(e,dict)
                      and (scoped or
                           (isinstance(e.get("producedBy"),dict)
                            and str(e["producedBy"].get("deviceId")) in focus))]
            if selected:
                def label(e:dict)->str:
                    return (safe_string(e.get("name"),32)+"="+safe_string(e.get("value"),45)
                            +" at "+safe_string(e.get("date") or e.get("time"),53))
                add(f"{ref}: {len(selected)} target events returned; newest {label(selected[0])}; oldest {label(selected[-1])}. Driver status events are NOT device heartbeats.")
        elif op=="hub_get_logs":
            summary=data.get("log_summary")
            if not isinstance(summary,dict):continue
            matches=[g for g in summary.get("warning_error_groups",[])
                     if isinstance(g,dict) and str(g.get("source_id")) in focus]
            if matches:
                add(f"{ref}: {summary.get('returned_rows')} sampled log rows; {len(matches)} target WARN/ERROR groups; full history unverified.")
                for g in matches[:6]:
                    add(f"{ref}: {safe_string(g.get('level'),12)} from {safe_string(g.get('source_name'),60)} (ID {safe_string(g.get('source_id'),20)}): {safe_string(g.get('message'),260)} ({g.get('count')} sampled rows; {safe_string(g.get('oldest_returned'),45)} to {safe_string(g.get('newest_returned'),45)}).")
            else:
                filters=w.get("read_filters")
                filters=filters if isinstance(filters,dict) else {}
                window=(f"{safe_string(summary.get('oldest_returned') or 'unknown',48)} "
                        f"to {safe_string(summary.get('newest_returned') or 'unknown',48)}")
                scope=(f"mode={safe_string(filters.get('mode','past'),30)}; "
                       f"level={safe_string(filters.get('level','unfiltered'),25)}; "
                       f"returned={safe_string(summary.get('returned_rows'),15)}")
                add(f"{ref}: log sample has no target-specific warnings; "
                    f"sample {scope}, timestamps {window}; coverage incomplete. "
                    "This is NOT evidence the target's earlier warnings stopped.",False)
        elif op=="hub_get_device_health":
            for field in ("staleDevices","unknownDevices"):
                rows=data.get(field)
                if isinstance(rows,list):
                    for row in rows:
                        if isinstance(row,dict) and str(row.get("id")) in focus:
                            add(f"{ref}: {field} includes {safe_string(row.get('name'),80)} (ID {row.get('id')}).")
    return (primary+secondary)[:16]

def focused_fallback(witnesses:Sequence[Mapping[str,Any]],
                     failures:Sequence[Mapping[str,Any]],
                     focus_ids:Sequence[str])->str|None:
    facts=focused_highlights(witnesses,focus_ids)
    if not facts:return None
    status={}
    log_messages=[]
    for w in witnesses:
        d=w.get("source_data")
        if not isinstance(d,dict):continue
        if w.get("operation")=="hub_get_device" and str(d.get("id")) in focus_ids:
            status.update(_attrs(d))
        report=d.get("log_summary")
        if isinstance(report,dict):
            log_messages.extend(safe_string(g.get("message"),260).lower()
                for g in report.get("warning_error_groups",[]) if isinstance(g,dict)
                and str(g.get("source_id")) in focus_ids)
    if str(status.get("healthStatus","")).lower()=="offline":
        conclusion=("The device is reported offline with stale telemetry. "
                    "Its physical failure mechanism is not established; power, "
                    "network and device configuration still require discrimination.")
    elif any("excessive hub load" in m or "ran for" in m for m in log_messages):
        conclusion=("Repeated runtime/performance warnings are recorded for "
                    "this device. A reported online network state does not "
                    "refute slow driver execution. Its contribution to wider "
                    "hub instability is not independently verified.")
    else:
        conclusion="These observations establish reported symptoms, not a verified root cause."
    lines=["**What the target's sources establish**",
           *["- "+fact for fact in facts[:10]],"",
           "**Supported conclusion:** "+conclusion,"",
           "**Limits:** Returned events and logs are bounded; attributes can "
           "be stale. A broker connection is not a device heartbeat. "
           "lastSeen and dataAgeSeconds may use different clocks/update "
           "rules; neither alone establishes the physical failure time."]
    if failures:
        lines.append("**Unavailable reads:** "+", ".join(sorted({
            safe_string(f.get("code"),50) for f in failures})))
    return "\n".join(lines)

def focused_model_view(operation:str,projected:Mapping[str,Any],
                       focus_ids:Sequence[str])->dict[str,Any]:
    if operation!="hub_get_logs" or not focus_ids:return dict(projected)
    summary=projected.get("log_summary")
    if not isinstance(summary,dict):return dict(projected)
    groups=[g for g in summary.get("warning_error_groups",[])
            if isinstance(g,dict) and str(g.get("source_id")) in focus_ids]
    return {"log_summary":{
        "returned_rows":summary.get("returned_rows"),
        "level_counts_in_returned_rows":summary.get("level_counts_in_returned_rows"),
        "oldest_returned":summary.get("oldest_returned"),
        "newest_returned":summary.get("newest_returned"),
        "truncated_or_partial":summary.get("truncated_or_partial"),
        "warning_error_groups":groups[:8],
        "target_group_count":len(groups),
        "other_group_count":max(0,summary.get("warning_error_group_count",0)-len(groups)),
        "warning_error_audit_complete":False},"source_complete":False}

__all__=["read_fingerprint","focused_highlights","focused_fallback","focused_model_view"]
