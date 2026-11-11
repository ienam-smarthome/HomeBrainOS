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
    text = item.get("label") or item.get("name") or "Unnamed device"
    return str(text)[:100] if isinstance(text, str) else "Unnamed device"


def summarize_device_inventory(response):
    """Return only observed attributes; never interpret missing as OFF or OK."""
    source = _body(response)
    devices = source["devices"]
    if len(devices) > 3000:
        raise OverviewUnavailable("Inventory is larger than the supported overview size")
    total = source.get("unfilteredTotal", source.get("total"))
    if type(total) is not int or total < len(devices) or total > 100000:
        total = None
    observed = 0
    switch_on = motion_active = battery_low = 0
    switch_covered = motion_covered = battery_covered = 0
    examples = {"switch_on": [], "motion_active": [], "battery_low": []}
    for device in devices:
        if not isinstance(device, dict):
            continue
        observed += 1
        states = _states(device)
        label = _safe_label(device)
        switch = states.get("switch")
        if isinstance(switch, str) and switch.lower() in ("on", "off"):
            switch_covered += 1
            if switch.lower() == "on":
                switch_on += 1
                if len(examples["switch_on"]) < 5:
                    examples["switch_on"].append(label)
        motion = states.get("motion")
        if isinstance(motion, str) and motion.lower() in ("active", "inactive"):
            motion_covered += 1
            if motion.lower() == "active":
                motion_active += 1
                if len(examples["motion_active"]) < 5:
                    examples["motion_active"].append(label)
        level = _numeric(states.get("battery"))
        if level is not None:
            battery_covered += 1
            if level < 20:
                battery_low += 1
                if len(examples["battery_low"]) < 5:
                    examples["battery_low"].append(label)
    partial = total is None or total > len(devices) or observed != len(devices)
    return {
        "read_only": True,
        "source": "native Hubitat MCP device inventory",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "returned_devices": observed,
        "source_declared_total": total,
        "inventory_full_coverage_verified": not partial,
        "metrics": {
            "switch_on": {"count": switch_on, "devices_with_state": switch_covered,
                          "examples": examples["switch_on"]},
            "motion_active": {"count": motion_active, "devices_with_state": motion_covered,
                              "examples": examples["motion_active"]},
            "battery_low": {"count": battery_low, "devices_with_state": battery_covered,
                            "threshold_exclusive_pct": 20,
                            "examples": examples["battery_low"]},
        },
        "notes": [
            "Switches ON includes all switch devices, not just lights.",
            "Only returned devices reporting the relevant attribute are counted.",
            "Absent or stale attributes are unknown, not confirmed OFF, inactive or healthy.",
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
