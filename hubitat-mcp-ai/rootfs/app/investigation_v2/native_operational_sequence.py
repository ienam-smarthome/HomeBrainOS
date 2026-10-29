"""Natural-language account of independently attested control/state sequences.

Source-only fallback when model-authored explanation cannot pass verification.
This does not infer the originating TRV, prove hardware operation or substitute
a model hypothesis. Render an actual event sequence in human terms instead
of an unrelated command-issuer/battery catalog. All facts must originate from
verified target-scoped historical event receipts.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Mapping


def _stamp(event: Mapping[str, Any]) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(event["date"]).replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError, KeyError):
        return None


def operational_sequence_brief(
    coverage: Mapping[str, Any] | None,
    display_name: str,
) -> dict[str, Any] | None:
    """Return a bounded, source-grounded change chronology if it explains action.

    This is a generic actuator/setpoint-to-operating-state correlation, not
    proof the automation made the physical system change. The model may make
    a richer causal assessment if it supplies source-citable evidence.
    """
    if not isinstance(coverage, Mapping):
        return None
    rows = coverage.get("material_event_examples")
    if not isinstance(rows, list) or len(rows) < 3:
        return None
    events = [e for e in rows if isinstance(e, Mapping)
              and _stamp(e) is not None]
    events.sort(key=lambda e: _stamp(e))
    # A thermostat's reported operating-state transition and the explicit
    # setpoint change from a named controller form a useful universal
    # control/response sequence. Values must be *real* source event states.
    states = [e for e in events if e.get("name") == "thermostatOperatingState"
              and str(e.get("value")).lower() in ("heating", "idle")]
    settings = [e for e in events
                if e.get("name") in ("heatingSetpoint", "thermostatSetpoint")
                and e.get("source_kind") == "issuing_app"
                and e.get("value") is not None]
    if len(states) < 2 or len(settings) < 2:
        return None
    for stopped in reversed(states):
        if str(stopped.get("value")).lower() != "idle":
            continue
        stop_time = _stamp(stopped)
        starts = [e for e in states if str(e.get("value")).lower() == "heating"
                  and _stamp(e) < stop_time
                  and stop_time - _stamp(e) <= timedelta(hours=3)]
        if not starts:
            continue
        last_started = starts[-1]
        before = [e for e in settings if _stamp(e) <= stop_time]
        if len(before) < 2:
            continue
        last_target = before[-1]
        prior = [e for e in before[:-1] if str(e.get("value")) != str(last_target.get("value"))]
        if not prior:
            continue
        prior_target = prior[-1]
        after_target = (stop_time - _stamp(last_target)).total_seconds()
        if not 0 <= after_target <= 180:
            continue
        if _stamp(prior_target) > _stamp(last_started) + timedelta(minutes=4):
            continue
        issuer = str(last_target.get("source_name") or "").strip()
        issuer = issuer if issuer and len(issuer) <= 75 else "the controlling automation"
        old = str(prior_target["value"])
        new = str(last_target["value"])
        name = display_name if isinstance(display_name, str) and display_name.strip() else "the thermostat"
        name = name.strip()[:90]
        start = _stamp(last_started).strftime("%H:%M")
        lowered = _stamp(last_target).strftime("%H:%M")
        idle = stop_time.strftime("%H:%M")
        return {
            "text": (
                f"**Likely explanation:** {name} stopped heating when {issuer} "
                f"changed its heating target from {old}°C to {new}°C at {lowered}. "
                f"The thermostat had reported heating at {start} and reported "
                f"idle at {idle}. This looks like a controlled change in heating "
                f"demand, rather than an unexplained loss of communication. "
                f"**Not established:** These device events do not show which "
                f"room thermostat or radiator triggered the scheduler's decision."
            ),
            "evidence_events": [
                {"read":e["read"],"name":e["name"],"date":e["date"]}
                for e in (prior_target,last_started,last_target,stopped)
            ],
            "cause_verified": False,
            "source": "attested_control_and_operating_state_sequence",
        }
    return None


__all__ = ["operational_sequence_brief"]
