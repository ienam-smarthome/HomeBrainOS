"""Negative-only boundary between general investigation and Hubitat writes.

The model decides a question's scope and tools. This gate does NOT classify
read topics, choose a tool, resolve a device or grant action authority.
It rejects only independently affirmative, command-shaped requests. V2's
manifest and tool executor still enforce READ-only operation even if the
question is ambiguous or the guard ever under-classifies a requested write.

Do not reuse the production control shortcut's broad route semantics here:
it is designed for an optional fast WRITE lane, not as a prerequisite for
general-purpose questions and analyses in an always-read-only model.
"""
from __future__ import annotations

import re

from control_intent_guard import (
    explicitly_read_only_request, independent_affirmative_mutation_clause,
)

_DIRECT_CONTROL_LEAD = re.compile(
    r"^\s*(?:please\s+|(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?))?"
    r"(?:turn|switch|power|toggle|set|dim|change|brighten|"
    r"increase|decrease|raise|lower|reduce|adjust|boost|heat|cool|"
    r"block|unblock|restrict|restart|reboot)\b",
    re.I,
)
_HUB_ADMIN_COMMAND = re.compile(
    r"^\s*(?:please\s+|(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?))?"
    r"(?:create|delete|remove|enable|disable|pause|resume|edit|update|"
    r"configure|install|uninstall)\s+(?:(?:an?|the|my)\s+)?"
    r"(?:hubitat\s+)?(?:rule|automation|app|device|schedule|scene|"
    r"trigger|driver|hub|setting|variable)\b",
    re.I,
)
_NEGATED_OBJECT = re.compile(r"(?i)^\s*(?:nothing\b|none\b|neither\b|no\s+)")


def incompatible_v2_control_request(question: str) -> bool:
    """Block independently requested Hubitat changes, not task vocabulary.

    An explicit no-write investigation must be admissible. The independent
    positive-clause check still rejects requests that append a second actual
    write ("inspect device; then turn it off"). Whether any subsequent
    model-selected tool can run remains a separate strict host READ gate.
    """
    text = str(question or "").strip()
    if not text:
        return False
    if independent_affirmative_mutation_clause(text):
        return True
    if explicitly_read_only_request(text):
        return False
    lead = _DIRECT_CONTROL_LEAD.match(text)
    if lead and not _NEGATED_OBJECT.match(text[lead.end():]):
        return True
    return bool(_HUB_ADMIN_COMMAND.match(text))


__all__ = ["incompatible_v2_control_request"]