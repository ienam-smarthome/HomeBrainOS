"""V2 compact, explicitly source-scoped native device overview.

One read-only inventory query, no model invocation, no V1 audit/journal,
no device control, no scheduled polling. The overview is a snapshot of
returned attribute states, NOT a whole-house diagnosis or health check.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone

from mcp import MCPClient, MCPError


class OverviewUnavailable(ValueError):
    pass


def _numeric(value):
    """Accept plain Hubitat numeric battery readings, not arbitrary strings."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (float, int)):
        result = float(value)
    elif isinstance(value, str) and re.fullmatch(r"\s*\d+(?:\.\d+)?\s*%?\s*", value):
        result = float(value.strip().removesuffix("%").strip())
    else:
        return None
    return result if math.isfinite(result) and 0 <= result <= 100 else None


def _states(device):
    source = device.get("currentStates")
    if isinstance(source, dict):
        return source
    if isinstance(source, list):
        values = {}
        for item in source:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                values[item["name"]] = item.get("value")
        return values
    return {}


def _body(response):
    if not isinstance(response, dict) or response.get("isError"):
        raise OverviewUnavailable("Inventory read did not succeed")
    blocks = response.get("content")
    if not isinstance(blocks, list):
        raise OverviewUnavailable("Inventory response contained no device list")
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        value = block.get("text", "")
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict) and isinstance(parsed.get("devices"), list):
                return parsed
        except (TypeError, ValueError):
            continue
    raise OverviewUnavailable("Inventory source did not return a usable device list")


def _safe_label(item):
    text = item.get("label") or item.get("name")
    if not isinstance(text, str):
        return "Unnamed device"
    return " ".join(text.split())[:100] or "Unnamed device"


# Positive evidence, rather than assuming every Switch is a light. Hubitat's
# generic switch and dimmer capabilities are also used by plugs, relays and
# non-light loads; neither proves lighting on its own.
_LIGHT_WORDS = re.compile(
    r"\b(?:lights?|lamps?|bulbs?|downlights?|spotlights?|spotlights?|"
    r"spots?|pendants?|chandeliers?|sconces?|floodlights?|"
    r"led[\s-]?strips?)\b", re.I,
)
_NON_LIGHT_WORDS = re.compile(
    r"\b(?:light\s+(?:level\s+)?sensors?|illuminance|lux\s+(?:sensors?|meters?)|"
    r"light\s+meters?|buttons?|smart\s+plugs?|plugs?|sockets?|outlets?)\b", re.I,
)
_LIGHT_CAPABILITIES = frozenset({
    "light", "colorcontrol", "colortemperature", "bulb", "lighteffects",
})


def _is_recognised_light(device, label):
    """Conservatively classify labelled/typed light *loads*, not switches."""
    details = [label]
    for key in ("type", "typeName", "deviceType", "deviceTypeName",
                "driver", "deviceClass", "category"):
        value = device.get(key)
        if isinstance(value, str):
            details.append(value)
    descriptions = " ".join(details)
    if _NON_LIGHT_WORDS.search(descriptions):
        return False
    capabilities = device.get("capabilities")
    if isinstance(capabilities, (list, tuple)):
        for item in capabilities:
            name = (item if isinstance(item, str)
                    else item.get("name", item.get("capability", ""))
                    if isinstance(item, dict) else "")
            if isinstance(name, str) and name.lower().replace("capability.", "") in _LIGHT_CAPABILITIES:
                return True
    return bool(_LIGHT_WORDS.search(descriptions))


