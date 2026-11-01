"""Opt-in, read-only model-first publication boundary for device telemetry.

This is a deliberately narrow vertical slice of HomeBrain vNext: keep the
model's genuine original explanation when request-local provenance and minimum
high-risk source consistency checks pass. It does NOT semantically certify
arbitrary prose. On failure the established source-typed renderer takes over.

No MCP actions, source discovery, command permissions, extra model calls,
hardware writes or credential handling happen in this module.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from model_first_draft_provenance import PrivateModelDraft

_UNCERTAINTY = re.compile(
    r"\b(?:uncertain|unknown|unverified|not proven|not verified|"
    r"does not (?:prove|establish|verify)|cannot (?:confirm|verify|establish)|"
    r"can't (?:confirm|verify|establish)|may|might|possible|unresolved)\b",
    re.IGNORECASE,
)
# Block only high-risk *definitive* root-cause/execution assertions in a
# source window explicitly lacking root-cause proof. This conservative gate
# cannot establish semantic entailment; other attribution guards still run.
_UNPROVEN_CAUSE = re.compile(
    r"\b(?:root cause (?:is|was)|(?:outage|failure|disconnect|"
    r"offline status|problem) (?:is|was) caused by|"
    r"(?:definitely|certainly|confirmedly) (?:caused|offline|disconnected)|"
    r"(?:turned off|went offline|disconnected) because of|"
    r"(?:physical|device) (?:power|operation) (?:is|was) confirmed)\b",
    re.IGNORECASE,
)
_FALSE_PHYSICAL_PROOF = re.compile(
    r"\b(?:mqttStatus|mqtt (?:being|is|was)?\s*connected)\b.{0,100}"
    r"\b(?:proves?|confirms?|guarantees?)\b.{0,90}"
    r"\b(?:plug|endpoint|physical|online|powered|reachable)\b|"
    r"\b(?:last (?:real|genuine|physical) (?:packet|contact)|"
    r"independently confirmed (?:offline|unreachable)|"
    r"(?:ping|icmp) (?:confirmed|proves?|shows?))\b",
    re.IGNORECASE | re.DOTALL,
)
_NON_READ_ONLY_ACTION = re.compile(
    r"\b(?:I (?:restarted|rebooted|switched|reset|changed|unplugged)|"
    r"(?:I|the assistant) (?:sent|issued|executed) (?:an? )?"
    r"(?:off|on|restart|reset) command)\b",
    re.IGNORECASE,
)


def admit_model_first_telemetry_answer(
    incoming: Any,
    trace: Any,
    normalized: Mapping[str, Any] | None,
    coverage: Mapping[str, Any] | None,
) -> tuple[str | None, str]:
    """Allow an unmodified model-authored telemetry answer or explain fallback.

    The post-coordinator/post-author output must match the original provider
    draft AND the incoming API boundary. Otherwise an intermediate safety
    repair may have changed its meaning; never bypass that repair. A later
    expansion may admit independently reviewed host-calibrated prose.
    """
    if not isinstance(normalized, Mapping) or not isinstance(coverage, Mapping):
        return None, "missing-typed-evidence"
    state = normalized.get("reportedDeviceState")
    device_id = str(normalized.get("deviceId") or "")
    if (
        not device_id.isdecimal()
        or not isinstance(state, Mapping)
        or str(state.get("deviceId") or "") != device_id
        or state.get("source") != "targeted-hubitat-device-state"
        or state.get("isPhysicalConnectivityProof") is True
        or coverage.get("rootCauseVerified") is not False
        or normalized.get("truncated") is True
        or normalized.get("commandCount") != 0
    ):
        return None, "unverified-source-scope"
    if (
        not isinstance(trace, PrivateModelDraft)
        or not trace.no_tools_final_stage
        or not isinstance(trace.raw_first, str)
        or trace.raw_first != trace.coordinator_result
        or trace.raw_first != trace.final_answer
        or trace.raw_first != incoming
    ):
        return None, "model-draft-provenance-changed"
    answer = trace.raw_first.strip()
    if (
        len(answer) < 100 or len(answer) > 5500
        or answer.startswith(("{", "[", "```"))
        or "\x00" in answer
    ):
        return None, "not-a-natural-explanation"
    attrs = state.get("reportedAttributes")
    if not isinstance(attrs, Mapping):
        return None, "missing-reported-attributes"
    health = str(attrs.get("healthStatus") or "").strip()
    if not health or health.casefold() not in answer.casefold():
        return None, "reported-health-omitted"
    mqtt = str(attrs.get("mqttStatus") or "").strip()
    if mqtt and "mqtt" not in answer.casefold():
        return None, "broker-versus-endpoint-omitted"
    if not _UNCERTAINTY.search(answer):
        return None, "material-uncertainty-omitted"
    if _UNPROVEN_CAUSE.search(answer):
        return None, "unverified-definitive-cause"
    if _FALSE_PHYSICAL_PROOF.search(answer):
        return None, "unverified-physical-telemetry"
    if _NON_READ_ONLY_ACTION.search(answer):
        return None, "unverified-action-claim"
    return answer, "model-authored-bounded-telemetry"


__all__ = ["admit_model_first_telemetry_answer"]
