"""Model-free native Rule Machine authoring for an exact, guarded night-idle OFF.

This module ONLY prepares a proposal for the existing user-confirmation
pipeline. It never executes hub_set_rule or a device command. Do not broaden
intent matching to arbitrary lighting requests: extra requirements would be
silently dropped and could make an active rule unsafe.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable

from mcp_client import HubitatMCPClient, tool_succeeded
from rule_authoring_service import (
    RULE_MACHINE_GATEWAY, RuleAuthoringDecision, RuleAuthoringService,
)
from tool_registry import rule_machine_proposal_error

_RULE_NAME = re.compile(r"['\"]([^'\"\n]*night\s+idle\s+off[^'\"\n]*)['\"]", re.I)
_CREATION = re.compile(r"^\s*(?:please\s+)?(?:create|build|add|write|install)\b", re.I)
_TEN_MINUTES = re.compile(r"\b10\s+(?:(?:continuous|uninterrupted|full)\s+)?minutes?\b", re.I)
_ACTIVE = re.compile(r"\bactive\b", re.I)
_DENY = re.compile(
    r"\b(?:do\s+not|don't|never)\s+(?:create|activate|write|install)\b"
    r"|\b(?:read.only|proposal.only|design.only)\b", re.I,
)
_EXTRA_ACTION = re.compile(
    r"\b(?:turn\s+on|switch\s+on|dim|set\s+(?:level|colour|color)|"
    r"send\s+(?:notification|alert)|change\s+mode)\b", re.I,
)

def recognise_night_idle_creation(prompt: str) -> str | None:
    """Return the EXACT requested name for the bounded authoring grammar."""
    prompt = str(prompt or "").strip()
    if not _CREATION.search(prompt):
        return None
    # ACTIVE must modify the *creation request*, not appear only in a
    # subsequent clause such as "cancel when motion becomes active".
    name_candidate = _RULE_NAME.search(prompt)
    if name_candidate is None:
        return None
    intro = prompt[:name_candidate.start()]
    if not _ACTIVE.search(intro) or re.search(r"\bdisabled\b", intro, re.I):
        return None
    if _DENY.search(prompt):
        # "do not create duplicates" is a safety restriction, not a ban.
        if _DENY.search(prompt.replace("do not create duplicates", "")
                        .replace("Do not create duplicates", "")):
            return None
    match = _RULE_NAME.search(prompt)
    if not match or len(match.group(1)) > 120:
        return None
    lowered = prompt.casefold()
    if not all(part in lowered for part in (
        "7805", "7978", "23:00", "06:00",
    )) or not _TEN_MINUTES.search(prompt):
        return None
    if not ("motion" in lowered and "inactive" in lowered):
        return None
    # A request with additional actuation requirements cannot be reduced to
    # an OFF-only compiler. "light turns ON" is an event requirement, not an
    # instruction to automatically issue an ON command, so avoid interpreting
    # that particular phrase as actuator authority.
    if _EXTRA_ACTION.search(prompt) and not re.search(
        r"\b(?:never|do\s+not)\s+(?:turn|switch)\s+on\b", prompt, re.I
    ):
        return None
    return match.group(1).strip()


def _device_record(value: Any, expected_id: str, *, depth: int = 0) -> dict[str, Any] | None:
    if depth > 4:
        return None
    if isinstance(value, dict):
        if str(value.get("id") or value.get("deviceId") or "").strip() == expected_id:
            return value
        for key in ("device", "details", "result", "data", "output", "target"):
            nested = _device_record(value.get(key), expected_id, depth=depth + 1)
            if nested is not None:
                return nested
    return None


def _capability_labels(device: dict[str, Any]) -> set[str]:
    # Upstream hub_get_device(mode="details") returns capabilities under
    # sections.attributes.capabilities, not at the device-record root.
    # A top-level capabilities array occurs in other live device read modes;
    # support both without inferring from device name or driver type.
    sections = device.get("sections")
    attributes = (
        sections.get("attributes") if isinstance(sections, dict) else None
    )
    sources = [device.get("capabilities")]
    if isinstance(attributes, dict):
        sources.append(attributes.get("capabilities"))
    result: set[str] = set()
    for values in sources:
        if isinstance(values, dict):
            values = list(values)
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                value = value.get("name") or value.get("capability")
            if value:
                result.add(str(value).casefold().replace(" ", ""))
    return result


def night_idle_write(name: str) -> dict[str, Any]:
    """Canonical seven-action program; no model-produced JSON is trusted."""
    condition = {
        "operator": "AND",
        "conditions": [
            {"capability": "Motion", "deviceIds": ["7978"], "state": "inactive"},
            {"capability": "Switch", "deviceIds": ["7805"], "state": "on"},
            {"capability": "Between two times",
             "start": {"type": "clock", "time": "23:00"},
             "end": {"type": "clock", "time": "06:00"}},
        ],
    }
    return {
        "tool": "hub_set_rule",
        "args": {
            "name": name,
            "addTriggers": [
                {"capability": "Motion", "deviceIds": ["7978"], "state": "inactive"},
                {"capability": "Switch", "deviceIds": ["7805"], "state": "on"},
                {"capability": "Certain Time (and optional date)",
                 "time": "A specific time", "atTime": "23:00"},
                {"capability": "Motion", "deviceIds": ["7978"], "state": "active"},
                {"capability": "Certain Time (and optional date)",
                 "time": "A specific time", "atTime": "06:00"},
                {"capability": "Switch", "deviceIds": ["7805"], "state": "off"},
            ],
            "addActions": [
                {"capability": "cancelDelay"},
                {"capability": "ifThen", "expression": condition},
                {"capability": "delay", "minutes": 10, "cancelable": True},
                {"capability": "ifThen", "expression": condition},
                {"capability": "switch", "action": "off", "deviceIds": ["7805"]},
                {"capability": "endIf"},
                {"capability": "endIf"},
            ],
        },
    }


async def propose_night_idle(
    prompt: str, *,
    mcp: HubitatMCPClient,
    record_evidence: Callable[..., Any],
    rules: RuleAuthoringService,
    available_gateways: set[str],
) -> RuleAuthoringDecision | None:
    name = recognise_night_idle_creation(prompt)
    if name is None:
        return None
    def stop(explanation: str) -> RuleAuthoringDecision:
        return RuleAuthoringDecision(
            True, "No rule was created or queued. " + explanation,
            rule_names=(name,),
        )
    if RULE_MACHINE_GATEWAY not in available_gateways:
        return stop(
            "The actual hub_manage_rule_machine write gateway is not "
            "available or enabled in the MCP tool list."
        )
    # Read the exact rules list before building a new named automation.
    # This lookup is REPEATED by the confirmation executor before writing.
    actions = (night_idle_write(name),)
    duplicate = await rules.duplicate_create_group_error(list(actions))
    if duplicate:
        return stop(duplicate)
    # Identity/capability checks are targeted and cannot silently replace
    # FP400 by the similarly named FP300 Toilet sensor.
    for device_id, capability in (("7805", "switch"), ("7978", "motionsensor")):
        # Request only attributes; omitting sections can force the entire
        # expanded device snapshot into a paginated json-fragment. The
        # current MCP server exposes caps in sections.attributes.
        arguments = {"tool": "hub_get_device",
                     "args": {"deviceId": device_id, "mode": "details",
                              "sections": ["attributes"]}}
        started = time.monotonic()
        try:
            result = await mcp.call_tool("hub_read_devices", arguments)
            record = _device_record(result.data, device_id)
            ok = tool_succeeded(result) and record is not None
            labels = _capability_labels(record or {})
            capability_ok = (capability in labels or
                             (capability == "motionsensor" and "motion" in labels))
            record_evidence(
                "hub_read_devices", arguments, success=ok,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                supports_live_claim=True, evidence_kind="native_rule_target_preflight",
                summary=f"device {device_id}: identity={'verified' if ok else 'unverified'}; "
                        f"required capability={'verified' if capability_ok else 'unverified'}",
            )
        except Exception:
            return stop(f"Device {device_id} could not be read and verified.")
        if not ok:
            return stop(f"Device {device_id} identity is not established by the live MCP read.")
        if labels and not capability_ok:
            return stop(
                f"Device {device_id} does not advertise the required "
                f"{capability} capability; no alternative device was substituted."
            )
        if not labels:
            return stop(
                f"Device {device_id} returned no usable capability list. "
                "The native authoring preflight cannot prove it is suitable."
            )
    guide_arguments = {"section": "set_rule_reference_actions"}
    started = time.monotonic()
    try:
        guide = await mcp.call_tool("hub_get_tool_guide", guide_arguments)
        data = guide.data if isinstance(guide.data, dict) else {}
        text = str(data.get("content") or "")
        guide_ok = tool_succeeded(guide) and all(
            term in text for term in ("ifThen", "cancelDelay", "delay", "endIf")
        )
        record_evidence(
            "hub_get_tool_guide", guide_arguments, success=guide_ok,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            supports_live_claim=guide_ok, evidence_kind="native_rule_schema_preflight",
            summary="Current native action subtype guide verified"
                    if guide_ok else "Native action guide incomplete/unavailable",
        )
    except Exception:
        guide_ok = False
    if not guide_ok:
        return stop("The live native action subtype guide was not independently verified.")
    proposal_error = rule_machine_proposal_error(
        RULE_MACHINE_GATEWAY, actions[0], user_prompt=prompt,
    )
    if proposal_error:
        return stop("The complete native proposal did not validate: " + proposal_error)
    # Final exact-name duplicate check, and again after confirmation.
    duplicate = await rules.duplicate_create_group_error(list(actions))
    if duplicate:
        return stop(duplicate)
    return RuleAuthoringDecision(
        True, actions=actions, rule_names=(name,),
        target={"deviceId": "7805", "motionDeviceId": "7978"},
    )


__all__ = ["night_idle_write", "recognise_night_idle_creation", "propose_night_idle"]