def summarize_device_inventory(response):
    """Return bounded named observed states, never infer absent readings."""
    source = _body(response)
    devices = source["devices"]
    if len(devices) > 3000:
        raise OverviewUnavailable("Inventory is larger than the supported overview size")
    total = source.get("unfilteredTotal", source.get("total"))
    if type(total) is not int or total < len(devices) or total > 100000:
        total = None
    observed = 0
    lights_on = motion_active = battery_low = 0
    light_covered = motion_covered = battery_covered = 0
    unclassified_switch_on = 0
    contact_open = water_wet = heating_active = reported_offline = 0
    contact_covered = water_covered = heating_covered = health_covered = 0
    other_switch_covered = 0
    members = {
        "lights_on": [], "motion_active": [], "battery_low": [],
        "contact_open": [], "water_wet": [], "heating_active": [],
        "reported_offline": [], "other_switches_on": [],
    }
    max_members_per_metric = 250
    for device in devices:
        if not isinstance(device, dict):
            continue
        observed += 1
        states = _states(device)
        label = _safe_label(device)
        switch = states.get("switch")
        if isinstance(switch, str) and switch.strip().lower() in ("on", "off"):
            is_light = _is_recognised_light(device, label)
            if is_light:
                light_covered += 1
                if switch.strip().lower() == "on":
                    lights_on += 1
                    if len(members["lights_on"]) < max_members_per_metric:
                        members["lights_on"].append({"name": label})
            else:
                other_switch_covered += 1
                if switch.strip().lower() == "on":
                    unclassified_switch_on += 1
                    if len(members["other_switches_on"]) < max_members_per_metric:
                        members["other_switches_on"].append({"name": label})
        motion = states.get("motion")
        if isinstance(motion, str) and motion.strip().lower() in ("active", "inactive"):
            motion_covered += 1
            if motion.strip().lower() == "active":
                motion_active += 1
                if len(members["motion_active"]) < max_members_per_metric:
                    members["motion_active"].append({"name": label})
        level = _numeric(states.get("battery"))
        if level is not None:
            battery_covered += 1
            if level < 20:
                battery_low += 1
                if len(members["battery_low"]) < max_members_per_metric:
                    members["battery_low"].append({"name": label, "battery_pct": level})
        # Additional summaries use the SAME inventory and state dictionary.
        # No event history, extra MCP call, inferred alerts or stale-state
        # "recovery" is permitted. Unknown attributes are not clean states.
        contact = states.get("contact")
        if isinstance(contact, str) and contact.strip().lower() in ("open", "closed"):
            contact_covered += 1
            if contact.strip().lower() == "open":
                contact_open += 1
                if len(members["contact_open"]) < max_members_per_metric:
                    members["contact_open"].append({"name": label})
        water = states.get("water")
        if isinstance(water, str) and water.strip().lower() in ("wet", "dry"):
            water_covered += 1
            if water.strip().lower() == "wet":
                water_wet += 1
                if len(members["water_wet"]) < max_members_per_metric:
                    members["water_wet"].append({"name": label})
        heat = states.get("thermostatOperatingState")
        if heat is None:
            heat = states.get("operatingState")
        if isinstance(heat, str) and heat.strip().lower() in (
                "heating", "idle", "cooling", "pending heat",
                "pending cool", "fan only", "off"):
            heating_covered += 1
            if heat.strip().lower() == "heating":
                heating_active += 1
                if len(members["heating_active"]) < max_members_per_metric:
                    members["heating_active"].append({"name": label})
        health = states.get("healthStatus")
        if isinstance(health, str) and health.strip().lower() in ("online", "offline"):
            health_covered += 1
            if health.strip().lower() == "offline":
                reported_offline += 1
                if len(members["reported_offline"]) < max_members_per_metric:
                    members["reported_offline"].append({"name": label})
    for key in ("lights_on", "motion_active", "contact_open",
                "water_wet", "heating_active", "reported_offline",
                "other_switches_on"):
        members[key].sort(key=lambda item: item["name"].casefold())
    members["battery_low"].sort(key=lambda item: (item["battery_pct"], item["name"].casefold()))
    partial = total is None or total > len(devices) or observed != len(devices)

    def metric(key, count, covered, **extra):
        return {
            "count": count,
            "devices_with_state": covered,
            "members": members[key],
            "members_omitted": max(0, count - len(members[key])),
            **extra,
        }

    return {
        "read_only": True,
        "source": "native Hubitat MCP device inventory",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "returned_devices": observed,
        "source_declared_total": total,
        "inventory_full_coverage_verified": not partial,
        "unclassified_on_switches": unclassified_switch_on,
        "metrics": {
            "lights_on": metric("lights_on", lights_on, light_covered),
            "motion_active": metric("motion_active", motion_active, motion_covered),
            "battery_low": metric("battery_low", battery_low, battery_covered,
                                  threshold_exclusive_pct=20),
            "contact_open": metric("contact_open", contact_open, contact_covered),
            "water_wet": metric("water_wet", water_wet, water_covered),
            "heating_active": metric("heating_active", heating_active, heating_covered),
            "reported_offline": metric("reported_offline", reported_offline, health_covered),
            "other_switches_on": metric(
                "other_switches_on", unclassified_switch_on, other_switch_covered),
        },
        "notes": [
            "Lights ON uses positive light names, device-type or colour-capability evidence; unidentified ON switches are excluded rather than counted as lights.",
            "Only returned devices reporting the relevant attribute are counted; names are truncated and the list is bounded.",
            "Absent or stale attributes are unknown, not confirmed OFF, inactive or healthy.",
            "Contact, water, heating and health counts use only explicit returned attributes with recognised values; an absent reading is unknown, not a clean or healthy status.",
            "ON switches lacking positive light identification are listed separately; they may be plugs, relays or other loads, not necessarily lighting.",
            "A snapshot is not the V1 scheduled system audit or proof of recent device reporting.",
        ],
    }


async def read_overview(mcp: MCPClient):
    """Select only the exact advertised read-only inventory tool.

    If the upstream catalog changes, stop instead of guessing a write-capable
    method or invoking a dissimilar tool. No model is involved.
    """
    catalog = await mcp.list_tools()
    by_name = {x["name"]: x for x in catalog if isinstance(x, dict) and isinstance(x.get("name"), str)}
    direct = by_name.get("hub_list_devices")
    if direct:
        result = await mcp.call("hub_list_devices", {})
    else:
        gateway = by_name.get("hub_read_devices")
        schema = gateway.get("inputSchema") if isinstance(gateway, dict) else None
        props = schema.get("properties") if isinstance(schema, dict) else None
        selector = props.get("tool") if isinstance(props, dict) else None
        allowed = selector.get("enum") if isinstance(selector, dict) else None
        if not (isinstance(allowed, list) and "hub_list_devices" in allowed
                and "args" in props):
            raise OverviewUnavailable("Connected MCP catalog does not advertise a safe device inventory read")
        result = await mcp.call("hub_read_devices", {
            "tool": "hub_list_devices", "args": {},
        })
    return summarize_device_inventory(result)
