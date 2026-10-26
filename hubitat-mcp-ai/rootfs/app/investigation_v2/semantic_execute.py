"""Host-side execution of an AI-proposed, *typed* current inventory question.

The model chooses WHAT evidence is relevant. The host alone performs typed
filtering, counting, aggregation and ranking over a freshly verified Hubitat
snapshot. Missing measurements are never treated as zero or false.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any, Mapping, Sequence

from device_state_summary import (
    capability_names, device_attributes, is_light_device, room_name,
)
from .semantic_plan import SemanticPlan


def _display(value: Any, max_chars: int = 100) -> str:
    raw=str(value or "").strip()[:max_chars]
    cleaned="".join(c if c.isprintable() and c not in "<>|*_[]{}`\\"
                    else " " for c in raw)
    return " ".join(cleaned.split()) or "Unassigned"


def _value(device: Mapping[str, Any], attribute: str) -> Any:
    fields=device_attributes(dict(device))
    chosen=next((v for k,v in fields.items()
                 if isinstance(k,str) and k.casefold()==attribute.casefold()),None)
    if chosen is not None:
        return chosen
    return next((v for k,v in device.items()
                 if isinstance(k,str) and k.casefold()==attribute.casefold()),None)


def _number(value: Any) -> float | None:
    if type(value) in (int,float):
        return float(value) if math.isfinite(value) else None
    if isinstance(value,str):
        match=re.match(r"^\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(?:[A-Za-z%°]*)\s*$",value)
        if match:
            numeric=float(match.group(1))
            return numeric if math.isfinite(numeric) else None
    return None


def _equal(a: Any,b: Any) -> bool:
    left=_number(a)
    right=_number(b)
    if left is not None and right is not None:
        return abs(left-right)<1e-9
    return str(a).strip().casefold()==str(b).strip().casefold()


def _matches(value: Any, op: str, bound: Any) -> bool:
    if op=="none":
        return True
    if value is None:
        return False
    if op=="eq":
        return _equal(value,bound)
    if op=="ne":
        return not _equal(value,bound)
    v,limit=_number(value),_number(bound)
    if v is None or limit is None:
        return False
    return {
        "gt":v>limit,"gte":v>=limit,
        "lt":v<limit,"lte":v<=limit,
    }.get(op,False)


def _devices_for_plan(devices: Sequence[Mapping[str,Any]],plan: SemanticPlan):
    inventory={}
    for item in devices:
        if not isinstance(item,dict):
            continue
        ident=item.get("id",item.get("deviceId"))
        if type(ident) not in (str,int) or not str(ident).isdecimal():
            continue
        inventory.setdefault(str(ident),item)
    values=list(inventory.items())
    if plan.scope=="lights":
        values=[(i,d) for i,d in values if is_light_device(d)]
    elif plan.scope=="switches":
        values=[(i,d) for i,d in values if _value(d,"switch") is not None]
    elif plan.scope=="sensors":
        values=[(i,d) for i,d in values if
                any("sensor" in cap for cap in capability_names(d))]
    elif plan.scope=="named":
        phrase=(plan.device_name or "").casefold()
        values=[(i,d) for i,d in values
                if any(isinstance(d.get(key),str)
                       and d.get(key).strip().casefold()==phrase
                       for key in ("name","label"))]
        if len(values)!=1:
            raise ValueError("Named device is absent or ambiguous in current inventory")
    if plan.room:
        values=[(i,d) for i,d in values
                if str(room_name(d) or "").casefold()==plan.room.casefold()]
    return values


def execute_inventory_plan(
    plan: SemanticPlan,
    devices: Sequence[Mapping[str,Any]],
    provenance: Mapping[str,Any],
    *,
    checked_at: datetime | None = None,
) -> dict[str,Any]:
    if plan.mode!="inventory":
        raise ValueError("not a current inventory plan")
    if not isinstance(devices,(list,tuple)) or not devices:
        raise ValueError("no current Hubitat inventory")
    source=list(_devices_for_plan(devices,plan))
    present=[]
    missing=0
    for ident,device in source:
        value=_value(device,plan.attribute) if plan.attribute else None
        if plan.attribute and value is None:
            missing+=1
            continue
        if not _matches(value,plan.operator,plan.value):
            continue
        present.append((ident,device,value))
    if plan.aggregation in ("top","bottom","sum","average"):
        numeric=[]
        for ident,device,value in present:
            amount=_number(value)
            if amount is None:
                missing+=1
            else:
                numeric.append((ident,device,amount))
        present=numeric
        if plan.aggregation in ("top","bottom"):
            present.sort(key=lambda row:(row[2],row[0]),
                         reverse=plan.aggregation=="top")
    else:
        present.sort(key=lambda row:(
            str(room_name(row[1]) or "").casefold(),
            str(row[1].get("label") or row[1].get("name") or "").casefold(),
            row[0],
        ))
    complete=isinstance(provenance,dict) and provenance.get("complete") is True
    checked=checked_at or datetime.now(timezone.utc)
    if checked.tzinfo is None or checked.utcoffset() is None:
        raise ValueError("current time must be timezone aware")
    total=len(present)
    subset=present[:plan.limit]
    attr=plan.attribute or "device"
    aggregate_value=None
    if plan.aggregation in ("sum","average"):
        aggregate_value=(sum(float(row[2]) for row in present)
                         if plan.aggregation=="sum" else
                         (sum(float(row[2]) for row in present)/len(present)
                          if present else None))
    title={
        "list":f"{total} matching device(s)",
        "count":f"{total} matching device(s)",
        "top":f"Top {min(total,plan.limit)} device(s) by {attr}",
        "bottom":f"Lowest {min(total,plan.limit)} device(s) by {attr}",
        "sum":f"Total {attr} from {total} measured device(s)",
        "average":f"Average {attr} across {total} measured device(s)",
    }[plan.aggregation]
    if plan.aggregation in ("sum","average"):
        if aggregate_value is None:
            title+=": no numeric values available"
        else:
            units=" W" if attr=="power" else " %" if attr=="battery" else ""
            title+=f": {aggregate_value:,.2f}{units}"
    lines=[title+" (Hubitat current reported states)."]
    if plan.scope!="all":
        lines.append("Group: "+_display(plan.device_name or plan.scope)+".")
    if plan.room:
        lines.append("Room: "+_display(plan.room)+".")
    if plan.attribute and plan.operator!="none":
        lines.append("Filter: "+_display(attr)+" "+plan.operator+" "+_display(plan.value)+".")
    if plan.aggregation!="count" and subset:
        lines.append("")
        for _,device,value in subset:
            label=_display(device.get("label") or device.get("name") or "Device")
            room=_display(room_name(device) or "Unassigned")
            reading=("" if not plan.attribute else
                     " — "+_display(value)+" "+("W" if attr=="power" and _number(value) is not None else ""))
            lines.append(f"• {room} — {label}{reading}")
    if total>plan.limit and plan.aggregation!="count":
        lines.append(f"... and {total-plan.limit} more matching device(s).")
    if missing:
        lines.append(f"{missing} scoped device(s) lacked a usable {attr} reading; "
                     "those measurements were excluded, not assumed zero.")
    if not complete:
        lines.append("Inventory coverage is not verified complete. "
                     "Counts and rankings may omit devices.")
    lines.append("Read-only Hubitat snapshot at "+
                 checked.astimezone(timezone.utc).isoformat(timespec="seconds")+
                 ". Reported state is not independent physical confirmation.")
    answer="\n".join(lines)
    return {
        "answer_mode":"semantic_inventory",
        "semantic_plan":plan.to_dict(),
        "answer":{"text":answer,"displayed_record_ids":[],
                  "omitted_material_record_ids":[],
                  "validation_issues":[] if complete and not missing else
                      ["inventory_coverage_or_readings_incomplete"],
                  "root_cause_verified":False,"human_review_required":False},
        "report":{"text":answer,"technical_answer_retained":False},
        "inventory_query":{
            "matched_count":total,"scoped_count":len(source),"missing_readings":missing,
            "inventory_complete":complete,"inventory_pages":(
                provenance.get("pages") if isinstance(provenance,dict) else None),
            "checked_at_utc":checked.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "aggregation":plan.aggregation,"attribute":plan.attribute,
            "aggregate_value":aggregate_value,
            "shown_count":len(subset) if plan.aggregation!="count" else 0,
        },
        "resolved_devices":[],"resolution_method":"semantic_verified_inventory",
        "test_mode":"explicit_read_only",
    }


__all__=["execute_inventory_plan"]
