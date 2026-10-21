"""Live, read-only capability preflight for stateful native Rule Machine authoring.

The goal is not to invent a permanent DSL from one working Claude example:
the installed hub's *own* tool guide determines whether periodic triggers,
variables, nested actions and switch controls are actually authorable.

No tool in this module mutates Hubitat. Existing confirmation, duplicate,
authorization and gateway validators remain responsible for write proposals.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable

_GUIDE_SECTIONS = (
    "set_rule_reference_triggers",
    "set_rule_reference_actions",
    "set_rule_reference_conditions",
    "variables",
)
_MANDATORY = {
    "set_rule_reference_triggers": ("periodic schedule", "device-state"),
    "set_rule_reference_actions": ("setvariable", "ifthen", "endif", "add number", "switch"),
    "set_rule_reference_conditions": ("variable",),
}
_MAX_CHARS_PER_SECTION = 14500


@dataclass(frozen=True)
class StatefulAuthoringPreflight:
    ready: bool
    instruction: str
    checked: tuple[str, ...]
    missing: tuple[str, ...]


def _extract_content(result: Any) -> str:
    if getattr(result, "is_error", False):
        return ""
    data = getattr(result, "data", None)
    if not isinstance(data, dict) or data.get("success") is False:
        return ""
    return str(data.get("content") or "").strip()


async def inspect_stateful_rule_capabilities(
    mcp: Any,
    record_evidence: Callable[..., Any],
    available_names: set[str] | frozenset[str],
) -> StatefulAuthoringPreflight:
    """Ground the proposed rule in bounded read-only live references.

    The dynamic tools' metadata and docs are authority, NOT unconditional
    permission to change the hub. Fail closed if any required reference is
    absent, incomplete or does not advertise the needed capability family.
    """
    needed_tools = ("hub_get_tool_guide", "hub_manage_rule_machine")
    missing_tools = [name for name in needed_tools if name not in available_names]
    if missing_tools:
        return StatefulAuthoringPreflight(
            False,
            "No automation was created or queued. Live Rule Machine authoring "
            "cannot be verified because the following tool(s) are unavailable: "
            + ", ".join(missing_tools) + ". No Hubitat settings were changed.",
            (), tuple(missing_tools),
        )

    checked: list[str] = []
    missing: list[str] = []
    reference: list[str] = []
    for section in _GUIDE_SECTIONS:
        arguments = {"section": section}
        started = time.monotonic()
        try:
            result = await mcp.call_tool("hub_get_tool_guide", arguments)
            content = _extract_content(result)
        except Exception:
            content = ""
        matched = [part for part in _MANDATORY.get(section, ()) if part in content.casefold()]
        required = _MANDATORY.get(section, ())
        ok = bool(content) and len(matched) == len(required)
        record_evidence(
            "hub_get_tool_guide", arguments,
            success=bool(content),
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=(section + ": " +
                     ("live guide read" if content else "live guide unavailable") +
                     (", missing " + ", ".join(set(required) - set(matched)) if required and not ok else "")),
            supports_live_claim=False,
            evidence_kind="stateful_rule_capability_reference",
        )
        if not ok:
            missing.append(section)
            continue
        checked.append(section)
        # Bound provider token use; a truncated guide is reference context,
        # never proof that omitted operations are supported.
        reference.append("LIVE GUIDE " + section + "\n" +
                         content[:_MAX_CHARS_PER_SECTION])

    if missing:
        return StatefulAuthoringPreflight(
            False,
            "No automation was created or queued. The connected Hubitat MCP "
            "server has not positively established every necessary Rule Machine "
            "authoring capability. Missing or incomplete live tool-guide "
            "sections: " + ", ".join(missing) + ". "
            "Inspect those sections or update the MCP server; do not construct "
            "a partial rule, guess action fields, or change another rule.",
            tuple(checked), tuple(missing),
        )

    return StatefulAuthoringPreflight(
        True,
        (
            "STATEFUL RULE MACHINE AUTHORING — HOST-VERIFIED READ-ONLY REFERENCES\n"
            "The live installed MCP tool guide advertises periodic triggers, "
            "device-state triggers, nested IF/ELSE/END-IF actions, variable "
            "arithmetic, switch commands and variable conditions. This is "
            "evidence of advertised authoring capabilities, NOT proof of a "
            "working compiled automation. Follow the precise fields from "
            "the live references below, and call the gateway's read-only "
            "addTrigger/addAction {discover:true} schema probes if more "
            "fields are needed. Build the smallest COMPLETE independently "
            "named Rule Machine proposal via hub_manage_rule_machine / "
            "hub_set_rule. Do NOT execute confirmed writes: submit the "
            "structured proposal for host confirmation. Verify both the "
            "accumulation path and reset path, including whether a brief "
            "block then unblock between minute ticks resets the counter. "
            "Do not pause, edit, delete or otherwise alter existing rules "
            "unless the user independently approved doing so. "
            "An ordinary switch on/off event does not prove its human issuer. "
            "Never claim installed/live based on the proposal alone.\n\n"
            + "\n\n".join(reference)
        ),
        tuple(checked), (),
    )

def cumulative_rule_proposal_error(arguments: dict[str, Any]) -> str | None:
    """Check that a proposed SINGLE-RULE accumulated-usage topology is complete.

    This complements the upstream schema/confirmation gates; it does not
    claim correctness of every condition or execute any action. A partial
    create with a periodic trigger and an off command is NOT a valid
    cumulative allowance. The model may retry with the live guide.
    """
    if arguments.get("tool") != "hub_set_rule":
        return None
    payload = arguments.get("args")
    if not isinstance(payload, dict):
        return "Cumulative automation needs a direct structured rule payload."
    if payload.get("appId") not in (None, ""):
        return "Requested NEW cumulative automation must not edit an existing Rule Machine rule."

    triggers = payload.get("addTriggers") or ([payload["addTrigger"]] if isinstance(payload.get("addTrigger"), dict) else [])
    actions = payload.get("addActions") or ([payload["addAction"]] if isinstance(payload.get("addAction"), dict) else [])
    if not isinstance(triggers, list) or not isinstance(actions, list):
        return "Cumulative automation requires complete typed trigger and action arrays."
    if not any(
        isinstance(t, dict) and str(t.get("capability", "")).casefold() == "periodic schedule"
        and isinstance(t.get("periodic"), dict)
        and str(t["periodic"].get("frequency", "")).casefold() == "minutes"
        and t["periodic"].get("everyN") == 1
        for t in triggers
    ):
        return "Missing the native every-1-minute periodic schedule trigger."
    if not any(
        isinstance(t, dict) and str(t.get("capability", "")).casefold() == "switch"
        and str(t.get("state", "")).casefold() == "off"
        for t in triggers
    ):
        return (
            "Missing an Internet-control switch-OFF event trigger; a periodic-only "
            "rule can miss a quick block/unblock and immediately block again."
        )

    capabilities = [
        str(a.get("capability") or "").casefold() if isinstance(a, dict) else ""
        for a in actions
    ]
    if "ifthen" not in capabilities or "endif" not in capabilities:
        return "Missing complete IF/END-IF conditional action structure."
    depth = 0
    for cap in capabilities:
        if cap == "ifthen":
            depth += 1
        elif cap in {"elseif", "else"}:
            if depth == 0:
                return "ELSE/ELSE-IF lacks a matching IF action."
        elif cap == "endif":
            depth -= 1
            if depth < 0:
                return "END-IF has no matching IF action."
    if depth:
        return "Unclosed IF/END-IF block in cumulative-allowance actions."

    variable_actions = [
        a for a in actions if isinstance(a, dict)
        and str(a.get("capability") or "").casefold() in {"setvariable", "setlocalvariable"}
    ]
    if not variable_actions:
        return "No variable actions; cannot accumulate and reset usage."
    increments = [
        a for a in variable_actions
        if str(a.get("numOp") or "").casefold() == "add number"
        or (isinstance(a.get("math"), dict)
            and str(a["math"].get("op")) == "+")
    ]
    if not increments:
        return "No supported arithmetic increment of accumulated usage."
    resets = [
        a for a in variable_actions
        if a.get("value") in (0, 0.0, "0") and not a.get("numOp")
    ]
    if not resets:
        return "No explicit zero reset of the accumulated-usage variable."
    targets = {str(a.get("variable") or "").casefold() for a in increments}
    if not targets or not any(str(a.get("variable") or "").casefold() in targets for a in resets):
        return "Increment and reset must address the same verified variable."
    if not any(
        isinstance(a, dict)
        and (
            (str(a.get("capability") or "").casefold() == "switch"
             and str(a.get("action") or "").casefold() == "off")
            or (str(a.get("capability") or "").casefold() == "runcommand"
                and str(a.get("command") or "").casefold() == "off")
        )
        for a in actions
    ):
        return "No explicit Internet-control OFF action at the usage limit."
    if not any(
        isinstance(a, dict)
        and str(a.get("capability") or "").casefold() in {"ifthen", "elseif"}
        and isinstance(a.get("expression"), dict)
        and "variable" in str(a["expression"]).casefold()
        for a in actions
    ):
        return "No variable-limit conditional verified before the block."
    return None
