"""Model-selected, host-local V2 control handoff.

The negative-only handoff is a semantic model choice made in the normal
planning call. It is not an MCP tool, has no effects and cannot authorise
writes. Literal historical commands, comparisons and negative instructions
should remain ordinary read-only investigations. All actual MCP access stays
behind the independent READ-only manifest, effect and argument guards.
"""
from __future__ import annotations

from typing import Any

NAME = "homebrain_request_main_ask"

_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Select only if the USER IS ASKING you to PERFORM a device, rule, "
            "automation or hub modification now or as a future action "
            "(for example 'turn my light off', 'create a rule'). This is a "
            "navigation-only handoff to Main Ask, never an executable command. "
            "NEVER select for evidence investigations, questions about past "
            "commands or app actions, 'OFF command', 'switch-state', "
            "status checks, hypothetical explanations, or 'read only; "
            "change nothing'. For mixed read+write requests, do not execute "
            "any write; direct the requested action to Main Ask."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


def handoff_tool() -> dict[str, Any]:
    return _TOOL_SCHEMA


def handoff_result(
    *, reads_executed: int, successful_reads: int,
    planning_model_calls: int, elapsed_ms: int,
) -> dict[str, Any]:
    """User-visible handoff, with no control or mutation permission."""
    message = (
        "This request asks HomeBrain to change Hubitat state. "
        "Investigation V2 is strictly read-only and did not execute any "
        "device or rule command. Use HomeBrain's main Ask/Chat interface "
        "for the requested action, with its normal approval checks."
    )
    return {
        "answer_mode": "v2_control_handoff",
        "answer": {
            "text": message,
            "root_cause_verified": False,
            "validation_issues": ["model_selected_control_handoff"],
        },
        "report": {
            "text": message,
            "technical_answer_retained": False,
        },
        "native_diagnostics": {
            "request_interpretation": "model_selected_control_handoff",
            "request_interpretation_source": "native_model_tool_choice",
            "reads_executed": reads_executed,
            "successful_reads": successful_reads,
            "planning_model_calls": planning_model_calls,
            "no_hubitat_writes": True,
            "total_elapsed_ms": elapsed_ms,
        },
        "resolved_devices": [],
        "resolution_method": "model_native_request_interpretation",
        "test_mode": "explicit_read_only",
    }


__all__ = ["NAME", "handoff_tool", "handoff_result"]
