"""Proof-carrying model-directed answer assembly for bounded device telemetry.

The model may choose/order *typed source claims* in its first no-tools final
response. It cannot author arbitrary sentences and receive a source certificate:
we render only independently normalized and fixed text. An unknown claim,
spurious prose, missing material uncertainty or changed raw draft fails closed
to the already established evidence-first publisher.

The claim envelope is an answer plan, not natural-language entailment and not
independent proof of physical state or upstream causation. Other domains fail
closed until they offer equivalent typed proof adapters.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from source_claim_contract import SCHEMA, admit_source_claim_plan
_SAFE = re.compile(r"^[\w .:/+\\-]{1,90}$", re.UNICODE)


def _scalar(value: Any, max_length: int = 90) -> str | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    value = str(value).strip()
    if not value or len(value) > max_length or not _SAFE.fullmatch(value):
        return None
    return value


def attested_telemetry_claims(
    normalized: Mapping[str, Any] | None,
    coverage: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Construct strictly source-typed statements, not proposed LLM facts."""
    if not isinstance(normalized, Mapping) or not isinstance(coverage, Mapping):
        return {}
    device_id = str(normalized.get("deviceId") or "")
    state = normalized.get("reportedDeviceState")
    if not device_id.isdecimal() or not isinstance(state, Mapping):
        return {}
    if (str(state.get("deviceId") or "") != device_id
            or state.get("source") != "targeted-hubitat-device-state"
            or state.get("isPhysicalConnectivityProof") is True):
        return {}
    if normalized.get("truncated") is True or normalized.get("eventHistoryComplete") is True:
        return {}
    if normalized.get("sourceIntegrityVerified") is True:
        # The source packet may be complete; this bounded-only contract does
        # not silently substitute for independent source-integrity validation.
        pass
    commands = normalized.get("commandCount")
    states = normalized.get("stateEventCount")
    returned = normalized.get("returnedEvents")
    if (type(commands) is not int or commands != 0 or type(states) is not int
            or type(returned) is not int or states != returned
            or returned < 1 or returned > 200):
        return {}
    if coverage.get("rootCauseVerified") is not False:
        return {}
    label = _scalar(normalized.get("deviceLabel"))
    attrs = state.get("reportedAttributes")
    if not label or not isinstance(attrs, Mapping):
        return {}
    health = _scalar(attrs.get("healthStatus"))
    mqtt = _scalar(attrs.get("mqttStatus"))
    if not health:
        return {}
    facts = {
        "reported_health": (
            f"Hubitat reports {label} healthStatus={health}; this is saved "
            "driver state, not independent proof of physical reachability."
        ),
        "source_scope": (
            f"The bounded device history returned {states} state reports "
            "and no recorded commands; completeness is not independently proven."
        ),
        "cause_unverified": (
            "The available source records do not establish whether "
            "the physical endpoint is reporting, accepting commands, or why "
            "its currently reported health state has that value."
        ),
        "next_readonly": (
            "The next read-only check is to compare genuine endpoint-originated "
            "packets with broker traffic and the installed driver's status-update logic."
        ),
    }
    if mqtt:
        facts["reported_mqtt"] = (
            f"Hubitat also reports mqttStatus={mqtt}, which does not "
            "verify that the endpoint is sending fresh data."
        )
    clock = coverage.get("telemetryClockConsistency")
    if (isinstance(clock, Mapping) and clock.get("sourcesAgree") is False
            and str(clock.get("deviceId") or "") == device_id):
        # We avoid model-derived age values and floating point formatting.
        facts["clock_conflict"] = (
            "The saved lastSeen and dataAgeSeconds metadata disagree; "
            "neither is independently verified as the last physical packet."
        )
    latest = normalized.get("latestReturnedStateEvent")
    if isinstance(latest, Mapping):
        attribute, value = _scalar(latest.get("attribute")), _scalar(latest.get("value"))
        date = _scalar(latest.get("date"))
        if attribute and value and date:
            facts["latest_report"] = (
                f"The latest returned report is {attribute}={value} at {date}; "
                "this is a Hubitat event, not a verified physical packet."
            )
    return facts


def model_claim_prompt(
    normalized: Mapping[str, Any] | None,
    coverage: Mapping[str, Any] | None,
) -> str | None:
    """No extra model calls; optional exact claim-ID response for final synthesis."""
    facts = attested_telemetry_claims(normalized, coverage)
    if not facts:
        return None
    display = "\n".join(f"- {key}: {value}" for key, value in facts.items())
    mandatory = ["reported_health"]
    mandatory += [x for x in ("reported_mqtt", "clock_conflict") if x in facts]
    mandatory += ["cause_unverified", "next_readonly"]
    example = json.dumps({"schema": SCHEMA, "claim_ids": mandatory}, separators=(",", ":"))
    return (
        "REQUIRED FINAL ANSWER FORMAT FOR THIS VERIFIED SOURCE PACKET: "
        "Output ONLY ONE JSON object (no Markdown fences or prose), with "
        "exactly two keys, e.g. " + example + ". "
        "The host will turn your chosen source-backed facts into the "
        "natural-language user-facing answer. "
        "Select 3-7 distinct claim IDs ONLY from the source-backed facts "
        "below, in the order that best answers the original question. "
        "You MUST include reported_health, cause_unverified and next_readonly; "
        "include reported_mqtt and clock_conflict whenever available. "
        "Do not include free-form explanation, comments or claims not in the "
        "source list. Unknown or unsupported output will be rejected and "
        "an evidence-safe fallback will be shown instead. "
        "Do not claim root-cause certainty, physical packet delivery or "
        "device reachability. This plan does not grant write permission.\n"
        + display
    )


def admit_model_claim_plan(
    draft: Any, normalized: Mapping[str, Any] | None,
    coverage: Mapping[str, Any] | None,
) -> tuple[str | None, str]:
    """Telemetry source adapter: select only receipt-attested host sentences."""
    facts = attested_telemetry_claims(normalized, coverage)
    mandatory = {"reported_health", "cause_unverified", "next_readonly"}
    mandatory.update(key for key in ("reported_mqtt", "clock_conflict") if key in facts)
    return admit_source_claim_plan(draft, facts, mandatory)


__all__ = [
    "SCHEMA", "attested_telemetry_claims", "model_claim_prompt",
    "admit_model_claim_plan",
]
