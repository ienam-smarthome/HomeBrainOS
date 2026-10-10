from __future__ import annotations

from datetime import datetime

from frozen_core import agent_prompt_policy_core as _core


render_device_manifest = _core.render_device_manifest
render_app_manifest = _core.render_app_manifest


_FRESHNESS_POLICY = """

DEVICE FRESHNESS SEMANTICS
- An old lastActivity, lastEvent, lastSeen, lastCheckin, or similar timestamp by itself proves only that no recent activity was observed. It does NOT prove that a device is offline, dead, failed, disconnected, unavailable, or stopped reporting.
- Device capabilities such as TemperatureMeasurement, RelativeHumidityMeasurement, PowerMeter, EnergyMeter, MotionSensor, ContactSensor, or Button do NOT establish a reporting cadence or freshness expectation.
- Use offline/unavailable language only when current-turn evidence directly reports a health, reachability, transport, poll, or integration failure.
- Use expected-update-overdue language only when current-turn evidence includes an explicit reporting, heartbeat, polling, or freshness expectation and the observed age exceeds that expectation. A missed expectation does not by itself establish the cause.
- Otherwise describe an old timestamp neutrally as no recent activity or no recent events observed.
- If a cached state such as switch=on, motion=active, presence=present, contact=open, or lock=unlocked is supported only by an old timestamp, say that the cached value exists but the live status cannot be confirmed from that evidence.
- A cluster of similar last-event timestamps is an observation or investigation hypothesis only. Do not infer a shared integration, cloud, network, poller, or device failure unless separate current-turn evidence links those devices to that mechanism.
- Do not turn neutral no-recent-activity observations into health alerts merely to make a home-status answer more complete. Preserve the fast deterministic snapshot path when it already answers the user's question.
"""


_ROOM_STATUS_POLICY = """

ROOM STATUS EVIDENCE
- For a room-status/state question, preserve useful per-device observations instead of collapsing distinct sensor readings into an unattributed range.
- Include relevant switch/level, motion/presence, temperature, humidity, illuminance, battery, and explicit health/connectivity states when current-turn evidence supplies them.
- Name the source device for environmental readings when more than one device reports the same attribute.
- Preserve source-supplied update/activity timestamps when they materially qualify a cached state. Never invent a timestamp.
- A sensor reporting motion=active or presence=present is a reported state. If its only supporting timestamp is old, do not call that fresh detection; apply DEVICE FRESHNESS SEMANTICS.
- Keep switch power, sensor health/status, transport diagnostics, and root cause separate. An MQTT error string can establish the observed diagnostic, not a definitive hardware/network cause by itself.
- EXPLICIT HEALTH PRECEDENCE: if the same device reports offline, unavailable, failed, timeout, disconnected, or a direct connection failure, surface that condition prominently and do not present its retained motion/presence value as a reliable current inactive/active reading. Say, for example, "offline; last reported inactive" rather than simply "inactive".
- If any device in the requested room has an explicit current health/connectivity failure, include a Device Health/Warning section in the answer; do not silently omit that failure while summarizing otherwise healthy room state.
- OFFLINE SENSOR EXCLUSION: when a device is explicitly offline, do not include it in either the current Active or Inactive occupancy groups. Mention retained motion/presence only in Device Health as historical/unverified readings. A power switch showing on does not override offline sensor status.
- STALE ENVIRONMENT EXCLUSION: do not use illuminance, temperature, humidity, or other retained measurements from an explicitly offline sensor in current room ranges or current extrema. If useful, show the value only under Device Health with a freshness-not-verified qualifier.
- Before finalizing a room summary, cross-check that no device named under Device Health as offline is also claimed as currently reporting active/inactive or contributing trustworthy current environmental readings.
- When deterministic room evidence contains a `health` object with activityReliable=false or environmentReliable=false, treat that reliability qualifier as authoritative presentation guidance: keep the retained value only as a qualified last/reported value and do not use it to classify current occupancy or current environmental conditions.
- Do not infer a missing room device from count differences unless current-turn evidence establishes comparable inventory scopes and the missing numeric ID.
- Do not pull a nearby/out-of-room sensor into the room summary unless it is clearly labelled as contextual.
"""


_INTERNET_ACCESS_POLICY = """

INTERNET ACCESS SWITCH SEMANTICS
- A device whose authoritative Hubitat room/group is exactly "Internet" is an Internet access control.
- For those Internet-group devices only, switch=on means Internet allowed and switch=off means Internet blocked.
- Present those states as "Internet allowed" or "Internet blocked". Do not describe switch=on as blocking being enabled, and do not describe switch=off as the Internet being allowed.
- Authoritative room/group membership establishes this meaning. Never infer it merely from a label prefix such as "Block"; a similarly named device outside the Internet group keeps ordinary switch semantics.
- If a switch row carries semantic_role=internet_access_control, internet_access, or state_label, prefer that semantic state over generic "switch on/off" wording in home summaries.
- This is presentation semantics only. Keep the literal Hubitat switch state and underlying on/off commands unchanged; never invert a command or mutate a device merely to render its state.
"""


def build_system_prompt(
    device_manifest: str,
    app_manifest_section: str = "",
    *,
    now: datetime | None = None,
) -> str:
    """Build the normal HomeBrain prompt plus evidence-bounded semantic rules."""
    base = _core.build_system_prompt(
        device_manifest,
        app_manifest_section,
        now=now,
    )
    return base + _FRESHNESS_POLICY + _ROOM_STATUS_POLICY + _INTERNET_ACCESS_POLICY


__all__ = [
    "build_system_prompt",
    "render_app_manifest",
    "render_device_manifest",
]
