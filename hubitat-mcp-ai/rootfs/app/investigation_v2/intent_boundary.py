"""Opt-in Investigation V2 boundary for requests requiring device mutation.

A control request cannot be performed in the V2 read-only test. This module
has no tool access and cannot authorize, schedule, or issue a write.

Reuse the production intent classifier for full request context; additionally
recognise a direct control *lead* even when production deliberately declines
a compound single-command shortcut. That last check is a denial only.
"""
from __future__ import annotations

import re

from control_intent_guard import explicitly_read_only_request
from mcp_agent_orchestrator import _explicit_mutation_request

# Only direct action leads; never scan descriptions / history for control
# verbs. No device-specific names, IDs or commands. This is NOT a write route.
_DIRECT_CONTROL_LEAD = re.compile(
    r"^\s*(?:please\s+|(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?))?"
    r"(?:turn|switch|power|toggle|set|dim|change|brighten|"
    r"increase|decrease|raise|lower|reduce|adjust|boost|heat|cool)\b",
    re.I,
)


def incompatible_v2_control_request(question: str) -> bool:
    """Refuse write-shaped questions, including compound requests.

    Historical, explanatory and explicitly read-only questions may still be
    investigated. A negative result never authorizes a write anywhere.
    """
    text = str(question or "").strip()
    if not text or explicitly_read_only_request(text):
        return False
    return _explicit_mutation_request(text) or bool(_DIRECT_CONTROL_LEAD.match(text))


__all__ = ["incompatible_v2_control_request"]
