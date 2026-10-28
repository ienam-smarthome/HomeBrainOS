"""Canonicalise only unambiguous, LIVE-advertised model read suboperations.

This is a host-controlled MCP syntax adapter, not a semantic intent router.
It never resolves an entity, guesses operation names, adds read permissions,
or executes calls. All output is reviewed again by the existing V2 planner.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from mcp_client import MCPTool
from tool_registry import ToolEffect, classify_tool_effect
from .planning import _schema_problem
from .receipt_projection import PROJECTED_V2_READ_OPERATIONS


def canonicalize_read_suboperations(
    proposals: Any, manifest: Iterable[MCPTool],
) -> tuple[Any, int]:
    """Resolve an operation-as-tool alias to one positively enumerated READ gateway.

    Preserve unknown model names, explicit gateways, mutating names, and
    ambiguous/malformed arguments so the standard host gate rejects them.
    An alias is accepted only if the exact complete gateway request already
    matches the same live schema that the normal reviewer will apply.
    """
    if not isinstance(proposals, list):
        return proposals, 0
    tools = [t for t in manifest if isinstance(t, MCPTool)]
    actual_names = {t.name for t in tools}
    providers: dict[str, list[MCPTool]] = {}
    for gateway in tools:
        if (not gateway.name.startswith("hub_read_")
                or classify_tool_effect(gateway, {}) is not ToolEffect.READ):
            continue
        ann = gateway.annotations if isinstance(gateway.annotations, dict) else {}
        if (ann.get("readOnlyHint") is False or ann.get("mutates") is True
                or ann.get("destructiveHint") is True):
            continue
        schema = gateway.input_schema if isinstance(gateway.input_schema, dict) else {}
        props = schema.get("properties", {})
        op = props.get("tool", {}) if isinstance(props, dict) else {}
        enum = op.get("enum") if isinstance(op, dict) else None
        if not isinstance(enum, list):
            continue  # Never trust model assertions or guess from gateway name.
        for item in enum:
            if (isinstance(item, str) and item in PROJECTED_V2_READ_OPERATIONS
                    and item.startswith(("hub_get_", "hub_list_", "hub_read_",
                                         "hub_search_", "hub_check_", "hub_find_"))):
                providers.setdefault(item, []).append(gateway)

    repaired: list[Any] = []
    rewritten_count = 0
    for proposal in proposals:
        if not isinstance(proposal, dict):
            repaired.append(proposal)
            continue
        name = proposal.get("tool")
        arguments = proposal.get("arguments")
        if (not isinstance(name, str) or name in actual_names
                or name not in PROJECTED_V2_READ_OPERATIONS
                or not isinstance(arguments, dict)):
            repaired.append(proposal)
            continue
        possible = providers.get(name, [])
        if len(possible) != 1:
            repaired.append(proposal)
            continue
        gateway = possible[0]
        if "tool" in arguments or "args" in arguments:
            # Do not silently discard extra wrapper fields or change a
            # contradictory model-supplied operation.
            if (set(arguments) != {"tool", "args"}
                    or arguments.get("tool") != name
                    or not isinstance(arguments.get("args"), dict)):
                repaired.append(proposal)
                continue
            inner = dict(arguments["args"])
        else:
            inner = dict(arguments)
        candidate_args = {"tool": name, "args": inner}
        if _schema_problem(candidate_args, gateway.input_schema) is not None:
            repaired.append(proposal)
            continue
        updated = dict(proposal)
        updated["tool"] = gateway.name
        updated["arguments"] = candidate_args
        repaired.append(updated)
        rewritten_count += 1
    return repaired, rewritten_count


__all__ = ["canonicalize_read_suboperations"]
