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


def build_system_prompt(
    device_manifest: str,
    app_manifest_section: str = "",
    *,
    now: datetime | None = None,
) -> str:
    """Build the normal HomeBrain prompt plus evidence-bounded freshness rules."""
    base = _core.build_system_prompt(
        device_manifest,
        app_manifest_section,
        now=now,
    )
    return base + _FRESHNESS_POLICY


__all__ = [
    "build_system_prompt",
    "render_app_manifest",
    "render_device_manifest",
]
