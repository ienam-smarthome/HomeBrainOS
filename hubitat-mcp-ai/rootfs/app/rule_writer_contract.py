"""Read-only negotiation of the installed native Rule Machine writer contract.

HomeBrain's legacy addTrigger/addAction shortcut compiler is NOT a native
document writer. Recent upstream hub_set_rule now accepts operation,
rule_id, args, confirm and bestPracticeKey; creating a rule requires
operation=create with args:{parent_id,name,changes:[typed native changes]}.
Never synthesize that native structure by renaming shortcut fields.
"""
from __future__ import annotations

import re
from typing import Any

LEGACY = "legacy-shortcut"
NATIVE_DOCUMENT = "native-document"
UNKNOWN = "unknown"


def _guide_text(value: Any, *, depth: int = 0) -> str:
    if depth > 5:
        return ""
    if isinstance(value, str):
        return value[:32000]
    if isinstance(value, dict):
        pieces = []
        # MCP responses vary between content blocks and structured maps.
        # Only explicitly textual guide fields, never arbitrary source data.
        for key in ("text", "content", "guide", "reference", "result", "data", "output", "structuredContent"):
            if key in value:
                pieces.append(_guide_text(value[key], depth=depth + 1))
        return "\n".join(piece for piece in pieces if piece)[:32000]
    if isinstance(value, list):
        return "\n".join(_guide_text(item, depth=depth + 1)
                         for item in value[:24])[:32000]
    return ""


def installed_rule_writer_contract(result: Any) -> str:
    """Return a contract only when an actual read-only guide attests its shape."""
    if getattr(result, "is_error", False):
        return UNKNOWN
    data = getattr(result, "data", result)
    source = _guide_text(data)
    if len(source) < 40:
        return UNKNOWN
    normalized = re.sub(r"\s+", "", source).casefold()
    # Native contract from upstream (Rule Machine document/form API).
    has_operation = (
        "hub_set_rule(operation:" in normalized
        or "hub_set_rule(operation=" in normalized
        or "operation:create" in normalized
        or "operation:'create'" in normalized
        or 'operation:"create"' in normalized
    )
    if has_operation and "parent_id" in source and "changes" in source:
        return NATIVE_DOCUMENT
    # Legacy shortcut contract: only this shape may receive our compiler's
    # direct addTrigger/addAction payload. An ambiguous guide fails closed.
    if (re.search(r"\baddTriggers?\b", source)
            and re.search(r"\baddActions?\b", source)
            and ("hub_set_rule" in source or "set_rule_reference" in source)
            and not has_operation):
        return LEGACY
    return UNKNOWN


def legacy_rule_writer_incompatibility(contract: str) -> str | None:
    if contract == LEGACY:
        return None
    if contract == NATIVE_DOCUMENT:
        return (
            "rm_contract_changed: Rule Machine creation was safely "
            "stopped before confirmation: the installed server requires the "
            "NEW native document API (operation='create', "
            "args={parent_id,name,changes}), while HomeBrain still uses "
            "retired addTrigger/addAction shortcuts. Native trigger/action "
            "fields are not yet verified. No rule write was queued or "
            "executed."
        )

    return (
        "Rule Machine creation was safely stopped: HomeBrain could not "
        "verify that the installed MCP server supports its addTrigger/"
        "addAction shortcut contract. Check the read-only "
        "hub_get_tool_guide(section='set_rule_reference') result and the "
        "installed MCP server version. No write was queued or executed."
    )


__all__ = [
    "LEGACY", "NATIVE_DOCUMENT", "UNKNOWN",
    "installed_rule_writer_contract", "legacy_rule_writer_incompatibility",
]
