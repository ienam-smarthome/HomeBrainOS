"""MCP skill-guided reasoning contract.

Adapted from the attached Hubitat MCP Claude skill. This is workflow guidance,
not a catalog of asserted server capabilities and not a permission boundary.
The live MCP server's tool list, search results and tool guide take precedence.
"""
from __future__ import annotations

import re

_GENERIC = """
MCP SKILL WORKFLOW (live catalog is authoritative)
- Understand the entire user objective. Break multi-part investigations into
  evidence questions: what happened, source/controller, upstream trigger,
  applicable conditions, alternative explanations, and uncertainty.
- Start with a focused, inexpensive read. Prefer configured or explicitly
  linked devices/apps over speculative room-wide scans.
- Discover missing capabilities through hub_search_tools. Search for the
  SPECIFIC operation/evidence you need, not only the entire user sentence.
  The installed server's accessible tool list is authoritative: a missing tool
  may be disabled by a Read/Write master or per-tool override. Do not invent it.
- For uncertain inputs, nested app pages, or native authoring, consult
  hub_get_tool_guide for the relevant section or inspect a discovered gateway
  schema before composing arguments. Treat live schemas as authoritative.
- A gateway routes to a sub-tool via tool and args. A read-only gateway is
  hub_read_*; hub_manage_* may contain writes even when some members are reads.
- After each tool result, assess which part of the original question remains
  unanswered. Follow the strongest missing evidence with a targeted read, then
  stop when adequate evidence exists or the bounded read budget is spent.
- Distinguish observed state, command issuer, configured trigger, executed
  condition, and human initiator. Configuration alone does not prove what
  happened historically. Correlation alone does not establish causation.
- Do not replace tool failures with fabricated information. Make uncertainty
  concise. Summarize the conclusion first, keep technical receipts separately.
- Preserve resource efficiency: narrow filters, requested attributes and
  bounded windows, cursor pagination for large responses. Respect server
  call limits; do not flood the single-threaded Hubitat hub.
- Tool discovery and annotations never authorize a write. The runtime effect
  registry, user authorization/confirmation, and MCP master gates are binding.
"""

_RULES = """
SKILL: AUTOMATION AND RULE ANALYSIS
- Distinguish triggers (start execution), conditions/required expressions
  (eligibility), actions (effects), nested branches, repeats, delayed and
  cancelled work. Rule definitions alone never prove historical execution.
- Investigate the active app/rule and relevant sub-page(s), matched devices
  and attributes, timestamp-scoped app logs, then connected event history.
- Search for the relevant installed native Rule Machine, Visual Rule Builder,
  and classic app tools rather than assuming only MCP custom rules exist.
- For rule authoring, consult the live tool guide's set_rule_reference or
  visual_rule_reference (as supported by the server) before sending payloads.
- Discover dynamic input pages via available list-app-pages and app-config
  operations instead of declaring a classic app impossible to configure.
"""

_CONTROL = """
SKILL: DEVICE COMMAND AUTHORIZATION
- Match the actual device identity exactly before acting. If only fuzzy or
  conflicting matches exist, request clarification instead of guessing.
- Read supportedCommands for nontrivial device commands. Never turn a
  network/internet block request into switch power off or vice versa.
- For sensitive/destructive changes, explain impact, respect confirmation,
  central Read/Write gates and backup requirements. Never send confirm=true
  without the user's appropriate approval.
- Confirm effects from returned execution/state evidence, not intentions.
"""

_DIAGNOSTICS = """
SKILL: INVESTIGATION AND DIAGNOSTICS
- Prefer filtered hub_get_logs, exact device events and app/rule diagnostics.
  Link reports by device/app ID and timestamp; current status alone cannot
  prove earlier conditions.
- Separate incomplete observation, a failed read, a disabled tool and a
  reported negative result. Do not claim absence from partial pages.
- For large lists, use server filters, projected fields and pagination. Do
  not claim an audit was complete until the source's coverage was verified.
"""


def build_mcp_skill_guidance(user_prompt: str) -> str:
    """Small on-demand guidance instead of dumping every skill reference."""
    text = str(user_prompt or "").casefold()
    parts = [_GENERIC]
    if re.search(r"\b(rule|automation|trigger|schedule|scheduled|app|scene|lighting|motion|occupancy)\b", text):
        parts.append(_RULES)
    if re.search(r"\b(turn|switch|set|unlock|lock|disable|enable|block|change|create|modify|delete|remove|reboot|shutdown|install)\b", text):
        parts.append(_CONTROL)
    if re.search(r"\b(why|investigat|analy[sz]|diagnos|audit|log|error|broken|fail|health|history|event|unexpected|offline|performance)\w*", text):
        parts.append(_DIAGNOSTICS)
    return "\n".join(parts).strip()


_SKILL_ROOMS = """
SKILL: ROOM MANAGEMENT
- Discover the live hub_read_rooms / hub_manage_rooms operations and their
  schemas. Verify exact room and device identities before changes.
- Confirm the affected device's room assignment after an authorised write.
- Room changes do not delete devices; never present them as removal.
"""

_SKILL_INTEGRATIONS = """
SKILL: INTEGRATION AND BRIDGE DIAGNOSTICS
- Distinguish state reported to Hubitat from commands originated by Hubitat,
  and distinguish a bridge event from proof of the external controller mapping.
- Look for the integration's native evidence before assigning a cause.
- Do not infer network reachability from a health flag or recent event alone.
"""

_SKILL_CODE = """
SKILL: HUB APP, DRIVER, AND CODE ADMINISTRATION
- Discover installed source and dependency information before proposing writes.
- Source updates/deletes require the relevant approval, backup and version checks.
- Do not treat a write acknowledgement as proof the changed code is operational.
"""

_SKILL_SECTIONS = {
    "device_control": _CONTROL,
    "automation": _RULES,
    "diagnostics": _DIAGNOSTICS,
    "hub_admin": _SKILL_ROOMS + "\n" + _CONTROL,
    "integrations": _SKILL_INTEGRATIONS + "\n" + _DIAGNOSTICS,
    "code_management": _SKILL_CODE,
}


def build_mcp_skill_guidance_for_domains(skill_domains: tuple[str, ...]) -> str:
    """Activate skill instructions from a validated semantic plan, not words.

    A missing or invalid plan keeps generic MCP guidance rather than guessing
    the user's intention. These sections are operational suggestions only;
    MCP live schemas and runtime permission checks remain authoritative.
    """
    parts = [_GENERIC]
    for domain in dict.fromkeys(skill_domains):
        section = _SKILL_SECTIONS.get(domain)
        if section is not None:
            parts.append(section)
    return "\n".join(parts).strip()


def wants_deep_investigation(user_prompt: str) -> bool:
    """Explicit effort request; ordinary one-step causal questions stay fast."""
    text = " ".join(str(user_prompt or "").casefold().split())
    return bool(re.search(
        r"\b(?:deep(?:ly)?|thorough(?:ly)?|comprehensive(?:ly)?|"
        r"investigate|investigation|analyse|analyze|diagnose|root cause|"
        r"trace the full|trace all|all possible causes)\b",
        text,
    ))


__all__ = ["build_mcp_skill_guidance", "build_mcp_skill_guidance_for_domains", "wants_deep_investigation"]
