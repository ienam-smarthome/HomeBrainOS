"""Evidence-completion contract for read-only investigations.

A room inventory or target-ID lookup is discovery, not an answer to the
user's diagnostic objective. Decide completeness from current-turn receipts,
not from the model's confident wording or the route that reached the agent.
Never authorize writes or assume unseen evidence exists.
"""
from __future__ import annotations

from typing import Any
import re

from ai_investigation_routing import active_request_interpretation
from investigation_checkpoint import is_investigative_question


_SUBSTANTIVE_READS = frozenset((
    "hub_get_app_config", "hub_get_source", "hub_get_rule_health",
    "hub_get_visual_rule", "hub_list_device_events", "hub_get_logs",
    "homebrain_device_history", "homebrain_read_groovy_source",
    "homebrain_motion_lockout_investigation",
    "homebrain_causal_trigger_correlation",
    "hub_get_device",  # useful live attributes, but identity-only does not count
))
_OBSERVATION_READS = _SUBSTANTIVE_READS - frozenset(("hub_get_device",))
_LOCAL_INVENTORY = frozenset(("homebrain_device_inventory",))


def investigating(prompt: str) -> bool:
    decision = active_request_interpretation(prompt)
    if decision is not None:
        return (
            decision.route == "model_led"
            and decision.objective not in ("system_audit", "performance_report")
        )
    return is_investigative_question(prompt)


def _leaf(row: dict[str, Any]) -> str:
    args = row.get("arguments")
    return str(
        row.get("sub_tool")
        or (args.get("tool") if isinstance(args, dict) else "")
        or row.get("tool") or ""
    )


def observation_sources(receipts: list[dict[str, Any]]) -> tuple[str, ...]:
    found = set()
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("mutates") is True or row.get("effect") not in (None, "read"):
            continue
        leaf = _leaf(row)
        if leaf not in _OBSERVATION_READS:
            continue
        found.add(leaf)
    return tuple(sorted(found))


def inventory_without_investigation(
    prompt: str, receipts: list[dict[str, Any]]
) -> bool:
    """True only for an investigative objective with no substantive reads."""
    return investigating(prompt) and not observation_sources(receipts)


_INVENTORY_PRESENTATION = re.compile(
    r"(?i)^\\s*(?:\\d+\\s+(?:Hubitat\\s+)?devices?\\s+"
    r"(?:in\\s+\\*\\*|across\\s+\\d+\\s+groups?)|"
    r"\\*\\*?Living Room\\*\\*?:?\\s*\\d+\\s+devices?)"
)


def inventory_answer(message: str) -> bool:
    """Answer-format validation, not another intent/router keyword rule."""
    text = str(message or "").strip()
    return bool(_INVENTORY_PRESENTATION.match(text))


def retry_instruction(prompt: str, receipts: list[dict[str, Any]]) -> str:
    decision = active_request_interpretation(prompt)
    goal = str(decision.purpose if decision and decision.purpose else prompt).strip()
    target = str(decision.target if decision and decision.target else "the requested device").strip()
    return (
        "HOST INVESTIGATION COMPLETION GATE (READ-ONLY): Current reads "
        "established at most device identity, attributes, room membership "
        "or dependent names, not the requested diagnosis. "
        "An inventory list is NOT an answer to this objective. "
        f"Investigate target {target!r}; original goal: {goal[:1200]}. "
        "Select a relevant advertised READ-ONLY source now: actual controlling "
        "app configuration, source implementation if needed, time-bounded "
        "device/sensor events, or app decision logs. "
        "Use existing exact IDs from prior receipts. Do not re-read the "
        "room inventory, speculate about unobserved code, or issue writes. "
        "A clone/virtual/soft sensor is not independent occupancy proof; "
        "verify the physical parent and whether it is an actual configured "
        "input before attributing any timer decision to it. "
        "If unavailable, say what cannot be established instead of inventing a cause."
    )


def honest_partial_answer(prompt: str, receipts: list[dict[str, Any]]) -> str:
    decision = active_request_interpretation(prompt)
    target = str(decision.target if decision and decision.target else "the requested device").strip()
    return (
        f"I found device/room information for {target}, but could not verify "
        "the controlling automation's execution, sensor activity or inactivity "
        "timer from the available evidence. The cause is not established. "
        "An inventory list would not answer the investigation."
    )
