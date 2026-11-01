"""Read-only cross-domain command witness adapter (not production publication).

Build candidate claim IDs solely from a uniquely identified, time-scoped,
app-issued command in returned Hubitat device events. This does NOT interpret
a later state report as physical execution, identify the app's upstream
trigger, or enable model prose on the historical/lighting/heating routes.
It provides reusable evidence contracts for offline negative-control tests.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from historical_command_source_contract import focused_command_observation
from source_claim_contract import admit_source_claim_plan

_NAMED_TARGET = re.compile(r"(?i)\bdevice\s*(?:id\s*)?[#:]?\s*(\d{2,9})\b")
_REQUIRED = frozenset({"recorded_command", "upstream_unknown", "execution_unknown"})


def attested_recorded_command_claims(
    request: str, evidence: list[dict[str, Any]],
) -> dict[str, str]:
    """Source-recorded command issuer, with no inferred physical or rule cause."""
    explicitly_named = set(_NAMED_TARGET.findall(request or ""))
    if len(explicitly_named) != 1 or not isinstance(evidence, list):
        return {}
    observed = focused_command_observation(request, evidence)
    if not isinstance(observed, dict):
        return {}
    target_id = str(observed.get("deviceId") or "")
    issuer = str(observed.get("recordedIssuerAppId") or "")
    action = str(observed.get("command") or "")
    timestamp = observed.get("recordedCommandTimestamp")
    if (
        target_id not in explicitly_named or not issuer.isdecimal()
        or action not in {"on", "off"}
        or observed.get("source") != "same-turn Hubitat device-event command record"
        or observed.get("commandRecorded") is not True
        or any(observed.get(key) is not False for key in (
            "deliveryVerified", "physicalActuationVerified", "upstreamTriggerVerified"
        ))
        or not isinstance(timestamp, str)
    ):
        return {}
    try:
        event_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if event_time.tzinfo is None:
            return {}
    except ValueError:
        return {}
    return {
        "recorded_command": (
            f"Hubitat recorded an {action.upper()} command for device "
            f"{target_id} at {event_time.isoformat()}, attributed to app {issuer}."
        ),
        "upstream_unknown": (
            "This command record does not establish what triggered the app "
            "or why it decided to issue the command."
        ),
        "execution_unknown": (
            "A recorded command does not independently establish delivery, "
            "device acknowledgement or physical execution."
        ),
    }


def admit_recorded_command_plan(
    draft: Any, request: str, evidence: list[dict[str, Any]],
) -> tuple[str | None, str]:
    """Only admit witness-derived claim IDs; not invoked by live publisher."""
    return admit_source_claim_plan(
        draft, attested_recorded_command_claims(request, evidence), _REQUIRED,
    )


__all__ = ["attested_recorded_command_claims", "admit_recorded_command_plan"]
