"""Deterministic, read-only checkpoint selection for investigation planning.

This selects an already justified evidence obligation; it never creates a
device/app identity, tool permission, network request or model answer.
Unverified, previously attempted and unavailable proposals are ineligible.
"""
from __future__ import annotations
from typing import Any, Iterable

PRIORITY = (
    "target-history",
    "issuer-decision",
    "upstream-input",
    "configuration-semantics",
    "diagnostic-discriminator",
)

def select_evidence_checkpoint(
    candidates: Iterable[dict[str, Any]],
    attempted: Iterable[str] = (),
) -> dict[str, Any] | None:
    """Select one unique scoped source obligation, or leave it unresolved.

    Candidates must be explicitly admitted upstream. In particular, an
    identity cannot be inferred from labels or a failed tool result.
    """
    used = set(attempted)
    eligible: list[tuple[int, str, dict[str, Any]]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        signature = item.get("signature")
        if kind not in PRIORITY or not isinstance(signature, str) or not signature:
            continue
        if signature in used or item.get("verified") is not True:
            continue
        if item.get("available") is not True or item.get("read_only") is not True:
            continue
        tool = item.get("tool")
        args = item.get("args")
        if not isinstance(tool, str) or not tool or not isinstance(args, dict):
            continue
        eligible.append((PRIORITY.index(kind), signature, item))
    if not eligible:
        return None
    eligible.sort(key=lambda row: (row[0], row[1]))
    chosen = eligible[0][2]
    return {
        "kind": chosen["kind"],
        "signature": chosen["signature"],
        "tool": chosen["tool"],
        "args": dict(chosen["args"]),
    }

__all__ = ["PRIORITY", "select_evidence_checkpoint"]
