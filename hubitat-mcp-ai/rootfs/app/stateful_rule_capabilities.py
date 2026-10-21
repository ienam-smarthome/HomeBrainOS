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
