"""Attested target relevance and source-backed fallback for native V2.

Question wording never selects a route. Focus IDs only come from verified
identity or typed source evidence; stale snapshots are not physical proof.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any, Mapping, Sequence
from .native_source_adapters import safe_string
from .native_provenance import correlated_command_warnings

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
                raw_total=data.get("count")
                extra=(f" ({len(selected)} projected from {raw_total} returned source rows)"
                       if isinstance(raw_total,int) and raw_total>len(selected)
                       else "")
                add(f"{ref}: {len(selected)} target events displayed{extra}; newest {label(selected[0])}; oldest {label(selected[-1])}. "
                    "This is the PROJECTED event window, not a guarantee "
                    "that older source commands are represented. Driver "
                    "status events are NOT device heartbeats.")
            if scoped:
                for issuer in data.get("issuer_apps",[])[:8]:
                    if not isinstance(issuer,dict):
                        continue
                    commands=issuer.get("commands")
                    add(f"{ref}: issuing app {safe_string(issuer.get('name'),75)} "
                        f"(app ID {safe_string(issuer.get('appId'),18)}) issued "
                        f"{safe_string(issuer.get('count'),12)} commands: "
                        f"{safe_string(commands,155)}; between "
                        f"{safe_string(issuer.get('oldest'),45)} and "
                        f"{safe_string(issuer.get('newest'),45)}. "
                        "This is command provenance, not proof of cause.")
        elif op=="hub_get_logs":
            # A targeted WARN subset already contained in an earlier sampled
            # group adds no new source facts. Keep its complete receipt in
            # native diagnostics but do not crowd the user's conclusion.
            if w.get("redundant_evidence") is True:
                continue
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
        elif op in ("hub_get_metrics", "hub_get_performance_stats"):
            current=data.get("current")
            trends=data.get("trends")
            if isinstance(current,dict) and current:
                add(f"{ref}: hub-reported current performance measurements "
                    f"{safe_string(current,300)}. These readings do not "
                    "independently attribute performance impact to a device.")
            if isinstance(trends,(dict,list)) and trends:
                add(f"{ref}: bounded hub performance trend samples "
                    f"{safe_string(trends,240)}; source history completeness "
                    "and causal attribution unverified.",False)
        elif op=="hub_get_memory_history":
            rows=data.get("entries",[])
            count=data.get("numeric_observation_rows",0)
            if isinstance(rows,list):
                if isinstance(count,int) and count>0:
                    numeric=[item for item in rows if isinstance(item,dict)
                             and any(type(v) in (int,float,bool)
                                     for k,v in item.items() if k!="timestamp")]
                    add(f"{ref}: {count} rows contain source-reported CPU/memory "
                        f"measurements. Bounded sample: {safe_string(numeric[:2],230)}. "
                        "These metrics do not independently attribute load "
                        "to a device.",False)
                else:
                    add(f"{ref}: memory history returned {len(rows)} projected "
                        "rows with no numeric CPU/memory measurements; "
                        "timestamps alone cannot corroborate a hub-load "
                        "warning or prove normal performance.",False)
        elif op=="hub_list_device_dependents":
            if str(w.get("read_filters",{}).get("deviceId")) in focus:
                apps=data.get("apps_using")
                if isinstance(apps,list):
                    app_names=", ".join(
                        f"{safe_string(item.get('name'),55)} (app {safe_string(item.get('appId'),18)})"
                        for item in apps[:8] if isinstance(item,dict))
                    add(f"{ref}: target device is referenced by "
                        f"{safe_string(data.get('count'),10)} apps: {app_names}. "
                        "These are dependency references, not confirmed command issuers.")
        elif op=="hub_get_app_config":
            app_id=data.get("requested_app_id") or data.get("appId") or data.get("id")
            name=data.get("label") or data.get("name") or data.get("appName")
            fields=data.get("app_settings_field_names") or data.get("settings_field_names") or []
            if data.get("source_app_id_matches_request") is False:
                add(f"{ref}: app config ID does NOT match approved appId "
                    f"{safe_string(app_id,18)}. Treat this as an identity "
                    "inconsistency, not evidence about the requested app.")
            else:
                source_section=bool(data.get("app_section_present"))
                add(f"{ref}: verified app config READ for app ID "
                    f"{safe_string(app_id,18)}; "
                    f"source label={safe_string(name or 'not provided',72)}, "
                    f"page={safe_string(data.get('page_name'),36)}, "
                    f"nested app section present={source_section}; "
                    f"enabled={safe_string(data.get('enabled'),15)}, "
                    f"paused={safe_string(data.get('paused'),15)}, "
                    f"settings field names={safe_string(fields,170)}, "
                    f"child apps={safe_string(data.get('child_app_count'),12)}. "
                    "Only current metadata and non-sensitive field names "
                    "were read; settings values, code and historical app "
                    "execution remain unverified.")
        elif op=="hub_list_app_pages":
            pages=data.get("page_names",[])
            app_id=data.get("requested_app_id") or data.get("returned_app_id")
            add(f"{ref}: read-only app page metadata for app ID "
                f"{safe_string(app_id or 'unverified',18)}; "
                f"primary page={safe_string(data.get('primary_page'),55)}, "
                f"page names={safe_string(pages[:10],185)}, "
                f"reported pages={safe_string(data.get('reported_page_count'),12)}. "
                "Navigation metadata cannot establish current settings values, "
                "executed code or historical cause.",False)
        elif op=="hub_get_source":
            kind=safe_string(data.get("requested_source_type") or "unknown",18)
            identity=safe_string(data.get("requested_source_id") or
                                 data.get("returned_source_id") or "unverified",20)
            status=data.get("source_read_status")
            if data.get("source_read_usable_for_method_reasoning") is True:
                methods=data.get("declared_method_names",[])
                add(f"{ref}: complete, identity-checked {kind} source ID "
                    f"{identity} returned lexical method declarations "
                    f"{safe_string(methods[:18],240)}. This is code "
                    "structure only, NOT evidence of execution or cause.")
            else:
                add(f"{ref}: {kind} source read for ID {identity}: "
                    f"{safe_string(status,60)}; "
                    f"{safe_string(data.get('source_inspection_blocker'),235)} "
                    "A successful gateway response with no code cannot "
                    "support implementation or callback claims.")
        elif op=="hub_get_device_health":
            for field in ("staleDevices","unknownDevices"):
                rows=data.get(field)
                if isinstance(rows,list):
                    for row in rows:
                        if isinstance(row,dict) and str(row.get("id")) in focus:
                            add(f"{ref}: {field} includes {safe_string(row.get('name'),80)} (ID {row.get('id')}).")
    for match in correlated_command_warnings(list(witnesses), focus):
        add(f"Read #{match['event_read']} vs Read #{match['log_read']}: "
            f"app {safe_string(match['app'],65)} (ID {match['appId']}) "
            f"issued {match['command']} at {match['command_time']}; "
            f"device-method warning at {match['warning_time']} "
            f"({match['wall_clock_delta_ms']}ms wall-clock difference). "
            "Clock timezone alignment and causation are unverified.")
    return (primary+secondary)[:18]

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
    # Source subsets may repeat one app across distinct event reads. Retain
    # distinct, type-attested callers without adding a second app identity
    # or summing counts from overlapping samples.
    issuer_index={}
    for w in witnesses:
        if (w.get("operation")=="hub_list_device_events"
                and str(w.get("read_filters",{}).get("deviceId")) in focus_ids):
            evidence=w.get("source_data",{})
            if isinstance(evidence,dict):
                for issuer in evidence.get("issuer_apps",[]):
                    if not isinstance(issuer,dict):
                        continue
                    app_id=str(issuer.get("appId") or "")
                    if app_id.isdecimal():
                        issuer_index.setdefault(app_id,issuer)
    issuing_apps=list(issuer_index.values())
    if str(status.get("healthStatus","")).lower()=="offline":
        conclusion=("The device is reported offline with stale telemetry. "
                    "Its physical failure mechanism is not established; power, "
                    "network and device configuration still require discrimination.")
    elif any("ran for" in m for m in log_messages):
        conclusion=("The returned logs report prolonged driver-method "
                    "executions on this device. An online network state does "
                    "not refute a slow callback. The driver mechanism "
                    "remains unverified; its contribution to wider "
                    "hub instability is not independently verified.")
    elif any("excessive hub load" in m for m in log_messages):
        conclusion=("The returned logs contain generic excessive-load "
                    "warnings for this device, but this sampled log evidence "
                    "does not include an independently timed slow-driver "
                    "method. Its cause and measured contribution to hub-wide "
                    "performance remain unverified.")
    else:
        conclusion="These observations establish reported symptoms, not a verified root cause."
    if issuing_apps and any("excessive hub load" in m or "ran for" in m
                            for m in log_messages):
        source_apps=", ".join(
            f"{safe_string(x.get('name'),58)} (app {safe_string(x.get('appId'),16)})"
            for x in issuing_apps[:5])
        conclusion+=(" Automations observed issuing commands to this device: "
                     +source_apps+". These caller identities are verified "
                     "for the sampled device history, not proof that any "
                     "caller caused a particular load warning or callback.")
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
    if operation=="hub_list_device_events" and focus_ids:
        events=projected.get("events")
        events=events if isinstance(events,list) else []
        commands=[e for e in events if isinstance(e,dict)
                  and str(e.get("name","")).startswith("command-")]
        states=[e for e in events if isinstance(e,dict)
                and not str(e.get("name","")).startswith("command-")]
        return {"issuer_apps":projected.get("issuer_apps",[])[:10],
                "count":projected.get("count"),
                "displayed_event_rows":projected.get("returned_event_rows"),
                "event_rows_omitted_from_model":projected.get("event_rows_omitted_from_model"),
                "events":commands[:20]+states[:5],
                "source_complete":False}
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
