"""Host-verified current device-group answers for opt-in Investigation V2.

This is a general read intent, not a requirement to name a specific device.
Device type and reported switch state reuse HomeBrain's established shared
Hubitat state helpers; paginated discovery is done by the existing MCP client.
No model guesses and no smart-home writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping, Sequence

from device_state_summary import device_attributes, is_light_device, room_name


def current_light_group_question(question: str) -> str | None:
    """Recognise an explicit current-state group question, not a write/causal one."""
    if not isinstance(question, str) or len(question)>1200:
        return None
    normal=" ".join(question.casefold().split())
    if not re.match(r"^(?:which|what|show|list|how many|are any|is any)\b",normal):
        return None
    if not re.search(r"\b(?:lights?|lamps?|bulbs?)\b",normal):
        return None
    if re.search(r"\b(?:yesterday|today|last night|ago|since|between|why|turn|toggle|set|dim|switch)\b",normal):
        return None
    states=set(re.findall(r"\b(on|off)\b",normal))
    return next(iter(states)) if len(states)==1 else None


def _cell(value: Any) -> str:
    """Render device labels as plain text, without Markdown or control chars."""
    raw=str(value or "").strip()[:100]
    clean=" ".join("".join(
        ch if ch.isprintable() and ch not in "|<>\\\\`*_[]{}" else " "
        for ch in raw
    ).split())
    return clean or "Unassigned"

def current_light_group_answer(
    question: str,
    devices: Sequence[Mapping[str, Any]],
    provenance: Mapping[str, Any],
    *,
    checked_at: datetime | None = None,
) -> dict[str, Any]:
    requested=current_light_group_question(question)
    if requested not in ("on","off"):
        raise ValueError("Not a supported current light group question")
    if not isinstance(devices,(list,tuple)) or not devices:
        raise ValueError("No live Hubitat device inventory returned")
    if not isinstance(provenance,dict):
        provenance={}
    ident=set()
    active=[]
    inactive=[]
    unknown=[]
    for device in devices:
        if not isinstance(device,dict):
            continue
        dev_id=device.get("id",device.get("deviceId"))
        if isinstance(dev_id,bool) or type(dev_id) not in (str,int):
            continue
        ident_s=str(dev_id)
        if not ident_s.isdecimal() or ident_s in ident:
            continue
        ident.add(ident_s)
        if not is_light_device(device):
            continue
        label=_cell(device.get("label") or device.get("name") or "Device "+ident_s)
        room=_cell(room_name(device))
        switch=device_attributes(device).get("switch",device.get("switch"))
        state=str(switch).casefold().strip() if isinstance(switch,str) else ""
        entry={"id":ident_s,"label":label,"room":room,"state":state}
        if state=="on":
            active.append(entry)
        elif state=="off":
            inactive.append(entry)
        else:
            unknown.append(entry)
    matched=active if requested=="on" else inactive
    matched.sort(key=lambda row:(row["room"].casefold(),row["label"].casefold(),int(row["id"])))
    counted=len(active)+len(inactive)+len(unknown)
    now=checked_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware observation time is required")
    read_time=now.astimezone(timezone.utc).isoformat(timespec="seconds")
    complete=provenance.get("complete") is True
    source=str(provenance.get("source") or "unknown")
    pages=provenance.get("pages")
    pages=pages if type(pages) is int and 0<=pages<=100 else None
    prefix="ON" if requested=="on" else "OFF"
    note="**Inventory complete:** verified paginated Hubitat source." if complete else (
        "**Inventory coverage not verified:** this may be a partial list of lights."
    )
    headline=f"Hubitat reports {len(matched)} light(s) {prefix} out of {counted} identified lights."
    lines=[
        headline,
        "Checked at "+read_time+" UTC.",
    ]
    if matched:
        lines.append("")
        lines.extend(
            f"• {item['room']} — {item['label']}"
            for item in matched
        )
    else:
        lines.append("No matching lights were reported in the returned inventory.")
    lines.append("")
    if not complete:
        lines.append("Coverage warning: the inventory may be incomplete; "
                     "this is not a guaranteed whole-home count.")
    if unknown:
        lines.append(f"{len(unknown)} identified light(s) have unknown switch state.")
    lines.append("These are Hubitat-reported switch states, not independent "
                 "confirmation of physical bulb state.")
    return {
        "answer_mode":"current_group_state",
        "answer":{"text":"\n".join(lines),"displayed_record_ids":[],
                  "omitted_material_record_ids":[],"validation_issues":
                  [] if complete and not unknown else ["live_group_state_coverage_unverified"],
                  "root_cause_verified":False,"human_review_required":False},
        "report":{"text":"\n".join(lines),"technical_answer_retained":False},
        "group_status":{
            "kind":"lights","requested_state":requested,"matched_count":len(matched),
            "identified_lights":counted,"on_count":len(active),
            "off_count":len(inactive),"unknown_count":len(unknown),
            "inventory_complete":complete,"inventory_source":source[:55],
            "inventory_pages":pages,"checked_at_utc":read_time,
            "matched":matched,
        },
        "resolved_devices":[],"resolution_method":"inventory_group",
        "test_mode":"explicit_read_only",
    }


__all__=["current_light_group_question","current_light_group_answer"]
