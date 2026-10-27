"""Host-side execution of an AI-proposed, *typed* current inventory question.

The model chooses WHAT evidence is relevant. The host alone performs typed
filtering, counting, aggregation and ranking over a freshly verified Hubitat
snapshot. Missing measurements are never treated as zero or false.
"""
from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
import math
import re
from typing import Any, Mapping, Sequence

from device_state_summary import (
    capability_names, device_attributes, is_light_device, room_name,
)
from .semantic_plan import SemanticPlan
from .measurement_semantics import measurement_scope, ROLES


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


def _quantity(value: Any, attribute: str | None) -> float | None:
    """Canonical unit conversion: W for power, kWh for accumulated energy."""
    if attribute not in ("power", "energy"):
        return _number(value)
    if type(value) in (int,float):
        return _number(value)
    if not isinstance(value,str):
        return None
    match=re.fullmatch(r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z]+)?\s*",value)
    if match is None:
        return None
    amount=float(match.group(1))
    if not math.isfinite(amount):
        return None
    unit=(match.group(2) or ("W" if attribute=="power" else "kWh")).casefold()
    scales=({"w":1.0,"kw":1000.0,"mw":1000000.0}
            if attribute=="power" else
            {"kwh":1.0,"wh":0.001,"mwh":1000.0})
    return amount*scales[unit] if unit in scales else None


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
        requested=plan.device_names or ((plan.device_name or ""),)
        chosen=[]
        for name in requested:
            phrase=name.strip().casefold()
            matches=[(i,d) for i,d in values
                     if any(isinstance(d.get(key),str)
                            and d.get(key).strip().casefold()==phrase
                            for key in ("name","label"))]
            # Exact-name duplicates and missing names must fail closed,
            # not silently read other devices. Never construct IDs from AI.
            if len(matches)!=1:
                raise ValueError("Named device is absent or ambiguous in current inventory")
            chosen.extend(matches)
        if len({i for i,_ in chosen})!=len(chosen):
            raise ValueError("Multiple supplied names resolve to one device")
        values=chosen
    if plan.room:
        values=[(i,d) for i,d in values
                if str(room_name(d) or "").casefold()==plan.room.casefold()]
    return values


def ground_named_inventory_plan(
    plan: SemanticPlan, question: str, devices: Sequence[Mapping[str, Any]],
) -> SemanticPlan:
    """Bind a named *read* plan to unique source identities in the question.

    The model may fail to express multiple names or mistakenly join them into
    one. Independently recovered, non-overlapping friendly labels are the
    authority; the model cannot add a device absent from the question.
    No device read or Hubitat command occurs in this function.
    """
    if plan.mode != "inventory" or plan.scope != "named":
        return plan
    from .test_service import resolve_verified_device_subjects
    if plan.device_names:
        # Even a syntactically valid name list is untrusted until its exact
        # IDs are matched with the independently parsed user request.
        ids, resolved, _ = resolve_verified_device_subjects(question, list(devices))
        planned_ids = []
        for name in plan.device_names:
            selected, _labels, _method = resolve_verified_device_subjects(
                question, list(devices), device_name=name)
            planned_ids.extend(selected)
        if (len(set(planned_ids)) != len(planned_ids)
                or set(planned_ids) != set(ids)):
            raise ValueError("Model-selected devices differ from verified question targets")
        return replace(plan, device_names=tuple(item["label"] for item in resolved),
                       device_name=None, room=None, limit=max(plan.limit,len(ids)))
    try:
        ids, resolved, _ = resolve_verified_device_subjects(question, list(devices))
    except ValueError:
        return plan  # Preserve existing unique single-name validation below.
    if not 2 <= len(ids) <= 4:
        return plan
    if plan.aggregation != "list":
        raise ValueError("Multi-device named read requires a list objective")
    # Single joined model phrase or missing array cannot supersede the
    # original verified question. Only read the devices explicitly mentioned.
    # An inferred room filter must not silently drop an explicitly named
    # device in another room. The host-verified full names are the scope.
    return replace(plan, device_name=None, room=None,
                   device_names=tuple(item["label"] for item in resolved),
                   limit=max(plan.limit,len(ids)))


