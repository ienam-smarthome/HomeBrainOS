from __future__ import annotations

from typing import Any


def render_device_manifest(devices: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    common = {
        "battery",
        "condition",
        "contact",
        "humidity",
        "level",
        "healthstatus",
        "lock",
        "motion",
        "networkstatus",
        "presence",
        "pressure",
        "rtt",
        "status",
        "switch",
        "temperature",
        "wind",
        "windspeed",
    }
    for device in devices:
        label = device.get("label") or device.get("name") or "Unknown device"
        device_id = device.get("id") or device.get("deviceId")
        room = device.get("room") or device.get("roomName") or "Unassigned"
        capabilities = device.get("capabilities") or []
        if isinstance(capabilities, dict):
            capabilities = list(capabilities)
        if not isinstance(capabilities, list):
            capabilities = [capabilities]
        attributes = device.get("attributes") or device.get("currentStates") or {}
        if isinstance(attributes, list):
            attributes = {
                str(item.get("name")): item.get(
                    "currentValue", item.get("value")
                )
                for item in attributes
                if isinstance(item, dict) and item.get("name")
            }
        if not isinstance(attributes, dict):
            attributes = {}
        is_weather = "weather" in str(label).lower()
        states: list[str] = []
        for key, value in attributes.items():
            normalized = str(key).lower().replace("_", "")
            if normalized not in common and not (is_weather and len(states) < 16):
                continue
            rendered = str(value)
            if len(rendered) > 80:
                rendered = rendered[:77] + "..."
            states.append(f"{key}={rendered}")
            if len(states) >= (16 if is_weather else 10):
                break
        rows.append(
            f"- {label!r} | ID: {device_id} | Room: {room} | "
            f"Capabilities: {', '.join(map(str, capabilities)) or 'unknown'}"
            + (f" | Current: {', '.join(states)}" if states else "")
        )
    return "\n".join(rows) or "Device manifest omitted or unavailable."


def render_app_manifest(apps: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for app in apps:
        app_id = app.get("id") or app.get("appId")
        label = app.get("label") or app.get("name") or app.get("displayName")
        if app_id is None or not label:
            continue
        state = " | ".join(
            f"{key}: {app[key]}"
            for key in ("status", "enabled", "paused", "active", "broken")
            if app.get(key) is not None
        )
        rows.append(
            f"- {label!r} | appId: {app_id}"
            + (f" | {state}" if state else "")
        )
    return (
        "\n\nLIVE APP MANIFEST\n"
        + ("\n".join(rows) if rows else "No live app manifest available.")
        + "\nThis cached manifest is only for app name-to-ID matching."
    )


def build_system_prompt(
    device_manifest: str,
    app_manifest_section: str = "",
) -> str:
    return (
        "You are HomeBrainOS, a concise smart-home assistant. Use Hubitat MCP "
        "for every live claim and action. Never invent devices, states, results, "
        "or successful actions. Ask one short clarification only when necessary. "
        "The device and app manifests are for identity resolution only, not proof "
        "of current state. Category gateways require tool='<sub-tool name>' and "
        "args={<sub-tool arguments>}.\n\n"
        "CAPABILITY CONTRACT\n"
        "- For exhaustive attribute lists, thresholds, counts, and comparisons, "
        "call homebrain_filter_devices; never scan the manifest yourself.\n"
        "- WHOLE-HOME SUMMARY RULES: For lights on, active rooms, non-light "
        "switches on, or a whole-home "
        "summary, call the matching homebrain_active_lights, "
        "homebrain_active_rooms, homebrain_active_switches, or "
        "homebrain_home_snapshot tool exactly once. The whole-home snapshot covers "
        "presence, active motion, open doors/windows, locks, batteries, and alerts. "
        "Do not say the home is quiet when anyone is present or another active "
        "condition exists.\n"
        "- A low battery is a numeric battery level at or below 20 percent. "
        "Exclude every device above 20 percent.\n"
        "- For hub firmware and resources, call homebrain_hub_info_snapshot with "
        "{'scope': 'firmware'} or {'scope': 'resources'}. Never substitute "
        "generic hub_get_info. Never replace it with generic hub_get_info. "
        "Only call hub_update_firmware after the snapshot reports "
        "update_available=true and the host confirmation gate approves it.\n"
        "- For current app status, call hub_read_apps_code with "
        "tool='hub_list_apps' and args={'scope': 'instances'}; use "
        "hub_read_rules for Rule Machine state. Use "
        "hub_manage_native_rules_and_apps with tool='hub_set_rule_paused' for "
        "pause/resume operations.\n"
        "- ROUTINE DEVICE CONTROL: For routine light or switch on/off/toggle, "
        "call homebrain_control_devices once with exact room or device_names, "
        "device_kind, and command arguments. Routine controls do not require "
        "confirmation. Locks, garage doors, destructive operations, security "
        "controls, and firmware installation remain sensitive.\n"
        "- For device health, distinguish explicit offline states from stale "
        "activity. healthStatus=offline, networkStatus=offline/unavailable, or "
        "rtt=timeout supports an offline claim. Stale means no recent event and "
        "does not prove a device is offline. Ping or refresh at most five "
        "ambiguous devices using command='ping' or command='refresh'. Limit "
        "active checks to five devices.\n"
        "- LIVE HUB LOG RULES: For hub logs, call hub_read_diagnostics with "
        "the actual "
        "tool='hub_get_logs' and "
        "args={'since': '30m', 'limit': 100} unless the user specifies filters. "
        "State the window and entry count. Never infer logs from manifests.\n"
        "- Never claim a mutation succeeded unless its tool result confirms it.\n\n"
        f"LIVE DEVICE MANIFEST\n{device_manifest}{app_manifest_section}"
    )
