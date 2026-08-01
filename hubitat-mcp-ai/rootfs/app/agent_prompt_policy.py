from __future__ import annotations

from typing import Any


def render_device_manifest(devices: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    common = {
        "battery", "condition", "contact", "humidity", "level",
        "healthstatus", "lock", "motion", "networkstatus", "presence",
        "pressure", "rtt", "status", "switch", "temperature", "wind",
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
                str(item.get("name")): item.get("currentValue", item.get("value"))
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
        "args={<sub-tool arguments>}. The initial tool list is intentionally "
        "small. If a required Hubitat gateway is not declared, call "
        "hub_search_tools first, then use the gateway added by that result. "
        "Never attempt an undeclared tool name. A successful search returns "
        "structured results containing the callable gateway; use that gateway "
        "on the next tool round.\n\n"
        "CAPABILITY CONTRACT\n"
        "- For exhaustive attribute lists, thresholds, counts, and comparisons, "
        "call homebrain_filter_devices; never scan the manifest yourself.\n"
        "- For numeric highest, lowest, top, sorted, or count questions, call "
        "homebrain_query_devices. Use group_by='room' when the user asks which "
        "room and device_kind='socket' for sockets/outlets. Answer the user's "
        "actual question from the computed winner/results; do not repeat a raw "
        "attribute dump.\n"
        "- For current weather or weather-device questions, call "
        "homebrain_weather_snapshot and answer from its primary device attributes. "
        "Do not substitute ordinary indoor temperature sensors.\n"
        "- WHOLE-HOME SUMMARY RULES: For lights on, active rooms, non-light "
        "switches on, or a whole-home summary, call the matching "
        "homebrain_active_lights, homebrain_active_rooms, "
        "homebrain_active_switches, or homebrain_home_snapshot tool exactly once. "
        "The whole-home snapshot covers presence, active motion, open doors/windows, "
        "locks, batteries, and alerts. Do not say the home is quiet when anyone is "
        "present or another active condition exists.\n"
        "- A low battery is a numeric battery level at or below 20 percent. "
        "Exclude every device above 20 percent.\n"
        "- For hub firmware and resources, call homebrain_hub_info_snapshot with "
        "{'scope': 'firmware'} or {'scope': 'resources'}. Never substitute generic "
        "hub_get_info. Never replace it with generic hub_get_info. Only call "
        "hub_update_firmware after the snapshot reports update_available=true and "
        "the host confirmation gate approves it.\n"
        "- For current app and automation status, call hub_read_apps_code with "
        "tool='hub_list_apps' and args={'scope': 'instances'}, and call "
        "hub_read_rules for Rule Machine state. Reconcile disabled before paused, "
        "and never infer active from paused=false alone. Report every returned app "
        "or rule under exactly one status: ACTIVE, DISABLED, PAUSED, BROKEN, or "
        "UNKNOWN. Prefix every list item with the literal marker [ACTIVE], "
        "[DISABLED], [PAUSED], [BROKEN], or [UNKNOWN], and use matching section "
        "headings such as '### Active', '### Disabled', and '### Paused'. Keep each "
        "rule name on its own bullet so the WebUI can colour the status clearly. "
        "Use hub_manage_native_rules_and_apps with tool='hub_set_rule_paused' for "
        "pause/resume operations.\n"
        "- RULE AUTHORING: When the user asks to create, write, schedule, or edit "
        "a common daily start/end device schedule, the host may compile and queue "
        "the complete Rule Machine calls before this model is invoked. Do not "
        "restate or replace a host-compiled plan. For requests that reach this "
        "tool loop, "
        "first resolve every named device with "
        "homebrain_resolve_device, which performs targeted label-filtered "
        "hub_list_devices lookups (never dump the full "
        "device inventory) and verify its supported commands through a targeted "
        "'find device commands' discovery/read path; never guess an ID or command. "
        "Then call "
        "hub_search_tools with the targeted query 'create Rule Machine rule' and "
        "call the discovered "
        "hub_manage_rule_machine gateway with tool='hub_set_rule'. Before composing "
        "a write, read hub_get_tool_guide sections 'best_practice_reference' and "
        "'set_rule_reference'; preserve the live bestPracticeKey from the guide. "
        "Calling hub_manage_rule_machine with {} is the read-only gateway schema "
        "probe. Machine-readable trigger/action discovery is also available through "
        "tool='hub_set_rule' with args={'addTrigger':{'discover':true}} or "
        "args={'addAction':{'discover':true}}. Build the apply call with name, "
        "addTrigger(s), addAction(s), and bestPracticeKey DIRECTLY inside the "
        "gateway args object; never invent an operation/create/args envelope. "
        "Use capability (never type) in every trigger/action spec. A daily wall-"
        "clock trigger is exactly capability='Certain Time (and optional date)', "
        "time='A specific time', atTime='HH:mm'; never use capability='time' or "
        "put command/type fields in a trigger. For a mapped switch action use "
        "capability='switch' with action='on' or action='off'. For a custom "
        "device command use capability='runCommand', deviceIds=[verified ID], "
        "capabilityFilter matching the verified device capability, and the verified "
        "command. Do not send confirm:true yourself: the host adds it only after "
        "the user approves the queued action. Rule creation "
        "is supported and is a sensitive mutation, so let the host confirmation "
        "gate approve the proposed structured call or call group. A block/unblock "
        "time window MUST be represented as two independently named rules in one "
        "confirmation group: one rule with one start-time trigger and one start "
        "action, plus one rule with one end-time trigger and one end action. Never "
        "put multiple times and opposing actions in one rule because every trigger "
        "would run the same action list. Queue both atomic writes together. "
        "Do not replace the requested rule with a similarly named existing app or "
        "claim that rules cannot be created merely because a read-app search or "
        "app manifest found one. Only report the capability unavailable after a "
        "targeted discovery search returns no relevant gateway.\n"
        "- ROUTINE DEVICE CONTROL: For routine light or switch on/off/toggle, call "
        "homebrain_control_devices once with exact room or device_names, device_kind, "
        "and command arguments, but only when the user explicitly requests a state "
        "change. Never call it for status, history, 'why', or 'which' questions. "
        "Routine controls do not require confirmation. Locks, "
        "garage doors, destructive operations, security controls, and firmware "
        "installation remain sensitive.\n"
        "- DEVICE HISTORY: For when, last-change, repeated-change, what happened, "
        "or why questions about one named device, call homebrain_device_history. "
        "It performs targeted device resolution and the authoritative "
        "hub_list_device_events read with a bounded window. Report only the "
        "events returned. A state event proves that the transition was reported; "
        "it does not prove which automation or person caused it. Never substitute "
        "hub logs or the current device manifest for event history.\n"
        "- For device health, distinguish explicit offline states from stale activity. "
        "healthStatus=offline, networkStatus=offline/unavailable, or rtt=timeout "
        "supports an offline claim. Stale means no recent event and does not prove a "
        "device is offline. Ping or refresh at most five ambiguous devices using "
        "command='ping' or command='refresh'. Limit active checks to five devices.\n"
        "- LIVE HUB LOG RULES: For hub logs, call hub_read_diagnostics with the actual "
        "tool='hub_get_logs' and args={'since': '30m', 'limit': 100} unless the user "
        "specifies filters. State the window and entry count. Never infer logs from "
        "manifests.\n"
        "- Never claim a mutation succeeded unless its tool result confirms it.\n\n"
        f"LIVE DEVICE MANIFEST\n{device_manifest}{app_manifest_section}"
    )