def ground_current_attribute_request(
    plan: SemanticPlan, question: str,
) -> SemanticPlan:
    """Recover explicitly requested CURRENT properties, never a new intent.

    Device identities are independently grounded before this stage. This
    does not infer supported attributes, invent missing readings, or affect
    duration/history/causal questions and any filter/ranking operations.
    """
    if (plan.mode != "inventory" or plan.scope != "named" or
            plan.aggregation != "list" or plan.operator != "none" or
            plan.attributes or plan.attribute not in (None, "switch", "level") or
            not isinstance(question, str)):
        return plan
    wants_switch = re.search(r"\bswitch\s+(?:state|status|reading)\b", question, re.I)
    wants_level = re.search(
        r"\b(?:brightness(?:\s+level)?|dimmer\s+level)\b", question, re.I)
    if wants_switch and wants_level:
        return replace(plan, attribute=None, attributes=("switch", "level"))
    return plan


def _execute_multi_attribute_inventory(
    plan: SemanticPlan, source: list[tuple[str, Mapping[str, Any]]],
    provenance: Mapping[str, Any], checked_at: datetime | None,
) -> dict[str, Any]:
    """Emit one source-backed value (or explicitly unavailable) per property."""
    checked = checked_at or datetime.now(timezone.utc)
    if checked.tzinfo is None or checked.utcoffset() is None:
        raise ValueError("current time must be timezone aware")
    if len(source) > 4:
        raise ValueError("multi-attribute reads require at most four named devices")
    complete = provenance.get("complete") is True
    lines = [
        f"{len(source)} matching device(s) (Hubitat current reported states).",
        "Group: " + _display(", ".join(plan.device_names)
                             if plan.device_names else plan.device_name or "named") + ".",
        "",
    ]
    missing = 0
    values = []
    for ident, device in source:
        attributes: dict[str, Any] = {}
        readings: list[str] = []
        for attribute in plan.attributes:
            reading = _value(device, attribute)
            # No model-supplied fallback, cached command receipt or history
            # is an admissible substitute for a live read.
            if reading is None or reading == "":
                attributes[attribute] = None
                readings.append(f"{attribute}=unavailable")
                missing += 1
            else:
                attributes[attribute] = reading
                suffix = "%" if attribute == "level" and _number(reading) is not None else ""
                readings.append(f"{attribute}={_display(reading)}{suffix}")
        label = _display(device.get("label") or device.get("name") or "Device")
        room = _display(room_name(device) or "Unassigned")
        lines.append(f"• {room} — {label} — " + ", ".join(readings))
        values.append({"id": ident, "label": label, "reported_attributes": attributes})
    if missing:
        lines.append(f"{missing} requested reading(s) unavailable; no values inferred.")
    if not complete:
        lines.append("Inventory coverage not independently verified complete.")
    lines.append(
        "Read-only Hubitat snapshot at " +
        checked.astimezone(timezone.utc).isoformat(timespec="seconds") +
        ". Reported state is not independent physical confirmation."
    )
    answer = "\n".join(lines)
    return {
        "answer_mode": "semantic_inventory",
        "semantic_plan": plan.to_dict(),
        "answer": {"text": answer, "displayed_record_ids": [],
                   "omitted_material_record_ids": [],
                   "validation_issues": ([] if complete and not missing
                                         else ["missing_requested_current_attributes"]),
                   "root_cause_verified": False, "human_review_required": False},
        "report": {"text": answer, "technical_answer_retained": False},
        "inventory_query": {
            "matched_count": len(source), "scoped_count": len(source),
            "missing_readings": missing, "inventory_complete": complete,
            "inventory_pages": provenance.get("pages"),
            "checked_at_utc": checked.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "aggregation": "list", "attribute": None,
            "attributes": list(plan.attributes), "reported_device_values": values,
            "aggregate_value": None, "shown_count": len(source),
            "suppressed_overlapping_meters": [],
            "unclassified_measurement_scopes": 0, "excluded_unknown_scope": 0,
            "inferred_individual_loads": 0, "missing_expected_measurements": missing,
            "unverified_measurement_support": 0, "aggregate_safe": True,
        },
        "resolved_devices": [], "resolution_method": "semantic_verified_inventory",
        "test_mode": "explicit_read_only",
    }


