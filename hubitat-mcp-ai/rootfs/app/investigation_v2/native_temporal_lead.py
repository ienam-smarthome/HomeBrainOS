"""Cross-source chronological leads for focused native READ investigations.

Generic comparison of independently device-ID-matched current metadata and
source-attested event command timestamps. Time proximity is a hypothesis
prompt, never proof a command was delivered or caused the reported state.
Raw source values, free-form event descriptions and private arguments are
never published. Only a short, independently supported lead reaches prose.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
import re
from typing import Any

from .native_source_adapters import safe_string
from .native_provenance import numeric_id


_LOCAL_TIME = re.compile(
    r"^(?:[A-Za-z]{3} )?([A-Za-z]{3} \d{1,2} \d\d:\d\d:\d\d) "
    r"(BST|GMT) (\d{4})$"
)
_ANCHORS = ("lastSeen", "lastContact", "lastMessage")


def _timestamp(value: Any) -> datetime | None:
    """Only parse timestamps with EXPLICIT UTC offsets or BST/GMT zones."""
    if not isinstance(value, str) or len(value) > 70:
        return None
    raw = value.strip()
    matched = _LOCAL_TIME.fullmatch(raw)
    if matched:
        try:
            local = datetime.strptime(
                matched.group(1) + " " + matched.group(3),
                "%b %d %H:%M:%S %Y")
        except ValueError:
            return None
        offset = 1 if matched.group(2) == "BST" else 0
        return local.replace(
            tzinfo=timezone(timedelta(hours=offset))).astimezone(timezone.utc)
    try:
        parsed = datetime.fromisoformat(
            raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def verified_temporal_lead(
    witnesses: Sequence[Mapping[str, Any]],
    focus_ids: Sequence[str],
    *, proximity_seconds: float = 3.0,
) -> dict[str, Any] | None:
    """Admit exact time matching only from independently scoped live receipts.

    A unique attested focus device, matching hub_get_device id, and
    hub_list_device_events scoped to exactly that id are all mandatory.
    A source count or command issuer is not proof a command executed.
    """
    focus = {str(x) for x in focus_ids if numeric_id(x) is not None}
    if len(focus) != 1:
        return None
    device_id = next(iter(focus))
    anchor = None
    for w in witnesses[:16]:
        filters = w.get("read_filters")
        data = w.get("source_data")
        if (w.get("operation") != "hub_get_device"
                or type(w.get("read")) is not int
                or not isinstance(filters, Mapping)
                or str(filters.get("deviceId")) != device_id
                or not isinstance(data, Mapping)
                or str(data.get("id")) != device_id
                or not isinstance(data.get("attributes"), list)):
            continue
        attr = {r.get("name"): r.get("value")
                for r in data["attributes"][:80]
                if isinstance(r, Mapping) and isinstance(r.get("name"), str)}
        for name in _ANCHORS:
            when = _timestamp(attr.get(name))
            if when is not None:
                anchor = {
                    "read": w["read"], "attribute": name,
                    "time": when, "source_text": safe_string(attr[name], 65),
                    "device_name": safe_string(
                        data.get("label") or data.get("name") or
                        "Device " + device_id, 80),
                    "health": (safe_string(attr.get("healthStatus"), 22)
                               if isinstance(attr.get("healthStatus"), str) else None),
                    "mqtt": (safe_string(attr.get("mqttStatus"), 22)
                             if isinstance(attr.get("mqttStatus"), str) else None),
                }
                break
        if anchor:
            break
    # A source-attested device lastSeen event can also anchor the sequence
    # if the model did not request a separate current device snapshot.
    # We evaluate that fallback below after collecting only same-device
    # events from an independently scoped, READ-only history receipt.
    commands = []
    # The projected event page may contain much more than the issuer's
    # five illustrative command samples. Retain bounded, same-device
    # state-event receipts so event chronology is not reduced to totals.
    state_events: list[dict[str, Any]] = []
    for w in witnesses[:16]:
        filters, data = w.get("read_filters"), w.get("source_data")
        if (w.get("operation") != "hub_list_device_events"
                or type(w.get("read")) is not int
                or not isinstance(filters, Mapping)
                or str(filters.get("deviceId")) != device_id
                or not isinstance(data, Mapping)
                or not isinstance(data.get("issuer_apps"), list)):
            continue
        for issuer in data["issuer_apps"][:16]:
            if not isinstance(issuer, Mapping):
                continue
            app_id = numeric_id(issuer.get("appId"))
            samples = issuer.get("samples")
            if app_id is None or not isinstance(samples, list):
                continue
            for sample in samples[:8]:
                if not isinstance(sample, Mapping):
                    continue
                verb = sample.get("command")
                source_time = sample.get("date")
                when = _timestamp(source_time)
                if (not isinstance(verb, str)
                        or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", verb)
                        or when is None):
                    continue
                commands.append({
                    "app_id": app_id, "app_name": safe_string(
                        issuer.get("name") or "app " + app_id, 88),
                    "command": verb, "timestamp": when,
                    "timestamp_text": safe_string(source_time, 70),
                    "read": w["read"],
                })
        # The event projection is bounded to 80 real source rows and
        # pre-redacts free-text command arguments. Only structured producer
        # identity may attest an app command or device state event.
        for event in data.get("events", [])[:80]:
            if not isinstance(event, Mapping):
                continue
            actor = event.get("producedBy")
            event_name = event.get("name")
            when_text = event.get("date")
            when = _timestamp(when_text)
            if (not isinstance(actor, Mapping) or
                    not isinstance(event_name, str) or when is None):
                continue
            app_id = numeric_id(actor.get("appId"))
            if event_name.startswith("command-") and app_id:
                verb = event_name[len("command-"):]
                if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", verb):
                    commands.append({
                        "app_id": app_id,
                        "app_name": safe_string(
                            actor.get("name") or "app " + app_id, 88),
                        "command": verb, "timestamp": when,
                        "timestamp_text": safe_string(when_text, 70),
                        "read": w["read"],
                    })
            if str(actor.get("deviceId") or "") != device_id:
                continue
            allowed = {
                "lastSeen": None, "lastContact": None,
                "lastMessage": None,
                "switch": {"on", "off"},
                "healthStatus": {"online", "offline"},
                "networkStatus": {"online", "offline"},
                "deviceHealth": {"online", "offline", "stale", "unknown"},
            }
            if event_name not in allowed:
                continue
            raw_value = event.get("value")
            if allowed[event_name] is not None:
                if not isinstance(raw_value, str) or raw_value not in allowed[event_name]:
                    continue
            state_events.append({
                "source_name": safe_string(actor.get("name") or
                    "Device " + device_id, 80),
                "attribute": event_name,
                "value": safe_string(raw_value, 40)
                if isinstance(raw_value, str) else None,
                "timestamp": when, "timestamp_text": safe_string(when_text, 70),
                "read": w["read"],
            })
    if not commands:
        return None
    if anchor is None:
        # Match the *reported value* of a contact event to its own event
        # timestamp. A driver/watchdog event not attesting fresh contact
        # cannot become a lastSeen anchor. Both identities and timestamps
        # must originate in already verified, device-scoped source rows.
        candidates = []
        for event in state_events:
            if event["attribute"] not in _ANCHORS:
                continue
            value_time = _timestamp(event["value"])
            if value_time is None:
                continue
            if abs((event["timestamp"] - value_time).total_seconds()) > 5.0:
                continue
            closest_command = min(
                commands, key=lambda item:
                abs((item["timestamp"] - event["timestamp"]).total_seconds()))
            gap = abs((closest_command["timestamp"] -
                       event["timestamp"]).total_seconds())
            if gap <= max(0.1, min(10.0, float(proximity_seconds))):
                candidates.append((gap, event))
        if not candidates:
            return None
        _, source = min(candidates, key=lambda item:
                        (item[0], item[1]["timestamp"]))
        anchor = {
            "read": source["read"],
            "attribute": source["attribute"],
            "time": _timestamp(source["value"]),
            "source_text": source["value"],
            "device_name": source["source_name"],
            "health": None,
            "mqtt": None,
        }
    # A repeated source page must not multiply apparent command history.
    unique = {(c["app_id"], c["command"], c["timestamp"]): c
              for c in commands}
    commands = list(unique.values())
    nearest = min(commands, key=lambda c: (
        abs((c["timestamp"] - anchor["time"]).total_seconds()),
        c["app_id"]))
    delta = (nearest["timestamp"] - anchor["time"]).total_seconds()
    if abs(delta) > max(0.1, min(10.0, float(proximity_seconds))):
        return None
    later = [c for c in commands
             if c["timestamp"] > anchor["time"] + timedelta(seconds=3)]
    # Select independently projected event rows, rather than inferring
    # execution from a command name or a stored snapshot attribute.
    # These indicate what HUBITAT recorded, never physical actuation.
    unique_states = {
        (e["attribute"], e["value"], e["timestamp"]): e
        for e in state_events
    }
    states = list(unique_states.values())

    def following(attributes: set[str], values: set[str] | None,
                  before: float, after: float) -> dict[str, Any] | None:
        eligible = []
        for event in states:
            if event["attribute"] not in attributes:
                continue
            if values is not None and event["value"] not in values:
                continue
            span = (event["timestamp"] - nearest["timestamp"]).total_seconds()
            if -before <= span <= after:
                eligible.append((abs(span), span, event))
        if not eligible:
            return None
        _, span, event = min(eligible, key=lambda e: (e[0], e[2]["timestamp"]))
        return {
            "attribute": event["attribute"], "value": event["value"],
            "timestamp": event["timestamp_text"],
            "seconds_after_command": round(span, 3),
            "read": event["read"],
            "source_reported_only": True,
        }

    observed_sequence = []
    contact_event = following(set(_ANCHORS), None, 2.0, 3.0)
    if contact_event:
        observed_sequence.append(contact_event)
    switch_event = (
        following({"switch"}, {nearest["command"].lower()}, 0.0, 5.0)
        if nearest["command"].lower() in ("off", "on") else None)
    if switch_event:
        observed_sequence.append(switch_event)
    # OFFLINE is a health report after the command, not a validated
    # transition from online, and not the last real device message.
    offline_event = following(
        {"healthStatus", "networkStatus", "deviceHealth"},
        {"offline"}, 0.0, 600.0)
    if offline_event:
        observed_sequence.append(offline_event)
    observed_sequence.sort(key=lambda event: (
        _timestamp(event["timestamp"]), event["attribute"]))
    app_config_receipts = [
        w["read"] for w in witnesses[:16]
        if w.get("operation") == "hub_get_app_config"
        and type(w.get("read")) is int
        and isinstance(w.get("read_filters"), Mapping)
        and str(w["read_filters"].get("appId")) == nearest["app_id"]
        and isinstance(w.get("source_data"), Mapping)
        and w["source_data"].get("source_app_id_matches_request") is True
    ]
    return {
        "device_id": device_id, "device_name": anchor["device_name"],
        "anchor_attribute": anchor["attribute"],
        "anchor_text": anchor["source_text"], "anchor_read": anchor["read"],
        "command": nearest["command"], "app_id": nearest["app_id"],
        "app_name": nearest["app_name"], "command_text": nearest["timestamp_text"],
        "command_read": nearest["read"], "absolute_gap_seconds": round(abs(delta), 3),
        "command_after_anchor": delta >= 0,
        "later_sampled_commands": len(later),
        "later_on_commands": sum(c["command"].lower() == "on" for c in later),
        "observed_event_sequence": observed_sequence,
        "app_config_metadata_reads": sorted(set(app_config_receipts)),
        "health_status": anchor["health"], "mqtt_status": anchor["mqtt"],
        "sample_complete": False, "clock_alignment_verified": False,
        "physical_command_delivery_verified": False,
        "mechanism_verified": False,
    }


def temporal_lead_brief(lead: Mapping[str, Any]) -> str:
    """Describe exact Hubitat event order, without physical-cause assertions."""
    device = safe_string(lead["device_name"], 80)
    app = safe_string(lead["app_name"], 88)
    header = (
        f"**Most relevant observed timing sequence for {device}:** "
        f"{app} (app {lead['app_id']}) issued "
        f"`{lead['command']}` at {lead['command_text']} "
        f"(Read #{lead['command_read']}). "
        f"The device reports {lead['anchor_attribute']}="
        f"{lead['anchor_text']}; that stored timestamp and the command "
        f"are {lead['absolute_gap_seconds']} seconds apart "
        f"(Read #{lead['anchor_read']})."
    )
    sequence = lead.get("observed_event_sequence", [])
    if sequence:
        details = []
        for event in sequence[:3]:
            span = event["seconds_after_command"]
            time = event["timestamp"]
            relative = (f"{abs(span):.3f}s "
                        + ("before" if span < 0 else "after")
                        + " the command")
            if event["attribute"] in _ANCHORS:
                details.append(
                    f"a `{event['attribute']}` event at {time} "
                    f"({relative})")
            elif event["attribute"] == "switch":
                details.append(
                    f"a `switch={event['value']}` event at {time} "
                    f"({relative})")
            else:
                minutes = int(span // 60)
                seconds = span - minutes * 60
                interval = (f"{minutes}m {seconds:.3f}s"
                            if minutes else f"{span:.3f}s")
                details.append(
                    f"a `{event['attribute']}={event['value']}` event "
                    f"at {time} ({interval} after the command)")
        header += (" Hubitat's same-device event history also recorded "
                   + "; ".join(details) + ".")
    if lead.get("health_status"):
        header += (
            f" The current driver reports healthStatus="
            f"{lead['health_status']}.")
    if lead.get("mqtt_status") == "connected":
        header += (" MQTT connected describes the driver's broker session "
                   "and does not independently confirm device connectivity.")
    if lead.get("later_on_commands"):
        count = lead["later_on_commands"]
        header += (f" {count} later `on` command"
                   + ("s" if count != 1 else "")
                   + " were observed in the bounded sample; these "
                   "do not prove the device recovered.")
    config = lead.get("app_config_metadata_reads")
    if config:
        header += (" App configuration metadata was also retrieved "
                   f"(Read #{config[0]}), but actual action settings and "
                   "historical execution were not verified.")
    next_check = (
        "Inspect source-attested rule actions and execution logs, then "
        "independently verify the plug's power and network communication."
        if config else
        "Inspect the issuing app's actual rule actions, execution logs "
        "and the plug's power/network communication.")
    switch_confirmed_in_hub = any(
        item.get("attribute") == "switch" for item in sequence)
    switch_limit = (
        "Hubitat's recorded switch-state event strengthens the observed "
        "sequence, but does not prove power physically switched at the outlet. "
        if switch_confirmed_in_hub else
        "No independently sourced switch-state event was matched to the "
        "command in the returned history; a command alone is not actuation proof. "
    )
    return (
        header + "\n\n**Assessment:** This command is a strong "
        "chronological lead, **not a verified cause** of physical power loss. "
        + switch_limit
        + "Subsequent health reports may be driver/watchdog-generated, "
        "not fresh device traffic; historical coverage is incomplete. "
        + next_check
    )


def temporal_lead_short_answer(lead: Mapping[str, Any]) -> str:
    """Answer a connectivity incident in plain language, preserving uncertainty.

    Historical commands are only one possible explanation. A user unplugging
    a socket is compatible with the same Hubitat reports, so neither cause
    can be asserted from the event chronology alone.
    """
    device = safe_string(lead["device_name"], 80)
    issuer = safe_string(lead["app_name"], 88)
    switch = next((
        e for e in lead.get("observed_event_sequence", [])
        if e.get("attribute") == "switch"
        and e.get("value") == lead.get("command")), None)
    offline = next((
        e for e in lead.get("observed_event_sequence", [])
        if e.get("attribute") in ("healthStatus", "networkStatus", "deviceHealth")
        and e.get("value") == "offline"), None)
    if lead.get("health_status") == "offline" or offline:
        start = (f"**Most likely explanation:** {device} lost its power "
                 "or network connection.")
    else:
        start = (f"**Strongest clue:** {issuer} issued "
                 f"`{lead['command']}` close to the last reported "
                 "device contact.")
    detail = (f" Hubitat recorded an `{lead['command']}` command "
              f"from {issuer} (app {lead['app_id']}) at "
              f"{lead['command_text']}, {lead['absolute_gap_seconds']} "
              "seconds apart from the saved lastSeen/contact timestamp.")
    if switch:
        detail += (f" It then recorded `switch={switch['value']}` "
                   f"at {switch['timestamp']}.")
    if offline:
        detail += (f" It reported `{offline['attribute']}=offline` "
                   f"at {offline['timestamp']}.")
    end = (
        " **Cause not confirmed:** Those events do not establish whether "
        "the automation cut power, the socket was physically disconnected, "
        "or the network link failed. Check physical power first."
        if lead.get("command") == "off" else
        " **Cause not confirmed:** A command and an offline report alone "
        "do not prove why communication stopped. Check power and network.")
    return start + detail + end


__all__ = ["verified_temporal_lead", "temporal_lead_brief", "temporal_lead_short_answer"]
