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
    if anchor is None:
        return None

    commands = []
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
    if not commands:
        return None
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
        "health_status": anchor["health"], "mqtt_status": anchor["mqtt"],
        "sample_complete": False, "clock_alignment_verified": False,
        "physical_command_delivery_verified": False,
        "mechanism_verified": False,
    }


def temporal_lead_brief(lead: Mapping[str, Any]) -> str:
    """Return bounded host-authored observations and explicit causal limits."""
    device = safe_string(lead["device_name"], 80)
    app = safe_string(lead["app_name"], 88)
    state = lead.get("health_status")
    header = (f"**Most relevant observed timing clue for {device}:** "
              f"{app} (app {lead['app_id']}) issued "
              f"`{lead['command']}` at {lead['command_text']}; "
              f"the device reports {lead['anchor_attribute']}="
              f"{lead['anchor_text']}. These timestamps are "
              f"{lead['absolute_gap_seconds']} seconds apart "
              f"(Read #{lead['command_read']} and Read #{lead['anchor_read']}).")
    extra = ""
    if state:
        extra += f" The current driver reports healthStatus={state}."
    if lead.get("mqtt_status") == "connected":
        extra += (" MQTT connected describes the driver's broker session "
                  "and does not independently confirm device connectivity.")
    if lead.get("later_on_commands"):
        extra += (f" At least {lead['later_on_commands']} later `on` "
                  "command(s) also appear in the bounded sample; issuing "
                  "them does not show successful recovery.")
    return (header + extra
            + "\n\n**Assessment:** The timing makes this command a "
              "specific lead to investigate, **not a verified cause**. "
              "The command may not have executed on the physical device, "
              "the status timestamp may not prove actual contact, and "
              "the available history is incomplete. Check the issuing "
              "app's read-only configuration and independently verify "
              "device power/network communication before attributing "
              "an outage to that app.")


__all__ = ["verified_temporal_lead", "temporal_lead_brief"]