def execute_inventory_plan(
    plan: SemanticPlan,
    devices: Sequence[Mapping[str,Any]],
    provenance: Mapping[str,Any],
    *,
    checked_at: datetime | None = None,
    operator_roles: Mapping[str,str] | None = None,
) -> dict[str,Any]:
    if plan.mode!="inventory":
        raise ValueError("not a current inventory plan")
    if not isinstance(devices,(list,tuple)) or not devices:
        raise ValueError("no current Hubitat inventory")
    source=list(_devices_for_plan(devices,plan))
    if plan.attributes:
        return _execute_multi_attribute_inventory(plan, source, provenance, checked_at)
    present=[]
    missing=0
    out_of_scope=[]
    unresolved_scope=[]
    unclassified_candidates=[]
    overlap_suppressed=0
    inferred_individual_loads=[]
    unsupported_capability=0
    missing_expected=0
    is_meter_quantity=plan.attribute in ("power","energy")
    comparison_of_individuals=(
        is_meter_quantity and plan.scope!="named"
        and plan.aggregation in ("top","bottom","sum","average")
    )
    for ident,device in source:
        value=_value(device,plan.attribute) if plan.attribute else None
        if plan.attribute and value is None:
            missing+=1
            if is_meter_quantity:
                caps=capability_names(device)
                advertised=("powermeter" if plan.attribute=="power"
                            else "energymeter")
                if advertised in caps:
                    missing_expected+=1
                else:
                    unsupported_capability+=1
            continue
        if is_meter_quantity:
            numeric=_quantity(value,plan.attribute)
            if numeric is None:
                missing+=1
                continue
            value=numeric
        if not _matches(value,plan.operator,plan.value):
            continue
        if comparison_of_individuals:
            scope=measurement_scope(
                device, hints=plan.measurement_roles, operator_roles=operator_roles,
            )
            if scope.role in ("site_total","circuit_subtotal"):
                out_of_scope.append({
                    "id":ident,
                    "label":str(device.get("label") or device.get("name") or "Device")[:95],
                    "role":scope.role,
                    "provenance":scope.provenance,
                    "verified":scope.verified,
                })
                overlap_suppressed+=1
                continue
            if scope.role=="unknown" or (
                plan.aggregation in ("sum","average") and not scope.verified
            ):
                unresolved_scope.append(ident)
            if scope.role=="unknown" and plan.measurement_target=="individual_load":
                # A source without a known measurement boundary must NOT be
                # presented as an individually metered load. Put it in a
                # separately explained category rather than silently ranking
                # a possible whole-house total as a single appliance.
                unclassified_candidates.append({
                    "id":ident,
                    "label":str(device.get("label") or device.get("name") or "Device")[:95],
                    "reading":value,
                })
                continue
            if scope.role=="individual_load" and not scope.verified:
                inferred_individual_loads.append(ident)
        present.append((ident,device,value))
    if plan.aggregation in ("top","bottom","sum","average"):
        numeric=[]
        for ident,device,value in present:
            amount=_quantity(value,plan.attribute)
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
        if comparison_of_individuals and (out_of_scope or unresolved_scope):
            # Do not return a mathematically precise but physically misleading
            # total when parent/submeter relationships remain unresolved.
            aggregate_value=None
        else:
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
    if comparison_of_individuals and plan.aggregation in ("top","bottom") and (
        unresolved_scope or inferred_individual_loads
    ):
        title+=" — provisional meter-scope classification"
    if plan.aggregation in ("sum","average"):
        if aggregate_value is None:
            title+=(": withheld — overlapping or unclassified meter scopes"
                    if comparison_of_individuals and
                       (out_of_scope or unresolved_scope)
                    else ": no numeric values available")
        else:
            units=(" W" if attr=="power" else " kWh" if attr=="energy"
                   else " %" if attr=="battery" else "")
            title+=f": {aggregate_value:,.2f}{units}"
    lines=[title+" (Hubitat current reported states)."]
    if plan.scope!="all":
        lines.append("Group: "+_display(
            ", ".join(plan.device_names) if plan.device_names else
            plan.device_name or plan.scope)+".")
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
                     " — "+_display(value)+" "+(
                         "W" if attr=="power" and _number(value) is not None
                         else "kWh" if attr=="energy" and _number(value) is not None
                         else ""))
            lines.append(f"• {room} — {label}{reading}")
    if total>plan.limit and plan.aggregation!="count":
        lines.append(f"... and {total-plan.limit} more matching device(s).")
    if out_of_scope:
        lines.append(
            f"{len(out_of_scope)} site/circuit aggregate meter(s) were shown "
            "separately rather than mixed into individual-load rankings:"
        )
        for meter in out_of_scope[:10]:
            lines.append(
                "• "+_display(meter["label"])+": "+meter["role"]+
                (" (operator-confirmed)" if meter["verified"]
                 else " (classification not independently verified)")
            )
        lines.append("A whole-house meter and its downstream loads overlap: "
                     "never add them together.")
    if unresolved_scope:
        lines.append(
            f"{len(unresolved_scope)} candidate measurement scope(s) remain "
            "unknown or unconfirmed; totals cannot treat these as independently "
            "metered loads.")
    if unclassified_candidates:
        lines.append(
            f"{len(unclassified_candidates)} meter(s) excluded from the "
            "individual-load ranking because their physical measurement "
            "scope was not established:")
        for candidate in sorted(
            unclassified_candidates,
            key=lambda x:-float(x["reading"]),
        )[:10]:
            lines.append(
                "• "+_display(candidate["label"])+": "
                +_display(candidate["reading"])+(" W" if attr=="power" else " kWh")
                +" (measurement scope unknown)"
            )
    if inferred_individual_loads and plan.aggregation in ("top","bottom"):
        lines.append(f"{len(inferred_individual_loads)} candidate individual "
                     "load role(s) were suggested by AI but not confirmed. "
                     "This ranking remains provisional.")
    if missing:
        if is_meter_quantity:
            lines.append(
                f"{missing} device(s) had no usable {attr} reading: "
                f"{missing_expected} advertised the matching meter capability "
                f"but lacked a value; {unsupported_capability} did not advertise "
                "that capability (measurement support unverified). "
                "They were excluded, not assumed zero.")
        else:
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
                  "validation_issues":(
                      [] if complete and not missing and not out_of_scope and
                            not unresolved_scope and not inferred_individual_loads else
                      ["inventory_coverage_or_measurement_scope_unverified"]
                  ),
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
            "suppressed_overlapping_meters":out_of_scope,
            "unclassified_measurement_scopes":len(unresolved_scope),
            "excluded_unknown_scope":len(unclassified_candidates),
            "inferred_individual_loads":len(inferred_individual_loads),
            "missing_expected_measurements":missing_expected,
            "unverified_measurement_support":unsupported_capability,
            "aggregate_safe":not (
                comparison_of_individuals and
                (out_of_scope or unresolved_scope)
            ),
        },
        "resolved_devices":[],"resolution_method":"semantic_verified_inventory",
        "test_mode":"explicit_read_only",
    }


__all__=["execute_inventory_plan","ground_named_inventory_plan","ground_current_attribute_request"]
